"""7-stage L8 induction orchestrator.

STAGE-1 Extract → STAGE-2 Community → STAGE-3 Summarize → STAGE-4 Induce →
STAGE-5 Naesengmoon Gate → STAGE-6 Hybrid retrieval → STAGE-7 Drift loop.

Spec: seed-prom16lag-cons-graphrag-biocypher-blueprint-2026-05-20.

P2 refactor (Naesengmoon SOLID HIGH-3, 2026-05-20): Stage + InductionOperator +
QualityGate protocols. stage_2/3/6/7 are NotImplementedStage instances that raise
explicitly; callers configure replacements via PipelineConfig injection.
"""
# KG: eureka-canonical-2026-05-26

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Optional

from engine.eureka import quality_gate as quality_gate_module
from engine.eureka.fidelity_gate import FidelityConfig, run_fidelity_for_members
from engine.eureka.formal_context_builder import (
    CypherRunner,
    FormalContextConfig,
    build_formal_context,
)
from engine.eureka.induction_operators import FcaResult, induce_fca
from engine.eureka.induction_models import (
    AbstractClass,
    AbstractClassStatus,
    GeneralizesEdge,
    InductionMethod,
)
from engine.eureka.oracle_lens import (
    CommandRunner,
    OracleLens,
    kg_oracle_gate,
    run_oracle_gate,
    subprocess_runner,
)
from engine.eureka.protocols import (
    NotImplementedStage,
    NotImplementedStageError,
    Stage,
    StageResult,
)
from engine.eureka.validator import gate_before_merge


@dataclass
class PipelineConfig:
    # KG: eureka-canonical-2026-05-26
    cycle_id: str
    gamma_sweep: tuple[float, ...] = (0.5, 1.0, 2.0)
    fca_min_extent: int = 2
    fca_min_stability: float = 0.5

    # induction operator 선택 (4-way bake-off): 'fca'(default) | 'amie3'(Java subprocess)
    # | 'leiden-llm'(offline CNM) | 'leiden-true'(genuine Leiden, needs leidenalg+igraph).
    method: str = "fca"
    # amie3 주입점 (테스트=fake, 실전=induce_amie3 default). amie3 전용 threshold도 재사용.
    amie3_runner: Optional[Any] = None
    amie3_min_pca: float = 0.5

    stage_community: Optional[Stage] = None
    stage_summarize: Optional[Stage] = None
    stage_hybrid_retrieval: Optional[Stage] = None
    stage_drift_loop: Optional[Stage] = None

    # 나생문 oracle 렌즈 (executable hard-gate, 2 lens-class). 비어있으면 opt-out(skip).
    # default_eureka_lenses(target)으로 ruff+pytest 주입. runner=None → subprocess_runner.
    oracle_lenses: tuple[OracleLens, ...] = ()
    oracle_runner: Optional[CommandRunner] = None

    # fidelity gate (stage_4.8, SOFT — consilience). runner 주입 시 per-ac 측정(block 안 함).
    fidelity_runner: Optional[CypherRunner] = None
    fidelity_cfg: Optional[FidelityConfig] = None

    # Optional semantic layer.  The structural inducer proposes extents/intents;
    # this injected port performs bounded abductive naming + independent critique.
    # Kept as a port so the deterministic kernel has no AgentClient dependency.
    creative_enricher: Optional[Any] = None

    # stage_6 KG persist (W1-I). None → pipeline stays read-only (dry-run default, like
    # occam/hades). Injected → gated ACs are MERGEd so hades can realize them. persist_accept
    # is the explicit PROPOSED→ACCEPTED transition (writes verdictStatus='ACCEPTED' only then).
    persist_cypher: Optional[CypherRunner] = None
    persist_accept: bool = False
    require_acceptance_receipt: bool = False

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
    # KG: eureka-canonical-2026-05-26
    config: PipelineConfig
    stages: list[StageResult] = field(default_factory=list)
    proposals: list[AbstractClass] = field(default_factory=list)
    creative_receipts: list[dict[str, Any]] = field(default_factory=list)
    creative_artifacts: list[dict[str, Any]] = field(default_factory=list)

    def record(self, stage: str, ok: bool, payload=None, error: Optional[str] = None) -> None:
        self.stages.append(StageResult(stage=stage, ok=ok, payload=payload, error=error))


