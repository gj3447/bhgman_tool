"""7-stage L8 induction orchestrator.

STAGE-1 Extract → STAGE-2 Community → STAGE-3 Summarize → STAGE-4 Induce →
STAGE-5 Naesengmoon Gate → STAGE-6 Hybrid retrieval → STAGE-7 Drift loop.

Spec: seed-prom16lag-cons-graphrag-biocypher-blueprint-2026-05-20.

P2 refactor (Naesengmoon SOLID HIGH-3, 2026-05-20): Stage + InductionOperator +
QualityGate protocols. stage_2/3/6/7 are NotImplementedStage instances that raise
explicitly; callers configure replacements via PipelineConfig injection.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Optional

import quality_gate as quality_gate_module
from induction_operators import FcaResult, induce_fca
from models import AbstractClass, AbstractClassStatus, GeneralizesEdge, InductionMethod
from protocols import NotImplementedStage, NotImplementedStageError, Stage, StageResult
from validator import gate_before_merge


@dataclass
class PipelineConfig:
    cycle_id: str
    gamma_sweep: tuple[float, ...] = (0.5, 1.0, 2.0)
    fca_min_extent: int = 2
    fca_min_stability: float = 0.5

    stage_community: Optional[Stage] = None
    stage_summarize: Optional[Stage] = None
    stage_hybrid_retrieval: Optional[Stage] = None
    stage_drift_loop: Optional[Stage] = None

    def resolve_stage_community(self) -> Stage:
        return self.stage_community or NotImplementedStage(
            "2-community",
            "Leiden community detection requires gds.leiden on Neo4j VM + Cypher integration. "
            "Inject via PipelineConfig.stage_community.",
        )

    def resolve_stage_summarize(self) -> Stage:
        return self.stage_summarize or NotImplementedStage(
            "3-summarize",
            "Per-community Haiku summarization via 재배맨 SOP. "
            "Inject via PipelineConfig.stage_summarize.",
        )

    def resolve_stage_hybrid_retrieval(self) -> Stage:
        return self.stage_hybrid_retrieval or NotImplementedStage(
            "6-hybrid-retrieval",
            "BM25 + vector + community-summary RRF integration with neo4j-graphrag. "
            "Inject via PipelineConfig.stage_hybrid_retrieval.",
        )

    def resolve_stage_drift_loop(self) -> Stage:
        return self.stage_drift_loop or NotImplementedStage(
            "7-drift-loop",
            "Nightly Leiden + GED >τ trigger. Wire via nightly_drift_check.py cron. "
            "Inject via PipelineConfig.stage_drift_loop for synchronous in-pipeline check.",
        )


@dataclass
class PipelineRun:
    config: PipelineConfig
    stages: list[StageResult] = field(default_factory=list)

    def record(self, stage: str, ok: bool, payload=None, error: Optional[str] = None) -> None:
        self.stages.append(StageResult(stage=stage, ok=ok, payload=payload, error=error))


def stage_1_extract(reference_sites: list[dict]) -> list[dict]:
    """L1-L7 ReferenceSite → :Candidate. Pure relabel."""
    return [{**rs, "_label": "Candidate"} for rs in reference_sites]


def stage_4_induce_fca(
    formal_context: dict[str, frozenset[str]],
    cycle_id: str,
    config: PipelineConfig,
) -> tuple[list[AbstractClass], list[GeneralizesEdge], FcaResult]:
    fca_result = induce_fca(
        formal_context,
        min_extent=config.fca_min_extent,
        min_stability=config.fca_min_stability,
    )

    abstract_classes: list[AbstractClass] = []
    edges: list[GeneralizesEdge] = []
    now = dt.datetime.now(dt.timezone.utc)

    for i, concept in enumerate(fca_result.concepts):
        ac_name = f"ac_fca_{cycle_id}_{i:04d}"
        intent_summary = ", ".join(sorted(concept.intent))[:200] or "(empty intent)"
        ac = AbstractClass(
            name=ac_name,
            summary=f"FCA concept: {intent_summary}",
            inductionMethod=InductionMethod.FCA,
            cycleId=cycle_id,
            createdAt=now,
            status=AbstractClassStatus.PROPOSED,
            extent=sorted(concept.extent),
            intent=sorted(concept.intent),
            stabilityScore=concept.stability,
        )
        abstract_classes.append(ac)
        for _ in concept.extent:
            edges.append(
                GeneralizesEdge(
                    confidence=concept.stability,
                    method=InductionMethod.FCA,
                    cycleId=cycle_id,
                    createdAt=now,
                    induced=True,
                )
            )
    return abstract_classes, edges, fca_result


def stage_5_naesengmoon_gate(abstract_classes: list[AbstractClass]) -> list[AbstractClass]:
    return [
        ac.model_copy(update={"status": AbstractClassStatus.VERDICT_PENDING})
        for ac in abstract_classes
    ]


def _try_run_stage(stage: Stage, context: dict[str, Any], record_to: PipelineRun) -> bool:
    """Run an injectable stage. Returns True if it ran successfully, False if
    explicitly NotImplemented (recorded but not fatal)."""
    try:
        result = stage.run(context)
        record_to.record(result.stage, result.ok, payload=result.payload, error=result.error)
        return result.ok
    except NotImplementedStageError as e:
        record_to.record(stage.name, False, error=str(e), payload={"not_implemented": True})
        return False


def run(
    reference_sites: list[dict],
    formal_context: dict[str, frozenset[str]],
    config: PipelineConfig,
) -> PipelineRun:
    pr = PipelineRun(config=config)

    candidates = stage_1_extract(reference_sites)
    pr.record("1-extract", True, payload={"count": len(candidates)})

    ctx = {"candidates": candidates, "gamma_sweep": config.gamma_sweep}
    _try_run_stage(config.resolve_stage_community(), ctx, pr)
    _try_run_stage(config.resolve_stage_summarize(), ctx, pr)

    acs, edges, fca_result = stage_4_induce_fca(formal_context, config.cycle_id, config)
    pr.record(
        "4-induce-fca",
        fca_result.fallback_reason is None,
        payload={"abstract_classes": len(acs), "edges": len(edges), "pruned": fca_result.pruned},
        error=fca_result.fallback_reason,
    )

    if acs:
        avg_stability = sum(ac.stabilityScore or 0.0 for ac in acs) / len(acs)
        q_report = quality_gate_module.evaluate(fca_stability=avg_stability)
        pr.record(
            "4.5-quality-gate",
            q_report.passed,
            payload=q_report,
            error="; ".join(q_report.reasons) if not q_report.passed else None,
        )
        if not q_report.passed:
            return pr

    gated_acs = stage_5_naesengmoon_gate(acs)
    pr.record("5-naesengmoon-gate", True, payload={"verdict_pending": len(gated_acs)})

    ac_payloads = [ac.model_dump(mode="json") for ac in gated_acs]
    edge_payloads = [e.model_dump(mode="json") for e in edges]
    try:
        gate_before_merge(ac_payloads, edge_payloads)
        pr.record("5.5-pre-merge-validator", True, payload={"validated": len(ac_payloads)})
    except Exception as e:
        pr.record("5.5-pre-merge-validator", False, error=str(e))
        return pr

    _try_run_stage(config.resolve_stage_hybrid_retrieval(), ctx, pr)
    _try_run_stage(config.resolve_stage_drift_loop(), ctx, pr)
    return pr


def main() -> None:
    cfg = PipelineConfig(cycle_id="cli-demo")
    result = run(reference_sites=[], formal_context={}, config=cfg)
    for s in result.stages:
        status = "ok" if s.ok else "FAIL"
        print(f"[{status}] {s.stage}: {s.payload if s.ok else s.error}")


if __name__ == "__main__":
    main()


__all__ = [
    "PipelineConfig",
    "PipelineRun",
    "run",
    "stage_1_extract",
    "stage_4_induce_fca",
    "stage_5_naesengmoon_gate",
]
