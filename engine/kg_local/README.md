# kg_local — 로컬 JSON KG 백엔드

neo4j 서버 없이 동작하는 로컬 KG (`~/.bhgman/kg.json`). `--local` 플래그가 가리키는 백엔드.

- `store.py` — JSON 저장/로드, MERGE 멱등
- `schema.py` — 노드/엣지 스키마 (코드가 스키마, 사전-seed 불필요)
- `runner.py` — 부트스트랩 러너
- `floating_scan.py` — 소스에 안 묶인(floating) 노드 탐지 (롱기누스 바인딩 부재)

> 진짜 neo4j 부트스트랩: 이 스키마에서 생성 가능 (README 루트 "neo4j 없이" 참조).