def stage_1_extract(reference_sites: list[dict]) -> list[dict]:
    # KG: eureka-canonical-2026-05-26
    """L1-L7 ReferenceSite → :Candidate. Pure relabel."""
    return [{**rs, "_label": "Candidate"} for rs in reference_sites]


def _concepts_to_acs(
    fca_result: FcaResult, cycle_id: str, method: InductionMethod
) -> tuple[list[AbstractClass], list[GeneralizesEdge]]:
    """FormalConcept(FCA든 AMIE3 어댑터든 동일 shape) → AbstractClass + GeneralizesEdge."""
    abstract_classes: list[AbstractClass] = []
    edges: list[GeneralizesEdge] = []
    now = dt.datetime.now(dt.timezone.utc)
    tag = method.value
    for i, concept in enumerate(fca_result.concepts):
        ac_name = f"ac_{tag}_{cycle_id}_{i:04d}"
        intent_summary = ", ".join(sorted(concept.intent))[:200] or "(empty intent)"
        abstract_classes.append(
            AbstractClass(
                name=ac_name,
                summary=f"{tag.upper()} concept: {intent_summary}",
                inductionMethod=method,
                cycleId=cycle_id,
                createdAt=now,
                status=AbstractClassStatus.PROPOSED,
                extent=sorted(concept.extent),
                intent=sorted(concept.intent),
                stabilityScore=concept.stability,
            )
        )
        for _ in concept.extent:
            edges.append(
                GeneralizesEdge(
                    confidence=concept.stability,
                    method=method,
                    cycleId=cycle_id,
                    createdAt=now,
                    induced=True,
                )
            )
    return abstract_classes, edges


def stage_4_induce(
    formal_context: dict[str, frozenset[str]],
    cycle_id: str,
    config: PipelineConfig,
) -> tuple[list[AbstractClass], list[GeneralizesEdge], FcaResult]:
    # KG: eureka-canonical-2026-05-26
    """induction operator dispatch (config.method): 'fca'(default) | 'amie3' | 'leiden-llm' | 'leiden-true'.

    모든 operator 가 FcaResult(FormalConcept) shape로 정규화 → 후단(quality/oracle/fidelity/gate)
    동일 처리. amie3는 Java subprocess(amie3_runner 주입식, 어댑터가 Horn rule→concept 변환);
    leiden-true는 genuine Leiden(leidenalg+igraph opt-in dep, 없으면 RuntimeError).
    """
    if config.method == "amie3":
        from engine.eureka.amie3_adapter import induce_via_amie3  # noqa: PLC0415 (Java-optional path)

        kw = {} if config.amie3_runner is None else {"amie3_fn": config.amie3_runner}
        fca_result = induce_via_amie3(
            formal_context,
            min_pca_confidence=config.amie3_min_pca,
            min_extent=config.fca_min_extent,
            **kw,
        )
        method = InductionMethod.AMIE3
    elif config.method == "leiden-llm":
        from engine.eureka.induction_operators import induce_leiden_llm  # noqa: PLC0415

        resolution = config.gamma_sweep[0] if config.gamma_sweep else 1.0
        fca_result = induce_leiden_llm(
            formal_context,
            resolution=resolution,
            min_extent=config.fca_min_extent,
            min_stability=config.fca_min_stability,
        )
        method = InductionMethod.LEIDEN_LLM
    elif config.method == "leiden-true":
        # Genuine Leiden (Traag-Waltman-vanEck 2019) — opt-in upgrade over the
        # offline CNM operator; needs leidenalg+igraph (raises a clear error if
        # absent). Same I/O as leiden-llm, so the bake-off compares algorithm
        # quality on identical formal contexts.
        from engine.eureka.induction_operators import induce_leiden_true  # noqa: PLC0415

        resolution = config.gamma_sweep[0] if config.gamma_sweep else 1.0
        fca_result = induce_leiden_true(
            formal_context,
            resolution=resolution,
            min_extent=config.fca_min_extent,
            min_stability=config.fca_min_stability,
        )
        method = InductionMethod.LEIDEN_TRUE
    else:
        fca_result = induce_fca(
            formal_context,
            min_extent=config.fca_min_extent,
            min_stability=config.fca_min_stability,
        )
        method = InductionMethod.FCA

    acs, edges = _concepts_to_acs(fca_result, cycle_id, method)
    return acs, edges, fca_result


