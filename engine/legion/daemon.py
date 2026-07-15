"""bhgman bot — legion 닫힌루프를 백그라운드에서 주기 반복하는 자율 데몬.

moltbot 류 "내 하드웨어에서 상시 도는 자율 에이전트"의 bhgman 판:
  vLLM(추론, BHGMAN_LLM_BASE_URL) + SearXNG(인터넷, BHGMAN_SEARXNG_URL)
  + Neo4j(KG) + 하네스(legion Contract handoff + oracle gate).

각 tick = topic 선택 → legion run(획득→연결→창조→정리→검증→실현) → KG read/write → sleep.
graceful: SIGTERM/SIGINT → 현재 tick 마치고 종료.

PROM16 하네스/루프 표준 (2026-07-15) 적용:
  - 타입付 종료: 루프는 항상 StopReason 으로 끝난다 (bare exception 이 terminal 아님).
  - 타입付 오류 분류(errors.py): transient 만 유한 재시도+backoff, 그 외는 programming_error
    로 기록 + 해당 topic 격리(재시도 금지). K회 연속이면 'error_storm' 정지.
    ⚠ 이전 동작(모든 예외를 격리하고 영원히 계속)에서 *의도적으로* 바뀐 지점이다 —
    결정론 버그가 매 tick 조용히 죽으며 봇이 영원히 도는 것이 원래 문제였다.
  - 지출 kill-switch(spend.py): spend_probe 주입 시 누적 예산/속도 초과 → 'spend_kill'.
  - 내구성(journal.py): journal_path 주입 시 tick 단위 append-only 체크포인트 →
    크래시 후 재시작이 이미 끝낸 tick 을 재지불하지 않는다.

배선(vLLM/KG/web)은 cmd_bot 이 하고, 이 모듈은 순수 루프 — build_ctx/run_tick/sleep/
spend_probe 주입으로 무네트워크 테스트 가능.

# KG: bhgman-bot-daemon-2026-06-16, prom16-harness-loop-standard
"""

from __future__ import annotations

import datetime as _dt
import os
import signal
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from engine.legion.errors import (
    ErrorClass,
    RetryPolicy,
    StopReason,
    classify_error,
    describe,
    run_with_retry,
)
from engine.legion.journal import KIND_BOT_DONE, KIND_RUN_START, KIND_TICK, JsonlJournal


@dataclass
class BotConfig:
    """봇 구동 파라미터."""

    interval: float = 300.0  # tick 간 sleep(초)
    max_ticks: int | None = None  # None = 무한, once → 1
    topics: Sequence[str] = ()  # rotation 큐 (비면 pick_work → KG, 그것도 없으면 idle)
    apply: bool = False  # KG write 여부 (dry-run default)
    # --- PROM16 루프 표준 (기본값이 *활성* — 이전 무제한 격리 동작에서 의도적 변경) ---
    transient_retries: int = 2  # transient 실패 재시도 횟수 (0=재시도 없음)
    retry_base_delay: float = 0.5  # 지수 backoff 기준 초
    quarantine_programming: bool = True  # programming_error 낸 topic 을 이후 tick 에서 격리
    error_storm_threshold: int = 5  # K회 연속 programming_error → error_storm 정지 (0=비활성)
    # --- 내구성 (opt-in: 경로를 줘야 켜진다) ---
    journal_path: str | os.PathLike[str] | None = None  # append-only JSONL 체크포인트
    run_id: str | None = None  # 명시하면 그 run 재개, 없으면 저널의 마지막 run_start 채택


@dataclass
class TickResult:
    """한 tick 결과 요약."""

    tick: int
    topic: str | None
    completed: bool
    ran: int
    detail: str = ""
    error_class: str = ""  # "" | "transient" | "programming_error" (errors.ErrorClass)


class BotRun(list):  # list[TickResult] — 기존 호출부(len/iterate/index)를 그대로 보존
    """run_bot 결과. list 하위라 기존 계약 불변 + 타입付 stop_reason/run_id 를 얹는다."""

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.stop_reason: str = ""
        self.run_id: str = ""


