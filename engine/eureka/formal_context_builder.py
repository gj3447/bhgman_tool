"""KG → FCA formal context 빌더 (유레카 Phase 0, stage_0 KG-EXTRACT).

하드진실 #1 실측 확증(eureka-formal-context-smoketest-2026-05-27): 알고리즘이 아니라
*입력 context 구성*이 레버리지. naive FCA = garbage(상관 facet tautology + mega-hub
오염 + bulk 노이즈). 3 pre-filter가 garbage↔signal을 가른다:

  ① bulk-exclude   : KG_AI/Comment/OCCAM_SLICED/ARCHIVED 등 노이즈 label 제외
  ② hub degree-cap : facet 차수 > cap 인 mega-hub 제외 (전 concept 오염원)
  ③ independent facets : 상관 동의어-묶음(evidence/normativity/artifact) 금지,
                         직교 facet만(예: ALIGNS_WITH_AXIS × USES_ABSTRACT_DOMAIN)

출력 = dict[object_name, frozenset[attribute]] — induce_fca() 입력 계약 그대로.
attribute = "facet:value" (facet 구분 유지).

# KG: eureka-formal-context-smoketest-2026-05-27 (3 pre-filter 실측 근거),
#     consensus-eureka-design-synthesis-2026-05-27 (FC3/FC4), eureka-canonical-2026-05-26
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass

# cypher runner: (query, params) -> list of row dicts. 주입식 (테스트=fake, 실전=Neo4j).
CypherRunner = Callable[[str, dict], "list[dict]"]

# 실측 확인된 기본 노이즈 label (eureka-formal-context-smoketest 2026-05-27)
DEFAULT_BULK_LABELS: frozenset[str] = frozenset({"KG_AI", "Comment", "OCCAM_SLICED", "ARCHIVED"})
# 실측 viable 한 첫 독립 facet 쌍
DEFAULT_FACET_RELS: tuple[str, ...] = ("ALIGNS_WITH_AXIS", "USES_ABSTRACT_DOMAIN")


@dataclass(frozen=True)
class FormalContextConfig:
    # KG: eureka-canonical-2026-05-26
    """formal context 구성 정책. 매직넘버 아님 — 실측 근거 default."""

    facet_rels: tuple[str, ...] = DEFAULT_FACET_RELS  # ③ 독립 facet
    bulk_labels: frozenset[str] = DEFAULT_BULK_LABELS  # ① 제외 label
    hub_degree_cap: int = 4  # ② hub 차수 상한
    min_facets_per_object: int = 2  # object가 ≥N facet 가져야 (1-facet=trivial)


def build_extraction_cypher(cfg: FormalContextConfig) -> tuple[str, dict]:
    # KG: eureka-canonical-2026-05-26
    """3 pre-filter 박힌 추출 cypher + params. (query, params) 반환."""
    query = """
    MATCH (o)-[r]->(v)
    WHERE type(r) IN $facet_rels
      AND v.name IS NOT NULL
      AND NONE(l IN labels(o) WHERE l IN $bulk_labels)
    WITH o, count(DISTINCT v) AS facet_deg,
         collect(DISTINCT type(r) + ':' + v.name) AS attrs
    WHERE facet_deg <= $hub_cap AND size(attrs) >= $min_facets
    RETURN o.name AS object, attrs AS attributes
    """
    params = {
        "facet_rels": list(cfg.facet_rels),
        "bulk_labels": list(cfg.bulk_labels),
        "hub_cap": cfg.hub_degree_cap,
        "min_facets": cfg.min_facets_per_object,
    }
    return query, params


def assemble_context(rows: Iterable[dict]) -> dict[str, frozenset[str]]:
    # KG: eureka-canonical-2026-05-26
    """cypher rows({object, attributes}) → formal context dict. 순수 함수(테스트 용이)."""
    ctx: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        obj = row.get("object")
        if obj is None:
            continue
        for attr in row.get("attributes") or []:
            ctx[obj].add(attr)
    return {o: frozenset(a) for o, a in ctx.items() if a}


def build_formal_context(
    run_cypher: CypherRunner, cfg: FormalContextConfig | None = None
) -> tuple[dict[str, frozenset[str]], dict]:
    # KG: eureka-canonical-2026-05-26
    """KG에서 formal context 추출 (stage_0). 반환: (context, metadata).

    run_cypher 주입: 실전=Neo4j read, 테스트=fake rows.
    """
    cfg = cfg or FormalContextConfig()
    query, params = build_extraction_cypher(cfg)
    rows = run_cypher(query, params)
    ctx = assemble_context(rows)
    intents = [len(v) for v in ctx.values()]
    meta = {
        "objects": len(ctx),
        "avg_intent": round(sum(intents) / len(intents), 2) if intents else 0.0,
        "facet_rels": list(cfg.facet_rels),
        "bulk_excluded": sorted(cfg.bulk_labels),
        "hub_cap": cfg.hub_degree_cap,
    }
    return ctx, meta


__all__ = [
    "DEFAULT_BULK_LABELS",
    "DEFAULT_FACET_RELS",
    "CypherRunner",
    "FormalContextConfig",
    "assemble_context",
    "build_extraction_cypher",
    "build_formal_context",
]