def stage_4_induce_fca(
    formal_context: dict[str, frozenset[str]],
    cycle_id: str,
    config: PipelineConfig,
) -> tuple[list[AbstractClass], list[GeneralizesEdge], FcaResult]:
    # KG: eureka-canonical-2026-05-26
    """Back-compat alias — FCA path. 신규 호출은 stage_4_induce(dispatch) 권장."""
    return stage_4_induce(formal_context, cycle_id, config)


def stage_4_7_oracle_gate(
    acs: list[AbstractClass], config: "PipelineConfig", pr: "PipelineRun"
) -> bool:
    # KG: eureka-canonical-2026-05-26
    """나생문 oracle hard-gate (executable lens-class) — 선(先) gate. KG backend.

    2 lens-class: 이 oracle(실행) 렌즈가 hard pre-gate, 이후 판단(LLM) 렌즈 = stage_5.
    well-formed 아닌 concept이면 의미검증(stage_5) 무의미하므로 여기서 차단.

    ① KG oracle (항상, 후보 concept에 결정론 불변식): extent recount / intent / acyclic / stability.
    ② shell oracle (config.oracle_lenses 주입 시): code backend / 외부 cypher 등. opt-in.
    """
    kg_passed, kg_verdicts = kg_oracle_gate(
        acs, min_extent=config.fca_min_extent, min_stability=config.fca_min_stability
    )
    pr.record(
        "4.7-naesengmoon-oracle-gate(KG)",
        kg_passed,
        payload={
            "verdicts": [{"lens": v.lens, "kind": v.kind, "passed": v.passed} for v in kg_verdicts]
        },
        error=None
        if kg_passed
        else "; ".join(f"{v.lens}: {v.detail}" for v in kg_verdicts if not v.passed),
    )
    if not kg_passed:
        return False

    if config.oracle_lenses:
        runner = config.oracle_runner or subprocess_runner
        sh_passed, sh_verdicts = run_oracle_gate(config.oracle_lenses, runner)
        pr.record(
            "4.7b-naesengmoon-oracle-gate(shell)",
            sh_passed,
            payload={
                "verdicts": [
                    {"lens": v.lens, "kind": v.kind, "passed": v.passed} for v in sh_verdicts
                ]
            },
            error=None
            if sh_passed
            else "; ".join(f"{v.lens}: {v.detail}" for v in sh_verdicts if not v.passed),
        )
        if not sh_passed:
            return False
    return True


def stage_4_8_fidelity_gate(
    acs: list[AbstractClass], config: "PipelineConfig", pr: "PipelineRun"
) -> None:
    # KG: eureka-canonical-2026-05-26
    """fidelity gate (SOFT, stage_4.8) — consilience. config.fidelity_runner 없으면 skip.

    per-ac witness coherence 측정 → SOFT_WARN/PASS 기록. block 안 함(판단렌즈가 흡수).
    """
    if config.fidelity_runner is None:
        pr.record("4.8-fidelity-gate", True, payload={"skipped": "no fidelity_runner (opt-out)"})
        return
    results = []
    for ac in acs:
        members = list(getattr(ac, "extent", []) or [])
        v = run_fidelity_for_members(ac.name, members, config.fidelity_runner, config.fidelity_cfg)
        results.append(
            {"concept": ac.name, "passed": v.passed, "witnesses_passing": v.witnesses_passing}
        )
    n_warn = sum(1 for r in results if not r["passed"])
    pr.record(
        "4.8-fidelity-gate",
        True,  # SOFT — 항상 통과(판단렌즈 escalate), 경고만 기록
        payload={"results": results, "soft_warns": n_warn},
    )


