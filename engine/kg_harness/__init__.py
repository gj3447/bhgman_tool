"""kg_harness — KG write 출혈-차단 하네스 (ingest-time 강제).

occam(engine/occam)이 *cleanup-time* archive라면, 여기는 *ingest-time* 예방.
오염이 들어오기 전에 3대 불변식을 강제한다:

  INV1 (anti-dup)        : 도메인 노드는 stable-id로 MERGE — naked CREATE 금지.
  INV2 (anti-god-object) : update-in-place — `_vN` 버전드 필드 누적 금지.
  INV3 (anti-orphan)     : supersede(tombstone)는 SUPERSEDED_BY 엣지 필수 —
                           '교체본 추적 불가' 묘비 금지(2026-06-26 실측: 0.4%만 엣지 보유).

순수 함수 + 주입식 CypherRunner (occam/eureka/hades sibling 패턴). 인프라 0.

# KG: occam-pass-metahumotonic-20260626, occam-kam-canonical-2026-05-26
"""

from __future__ import annotations

from engine.kg_harness.write_guard import (
    ALLOW_CREATE_MARKER,
    CypherRunner,
    GuardReport,
    Severity,
    Violation,
    WriteGuardError,
    constraint_cypher,
    guarded_run,
    supersede_node,
    upsert_node,
    validate_write,
)

__all__ = [
    "ALLOW_CREATE_MARKER",
    "CypherRunner",
    "GuardReport",
    "Severity",
    "Violation",
    "WriteGuardError",
    "constraint_cypher",
    "guarded_run",
    "supersede_node",
    "upsert_node",
    "validate_write",
]
