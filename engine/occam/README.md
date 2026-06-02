# occam (오캄/캄) — 정리 군단장

KG 노드 dedup + supersession σ 스코어링. **삭제 안 함** — 낡은/대체된 노드를 active/log로 분리·아카이빙.

- `occam.py` / `occam_runner.py` — 본체 + 러너
- `scoring.py` — supersession σ (twin 있는 superseded만 처리)
- `semantic_dedup.py` — 의미 중복 탐지
- `oracle_lens.py` — confidence 낮으면 나생문 escalate
- `ontology.py` — 온톨로지 층 위생 (superseded OntologyClass 정리)
- `kg_adapter.py` — neo4j / `--local` JSON KG 어댑터

CLI: `bhgman-tool occam [--local]`. neo4j 없이 동작.

> 원칙: 마구잡이 금지, 삭제 금지, twin 있는 superseded만 (`feedback_occam_kg_node_dedup_is_primary`).
