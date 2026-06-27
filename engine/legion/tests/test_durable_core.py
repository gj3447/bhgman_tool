"""Legion durable 코어 3종 TDD — fallback 경로 + 멱등 + 정체감지.

# KG: durable-legion-fallback-2026-06-27, legion-stuck-detector-2026-06-27,
#     hades-realize-idempotency-2026-06-27
"""

from __future__ import annotations

from engine.legion.durable import HAS_DBOS, durable_run
from engine.legion.legion import Legion
from engine.legion.legion_models import CommanderStage
from engine.legion.realize_idempotency import RealizationLedger, realize_idempotency_key
from engine.legion.stuck_detector import StuckDetector


def _toy_legion() -> Legion:
    stage = CommanderStage(
        name="prometheus",
        verb="획득",
        requires=(),
        provides=("acquired",),
        run=lambda ctx: {"acquired": True},
    )
    return Legion().register(stage)


# ─── durable_run (fallback seam) ────────────────────────────────────────


def test_durable_run_fallback_equals_legion_run():
    a = durable_run(_toy_legion(), {"seed": 1}, cycle_id="cyc-1")
    b = _toy_legion().run({"seed": 1})
    assert a.completed and b.completed
    assert a.outcomes[0].stage == b.outcomes[0].stage == "prometheus"
    assert "acquired" in a.final_context_keys


def test_durable_run_without_cycle_id_is_in_process():
    r = durable_run(_toy_legion())
    assert r.completed and "acquired" in r.final_context_keys


def test_has_dbos_is_bool():
    assert isinstance(HAS_DBOS, bool)  # 환경 무관, 미설치면 False (fallback)


# ─── StuckDetector (정체 감지, 깊이캡과 직교) ───────────────────────────


def test_stuck_detector_halts_after_patience_no_progress():
    sd = StuckDetector(patience=3)
    assert not sd.observe("sig-A")
    assert not sd.observe("sig-A")
    assert sd.observe("sig-A")  # 3연속 동일 → stuck
    assert sd.is_stuck


def test_stuck_detector_progress_resets_repeat():
    sd = StuckDetector(patience=2)
    sd.observe("a")
    assert sd.observe("a")  # 2연속 → stuck
    sd.observe("b")  # 진전 → 리셋
    assert not sd.is_stuck


def test_stuck_detector_rejects_bad_patience():
    import pytest

    with pytest.raises(ValueError):
        StuckDetector(patience=0)


# ─── 하데스 실현 멱등 ────────────────────────────────────────────────────


def test_realize_idempotency_key_stable_and_path_sensitive():
    k1 = realize_idempotency_key("cyc1", "sha-abc", "/x/y.py")
    k2 = realize_idempotency_key("cyc1", "sha-abc", "/x/y.py")
    k3 = realize_idempotency_key("cyc1", "sha-abc", "/x/z.py")
    assert k1 == k2  # 같은 입력 → 같은 키
    assert k1 != k3  # 대상 경로 다르면 다른 키
    assert k1.startswith("realize-")


def test_realization_ledger_realizes_exactly_once():
    ledger = RealizationLedger()
    calls: list[int] = []
    key = realize_idempotency_key("c", "s", "/t")
    did1, _ = ledger.realize_once(key, lambda: calls.append(1))
    did2, _ = ledger.realize_once(key, lambda: calls.append(1))  # at-least-once 재호출
    assert did1 is True and did2 is False
    assert len(calls) == 1  # 부수효과는 정확히 1회
    assert ledger.seen(key)
