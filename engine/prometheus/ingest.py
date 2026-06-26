"""ingest — Finding → :ResearchFinding MERGE (PROPOSE/dry-run 기본).

covenant: write_cypher 없거나 apply=False면 planned cypher만 반환 (eureka/하데스/오캄과 동일
archive-only 안전). findingId 키로 idempotent MERGE → 재실행 안전.

# KG: project-legion-unification-kg-engine-2026-06-01
"""

from __future__ import annotations

from collections.abc import Callable

from engine.prometheus.models import Finding

CypherRunner = Callable[[str, dict], list[dict]]

# 정전 필드명 정렬 (provexport _ATTR_MAP / FullFindingRecord).
_MERGE = (
    "MERGE (f:ResearchFinding {findingId:$findingId}) "
    "SET f.oneLineSummary=$claim, f.citation_url=$citation_url, "
    "f.contentSha256=$sha, f.cycleId=$cycle_id, f.sourceKgBinding=$gap_id, "
    "f.researchedAt=$researched_at"
)


def plan_cypher(f: Finding) -> tuple[str, dict]:
    # KG: ATOM_Skill_prometheus
    return _MERGE, {
        "findingId": f.finding_id,
        "claim": f.claim,
        "citation_url": f.citation_url,
        "sha": f.content_sha256,
        "cycle_id": f.cycle_id,
        "gap_id": f.gap_id,
        "researched_at": f.researched_at,
    }


def ingest_findings(
    findings: tuple[Finding, ...],
    *,
    write_cypher: CypherRunner | None = None,
    apply: bool = False,
) -> tuple[int, tuple[str, ...]]:
    # KG: ATOM_Skill_prometheus
    """(written_count, planned_cyphers). apply+write_cypher 일 때만 실제 write.

    findingId(=sha256(gap|url|claim))로 dedup — 같은 키 Finding은 동일 :ResearchFinding 노드
    (idempotent MERGE)이므로 written/planned 는 *구별 노드 수*를 센다(쓰기-호출 수 아님). 중복
    claim이 ingested 카운트를 부풀려 legion research_finding_count 임계를 거짓 통과시키는 구멍 차단.
    """
    planned: list[str] = []
    written = 0
    seen: set[str] = set()
    do_write = apply and write_cypher is not None
    for f in findings:
        if f.finding_id in seen:
            continue  # 동일 findingId = 같은 노드의 재출현 → 한 번만 센다(재실행 안전)
        seen.add(f.finding_id)
        cypher, params = plan_cypher(f)
        planned.append(cypher)
        if do_write:
            try:
                write_cypher(cypher, params)  # type: ignore[misc]
                written += 1
            except Exception:  # noqa: BLE001 — 백엔드 미지원 시 PROPOSE로 degrade
                pass
    return written, tuple(planned)


__all__ = ["ingest_findings", "plan_cypher"]