class _Stopper:
    """SIGTERM/SIGINT → 현재 tick 후 graceful stop."""

    def __init__(self) -> None:
        self.stop = False

    def install(self) -> None:
        def _handler(signum, _frame):  # noqa: ANN001
            self.stop = True
            print(
                f"[bot] signal {signum} → graceful stop after current tick",
                file=sys.stderr,
                flush=True,
            )

        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, _handler)


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class _LoopState:
    """루프의 가변 상태 — 재개 시 저널에서 그대로 복원되는 것이 전부여야 한다."""

    tick: int = 0
    consecutive_programming: int = 0
    quarantine_skips: int = 0
    quarantined: set[str] = field(default_factory=set)
    results: BotRun = field(default_factory=BotRun)


def _resolve_run_id(journal: JsonlJournal, cfg: BotConfig) -> str:
    """재개 대상 run_id 결정 (FIX-C: tick 저널은 반드시 run 으로 scope 된다).

    우선순위: 명시 cfg.run_id → 저널의 마지막 run_start(단 bot_done 없으면 = 미완 run,
    이어서 재개) → 새 run 발급. 이미 bot_done 인 run 은 끝난 run 이므로 새 id 를 판다.
    """
    if cfg.run_id:
        return cfg.run_id
    last = journal.last_run_id()
    if last is not None and not journal.has(KIND_BOT_DONE, last):
        return last  # 크래시로 중단된 run — 이어서 재개
    return "bot-" + _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")


def _replay(journal: JsonlJournal, run_id: str, cfg: BotConfig) -> _LoopState:
    """저널된 tick 을 결과·격리·tick 번호로 복원 — 재실행 0 (LLM 비용 재지불 0)."""
    state = _LoopState()
    for e in journal.entries(run_id=run_id, kind=KIND_TICK):
        p = e.payload
        tr = TickResult(
            tick=int(p.get("tick", 0)),
            topic=p.get("topic"),
            completed=bool(p.get("completed", False)),
            ran=int(p.get("ran", 0)),
            detail=str(p.get("detail", "")),
            error_class=str(p.get("error_class", "")),
        )
        state.results.append(tr)
        state.tick = max(state.tick, tr.tick)
        _absorb_counters(state, tr, cfg)
    return state


def _absorb_counters(state: _LoopState, tr: TickResult, cfg: BotConfig) -> None:
    """TickResult → 연속 오류/격리 상태 갱신 (fresh 실행과 재개가 같은 함수를 쓴다)."""
    if tr.error_class == ErrorClass.PROGRAMMING.value:
        state.consecutive_programming += 1
        state.quarantine_skips = 0
        if cfg.quarantine_programming and tr.topic:
            state.quarantined.add(tr.topic)
    elif tr.detail == _QUARANTINE_DETAIL:
        state.quarantine_skips += 1
    else:
        state.consecutive_programming = 0
        state.quarantine_skips = 0


_QUARANTINE_DETAIL = "quarantined"


def _next_topic(
    cfg: BotConfig,
    topics: list[str],
    tick: int,
    pick_work: Callable[[], str | None] | None,
    emit: Callable[[str], None],
) -> str | None:
    if topics:
        return topics[(tick - 1) % len(topics)]
    if pick_work is None:
        return None
    try:
        return pick_work()
    except Exception as e:  # noqa: BLE001 — KG pull 실패해도 봇은 계속 (일감 없음 취급)
        emit(f"[bot] tick {tick} pick_work 실패: {describe(e)}")
        return None


def _execute_tick(
    tick: int,
    topic: str,
    build_ctx: Callable[[str], dict],
    run_tick: Callable[[dict, str], dict],
    cfg: BotConfig,
    sleep: Callable[[float], None],
    emit: Callable[[str], None],
) -> TickResult:
    """1 tick 실행. transient 는 유한 재시도, 그 외는 타입付 programming_error 로 기록."""
    policy = RetryPolicy(attempts=max(0, cfg.transient_retries), base_delay=cfg.retry_base_delay)

    def _on_retry(n: int, e: BaseException, delay: float) -> None:
        emit(f"[bot] tick {tick} transient 재시도 {n}/{policy.attempts} in {delay}s: {describe(e)}")

    try:
        res = run_with_retry(
            lambda: run_tick(build_ctx(topic), topic),
            policy=policy,
            sleep=sleep,
            on_retry=_on_retry,
        )
        run = res["legion_run"]
        return TickResult(
            tick,
            topic,
            bool(getattr(run, "completed", False)),
            int(getattr(run, "ran", 0)),
            getattr(run, "gate_failure", "") or "",
        )
    except Exception as e:  # noqa: BLE001 — 분류해서 타입付 결과로 기록 (조용히 삼키지 않음)
        klass = classify_error(e)
        return TickResult(tick, topic, False, 0, f"error: {describe(e)}", klass.value)


