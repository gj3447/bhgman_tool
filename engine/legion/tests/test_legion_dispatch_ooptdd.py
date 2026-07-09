"""ooptdd trace-gate over the dispatch 폐루프 (G5-C5 소비자) — 영수증 4축.

Positive-TDD / log-based gate: the *backend store* is the judge. We drive the REAL
chain through ooptdd/legion_dispatch_adapter.py (seed 12 확신-dup 그룹 → legion run
발화 → consume_dispatch 실행 → 재run 재발화 실측) and the spec independently re-checks
arrival. Counts are re-derived from KG state + DispatchConsumeReport — never hand-typed.

Axes:
  * test_dispatch_consume_arrives_green — 발화→소비→실행→자기해소 전 사슬 green 실측.
  * test_silent_loss_is_caught (counter, axis A) — drop=True 백엔드: self-report 는
    동일 green 인데 gate 는 RED (store 에 아무것도 안 닿음).
  * test_below_threshold_no_fire (판별력, axis C) — 10그룹(임계 미달) seeding 이면 발화
    0 → ==1 gate RED: 카운트가 실측이지 상수가 아님.
  * test_dry_run_no_self_heal (판별력, axis C) — apply=False 면 janitor 가 백로그를 못
    닫아 재발화 잔존 → trigger_cleared 0 = RED: 자기해소 축이 실측임의 증명.
  * test_longinus_binding_is_real (axis B) — must_emit 리터럴이 바운드 심볼 본문에
    실재, rename 은 UNBOUND.
  * test_engine_stays_literal_free (하드코어 grep 가드) — 이벤트 리터럴은 어댑터에만,
    engine/legion/*.py 에는 절대 없음.

# KG: finding-ooptdd-bhgman-legion-dispatch-adapter-20260710
# KG: LakatosTree_BhgmanDispatchLoop_20260710/dispatch_consumer_keystone
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ooptdd/ooptdd_loop = dev-only methodology siblings (private, not on any index). CI does
# not install them, so skip these instrumentation tests there. The consumer behaviour is
# covered by engine/legion/tests/test_dispatch_consumer.py either way.
pytest.importorskip("ooptdd.backends")
pytest.importorskip("ooptdd_loop")

from ooptdd.backends.memory import MemoryBackend, reset
from ooptdd.engine.gate import evaluate, load_gate
from ooptdd_loop.domain.spec import Longinus
from ooptdd_loop.engine.longinus import verify_binding

from ooptdd.legion_dispatch_adapter import (
    _KG_ANCHOR,
    run_legion_dispatch_pipeline,
)

_ROOT = str(Path(__file__).resolve().parents[3])
_ADAPTER_SRC = "ooptdd/legion_dispatch_adapter.py"
_GATE_PATH = str(Path(__file__).parent / "gates" / "legion_dispatch_flow.yaml")
_CID = "legion-dispatch-ooptdd"

_EVENT_LITERALS = (
    "dispatch_consume_started",
    "dispatch_consume_completed",
    "dispatch_decision_fired",
    "dispatch_decision_consumed",
    "dispatch_janitor_executed",
    "dispatch_trigger_cleared",
)


def _gates():
    return load_gate(_GATE_PATH)


def test_dispatch_consume_arrives_green():
    reset()
    backend = MemoryBackend()
    out = run_legion_dispatch_pipeline(backend, _CID)
    assert out["fired"] == 1 and out["executed"] >= 1 and out["cleared"] == 1
    result = evaluate(backend, _gates(), cid=_CID)
    assert result["ok"] is True, f"gate must be green on the real chain: {result}"


def test_silent_loss_is_caught():
    reset()
    backend = MemoryBackend(drop=True)
    out = run_legion_dispatch_pipeline(backend, _CID)
    assert out["fired"] == 1 and out["cleared"] == 1, "self-report 는 여전히 green"
    result = evaluate(backend, _gates(), cid=_CID)
    assert result["ok"] is False, "store 에 아무것도 안 닿았으면 gate 는 RED 여야"


def test_below_threshold_no_fire():
    reset()
    backend = MemoryBackend()
    out = run_legion_dispatch_pipeline(backend, _CID, n_groups=10)  # 임계(>10) 미달
    assert out["fired"] == 0, "10그룹이면 dead_node_count=10 은 발화하면 안 됨"
    result = evaluate(backend, _gates(), cid=_CID)
    assert result["ok"] is False, "발화 ==1 gate 가 RED 여야 (카운트=실측 증명)"


def test_dry_run_no_self_heal():
    reset()
    backend = MemoryBackend()
    out = run_legion_dispatch_pipeline(backend, _CID, apply=False)
    assert out["cleared"] == 0, "dry-run janitor 는 백로그를 못 닫는다 (재발화 잔존)"
    result = evaluate(backend, _gates(), cid=_CID)
    assert result["ok"] is False, "self-heal ==1 gate 가 RED 여야 (자기해소=실측 증명)"


def test_longinus_binding_is_real():
    cases = [
        ("run_legion_dispatch_pipeline", "dispatch_consume_completed"),
        ("emit_fired_phase", "dispatch_decision_fired"),
        ("emit_consumed_phase", "dispatch_decision_consumed"),
        ("emit_executed_phase", "dispatch_janitor_executed"),
        ("emit_self_heal_phase", "dispatch_trigger_cleared"),
    ]
    for symbol, literal in cases:
        bound = verify_binding(_ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal))
        assert bound.bound is True, f"{symbol} should emit {literal}: {bound.reason}"
        miss = verify_binding(
            _ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal + "_RENAMED")
        )
        assert miss.bound is False, f"{symbol} must NOT bind a renamed literal"


def test_engine_stays_literal_free():
    """하드코어 grep 가드: 이벤트 리터럴은 ooptdd/legion_dispatch_adapter.py 에만 —
    engine/legion/*.py (dispatch_consumer.py 포함) 는 emit-free/리터럴-free."""
    engine_dir = Path(_ROOT) / "engine" / "legion"
    offenders: list[str] = []
    for py in sorted(engine_dir.glob("*.py")):  # top-level modules only, not tests/
        src = py.read_text(encoding="utf-8")
        offenders.extend(f"{py.name}:{lit}" for lit in _EVENT_LITERALS if lit in src)
    assert not offenders, (
        f"event literals must live ONLY in {_ADAPTER_SRC}, never in engine/legion/: {offenders}"
    )
