"""bhgman bot daemon (run_bot) — 무네트워크 단위. build_ctx/run_tick/sleep 주입.

# KG: bhgman-bot-daemon-2026-06-16
"""

from __future__ import annotations

from types import SimpleNamespace

from engine.legion.daemon import BotConfig, run_bot


def _good_tick(_ctx, _topic):
    return {"legion_run": SimpleNamespace(completed=True, ran=6, gate_failure="")}


def test_topics_rotation_and_max_ticks():
    r = run_bot(
        build_ctx=lambda t: {"topic": t},
        run_tick=_good_tick,
        cfg=BotConfig(interval=0, max_ticks=3, topics=("a", "b")),
        sleep=lambda _s: None,
        install_signals=False,
    )
    assert len(r) == 3 and all(x.completed for x in r)
    assert [x.topic for x in r] == ["a", "b", "a"]  # rotation


def test_pick_work_fallback_when_no_topics():
    r = run_bot(
        build_ctx=lambda t: {},
        run_tick=_good_tick,
        cfg=BotConfig(interval=0, max_ticks=2),
        pick_work=lambda: "kg-topic",
        sleep=lambda _s: None,
        install_signals=False,
    )
    assert [x.topic for x in r] == ["kg-topic", "kg-topic"]


def test_tick_failure_isolated_bot_continues():
    """transient 실패는 예전처럼 격리되고 봇은 계속 돈다 (재시도 소진 후에도 tick 은 계속).

    (2026-07-15 PROM16: 이 격리 보장은 이제 *transient 로 분류된* 실패에만 해당한다.
    분류 불가 예외 = programming_error → 격리·정지. 아래 test_programming_error_* 참조.)
    """

    def boom(_ctx, _topic):
        raise ConnectionError("vllm down")

    r = run_bot(
        build_ctx=lambda t: {},
        run_tick=boom,
        cfg=BotConfig(interval=0, max_ticks=2, topics=("x",)),
        sleep=lambda _s: None,
        install_signals=False,
    )
    assert len(r) == 2 and not any(x.completed for x in r)
    assert "error" in r[0].detail and "vllm down" in r[0].detail
    assert r[0].error_class == "transient" and r.stop_reason == "max_ticks"


def test_idle_when_no_work():
    r = run_bot(
        build_ctx=lambda t: {},
        run_tick=_good_tick,
        cfg=BotConfig(interval=0, max_ticks=1),
        pick_work=lambda: None,
        sleep=lambda _s: None,
        install_signals=False,
    )
    assert r[0].topic is None and r[0].detail == "idle"


def test_sleep_skipped_on_last_tick():
    sleeps: list = []
    run_bot(
        build_ctx=lambda t: {},
        run_tick=_good_tick,
        cfg=BotConfig(interval=5, max_ticks=2, topics=("a",)),
        sleep=sleeps.append,
        install_signals=False,
    )
    assert sleeps == [5]  # tick1 후 1회만 — 마지막 tick 뒤엔 sleep 생략
