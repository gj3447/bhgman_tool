"""재배맨 KG 어댑터 — read(분해 anchor의 자식) + write(씨앗 MERGE + 계획 엣지).

순수 cypher 빌더 + 주입식 CypherRunner. planner.py(순수 재귀)와 분리: 여기는 IO 경계.
occam.kg_adapter와 동형 covenant:

  - write cypher에 DELETE/DETACH/REMOVE 토큰 부재 → assert로 차단 (씨앗은 *심기만*, 뽑지 않음).
  - 씨앗 = MERGE (멱등 upsert). 같은 계획 재실행 시 중복 씨앗 안 생김.
  - depth = coalesce($depth, 0) 강제 (SKILL.md v2.4 §p3 t_depth_not_null trigger — NULL이면 rollback).
  - dry_run 기본: write_cypher 있어도 dry_run=True면 실행 안 함.

KG 구조:
  (anchor)-[:HAS_SEED {wave_index,status,cycle_id}]->(:SubagentTaskSpec)   -- 발아 원천 ↔ 씨앗
  (parent_seed)-[:DECOMPOSES_TO]->(child_seed)                             -- 계획에 대한 계획(트리)

# KG: 재배맨-v2-subagent-runtime-protocol, span-gap3-jaebaeman-seed-fk-2026-05-14,
#     lesson-jaebaeman-depth-invariant-2026-05-14, jaebaeman-planfirst-essence-reframe-2026-05-27
"""

from __future__ import annotations

from collections.abc import Callable

from engine.jaebaeman.jaebaeman_models import Goal, SeedApplyResult, SeedRecord

CypherRunner = Callable[[str, dict], "list[dict]"]

# covenant: 재배맨은 씨앗을 *심기*만 — 이 토큰들이 write cypher에 있으면 위반.
FORBIDDEN_TOKENS = ("DELETE", "DETACH", "REMOVE")

# ── READ: 분해 anchor의 자식 (KG-anchored decomposition) ─────────────────────
# 한 anchor 노드 밑의 분해 구조(하위 Span/계획)를 읽어 하위 Goal로. 잎이면 빈 결과.
_CHILDREN_CYPHER = (
    "MATCH (p {name: $anchor})-[:DECOMPOSES_TO|HAS_CHILD|DEPENDS_ON]->(c) "
    "WHERE c.name IS NOT NULL "
    "RETURN c.name AS child, coalesce(c.objective, c.name) AS objective, "
    "coalesce(c.targetDomain, '') AS target_domain"
)


def children_cypher(anchor: str) -> tuple[str, dict]:
    return _CHILDREN_CYPHER, {"anchor": anchor}


def kg_decompose(run_cypher: CypherRunner, *, task_type: str = "research"):
    """KG 구조 기반 분해 규칙 — anchor 밑 자식들을 하위 Goal로. planner.DecomposeFn.

    node.anchor 없으면 분해 불가(잎). 자식의 name이 다음 단계 anchor가 되어 재귀가 이어진다.
    """

    def decompose(node):  # node: PlanNode
        if node.anchor is None:
            return []
        cypher, params = children_cypher(node.anchor)
        rows = run_cypher(cypher, params)
        return [
            Goal(
                name=r["child"],
                objective=r.get("objective") or r["child"],
                task_type=task_type,
                target_domain=r.get("target_domain") or "",
                anchor=r["child"],
            )
            for r in rows
            if r.get("child")
        ]

    return decompose