def stage_5_naesengmoon_gate(abstract_classes: list[AbstractClass]) -> list[AbstractClass]:
    # KG: eureka-canonical-2026-05-26
    return [
        ac.model_copy(update={"status": AbstractClassStatus.VERDICT_PENDING})
        for ac in abstract_classes
    ]


# eureka→KG persist. Sets `verdictStatus` — the field hades filters on to realize
# (`a.verdictStatus = 'ACCEPTED'`). Distinct shape from the hades self-MERGE route
# (`{name:$concept}` no space) so the local backend routes it separately. (W1-I)
_PERSIST_AC_CYPHER = (
    "MERGE (a:AbstractClass {name: $name}) "
    "SET a.verdictStatus = $verdictStatus, a.status = $status, a.summary = $summary, "
    "a.createdAt = coalesce(a.createdAt, $createdAt), "
    "a.inductionMethod = $inductionMethod, a.cycleId = $cycleId, "
    "a.extent = $extent, a.intent = $intent, a.stabilityScore = $stabilityScore, "
    "a.semanticName = $semanticName, a.mechanism = $mechanism, a.scope = $scope, "
    "a.falsifier = $falsifier, a.candidateDigest = $candidateDigest, "
    "a.validationReceiptDigest = $validationReceiptDigest, a.noveltyScore = $noveltyScore "
    "RETURN a.name AS name"
)


def _parse_validation_receipt(raw_receipt: dict[str, Any], index: int) -> tuple[Any, str]:
    from engine.eureka.creative import ValidationReceipt  # noqa: PLC0415

    claimed_digest = raw_receipt.get("receipt_digest")
    try:
        receipt = ValidationReceipt.model_validate(raw_receipt)
    except Exception as error:
        raise ValueError(
            f"serialized validation receipt at index {index} failed schema validation"
        ) from error
    computed_digest = receipt.receipt_digest
    if claimed_digest != computed_digest:
        raise ValueError(f"serialized validation receipt at index {index} has a digest mismatch")
    return receipt, computed_digest


def _index_validation_receipts(
    creative_receipts: list[dict[str, Any]] | None,
) -> dict[str, tuple[Any, str]]:
    indexed: dict[str, tuple[Any, str]] = {}
    for index, raw_receipt in enumerate(creative_receipts or []):
        if not isinstance(raw_receipt, dict):
            raise ValueError(f"serialized validation receipt at index {index} must be an object")
        receipt, computed_digest = _parse_validation_receipt(raw_receipt, index)
        if receipt.candidate_digest in indexed:
            raise ValueError(
                f"duplicate serialized validation receipt for candidate "
                f"{receipt.candidate_digest!r}"
            )
        indexed[receipt.candidate_digest] = (receipt, computed_digest)
    return indexed


def _validate_candidate_acceptance(
    ac: AbstractClass, validated_receipts: dict[str, tuple[Any, str]]
) -> None:
    if not (ac.candidateDigest and ac.validationReceiptDigest):
        raise ValueError(
            f"candidate {ac.name!r} cannot become ACCEPTED without a serialized validation receipt"
        )
    bound = validated_receipts.get(ac.candidateDigest)
    if bound is None:
        raise ValueError(f"candidate {ac.name!r} has no matching serialized validation receipt")
    receipt, computed_digest = bound
    if not receipt.accepted:
        raise ValueError(f"candidate {ac.name!r} validation receipt did not earn acceptance")
    if receipt.candidate_digest != ac.candidateDigest:
        raise ValueError(f"candidate {ac.name!r} validation receipt is bound to another candidate")
    if receipt.cycle_id != ac.cycleId:
        raise ValueError(f"candidate {ac.name!r} validation receipt cycle does not match")
    if ac.validationReceiptDigest != computed_digest:
        raise ValueError(f"candidate {ac.name!r} validation receipt digest does not match")


def _validate_acceptance_batch(
    persistable_acs: list[AbstractClass],
    creative_receipts: list[dict[str, Any]] | None,
) -> None:
    validated_receipts = _index_validation_receipts(creative_receipts)
    for ac in persistable_acs:
        _validate_candidate_acceptance(ac, validated_receipts)


