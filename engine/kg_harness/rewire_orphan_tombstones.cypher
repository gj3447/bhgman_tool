// orphan-tombstone 추적가능화 — bolt 운영자 실행. 삭제 0, 가역.
// 1) 임시 인덱스 (없으면 풀스캔 타임아웃)
CREATE INDEX kgh_superseded_name IF NOT EXISTS FOR (n:Superseded) ON (n.name);

// 2) 단일 live 동명twin(라벨공유) → 누락 SUPERSEDED_BY backfill (서버사이드 배치)
CALL apoc.periodic.iterate(
  'MATCH (s:Superseded) WHERE NOT (s)-[:SUPERSEDED_BY]->() AND s.name IS NOT NULL RETURN s',
  'MATCH (t) WHERE t.name = s.name AND NOT t:Superseded AND elementId(t) <> elementId(s)
     AND any(l IN labels(t) WHERE l IN labels(s) AND NOT l IN ["_Node", "Superseded", "_AuraImport"])
   WITH s, collect(DISTINCT t) AS twins WHERE size(twins) = 1
   MERGE (s)-[r:SUPERSEDED_BY]->(twins[0]) SET r.backfilled = true, r.by = "kgh-rewire-20260626"',
  {batchSize: 500, parallel: false}
) YIELD batches, total, errorMessages
RETURN batches, total, errorMessages;

// 3) 남은 orphan(twin 모호/부재)은 flag만 — 사람/Longinus 판단.
//    MATCH (s:Superseded) WHERE NOT (s)-[:SUPERSEDED_BY]->() RETURN count(s);
// 되돌리기: MATCH ()-[r:SUPERSEDED_BY {by:"kgh-rewire-20260626"}]->() DELETE r;
