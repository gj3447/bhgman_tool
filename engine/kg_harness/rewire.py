"""rewire — orphan-tombstone(SUPERSEDED_BY 없는 Superseded) 추적가능화 스크립트 생성.

2026-06-26 실측: Superseded 18,612 중 18,566(99.8%)이 교체본 추적엣지 없음 = 늪.
근본 처방은 두 갈래:
  (a) 미래 출혈 = write_guard(ORPHAN_TOMBSTONE ERROR)가 이미 차단.
  (b) 기존 18.6k = 여기 생성 스크립트로 *backfill*(단일 live 동명twin → SUPERSEDED_BY).

⚠️ MCP write 도구는 DDL(CREATE INDEX) 거부 + 덤프 노드 name 인덱스 부재 →
18k×300k 풀스캔이 클라이언트 타임아웃. 따라서 이 스크립트는 **bolt 접근 운영자**가
cypher-shell로 실행(임시 인덱스 + apoc.periodic.iterate 서버사이드 배치). 삭제 0, 가역
(backfill 엣지에 태그 → 되돌리기 가능).

# KG: occam-pass-metahumotonic-20260626
"""

from __future__ import annotations

# 동일 엔티티 판정에서 무시할 내부/임포트 라벨.
_IGNORE_LABELS = ("_Node", "Superseded", "_AuraImport")
_TAG = "kgh-rewire-20260626"


def rewire_script() -> str:
    """orphan-tombstone backfill cypher 스크립트(운영자용, bolt + apoc).

    단일 live 동명twin(라벨 1개 이상 공유)에만 SUPERSEDED_BY를 건다 — 모호한
    multi-twin/no-twin은 건드리지 않음(사람/Longinus 판단 대상).
    """
    ignore = ", ".join(f'"{l}"' for l in _IGNORE_LABELS)
    return f"""// orphan-tombstone 추적가능화 — bolt 운영자 실행. 삭제 0, 가역.
// 1) 임시 인덱스 (없으면 풀스캔 타임아웃)
CREATE INDEX kgh_superseded_name IF NOT EXISTS FOR (n:Superseded) ON (n.name);

// 2) 단일 live 동명twin(라벨공유) → 누락 SUPERSEDED_BY backfill (서버사이드 배치)
CALL apoc.periodic.iterate(
  'MATCH (s:Superseded) WHERE NOT (s)-[:SUPERSEDED_BY]->() AND s.name IS NOT NULL RETURN s',
  'MATCH (t) WHERE t.name = s.name AND NOT t:Superseded AND elementId(t) <> elementId(s)
     AND any(l IN labels(t) WHERE l IN labels(s) AND NOT l IN [{ignore}])
   WITH s, collect(DISTINCT t) AS twins WHERE size(twins) = 1
   MERGE (s)-[r:SUPERSEDED_BY]->(twins[0]) SET r.backfilled = true, r.by = "{_TAG}"',
  {{batchSize: 500, parallel: false}}
) YIELD batches, total, errorMessages
RETURN batches, total, errorMessages;

// 3) 남은 orphan(twin 모호/부재)은 flag만 — 사람/Longinus 판단.
//    MATCH (s:Superseded) WHERE NOT (s)-[:SUPERSEDED_BY]->() RETURN count(s);
// 되돌리기: MATCH ()-[r:SUPERSEDED_BY {{by:"{_TAG}"}}]->() DELETE r;
"""


__all__ = ["rewire_script"]