# ── READ-BACK: 심긴 READY 씨앗 → SeedRecord (씨앗→발아 핸드오프 입력) ──────────
# plant_seeds가 status='READY'로 심은 :SubagentTaskSpec를 다시 읽어 SeedRecord로 복원.
# 이것이 "발아"의 입력 — lifecycle.drive_seeds(agent_dispatcher)가 소비해 출격→동작.
# 감사 finding-jaebaeman-seed-dispatch-handoff-unwired-2026-06-07 해소 (read-back 부재 → 추가).
_READY_SEEDS_RETURN = (
    "OPTIONAL MATCH (p:SubagentTaskSpec)-[:DECOMPOSES_TO]->(s) "
    "WITH s, head(collect(p.name)) AS parent "  # dedupe: 다중 부모(DAG) 시 씨앗당 1행
    "RETURN s.name AS name, coalesce(s.skill, 'jaebaeman') AS skill, "
    "coalesce(s.sourceId, s.name) AS sourceId, coalesce(s.displayName, s.name) AS displayName, "
    "coalesce(s.taskType, 'research') AS taskType, coalesce(s.targetDomain, '') AS targetDomain, "
    "coalesce(s.expectedOutcome, '') AS expectedOutcome, "
    "coalesce(s.germinationMethod, 'manual') AS germinationMethod, "
    "coalesce(s.depth, 0) AS depth, parent "
    "ORDER BY s.depth, s.name"
)


def ready_seeds_cypher(limit: int | None = None, cycle_id: str | None = None) -> tuple[str, dict]:
    """READY 씨앗 read-back cypher + params. read-only (covenant 토큰 부재 — 검증 불필요).

    cycle_id 주면 그 cycle에 심긴 씨앗만(s.cycleId) — KG 전역 READY 씨앗 무차별 발아 footgun 방지.
    """
    where = "WHERE s.status = 'READY'"
    params: dict = {}
    if cycle_id is not None:
        where += " AND s.cycleId = $cycle_id"
        params["cycle_id"] = cycle_id
    cypher = f"MATCH (s:SubagentTaskSpec) {where} " + _READY_SEEDS_RETURN
    if limit is not None:
        cypher += " LIMIT $limit"
        params["limit"] = limit
    return cypher, params


def read_ready_seeds(
    run_cypher: CypherRunner, *, limit: int | None = None, cycle_id: str | None = None
) -> list[SeedRecord]:
    """심긴 READY :SubagentTaskSpec 씨앗을 KG에서 읽어 SeedRecord로 복원 (plant_seeds의 역).

    dispatch가 소비할 씨앗 read-back — 씨앗(KG)↔발아(dispatch) 사이 끊겨 있던 핸드오프.
    parent = DECOMPOSES_TO 부모(계획 트리 보존). cycle_id로 scope(전역 무차별 발아 방지). read-only.
    """
    cypher, params = ready_seeds_cypher(limit, cycle_id)
    rows = run_cypher(cypher, params)
    return [
        SeedRecord(
            name=r["name"],
            skill=r.get("skill") or "jaebaeman",
            source_id=r.get("sourceId") or r["name"],
            display_name=r.get("displayName") or r["name"],
            task_type=r.get("taskType") or "research",
            target_domain=r.get("targetDomain") or "",
            expected_outcome=r.get("expectedOutcome") or "",
            germination_method=r.get("germinationMethod") or "manual",
            depth=int(r.get("depth") or 0),
            parent=r.get("parent"),
        )
        for r in rows
        if r.get("name")
    ]


# ── WRITE (covenant: MERGE-only, depth NOT NULL) ─────────────────────────────
_SEED_MERGE = (
    "MERGE (s:SubagentTaskSpec {name: $name}) "
    "SET s.skill = $skill, "
    "s.sourceId = $sourceId, "
    "s.displayName = $displayName, "
    "s.taskType = $taskType, "
    "s.targetDomain = $targetDomain, "
    "s.expectedOutcome = $expectedOutcome, "
    "s.germinationMethod = $germinationMethod, "
    "s.depth = coalesce($depth, 0), "  # SKILL v2.4 §p3: NULL이면 t_depth_not_null rollback
    "s.cycleId = $cycle_id, "  # germinate scope key — read_ready_seeds가 이 cycle만 발아
    "s.status = 'READY', "
    "s.createdAt = datetime() "
    "RETURN s.name AS seeded"
)

_HAS_SEED_EDGE = (
    "MATCH (a {name: $anchor}) "
    "MATCH (s:SubagentTaskSpec {name: $seed}) "
    "MERGE (a)-[r:HAS_SEED]->(s) "
    "SET r.wave_index = $wave, r.status = 'READY', r.cycle_id = $cycle "
    "RETURN s.name AS linked"
)

