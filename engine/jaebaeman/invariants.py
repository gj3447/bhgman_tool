"""재배맨 씨앗 불변식 게이트 (PROM 16 P1) — plant_seeds() 전 fail-closed 검증.

v1은 FK/depth/중복 불변식을 *선언*만 하고 코드 검증이 없었다. 이 모듈이 그 게이트:
배치를 KG에 심기 *전에* 위반을 모아 surface(또는 apply 차단). bench가 잡은 orphan/depth/중복을
회귀로 못박는 자리.

검증 (occam.kg_adapter covenant과 동형 — read-only, 파괴 토큰 없음):
  로컬(run_cypher 불필요): E4 depth-range / DUP_SEED_NAME / E3 batch-내 anchor 중복 / DANGLING_PARENT
  KG(run_cypher 있으면): E1 외부 anchor가 KG에 실존하나 (FK orphan)

정직: run_cypher 없거나 local backend가 미지원이면 KG 체크는 *조용히 skip*하지 않고 로컬만 돌린
사실을 호출자가 안다(violations에 E1 부재 = "KG 미검증"). occam/eureka처럼 결정론 코어 floor.

# KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01 (C4 다층 게이트),
#     finding-jbm-eng-C4 (validate_seed_invariants 게이트), span-gap3-jaebaeman-seed-fk-2026-05-14
"""

from __future__ import annotations

from collections.abc import Callable

from engine.jaebaeman.jaebaeman_models import (
    MAX_DEPTH,
    SeedRecord,
    SeedViolation,
    ViolationCode,
)

CypherRunner = Callable[[str, dict], "list[dict]"]

# 외부 anchor 실존 확인 (read-only). UNWIND → 없는 것만 collect. covenant: MATCH/RETURN만.
_ORPHAN_ANCHOR_CYPHER = (
    "UNWIND $anchors AS a "
    "OPTIONAL MATCH (n {name: a}) "
    "WITH a, n WHERE n IS NULL "
    "RETURN collect(a) AS missing"
)


def _is_external_anchor(seed: SeedRecord) -> bool:
    """source_id가 자기 seed name과 다르면 외부 anchor(FK 대상). 같으면 self-anchored root."""
    return seed.source_id != seed.name


def _check_dup_names(seeds: list[SeedRecord]) -> list[SeedViolation]:
    seen: set[str] = set()
    out: list[SeedViolation] = []
    for s in seeds:
        if s.name in seen:
            out.append(
                SeedViolation(
                    ViolationCode.DUP_SEED_NAME, s.name, "배치 내 씨앗 name 중복 (PK 충돌)"
                )
            )
        seen.add(s.name)
    return out


def _check_depth(seeds: list[SeedRecord], max_depth: int) -> list[SeedViolation]:
    return [
        SeedViolation(ViolationCode.E4_DEPTH_RANGE, s.name, f"depth={s.depth} ∉ [0,{max_depth}]")
        for s in seeds
        if s.depth is None or not (0 <= s.depth <= max_depth)
    ]


def _check_dangling_parent(seeds: list[SeedRecord]) -> list[SeedViolation]:
    nameset = {s.name for s in seeds}
    return [
        SeedViolation(ViolationCode.DANGLING_PARENT, s.name, f"parent '{s.parent}'가 배치에 없음")
        for s in seeds
        if s.parent is not None and s.parent not in nameset
    ]


def _check_multiple_anchor(seeds: list[SeedRecord]) -> list[SeedViolation]:
    owners: dict[str, list[str]] = {}
    for s in seeds:
        if _is_external_anchor(s):
            owners.setdefault(s.source_id, []).append(s.name)
    return [
        SeedViolation(
            ViolationCode.E3_MULTIPLE_SEED_PER_ANCHOR,
            name,
            f"anchor '{anchor}'를 {len(names)}개 씨앗이 점유: {names}",
        )
        for anchor, names in owners.items()
        if len(names) > 1
        for name in names
    ]


def _check_orphan_anchor(seeds: list[SeedRecord], run_cypher: CypherRunner) -> list[SeedViolation]:
    ext = sorted({s.source_id for s in seeds if _is_external_anchor(s)})
    if not ext:
        return []
    rows = run_cypher(_ORPHAN_ANCHOR_CYPHER, {"anchors": ext})
    missing = set(rows[0]["missing"]) if rows and rows[0].get("missing") else set()
    return [
        SeedViolation(
            ViolationCode.E1_ORPHAN_ANCHOR,
            s.name,
            f"anchor '{s.source_id}'가 KG에 없음 (FK orphan)",
        )
        for s in seeds
        if _is_external_anchor(s) and s.source_id in missing
    ]


def validate_seed_invariants(
    seeds: list[SeedRecord],
    run_cypher: CypherRunner | None = None,
    *,
    max_depth: int = MAX_DEPTH,
) -> list[SeedViolation]:
    """씨앗 배치의 불변식 위반 리스트. 빈 리스트 = 통과. plant_seeds() 전 게이트.

    로컬 4종(dup/depth/dangling/E3) 항상 + E1(orphan anchor)은 run_cypher 있을 때만.
    """
    violations: list[SeedViolation] = []
    violations += _check_dup_names(seeds)
    violations += _check_depth(seeds, max_depth)
    violations += _check_dangling_parent(seeds)
    violations += _check_multiple_anchor(seeds)
    if run_cypher is not None:
        violations += _check_orphan_anchor(seeds, run_cypher)
    return violations


__all__ = ["CypherRunner", "validate_seed_invariants"]