def _persist_params(ac: AbstractClass, *, accept: bool) -> dict[str, Any]:
    return {
        "name": ac.name,
        "verdictStatus": "ACCEPTED" if accept else "VERDICT_PENDING",
        "status": ac.status.value,
        "summary": ac.summary,
        "createdAt": ac.createdAt.isoformat(),
        "inductionMethod": ac.inductionMethod,
        "cycleId": ac.cycleId,
        "extent": ac.extent or [],
        "intent": ac.intent or [],
        "stabilityScore": ac.stabilityScore,
        "semanticName": ac.semanticName,
        "mechanism": ac.mechanism,
        "scope": ac.scope,
        "falsifier": ac.falsifier,
        "candidateDigest": ac.candidateDigest,
        "validationReceiptDigest": ac.validationReceiptDigest,
        "noveltyScore": ac.noveltyScore,
    }


def stage_6_persist(
    gated_acs: list[AbstractClass],
    persist_cypher: CypherRunner,
    *,
    accept: bool,
    require_acceptance_receipt: bool = False,
    creative_receipts: list[dict[str, Any]] | None = None,
) -> int:
    # KG: eureka-canonical-2026-05-26
    """Persist gated AbstractClass nodes to the KG so hades can fetch + realize them.

    Closes the dead producer→consumer seam: hades reads `verdictStatus='ACCEPTED'` but
    eureka never wrote it. The PROPOSED→ACCEPTED transition is GATED on an explicit
    ``accept`` signal — a VERDICT_PENDING concept is written ACCEPTED only when the
    operator/oracle accepts the in-pipeline gate chain; otherwise it persists as
    VERDICT_PENDING (visible, not yet realizable). REJECTED concepts are never persisted
    as realizable. Returns the number of nodes written. (W1-I)
    """
    # Retain the flag in the call contract for compatibility. ACCEPTED is always
    # receipt-gated, independent of its historical value.
    _ = require_acceptance_receipt
    persistable_acs = [ac for ac in gated_acs if ac.status is not AbstractClassStatus.REJECTED]
    if accept:
        _validate_acceptance_batch(persistable_acs, creative_receipts)
    for ac in persistable_acs:
        persist_cypher(_PERSIST_AC_CYPHER, _persist_params(ac, accept=accept))
    return len(persistable_acs)


def _try_run_stage(stage: Stage, context: dict[str, Any], record_to: PipelineRun) -> bool:
    """Run an injectable stage. Returns True if it ran successfully, False if
    explicitly NotImplemented (recorded but not fatal)."""
    try:
        result = stage.run(context)
        record_to.record(result.stage, result.ok, payload=result.payload, error=result.error)
        # 성공 + dict payload면 context에 merge → 다음 stage가 산출을 본다 (GraphRAG 체인).
        if result.ok and isinstance(result.payload, dict):
            context.update(result.payload)
        return result.ok
    except NotImplementedStageError as e:
        record_to.record(stage.name, False, error=str(e), payload={"not_implemented": True})
        return False


def _apply_quality_gate(
    abstract_classes: list[AbstractClass], record_to: PipelineRun
) -> list[AbstractClass] | None:
    if not abstract_classes:
        return abstract_classes
    floor = quality_gate_module.FCA_STABILITY_MIN
    survivors = [ac for ac in abstract_classes if (ac.stabilityScore or 0.0) >= floor]
    record_to.record(
        "4.5-quality-gate",
        bool(survivors),
        payload={
            "survived": len(survivors),
            "pruned_below_floor": len(abstract_classes) - len(survivors),
        },
        error=(
            None
            if survivors
            else f"all {len(abstract_classes)} concept(s) below fca_stability floor {floor}"
        ),
    )
    return survivors or None


