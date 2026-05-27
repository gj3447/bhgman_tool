"""semantic-fidelity gate (유레카 Phase 2, stage_4.7 — task-effect only).

설계 코어(consensus-eureka-design-synthesis SF1-4) + 나생문 교정:
- quality(4.5)=압축·안정성 / oracle(4.6)=불변식 / **fidelity(4.7)=downstream 효용**.
- 모든 proxy=Goodhart(SF3) → 단일 metric 금지, ensemble k≥2 witness.
- **SOFT verdict**: FAIL=SOFT_WARN→판단렌즈(stage_5) escalate, hard reject 아님.

**측정 = Whewell consilience (cheap·runnable, oracle-grounded, NOT formal cathedral)**:
추상은 *형성에 안 쓴* 관계(witness, facet_rels 제외)로도 cohere해야 진짜.
per-witness top_share = (한 target 공유 최대 멤버수)/extent. ≥min_top_share면 그 witness PASS.
ensemble: PASS witness ≥ k 면 fidelity PASS. (facet으로만 정의된 thin/tautological 추상은
witness로 흩어져 SOFT_WARN — concept1 tautological이 잡힌 것의 downstream 짝.)

# KG: consensus-eureka-design-synthesis-2026-05-27 (SF1-4), formal-cathedral-detection-2026-05-27,
#     eureka-formal-context-smoketest-2026-05-27
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

CypherRunner = Callable[[str, dict], "list[dict]"]

# witness = 형성(facet)에 안 쓴 held-out 관계 (consilience 신호)
DEFAULT_WITNESS_RELS: tuple[str, ...] = (
    "IN_CATEGORY",
    "RELATED_TO",
    "SAME_TRADITION",
    "ABOUT",
    "CLASSIFIED_AS",
    "CONTAINS",
)


@dataclass(frozen=True)
class FidelityConfig:
    witness_rels: tuple[str, ...] = DEFAULT_WITNESS_RELS
    min_top_share: float = 0.30  # per-witness coherence 임계
    min_witnesses_passing: int = 2  # ensemble k (≥2 독립 신호 cohere = Whewell)


@dataclass(frozen=True)
class FidelityVerdict:
    concept: str
    extent: int
    witness_top_share: dict[str, float]
    witnesses_passing: int
    passed: bool  # SOFT: True=PASS / False=SOFT_WARN(→judgment escalate, hard reject 아님)
    detail: str


def fidelity_witness_cypher(concept_name: str, cfg: FidelityConfig) -> tuple[str, dict]:
    """concept의 INSTANCE_OF 멤버에 대해 witness별 top_share 계산 cypher."""
    query = """
    MATCH (ca {name:$concept})<-[:INSTANCE_OF]-(o)
    WITH count(DISTINCT o) AS extent
    UNWIND $witness_rels AS wrel
    CALL {
      WITH wrel
      MATCH (ca {name:$concept})<-[:INSTANCE_OF]-(o)-[r]->(t)
      WHERE type(r)=wrel AND t.name IS NOT NULL
      WITH t.name AS target, count(DISTINCT o) AS shared
      RETURN max(shared) AS top_shared
    }
    RETURN wrel AS witness, coalesce(top_shared,0) AS top_shared, extent
    """
    return query, {"concept": concept_name, "witness_rels": list(cfg.witness_rels)}


def fidelity_members_cypher(member_names: list[str], cfg: FidelityConfig) -> tuple[str, dict]:
    """pre-materialize 모드: extent 멤버명 직접 받아 witness top_share 계산 (INSTANCE_OF 불필요).

    pipeline stage용 — induce_fca 직후 ac.extent(멤버명)로 fidelity 측정.
    """
    query = """
    UNWIND $witness_rels AS wrel
    CALL {
      WITH wrel
      MATCH (o)-[r]->(t)
      WHERE o.name IN $members AND type(r)=wrel AND t.name IS NOT NULL
      WITH t.name AS target, count(DISTINCT o) AS shared
      RETURN max(shared) AS top_shared
    }
    RETURN wrel AS witness, coalesce(top_shared,0) AS top_shared, $extent AS extent
    """
    return query, {
        "members": list(member_names),
        "witness_rels": list(cfg.witness_rels),
        "extent": len(member_names),
    }


def assess_fidelity(
    concept: str, rows: list[dict], cfg: FidelityConfig | None = None
) -> FidelityVerdict:
    """witness rows({witness, top_shared, extent}) → FidelityVerdict. 순수 함수."""
    cfg = cfg or FidelityConfig()
    extent = max((r.get("extent") or 0 for r in rows), default=0)
    shares: dict[str, float] = {}
    for r in rows:
        w = r.get("witness")
        ts = (r.get("top_shared") or 0) / extent if extent else 0.0
        if w is not None:
            shares[w] = round(ts, 3)
    passing = sum(1 for s in shares.values() if s >= cfg.min_top_share)
    passed = passing >= cfg.min_witnesses_passing
    detail = (
        f"witnesses_passing={passing}/{cfg.min_witnesses_passing} "
        f"(top_share≥{cfg.min_top_share}); {'PASS' if passed else 'SOFT_WARN→judgment'}"
    )
    return FidelityVerdict(
        concept=concept,
        extent=extent,
        witness_top_share=shares,
        witnesses_passing=passing,
        passed=passed,
        detail=detail,
    )


def run_fidelity_gate(
    concept_name: str, run_cypher: CypherRunner, cfg: FidelityConfig | None = None
) -> FidelityVerdict:
    """concept의 fidelity 측정 (stage_4.7). run_cypher 주입(실전=Neo4j, 테스트=fake)."""
    cfg = cfg or FidelityConfig()
    query, params = fidelity_witness_cypher(concept_name, cfg)
    rows = run_cypher(query, params)
    return assess_fidelity(concept_name, rows, cfg)


def run_fidelity_for_members(
    concept: str,
    member_names: list[str],
    run_cypher: CypherRunner,
    cfg: FidelityConfig | None = None,
) -> FidelityVerdict:
    """pre-materialize fidelity (pipeline stage용) — 멤버명으로 측정."""
    cfg = cfg or FidelityConfig()
    if not member_names:
        return FidelityVerdict(concept, 0, {}, 0, False, "empty extent")
    query, params = fidelity_members_cypher(member_names, cfg)
    return assess_fidelity(concept, run_cypher(query, params), cfg)


__all__ = [
    "DEFAULT_WITNESS_RELS",
    "CypherRunner",
    "FidelityConfig",
    "FidelityVerdict",
    "assess_fidelity",
    "fidelity_members_cypher",
    "fidelity_witness_cypher",
    "run_fidelity_for_members",
    "run_fidelity_gate",
]
