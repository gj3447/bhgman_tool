"""7군단장 → CommanderStage 통일 배선 검증.

증명 대상:
- 6 능동 군단장이 CommanderStage 프로토콜에 conform (CANONICAL_ORDER).
- Legion 닫힌 루프가 Contract-bound handoff로 end-to-end 완주 (neo4j 불필요).
- 프로메테우스(획득)·나생문(검증)이 LLM(client) 없이 결정론 코어로 동작 — 키 불필요 floor.
- 하데스(실현)가 나생문 oracle FAIL 시 skip (gate 의미화).

# KG: adr-seven-commander-legion-architecture-2026-05-27
"""

from __future__ import annotations

from engine.legion.commanders import build_default_legion, default_stages
from engine.legion.legion import CANONICAL_ORDER
from engine.legion.legion_models import CommanderStage
from engine.legion.commanders import _run_acquire, _run_realize, _run_verify


def _empty_rc(_cypher: str, _params: dict) -> list[dict]:
    """모든 쿼리에 [] 반환하는 fake cypher (neo4j 불필요)."""
    return []


# ── 프로토콜 conformance ────────────────────────────────────────────────────
def test_default_stages_conform_protocol():
    stages = default_stages()
    assert len(stages) == 6
    for s in stages:
        assert isinstance(s, CommanderStage)
        assert callable(s.run)
        assert s.requires and s.provides


def test_default_stages_follow_canonical_order():
    verbs = tuple(s.verb for s in default_stages())
    assert verbs == CANONICAL_ORDER  # 획득 연결 창조 정리 검증 실현


def test_verify_requires_all_four_upstream_provides():
    verify = next(s for s in default_stages() if s.verb == "검증")
    assert set(verify.requires) == {"acquired", "bindings", "abstractions", "hygiene"}
    realize = next(s for s in default_stages() if s.verb == "실현")
    assert realize.requires == ("verdict",)  # 검증 후에만 실현


# ── 닫힌 루프 end-to-end (Contract-bound handoff) ───────────────────────────
def test_closed_loop_completes_with_contract_handoff():
    legion = build_default_legion()
    run = legion.run(context={"run_cypher": _empty_rc})
    assert run.contract_violation is None, run.contract_violation
    assert run.completed is True
    keys = set(run.final_context_keys)
    assert {"acquired", "bindings", "abstractions", "hygiene", "verdict", "realized"} <= keys


def test_loop_blocks_when_run_cypher_missing():
    """run_cypher 없으면 획득 stage requires 위반 → Contract violation (handoff 강제)."""
    legion = build_default_legion()
    run = legion.run(context={})
    assert run.completed is False
    assert run.contract_violation is not None
    assert "run_cypher" in run.contract_violation


# ── 결정론 코어 (LLM 없이) ──────────────────────────────────────────────────
def test_acquire_deterministic_core_reads_gap_nodes_without_llm():
    def rc(_c: str, _p: dict) -> list[dict]:
        return [
            {"id": "q1", "question": "what is X", "kind": "OpenQuestion"},
            {"id": "q2", "question": "what is Y", "kind": "OpenQuestion"},
            {"id": "q3", "question": "what is Z", "kind": "OpenQuestion"},
        ]

    out = _run_acquire({"run_cypher": rc})  # client 없음, fetcher 없음 → gap+query only
    assert out["acquired"]["mode"] == "kg-deterministic"
    assert out["acquired"]["gap_nodes"] == 3
    assert out["acquired"]["dry_run"] is True


def test_verify_oracle_pass_when_upstream_clean():
    ctx = {
        "acquired": {"mode": "kg-deterministic"},
        "bindings": {"mode": "kg-deterministic"},
        "abstractions": {"mode": "fca"},
        "hygiene": {"mode": "occam"},
    }
    out = _run_verify(ctx)
    assert out["verdict"]["oracle"] == "PASS"
    assert out["verdict"]["mode"] == "oracle-deterministic"  # client 없음 → judgment 없음


def test_verify_oracle_fails_on_degraded_upstream():
    ctx = {
        "acquired": {"mode": "degraded"},
        "bindings": {"mode": "kg-deterministic"},
        "abstractions": {"mode": "fca"},
        "hygiene": {"mode": "occam"},
    }
    out = _run_verify(ctx)
    assert out["verdict"]["oracle"] == "FAIL"
    assert "acquired" in out["verdict"]["degraded_upstream"]


def test_realize_skips_when_oracle_gate_fails():
    out = _run_realize(
        {"run_cypher": _empty_rc, "verdict": {"oracle": "FAIL", "degraded_upstream": ["acquired"]}}
    )
    assert out["realized"]["mode"] == "skipped"


def test_realize_skips_when_ensemble_rejects():
    """W1-D: hades must not realize a product the adversary ensemble REJECTed, even if
    the oracle leg passed."""
    out = _run_realize(
        {"run_cypher": _empty_rc, "verdict": {"oracle": "PASS", "ensemble": "REJECT"}}
    )
    assert out["realized"]["mode"] == "skipped"


def test_realize_skips_when_ensemble_fails():
    out = _run_realize({"run_cypher": _empty_rc, "verdict": {"oracle": "PASS", "ensemble": "FAIL"}})
    assert out["realized"]["mode"] == "skipped"