def _acceptance_fidelity_ready(config: PipelineConfig, record_to: PipelineRun) -> bool:
    if not (config.persist_accept and config.require_acceptance_receipt):
        return True
    fidelity_stage = record_to.stages[-1]
    payload = fidelity_stage.payload if isinstance(fidelity_stage.payload, dict) else {}
    skipped = bool(payload.get("skipped"))
    soft_warns = int(payload.get("soft_warns", 0) or 0)
    ready = not skipped and soft_warns == 0
    record_to.record(
        "4.8b-acceptance-fidelity-hard-gate",
        ready,
        payload={"skipped": skipped, "soft_warns": soft_warns},
        error=(
            None
            if ready
            else "ACCEPTED requires measured held-out fidelity with zero soft warnings"
        ),
    )
    return ready


def _run_fidelity_stages(
    abstract_classes: list[AbstractClass], config: PipelineConfig, record_to: PipelineRun
) -> bool:
    if not abstract_classes:
        return True
    stage_4_8_fidelity_gate(abstract_classes, config, record_to)
    return _acceptance_fidelity_ready(config, record_to)


def _capture_creative_artifacts(enriched: Any, record_to: PipelineRun) -> None:
    receipt_by_candidate = {receipt.candidate_digest: receipt for receipt in enriched.receipts}
    for creative_run in enriched.runs:
        for proposal in creative_run.accepted:
            candidate_digest = proposal.candidate_digest(creative_run.context)
            receipt = receipt_by_candidate[candidate_digest]
            record_to.creative_artifacts.append(
                {
                    "candidate_digest": candidate_digest,
                    "input_snapshot_hash": creative_run.context.input_snapshot_hash,
                    "baseline_snapshot_hash": creative_run.context.baseline_snapshot_hash,
                    "proposal": proposal.model_dump(mode="json"),
                    "receipt_digest": receipt.receipt_digest,
                    "source_layer": "SECONDARY_AI",
                }
            )


def _record_creative_enrichment(enriched: Any, record_to: PipelineRun) -> list[AbstractClass]:
    abstract_classes = list(enriched.abstract_classes)
    record_to.creative_receipts = [
        receipt.model_dump(mode="json") | {"receipt_digest": receipt.receipt_digest}
        for receipt in enriched.receipts
    ]
    _capture_creative_artifacts(enriched, record_to)
    record_to.record(
        "4.9-semantic-creative-loop",
        bool(abstract_classes),
        payload={
            "structural_candidates": len(enriched.runs),
            "proposed": len(abstract_classes),
            "receipts": len(enriched.receipts),
            "outcomes": [run.outcome.value for run in enriched.runs],
        },
        error=None if abstract_classes else "no semantic proposal survived falsification",
    )
    return abstract_classes


def _run_creative_stage(
    abstract_classes: list[AbstractClass],
    formal_context: dict[str, frozenset[str]],
    config: PipelineConfig,
    record_to: PipelineRun,
) -> tuple[list[AbstractClass], bool]:
    if not abstract_classes or config.creative_enricher is None:
        return abstract_classes, False
    try:
        enriched = config.creative_enricher.enrich(abstract_classes, formal_context)
        enriched_acs = _record_creative_enrichment(enriched, record_to)
    except Exception as error:  # noqa: BLE001 — model/adapter boundary, fail closed
        record_to.record("4.9-semantic-creative-loop", False, error=str(error))
        return [], True
    return enriched_acs, not enriched_acs


def _prepare_gated_acs(
    abstract_classes: list[AbstractClass],
    edges: list[GeneralizesEdge],
    record_to: PipelineRun,
) -> list[AbstractClass] | None:
    gated_acs = stage_5_naesengmoon_gate(abstract_classes)
    record_to.proposals = list(gated_acs)
    record_to.record("5-naesengmoon-gate", True, payload={"verdict_pending": len(gated_acs)})
    try:
        gate_before_merge(
            [ac.model_dump(mode="json") for ac in gated_acs],
            [edge.model_dump(mode="json") for edge in edges],
        )
    except Exception as error:
        record_to.record("5.5-pre-merge-validator", False, error=str(error))
        return None
    record_to.record("5.5-pre-merge-validator", True, payload={"validated": len(gated_acs)})
    return gated_acs