def _journal_tick(journal: JsonlJournal, run_id: str, tr: TickResult) -> None:
    journal.append(
        KIND_TICK,
        run_id,
        unit=str(tr.tick),
        payload={
            "tick": tr.tick,
            "topic": tr.topic,
            "completed": tr.completed,
            "ran": tr.ran,
            "detail": tr.detail,
            "error_class": tr.error_class,
        },
    )


def _no_work_left(state: _LoopState, cfg: BotConfig) -> bool:
    """rotation 큐가 통째로 격리됐거나(즉시), 격리 skip 만 K회 연속(pick_work 모드 안전망)."""
    if cfg.topics and set(cfg.topics) <= state.quarantined:
        return True
    return cfg.error_storm_threshold > 0 and state.quarantine_skips >= cfg.error_storm_threshold


def _terminal_after_tick(state: _LoopState, cfg: BotConfig) -> StopReason | None:
    if cfg.error_storm_threshold > 0 and state.consecutive_programming >= cfg.error_storm_threshold:
        return StopReason.ERROR_STORM
    if _no_work_left(state, cfg):
        return StopReason.ALL_QUARANTINED
    return None


def run_bot(
    *,
    build_ctx: Callable[[str], dict],
    run_tick: Callable[[dict, str], dict],
    cfg: BotConfig,
    pick_work: Callable[[], str | None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] | None = None,
    install_signals: bool = True,
    spend_probe: Callable[[], str | None] | None = None,
) -> BotRun:
    """tick loop. 각 tick: topic 선택(rotation→pick_work) → build_ctx → run_tick → sleep.

    build_ctx(topic)→ctx, run_tick(ctx,topic)→{'legion_run':...} 주입 (테스트는 fake).
    spend_probe()→초과사유|None 을 주면 매 tick 전후로 물어 초과 시 spend_kill 로 정지한다
    (에이전트 자기판단과 독립된 정지 권한). cfg.journal_path 를 주면 tick 이 체크포인트되어
    크래시 후 같은 run_id 로 재시작하면 끝낸 tick 을 건너뛴다.

    Returns:
        BotRun — TickResult 리스트(list 하위, 기존 계약 불변) + 타입付 stop_reason/run_id.
    """
    emit = log or (lambda m: print(m, file=sys.stderr, flush=True))
    stopper = _Stopper()
    if install_signals:
        stopper.install()

    journal = JsonlJournal(cfg.journal_path)
    run_id = _resolve_run_id(journal, cfg) if journal.enabled else (cfg.run_id or "")
    state = _replay(journal, run_id, cfg) if journal.enabled else _LoopState()
    if journal.enabled and state.tick == 0:
        journal.append(KIND_RUN_START, run_id, payload={"started_at": _now()})
    resumed = state.tick

    topics = list(cfg.topics)
    emit(
        f"[bot] start {_now()} interval={cfg.interval}s max_ticks={cfg.max_ticks} "
        f"topics={len(topics)} apply={cfg.apply}"
        + (f" run_id={run_id} resumed_from_tick={resumed}" if journal.enabled else "")
    )

    stop_reason = _drive(
        state=state,
        cfg=cfg,
        topics=topics,
        stopper=stopper,
        build_ctx=build_ctx,
        run_tick=run_tick,
        pick_work=pick_work,
        sleep=sleep,
        emit=emit,
        spend_probe=spend_probe,
        journal=journal,
        run_id=run_id,
    )
    if journal.enabled and stop_reason is not StopReason.SIGNAL:
        journal.append(KIND_BOT_DONE, run_id, payload={"stop_reason": stop_reason.value})

    state.results.stop_reason = stop_reason.value
    state.results.run_id = run_id
    emit(
        f"[bot] stop {_now()} — {len(state.results)} ticks ran "
        f"(stop_reason={stop_reason.value}, {state.tick - resumed} this process)"
    )
    return state.results


