"""stable-id 레지스트리 — 엔진이 MERGE하는 (label → id_key) 정전 규약.

이 매핑이 SSOT: upsert_node 호출도, DB-level constraint도 여기서 파생.
새 도메인 노드 타입을 MERGE로 쓰기 시작하면 여기 한 줄 추가 → constraint 번들이
자동 포함. (grep로 발굴: `MERGE (x:Label {key:` 사이트, 2026-06-26.)

NEEDS_DEDUP: 현재 KG에 같은 id 중복이 남아 constraint 설치가 *지금은* 실패하는 라벨.
occam dedup 선행 후 해제. (2026-06-26 실측 dup_groups 주석.)

# KG: occam-pass-metahumotonic-20260626
"""

from __future__ import annotations

from engine.kg_harness.write_guard import constraint_cypher

# label → 유일 식별 키 (엔진 MERGE 규약과 1:1). str=단일키, tuple=복합키.
#
# ⚠️ 2026-06-26 교정: `sourceId`는 유니크 키가 아니라 *컬렉션/코퍼스 grouping*이다
# (ReferenceSite 4989노드가 sourceId 1677종 — 한 canon 안 distinct 참조들이 sourceId 공유).
# ReferenceSite 진짜 identity = 복합 (sourceId, name). "595 dup groups"는 허위(grouping),
# 실제 dup은 복합키 50그룹(거의 zero-edge stub)뿐 → occam supersede 완료(occam-refsite-20260626).
STABLE_IDS: dict[str, str | tuple[str, ...]] = {
    "Apostle": "roman",
    "BreakGlassEntry": "auditId",
    "DispatchEvent": "source_commander",
    "DriftCheck": "name",
    "GateAuditEntry": "auditId",
    "HarnessDiagnosis": "name",
    "JaebaemanDispatchTelemetry": "name",
    "JaebaemanRun": "name",
    "KnowledgeHub": "name",
    "ReferenceSite": ("sourceId", "name"),  # 복합 NODE KEY (50 stub dedup 후 clean)
    "ReinductionTrigger": "name",
    "SourceCodeDriftEvent": "name",
    "ResearchFinding": "findingId",  # dead-island/orphan 청소로 0 dup → clean
    "SourceCodeNode": "sourcePath",  # ⚠️ UNCONSTRAINABLE (아래)
    "SubagentTaskSpec": ("sourceId", "name"),  # 명확우위 4 dedup, sourceId null로 복합 면제 → clean
}

# constraint 설치 전 dedup 필요한 라벨 (clean해지면 제거). 현재 전부 해소(졸업).
NEEDS_DEDUP: frozenset[str] = frozenset()

# ⚠️ 2026-06-26 발견: **archive식 dedup(SUPERSEDED_BY로 노드 보존)은 키를 풀지 못한다** —
# uniqueness constraint는 :Superseded 노드도 카운트하므로 live canonical과 키 충돌.
# 해법: dedup-archive 시 식별 키를 free(복합은 한 성분 null→면제, ReferenceSite sourceId 처리 완료).
# 단 SourceCodeNode는 occam 버전-아카이브가 같은 sourcePath를 *영구* 보유(파일 이력) →
# 단일키 sourcePath UNIQUE는 근본적으로 불가. constraint 후보에서 제외.
UNCONSTRAINABLE: frozenset[str] = frozenset({"SourceCodeNode"})


def constraint_bundle(*, include_pending: bool = False) -> list[str]:
    """stable-id 유니크 constraint DDL 번들.

    기본은 NEEDS_DEDUP(설치하면 실패) + UNCONSTRAINABLE(archive-model 충돌) 제외 —
    즉시 설치 가능한 것만. include_pending=True면 전체(주석/계획용).
    """
    skip = NEEDS_DEDUP | UNCONSTRAINABLE
    return [
        constraint_cypher(label, key)
        for label, key in sorted(STABLE_IDS.items())
        if include_pending or label not in skip
    ]


__all__ = ["NEEDS_DEDUP", "STABLE_IDS", "UNCONSTRAINABLE", "constraint_bundle"]