def _run_persist_stage(
    gated_acs: list[AbstractClass], config: PipelineConfig, record_to: PipelineRun
) -> None:
    if config.persist_cypher is None:
        return
    try:
        persisted = stage_6_persist(
            gated_acs,
            config.persist_cypher,
            accept=config.persist_accept,
            require_acceptance_receipt=config.require_acceptance_receipt,
            creative_receipts=record_to.creative_receipts,
        )
        record_to.record(
            "6-persist",
            True,
            payload={"persisted": persisted, "accepted": config.persist_accept},
        )
    except Exception as error:  # noqa: BLE001 — persist failure must not crash the pipeline
        record_to.record("6-persist", False, error=str(error))


def run(
    reference_sites: list[dict],
    formal_context: dict[str, frozenset[str]],
    config: PipelineConfig,
) -> PipelineRun:
    # KG: eureka-canonical-2026-05-26
    pr = PipelineRun(config=config)

    candidates = stage_1_extract(reference_sites)
    pr.record("1-extract", True, payload={"count": len(candidates)})

    ctx = {"candidates": candidates, "gamma_sweep": config.gamma_sweep}
    _try_run_stage(config.resolve_stage_community(), ctx, pr)
    _try_run_stage(config.resolve_stage_summarize(), ctx, pr)

    acs, edges, fca_result = stage_4_induce(formal_context, config.cycle_id, config)
    pr.record(
        f"4-induce-{config.method}",
        fca_result.fallback_reason is None,
        payload={"abstract_classes": len(acs), "edges": len(edges), "pruned": fca_result.pruned},
        error=fca_result.fallback_reason,
    )

    quality_survivors = _apply_quality_gate(acs, pr)
    if quality_survivors is None:
        return pr
    acs = quality_survivors

    # 4.7 나생문 oracle hard-gate (executable, KG 불변식). FAIL → 판단렌즈(stage_5) 진입 차단.
    if acs and not stage_4_7_oracle_gate(acs, config, pr):
        return pr

    # 4.8 fidelity gate (SOFT, consilience) — 경고만, block 안 함.
    if not _run_fidelity_stages(acs, config, pr):
        return pr

    # 4.9 semantic creative loop (optional).  Unlike old stage 3 summaries, this
    # output is threaded into the actual AbstractClass artifacts and persistence.
    acs, creative_halted = _run_creative_stage(acs, formal_context, config, pr)
    if creative_halted:
        return pr

    gated_acs = _prepare_gated_acs(acs, edges, pr)
    if gated_acs is None:
        return pr
    _run_persist_stage(gated_acs, config, pr)

    _try_run_stage(config.resolve_stage_hybrid_retrieval(), ctx, pr)
    _try_run_stage(config.resolve_stage_drift_loop(), ctx, pr)
    return pr


def run_from_kg(
    run_cypher: CypherRunner,
    config: PipelineConfig,
    fc_cfg: FormalContextConfig | None = None,
) -> PipelineRun:
    # KG: eureka-canonical-2026-05-26
    """stage_0 (KG-EXTRACT) → 전체 pipeline. formal_context_builder로 KG에서 context 빌드 후 run().

    Phase 1 wiring (2026-05-27): build_formal_context(3 pre-filter) → induce_fca.
    run_cypher 주입 (실전=Neo4j read, 테스트=fake). 실측 oracle: 321 obj/avg_intent 3.63 → 비자명 concept.
    """
    formal_context, meta = build_formal_context(run_cypher, fc_cfg)
    pr = run(reference_sites=[], formal_context=formal_context, config=config)
    pr.stages.insert(
        0,
        StageResult(
            stage="0-kg-extract-formal-context",
            ok=bool(formal_context),
            payload=meta,
            error=None
            if formal_context
            else "formal context empty: 0 objects with facet intents extracted "
            "(KG has no usable concept nodes — expected on the minimal local bundle)",
        ),
    )
    return pr


def main() -> None:
    # KG: eureka-canonical-2026-05-26
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
    "run_from_kg",
    "stage_1_extract",
    "stage_4_7_oracle_gate",
    "stage_4_8_fidelity_gate",
    "stage_4_induce",
    "stage_4_induce_fca",
    "stage_5_naesengmoon_gate",
]