def _drive(  # noqa: PLR0913 — 순수 루프의 주입 지점들 (모듈 DI 규율)
    *,
    state: _LoopState,
    cfg: BotConfig,
    topics: list[str],
    stopper: _Stopper,
    build_ctx: Callable[[str], dict],
    run_tick: Callable[[dict, str], dict],
    pick_work: Callable[[], str | None] | None,
    sleep: Callable[[float], None],
    emit: Callable[[str], None],
    spend_probe: Callable[[], str | None] | None,
    journal: JsonlJournal,
    run_id: str,
) -> StopReason:
    """tick 루프 본체 → 타입付 종료 상태. 모든 탈출구가 StopReason 을 낸다."""
    while not stopper.stop:
        pre = _terminal_before_tick(state, cfg, spend_probe, emit)
        if pre is not None:
            return pre

        state.tick += 1
        tr = _one_tick(state, cfg, topics, build_ctx, run_tick, pick_work, sleep, emit)
        state.results.append(tr)
        _absorb_counters(state, tr, cfg)
        if journal.enabled:
            _journal_tick(journal, run_id, tr)

        terminal = _terminal_after_tick(state, cfg)
        if terminal is not None:
            emit(f"[bot] {terminal.value} → 정지 (tick {state.tick})")
            return terminal
        if cfg.max_ticks is not None and state.tick >= cfg.max_ticks:
            return StopReason.MAX_TICKS
        if stopper.stop:
            break
        sleep(cfg.interval)
    return StopReason.SIGNAL


def _terminal_before_tick(
    state: _LoopState,
    cfg: BotConfig,
    spend_probe: Callable[[], str | None] | None,
    emit: Callable[[str], None],
) -> StopReason | None:
    """tick 시작 전 독립 정지 검사 — step 상한 + 지출 kill-switch (에이전트 판단과 무관)."""
    if cfg.max_ticks is not None and state.tick >= cfg.max_ticks:
        return StopReason.MAX_TICKS
    kill = spend_probe() if spend_probe is not None else None
    if kill:
        emit(f"[bot] 지출 상한 초과 → 정지: {kill}")
        return StopReason.SPEND_KILL
    return None


def _one_tick(
    state: _LoopState,
    cfg: BotConfig,
    topics: list[str],
    build_ctx: Callable[[str], dict],
    run_tick: Callable[[dict, str], dict],
    pick_work: Callable[[], str | None] | None,
    sleep: Callable[[float], None],
    emit: Callable[[str], None],
) -> TickResult:
    """topic 선택 → (격리/idle 이면 skip) → 실행. 항상 TickResult 를 낸다."""
    tick = state.tick
    topic = _next_topic(cfg, topics, tick, pick_work, emit)
    if not topic:
        emit(f"[bot] tick {tick} idle (일감 없음)")
        return TickResult(tick, None, False, 0, "idle")
    if topic in state.quarantined:
        emit(f"[bot] tick {tick} ⊘ topic={topic!r} 격리됨 (programming_error 이력) — skip")
        return TickResult(tick, topic, False, 0, _QUARANTINE_DETAIL)
    emit(f"[bot] tick {tick} ▶ topic={topic!r}")
    tr = _execute_tick(tick, topic, build_ctx, run_tick, cfg, sleep, emit)
    if tr.error_class:
        emit(f"[bot] tick {tick} ✗ {tr.error_class}: {tr.detail}")
    else:
        gate = f" GATE_FAIL:{tr.detail}" if tr.detail else ""
        emit(f"[bot] tick {tick} ✓ completed={tr.completed} ran={tr.ran}/6{gate}")
    return tr


__all__ = ["BotConfig", "BotRun", "TickResult", "run_bot"]
