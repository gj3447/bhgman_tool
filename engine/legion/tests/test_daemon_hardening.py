"""데몬 루프 하드닝 (GAP-1 오류분류/격리/error_storm, GAP-2 spend_kill, GAP-3 crash→resume).

전부 무네트워크 — build_ctx/run_tick/sleep/spend_probe 주입 (daemon.py DI 규율).
각 가드는 *양방향* 으로 검사한다: 발동해야 할 때 발동하고, 정상 경로는 건드리지 않는다.

# KG: prom16-harness-loop-standard, bhgman-bot-daemon-2026-06-16
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.legion.daemon import BotConfig, run_bot
from engine.legion.journal import KIND_TICK, JsonlJournal


def _good_tick(_ctx, _topic):
    return {"legion_run": SimpleNamespace(completed=True, ran=6, gate_failure="")}


def _run(cfg, run_tick=_good_tick, sleep=lambda _s: None, **kw):
    return run_bot(
        build_ctx=lambda t: {"topic": t},
        run_tick=run_tick,
        cfg=cfg,
        sleep=sleep,
        install_signals=False,
        **kw,
    )


class _Crash(Exception):
    """프로세스 급사(kill -9) 시뮬레이션."""


def _crash_after(n: int):
    """n 번째 tick-간 sleep 에서 급사시킨다.

    sleep 은 루프의 try 밖이라 예외가 run_bot 을 그대로 탈출한다 = 정상종료 마커(bot_done)를
    남기지 않는 진짜 크래시. 저널엔 완료된 tick 만 남는다.
    """
    seen = {"n": 0}

    def _sleep(_s):
        seen["n"] += 1
        if seen["n"] >= n:
            raise _Crash("kill -9")

    return _sleep


# ---------------------------------------------------------------- GAP-1 분류/격리/error_storm


def test_programming_error_quarantines_topic_and_is_not_retried():
    """결정론 버그는 타입付으로 기록되고 그 topic 은 이후 tick 에서 재실행되지 않는다.

    pre-fix 는 매 tick 같은 버그를 조용히 다시 밟았다 (calls == max_ticks).
    """
    calls = {"n": 0}

    def bug(_ctx, _topic):
        calls["n"] += 1
        raise AttributeError("'NoneType' has no attribute 'value'")

    r = _run(BotConfig(interval=0, max_ticks=4, topics=("a", "b")), run_tick=bug)
    assert r[0].error_class == "programming_error"
    assert "AttributeError" in r[0].detail  # 타입名 보존 = 진단 가능
    assert calls["n"] == 2  # a, b 각 1회씩만 — 격리 후 재실행 없음
    assert r.stop_reason == "all_quarantined"


def test_transient_error_is_retried_and_topic_not_quarantined():
    """transient 는 유한 재시도 후에도 격리 대상이 아니다 (다음 tick 에 다시 시도)."""
    calls = {"n": 0}

    def flaky(_ctx, _topic):
        calls["n"] += 1
        raise ConnectionError("vllm restarting")

    r = _run(BotConfig(interval=0, max_ticks=2, topics=("a",), transient_retries=2), run_tick=flaky)
    assert [x.error_class for x in r] == ["transient", "transient"]
    assert calls["n"] == 6  # tick 2회 × (최초 1 + 재시도 2) — 격리 안 됨
    assert r.stop_reason == "max_ticks"


def test_error_storm_stops_the_loop():
    """K회 연속 programming_error → 타입付 error_storm 정지 (봇이 영원히 돌지 않는다)."""
    seq = iter(range(100))

    def bug(_ctx, _topic):
        raise TypeError(f"bug {next(seq)}")

    # topic 이 매번 달라 격리로는 안 멈춘다 → error_storm 이 유일한 정지 근거.
    r = _run(
        BotConfig(interval=0, max_ticks=None, error_storm_threshold=3),
        run_tick=bug,
        pick_work=lambda: f"t{next(seq)}",
    )
    assert r.stop_reason == "error_storm"
    assert len(r) == 3


def test_error_storm_counter_resets_on_success():
    """정상 tick 이 끼면 연속 카운터가 리셋 — 산발적 버그로 정지하지 않는다 (반대 방향)."""
    state = {"n": 0}

    def alternating(_ctx, _topic):
        state["n"] += 1
        if state["n"] % 2 == 1:
            raise TypeError("odd tick bug")
        return _good_tick(_ctx, _topic)

    r = _run(
        BotConfig(interval=0, max_ticks=6, error_storm_threshold=2, quarantine_programming=False),
        run_tick=alternating,
        pick_work=lambda: f"t{state['n']}",
    )
    assert r.stop_reason == "max_ticks" and len(r) == 6


def test_healthy_loop_untouched_by_guards():
    """정상 경로: 가드가 켜져 있어도 rotation/max_ticks 는 예전 그대로."""
    r = _run(BotConfig(interval=0, max_ticks=3, topics=("a", "b")))
    assert [x.topic for x in r] == ["a", "b", "a"]
    assert all(x.completed and x.error_class == "" for x in r)
    assert r.stop_reason == "max_ticks"


# ---------------------------------------------------------------------- GAP-2 spend kill-switch


def test_spend_probe_stops_loop_when_budget_exceeded():
    ticks = {"n": 0}

    def counting(_ctx, _topic):
        ticks["n"] += 1
        return _good_tick(_ctx, _topic)

    r = _run(
        BotConfig(interval=0, max_ticks=100, topics=("a",)),
        run_tick=counting,
        spend_probe=lambda: "tokens 999 >= max_total_tokens 500" if ticks["n"] >= 2 else None,
    )
    assert r.stop_reason == "spend_kill"
    assert ticks["n"] == 2  # 초과 감지 즉시 정지 — 다음 tick 은 아예 안 돈다


def test_spend_probe_that_never_fires_does_not_change_behavior():
    r = _run(BotConfig(interval=0, max_ticks=3, topics=("a",)), spend_probe=lambda: None)
    assert len(r) == 3 and r.stop_reason == "max_ticks"


# ------------------------------------------------------------------- GAP-3 crash → resume (저널)


def test_journal_resume_skips_completed_ticks_without_repaying(tmp_path):
    """크래시 후 재시작이 끝낸 tick 을 재실행하지 않고(비용 재지불 0), 이력은 이어붙는다."""
    jp = tmp_path / "bot.jsonl"
    calls: list[str] = []

    def counting(_ctx, topic):
        calls.append(topic)
        return _good_tick(_ctx, topic)

    cfg = BotConfig(interval=0, max_ticks=None, topics=("a", "b"), journal_path=jp)
    with pytest.raises(_Crash):  # tick1 → tick2 → 급사 (bot_done 없음)
        _run(cfg, run_tick=counting, sleep=_crash_after(2))
    assert calls == ["a", "b"]
    crashed_run_id = JsonlJournal(jp).last_run_id()

    calls.clear()
    second = _run(  # 같은 저널로 재시작 = 크래시 복구
        BotConfig(interval=0, max_ticks=4, topics=("a", "b"), journal_path=jp), run_tick=counting
    )
    assert calls == ["a", "b"]  # tick 3,4 만 새로 — tick 1,2 는 재지불 0
    assert [x.tick for x in second] == [1, 2, 3, 4]  # 복원된 이력 + 새 tick
    assert second.run_id == crashed_run_id  # 미완 run 을 이어받음


def test_same_run_rotation_still_revisits_topics_with_journal_on(tmp_path):
    """FIX-C: 저널을 켜도 주기 데몬은 여전히 topic 을 재방문한다.

    unit 이 topic 이면 'a' 가 영원히 억제돼 주기 봇이 run-once-per-topic 으로 조용히
    바뀐다 — unit 은 (run_id, tick) 이어야 한다.
    """
    jp = tmp_path / "bot.jsonl"
    seen: list[str] = []

    def counting(_ctx, topic):
        seen.append(topic)
        return _good_tick(_ctx, topic)

    r = _run(
        BotConfig(interval=0, max_ticks=5, topics=("a", "b"), journal_path=jp), run_tick=counting
    )
    assert seen == ["a", "b", "a", "b", "a"]  # 같은 run 안에서 rotation 유지
    assert [x.topic for x in r] == ["a", "b", "a", "b", "a"]


def test_finished_run_starts_fresh_run_id_on_restart(tmp_path):
    """정상 종료(bot_done)한 run 은 재개 대상이 아니다 — 재시작은 새 run 을 판다."""
    jp = tmp_path / "bot.jsonl"
    first = _run(BotConfig(interval=0, max_ticks=1, topics=("a",), journal_path=jp))
    second = _run(BotConfig(interval=0, max_ticks=1, topics=("a",), journal_path=jp))
    assert second.run_id != first.run_id
    assert [x.tick for x in second] == [1]  # 새 run 이므로 tick 1 부터


def test_resume_restores_quarantine_state(tmp_path):
    """격리도 저널에서 복원 — 재시작이 이미 죽은 topic 을 다시 밟지 않는다."""
    jp = tmp_path / "bot.jsonl"
    calls: list[str] = []

    def bug(_ctx, topic):
        calls.append(topic)
        raise ValueError("deterministic")

    cfg = BotConfig(interval=0, max_ticks=None, topics=("a", "b"), journal_path=jp)
    with pytest.raises(_Crash):  # tick1(a → 격리) 직후 급사
        _run(cfg, run_tick=bug, sleep=_crash_after(1))
    assert calls == ["a"]

    calls.clear()
    r = _run(BotConfig(interval=0, max_ticks=3, topics=("a", "b"), journal_path=jp), run_tick=bug)
    assert calls == ["b"]  # a 는 복원된 격리로 skip, b 만 새로 시도(그리고 격리)
    assert r.stop_reason == "all_quarantined"


def test_journal_off_by_default_writes_nothing(tmp_path):
    """반대 방향: journal_path 없으면 파일도 저널 동작도 없다 (현행 동작 보존)."""
    r = _run(BotConfig(interval=0, max_ticks=2, topics=("a",)))
    assert len(r) == 2 and r.run_id == ""
    assert list(tmp_path.iterdir()) == []


def test_journal_records_one_entry_per_tick(tmp_path):
    jp = tmp_path / "bot.jsonl"
    r = _run(BotConfig(interval=0, max_ticks=3, topics=("a",), journal_path=jp))
    units = JsonlJournal(jp).completed_units(KIND_TICK, r.run_id)
    assert units == {"1", "2", "3"}


def test_corrupt_journal_tail_is_treated_as_incomplete(tmp_path):
    """크래시로 반쪽 기록된 마지막 줄은 미완료 단위 → 그 tick 은 재실행된다 (조용한 손실 금지)."""
    jp = tmp_path / "bot.jsonl"
    calls: list[str] = []

    def counting(_ctx, topic):
        calls.append(topic)
        return _good_tick(_ctx, topic)

    r1 = _run(BotConfig(interval=0, max_ticks=2, topics=("a",), journal_path=jp), run_tick=counting)
    with jp.open("a", encoding="utf-8") as fh:
        fh.write('{"kind": "tick", "run_id": "' + r1.run_id + '", "unit": "3", "payl')  # 반쪽 줄
    calls.clear()
    r2 = _run(
        BotConfig(interval=0, max_ticks=3, topics=("a",), journal_path=jp, run_id=r1.run_id),
        run_tick=counting,
    )
    assert calls == ["a"]  # tick 3 을 다시 — 손상된 줄은 완료로 치지 않는다
    assert [x.tick for x in r2] == [1, 2, 3]
