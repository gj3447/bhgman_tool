"""Legion durable 코어 TDD — fallback 경로 + 정체감지.

(하데스 실현 멱등은 engine/legion/verdict_gate.py 의 VerdictLedger/KgVerdictLedger 가 담당 —
 중복 RealizationLedger 제거 2026-06-27. 그 테스트는 test_verdict_gate.py.)

# KG: durable-legion-fallback-2026-06-27, legion-stuck-detector-2026-06-27
"""

from __future__ import annotations

from engine.legion.durable import HAS_DBOS, durable_run
from engine.legion.legion import Legion
from engine.legion.legion_models import CommanderStage
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