_DECOMPOSES_TO_EDGE = (
    "MATCH (p:SubagentTaskSpec {name: $parent}) "
    "MATCH (c:SubagentTaskSpec {name: $child}) "
    "MERGE (p)-[:DECOMPOSES_TO]->(c) "
    "RETURN c.name AS child"
)


def _assert_covenant(cypher: str) -> None:
    up = cypher.upper()
    violations = [tok for tok in FORBIDDEN_TOKENS if tok in up]
    if violations:
        raise AssertionError(f"jaebaeman covenant violation: {violations} in seed-write cypher")


def build_seed_merge(seed: SeedRecord, cycle_id: str) -> tuple[str, dict]:
    """씨앗 MERGE cypher + params. covenant: 파괴적 토큰 부재를 assert로 강제."""
    _assert_covenant(_SEED_MERGE)
    params = {
        "name": seed.name,
        "skill": seed.skill,
        "sourceId": seed.source_id,
        "displayName": seed.display_name,
        "taskType": seed.task_type,
        "targetDomain": seed.target_domain,
        "expectedOutcome": seed.expected_outcome,
        "germinationMethod": seed.germination_method,
        "depth": seed.depth,
        "cycle_id": cycle_id,
    }
    return _SEED_MERGE, params


def build_has_seed_edge(seed: SeedRecord, wave: int, cycle_id: str) -> tuple[str, dict] | None:
    """anchor↔씨앗 HAS_SEED 엣지. self-anchored root(anchor==name)면 None (자기 자신엔 안 검)."""
    if seed.source_id == seed.name:
        return None
    _assert_covenant(_HAS_SEED_EDGE)
    return _HAS_SEED_EDGE, {
        "anchor": seed.source_id,
        "seed": seed.name,
        "wave": wave,
        "cycle": cycle_id,
    }


def build_decomposes_to_edge(seed: SeedRecord) -> tuple[str, dict] | None:
    """parent_seed→child_seed DECOMPOSES_TO (계획에 대한 계획 = 트리 구조 KG화). 루트면 None."""
    if seed.parent is None:
        return None
    _assert_covenant(_DECOMPOSES_TO_EDGE)
    return _DECOMPOSES_TO_EDGE, {"parent": seed.parent, "child": seed.name}


def plant_seeds(
    seeds: list[SeedRecord],
    write_cypher: CypherRunner | None = None,
    cycle_id: str = "jaebaeman-cli",
    dry_run: bool = True,
) -> SeedApplyResult:
    """씨앗 트리를 KG에 심는다. dry_run 기본 — write_cypher 있어도 실행 안 함 (planned만).

    순서: 씨앗 MERGE 전부 → HAS_SEED 엣지 → DECOMPOSES_TO 엣지 (엣지 전에 양끝 노드 존재 보장).
    """
    plans: list[tuple[str, dict]] = []
    for s in seeds:
        plans.append(build_seed_merge(s, cycle_id))
    for wave, s in enumerate(seeds):
        if (e := build_has_seed_edge(s, wave, cycle_id)) is not None:
            plans.append(e)
    for s in seeds:
        if (e := build_decomposes_to_edge(s)) is not None:
            plans.append(e)

    seed_names = tuple(s.name for s in seeds)
    if dry_run or write_cypher is None:
        return SeedApplyResult(
            seeded=seed_names,
            planned_cyphers=tuple(plans),
            dry_run=True,
            applied_count=0,
            notes=("dry-run: planned only, no write (covenant: 씨앗은 심기만, MERGE-only)",),
        )

    for cypher, params in plans:
        write_cypher(cypher, params)
    return SeedApplyResult(
        seeded=seed_names,
        planned_cyphers=tuple(plans),
        dry_run=False,
        applied_count=len(seeds),
        notes=(f"planted {len(seeds)} seed(s) + {len(plans) - len(seeds)} plan edge(s)",),
    )


__all__ = [
    "CypherRunner",
    "FORBIDDEN_TOKENS",
    "build_decomposes_to_edge",
    "build_has_seed_edge",
    "build_seed_merge",
    "children_cypher",
    "kg_decompose",
    "plant_seeds",
    "read_ready_seeds",
    "ready_seeds_cypher",
]
