"""MCP tool — eureka_induce (창조, 유레카): KG 패턴 → 추상 개념 induction, EARNED counts.

7군단장 실체감사(wf_376c327b-8f3)에서 유레카는 형제 중 유일하게 MCP 전용 툴이 없었다.
이 툴은 legion 우회 없이 실 엔진 경로(engine.eureka.pipeline.run_from_kg + LocalKgStore)를
단독 노출한다 — infra-0 covenant(번들 결정론 store, 실 Neo4j/키 불요), PROPOSE-only(비파괴).

Honest-count 계약 (ooptdd/eureka_adapter.py 와 동일): 보고 카운트는 stage payload 에서
RE-DERIVED — '4-induce'.abstract_classes(induced) / '4.5-quality-gate'.survived(survived).
stages_ok 는 진단 필드일 뿐 성공 지표가 아니다: 빈 KG 에서도 파이프라인 stages 는 green 으로
돌기 때문에(어댑터가 증명한 fake-green 축) earned 카운트만이 실제 산출을 말한다.

# KG: LakatosTree_Bhgman6CommanderOoptdd_20260624/eureka_mcp_earned_counts
# KG: eureka-canonical-2026-05-26, finding-ooptdd-bhgman-eureka-adapter-20260624
"""

from __future__ import annotations

from typing import Any


def _stage_count(pr: Any, prefix: str, key: str) -> int:
    """실 PipelineRun stage payload 에서 카운트 재도출 — stages_ok 재포장 금지 (어댑터 계약과 동일)."""
    for s in pr.stages:
        if s.stage.startswith(prefix) and isinstance(s.payload, dict):
            return int(s.payload.get(key, 0) or 0)
    return 0


def _candidate_payload(ac: Any) -> dict[str, Any]:
    return {
        "candidate_id": ac.candidateDigest or ac.name,
        "candidate_digest": ac.candidateDigest,
        "concept_name": ac.semanticName or ac.name,
        "definition": ac.summary,
        "mechanism": ac.mechanism,
        "scope": ac.scope,
        "falsifier": ac.falsifier,
        "extent": ac.extent or [],
        "intent": ac.intent or [],
        "stability_score": ac.stabilityScore,
        "novelty_score": ac.noveltyScore,
        "validation_receipt_digest": ac.validationReceiptDigest,
        "status": ac.status.value,
        "source_layer": "STRUCTURAL_INDUCTION",
        "artifact": None,
    }


def _induction_outcome(candidates: list[dict[str, Any]], induced: int) -> str:
    if candidates:
        return "PROPOSED"
    return "GATE_REJECTED" if induced else "NO_CANDIDATE"


def _induction_response(
    pr: Any,
    cfg: Any,
    *,
    cycle_id: str,
    induced: int,
    survived: int,
) -> dict[str, Any]:
    candidates = [_candidate_payload(ac) for ac in pr.proposals]
    stages_ok = sum(1 for stage in pr.stages if stage.ok)
    outcome = _induction_outcome(candidates, induced)
    return {
        "schema": "bhgman.eureka.run.v1",
        "cycle_id": cycle_id,
        "outcome": outcome,
        "mode": "structural",
        "method": cfg.method,
        "earned": {
            "induced": induced,
            "survived": survived,
            "proposed": len(candidates),
            "persisted": 0,
            "pruned_below_floor": max(0, induced - survived),
        },
        "stages_ok": stages_ok,
        "stages_total": len(pr.stages),
        "stages": [
            {"name": stage.stage, "ok": bool(stage.ok), "error": stage.error} for stage in pr.stages
        ],
        "candidates": candidates,
        "validation_receipts": [],
        "persistence": {
            "requested": False,
            "verdict": None,
            "receipt_required": False,
        },
        "errors": [stage.error for stage in pr.stages if stage.error],
        "summary": f"eureka[fca]: induced={induced} survived={survived} "
        f"proposed={len(candidates)} outcome={outcome} "
        f"(PROPOSE only; 진단 {stages_ok}/{len(pr.stages)} stages)",
        "backend": "local-kg (infra-0; PROPOSE-only — hades 가 나중에 실현)",
    }


def eureka_induce_impl(
    cycle_id: str = "mcp-eureka", kg_path: str | None = None, store: Any | None = None
) -> dict[str, Any]:
    """FCA induction 1회 (PROPOSE-only, 결정론). earned 카운트가 응답의 머리.

    ``store`` 는 테스트용 DIP seam (MCP 툴 시그니처 비노출).
    """
    from engine.eureka import pipeline, stages  # noqa: PLC0415
    from engine.kg_local.runner import make_local_runner  # noqa: PLC0415
    from engine.kg_local.store import LocalKgStore  # noqa: PLC0415

    if store is None:
        store = LocalKgStore(kg_path) if kg_path else LocalKgStore()
    run_cypher = make_local_runner(store, autosave=False)

    cfg = pipeline.PipelineConfig(
        cycle_id=cycle_id,
        fidelity_runner=run_cypher,
        **stages.wire_default_stages(run_cypher),
    )
    pr = pipeline.run_from_kg(run_cypher, cfg)

    induced = _stage_count(pr, "4-induce", "abstract_classes")
    survived = _stage_count(pr, "4.5-quality-gate", "survived")
    return _induction_response(
        pr,
        cfg,
        cycle_id=cycle_id,
        induced=induced,
        survived=survived,
    )


def register(mcp: Any) -> None:
    """Attach the eureka tool to the FastMCP instance."""

    @mcp.tool()
    def eureka_induce(cycle_id: str = "mcp-eureka", kg_path: str = "") -> dict[str, Any]:
        """Induce abstract concepts from the KG (창조, FCA — PROPOSE only, EARNED counts).

        Args:
            cycle_id: label for this induction run.
            kg_path: optional LocalKgStore JSON path; empty = default bundle.

        Returns: {earned: {induced, survived, pruned_below_floor}, stages_ok, summary, ...}.
        """
        return eureka_induce_impl(cycle_id=cycle_id, kg_path=kg_path or None)


__all__ = ["eureka_induce_impl", "register"]
