"""오캄 fsck — 아카이브 무결성 불변식 검사 (archive integrity invariants).

PROM 6 C8 (rf-occam-adv-A3): 모든 `:ARCHIVED` SourceCodeNode 는 **정확히 1개**의
`:SUPERSEDED_BY` → non-archived 타겟을 가져야 한다.
  - 0개 = **DANGLING** 무덤: 가리킬 대상 없는 superseded 노드 (un-traceable deprecation).
  - >1개 = **AMBIGUOUS**: 생존자(current) 다수 → 어느 게 정본인지 불명.
둘 다 불변식 위반. read-only 검사 — 위반을 리포트할 뿐 수정하지 않는다(수정은 occam
supersede 경로). 순수 Cypher + 주입식 CypherRunner (kg_adapter 와 동일 IO 경계).

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A3-2026-07-19,
#     occam-kam-canonical-2026-05-26
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

CypherRunner = Callable[[str, "dict"], "list[dict]"]

# 모든 :ARCHIVED 노드의 live(비아카이브) SUPERSEDED_BY 타겟 수 집계 → 1이 아닌 것만.
_ARCHIVE_INTEGRITY_CYPHER = (
    "MATCH (a:SourceCodeNode:ARCHIVED) "
    "OPTIONAL MATCH (a)-[:SUPERSEDED_BY]->(t) WHERE NOT t:ARCHIVED "
    "WITH a, count(t) AS live_targets "
    "WHERE live_targets <> 1 "
    "RETURN a.name AS name, a.sourcePath AS source_path, live_targets AS live_targets "
    "ORDER BY live_targets, name"
)


@dataclass(frozen=True)
class IntegrityViolation:
    """무덤 하나의 불변식 위반. kind = 'DANGLING'(0 타겟) | 'AMBIGUOUS'(>1 타겟)."""

    name: str | None
    source_path: str | None
    live_targets: int
    kind: str


def check_archive_integrity(run_cypher: CypherRunner) -> list[IntegrityViolation]:
    """모든 `:ARCHIVED` 노드가 정확히 1개의 live `:SUPERSEDED_BY` 타겟을 갖는지 검사.

    위반 목록 반환 (빈 리스트 = 무결). read-only — 절대 write 안 함.
    """
    rows = run_cypher(_ARCHIVE_INTEGRITY_CYPHER, {})
    out: list[IntegrityViolation] = []
    for r in rows:
        n = int(r.get("live_targets") or 0)
        out.append(
            IntegrityViolation(
                name=r.get("name"),
                source_path=r.get("source_path"),
                live_targets=n,
                kind="DANGLING" if n == 0 else "AMBIGUOUS",
            )
        )
    return out


__all__ = ["IntegrityViolation", "check_archive_integrity"]
