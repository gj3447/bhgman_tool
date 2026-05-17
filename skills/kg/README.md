# skills/kg/ — Knowledge Graph snapshot bundle

> SYMPOSIUM ↔ bhgman_tool 측 KG 측 same dgx neo4j DB 인스턴스 사용 (`SAME_DB_AUTO_SYNCED` policy, KG: `span-bhgman-w12-w14-sync-2026-05-14`).

## kg/dump.sh

KG 측 모든 노드/edge 측 Cypher MERGE 형태로 dump → `kg/snapshot.cypher` 생성.

```bash
bash skills/kg/dump.sh           # → skills/kg/snapshot.cypher (gitignored)
git add skills/kg/snapshot.cypher && git commit -m "kg snapshot" && git push
```

## 외부 머신 측 측 install with KG

`install.metahumotonic.com/install` 측 측 `--with-kg` flag 측 snapshot.cypher 측 import.

## NOTE

`dump.sh` 측 측 미구현 — TODO (sprint trigger: bhgman_tool wave11+). 현재 측 측 직접 측 `neo4j-admin dump` 또는 MCP `neo4j_dump_cypher` 측 측 수동 측 export.

KG ref: `span-bhgman-w12-w14-sync-2026-05-14` (SAME_DB_AUTO_SYNCED policy)
