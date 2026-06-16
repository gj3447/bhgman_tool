"""bhgman bot — legion 닫힌루프를 백그라운드에서 주기 반복하는 자율 데몬.

moltbot 류 "내 하드웨어에서 상시 도는 자율 에이전트"의 bhgman 판:
  vLLM(추론, BHGMAN_LLM_BASE_URL) + SearXNG(인터넷, BHGMAN_SEARXNG_URL)
  + Neo4j(KG) + 하네스(legion Contract handoff + oracle gate).

각 tick = topic 선택 → legion run(획득→연결→창조→정리→검증→실현) → KG read/write → sleep.
graceful: SIGTERM/SIGINT → 현재 tick 마치고 종료. tick 실패는 격리(봇은 계속).

배선(vLLM/KG/web)은 cmd_bot 이 하고, 이 모듈은 순수 루프 — build_ctx/run_tick/sleep 주입으로
무네트워크 테스트 가능.

# KG: bhgman-bot-daemon-2026-06-16
"""

from __future__ import annotations

import datetime as _dt
import signal
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass
class BotConfig:
    """봇 구동 파라미터."""

    interval: float = 300.0  # tick 간 sleep(초)
    max_ticks: int | None = None  # None = 무한, once → 1
    topics: Sequence[str] = ()  # rotation 큐 (비면 pick_work → KG, 그것도 없으면 idle)
    apply: bool = False  # KG write 여부 (dry-run default)


@dataclass
class TickResult:
    """한 tick 결과 요약."""

    tick: int
    topic: str | None
    completed: bool
    ran: int
    detail: str = ""


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


def run_bot(
    *,
    build_ctx: Callable[[str], dict],
    run_tick: Callable[[dict, str], dict],
    cfg: BotConfig,
    pick_work: Callable[[], str | None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] | None = None,
    install_signals: bool = True,
) -> list[TickResult]:
    """tick loop. 각 tick: topic 선택(rotation→pick_work) → build_ctx → run_tick → sleep.

    build_ctx(topic)→ctx, run_tick(ctx,topic)→{'legion_run':...} 주입 (테스트는 fake).
    """
    emit = log or (lambda m: print(m, file=sys.stderr, flush=True))
    stopper = _Stopper()
    if install_signals:
        stopper.install()
    results: list[TickResult] = []
    topics = list(cfg.topics)
    tick = 0
    emit(
        f"[bot] start {_now()} interval={cfg.interval}s max_ticks={cfg.max_ticks} "
        f"topics={len(topics)} apply={cfg.apply}"
    )
    while not stopper.stop:
        if cfg.max_ticks is not None and tick >= cfg.max_ticks:
            break
        tick += 1
        topic: str | None = None
        if topics:
            topic = topics[(tick - 1) % len(topics)]
        elif pick_work is not None:
            try:
                topic = pick_work()
            except Exception as e:  # noqa: BLE001 — KG pull 실패해도 봇은 계속
                emit(f"[bot] tick {tick} pick_work 실패: {e}")
        if not topic:
            emit(f"[bot] tick {tick} idle (일감 없음)")
            results.append(TickResult(tick, None, False, 0, "idle"))
        else:
            emit(f"[bot] tick {tick} ▶ topic={topic!r}")
            try:
                res = run_tick(build_ctx(topic), topic)
                run = res["legion_run"]
                tr = TickResult(
                    tick,
                    topic,
                    bool(getattr(run, "completed", False)),
                    int(getattr(run, "ran", 0)),
                    getattr(run, "gate_failure", "") or "",
                )
                gate = f" GATE_FAIL:{tr.detail}" if tr.detail else ""
                emit(f"[bot] tick {tick} ✓ completed={tr.completed} ran={tr.ran}/6{gate}")
                results.append(tr)
            except Exception as e:  # noqa: BLE001 — tick 실패 격리, 봇은 계속
                emit(f"[bot] tick {tick} ✗ error: {e}")
                results.append(TickResult(tick, topic, False, 0, f"error: {e}"))
        if cfg.max_ticks is not None and tick >= cfg.max_ticks:
            break
        if stopper.stop:
            break
        sleep(cfg.interval)
    emit(f"[bot] stop {_now()} — {len(results)} ticks ran")
    return results


__all__ = ["BotConfig", "TickResult", "run_bot"]
