---
name: db-query
kg_ref: ATOM_Skill_db_query
version: "1.1.0"
channel: stable
defer_loading: true   # Anthropic Skills frontmatter extension (ToolSearch deferred manifest, Jan 2026)
                       # MCP tool schemas listed in `optional_mcp_tools` are NOT loaded at session start.
                       # Loaded on-demand via ToolSearch (`select:<tool_name>` or keyword search).
                       # Estimated savings: ~7-10k baseline tokens (mongodb 32 + redis 40 + others).
optional_mcp_tools:
  # Each entry = MCP tool name → 1-line trigger hint for ToolSearch resolution.
  # Format: <fully_qualified_tool_name>: <when to load>
  mongodb:
    mcp__mongodb__find:                 "MongoDB document query / 컬렉션 조회"
    mcp__mongodb__aggregate:            "MongoDB aggregation pipeline 실행"
    mcp__mongodb__count:                "MongoDB document count"
    mcp__mongodb__collection-schema:    "MongoDB collection schema inspection"
    mcp__mongodb__collection-indexes:   "MongoDB index 조사"
    mcp__mongodb__list-collections:     "MongoDB collection listing"
    mcp__mongodb__list-databases:       "MongoDB DB listing"
    mcp__mongodb__insert-many:          "MongoDB bulk insert (WRITE — user confirm)"
    mcp__mongodb__update-many:          "MongoDB bulk update (WRITE — user confirm)"
    mcp__mongodb__delete-many:          "MongoDB bulk delete (WRITE — user confirm)"
    mcp__mongodb__explain:              "MongoDB query plan inspection"
  postgres:
    mcp__postgres__execute_sql:         "PostgreSQL query 실행"
    mcp__postgres__explain_query:       "Postgres EXPLAIN ANALYZE"
    mcp__postgres__list_schemas:        "Postgres schema listing"
    mcp__postgres__list_objects:        "Postgres table/view/index listing"
    mcp__postgres__get_object_details:  "Postgres object 상세 (column / constraint)"
    mcp__postgres__get_top_queries:     "Postgres pg_stat_statements top N"
    mcp__postgres__analyze_db_health:   "Postgres health check (bloat / vacuum / etc.)"
    mcp__postgres__analyze_query_indexes:    "Postgres single-query index advisor"
    mcp__postgres__analyze_workload_indexes: "Postgres workload-level index advisor"
  redis:
    mcp__redis__get:                    "Redis string GET"
    mcp__redis__set:                    "Redis string SET (WRITE)"
    mcp__redis__hgetall:                "Redis hash 전체 조회"
    mcp__redis__hget:                   "Redis hash field 조회"
    mcp__redis__hset:                   "Redis hash field SET (WRITE)"
    mcp__redis__lrange:                 "Redis list 범위 조회"
    mcp__redis__zrange:                 "Redis sorted set 범위 조회"
    mcp__redis__scan_keys:              "Redis key 패턴 탐색"
    mcp__redis__info:                   "Redis 서버 INFO"
    mcp__redis__dbsize:                 "Redis DB key 개수"
    mcp__redis__vector_search_hash:     "Redis vector similarity search"
    mcp__redis__hybrid_search:          "Redis hybrid (vector + text) search"
  neo4j:
    mcp__neo4j__read_neo4j_cypher:      "Neo4j read-only Cypher (KG 조회 default)"
    mcp__neo4j__write_neo4j_cypher:     "Neo4j write Cypher (CREATE/MERGE/SET — user confirm)"
    mcp__neo4j__get_neo4j_schema:       "Neo4j schema (label / rel / property)"
  # NOTE: mcp__neo4j__* schemas are listed even though not in current env probe —
  # APT KG canonical store. Loaded on-demand when KG queries surface in conversation.
description: >
  비행기맨 서버의 DB에 쿼리를 실행합니다. Neo4j Cypher, PostgreSQL SQL, MongoDB 쿼리, Redis 명령어를 실행할 때 사용합니다.
  defer_loading=true — MCP tool schemas (~7-10k tokens) loaded on-demand via ToolSearch.
---

# DB 쿼리 실행

사용자의 요청에 따라 적절한 DB에 쿼리를 실행합니다.

## ToolSearch 사용 패턴 (defer_loading 매니페스트)

이 스킬은 **deferred MCP loading** 을 채택. `optional_mcp_tools` frontmatter 의 ~70 도구 schema 는
세션 시작 시 로드되지 **않음** (token saving ~7-10k). 필요 시 ToolSearch 로 on-demand resolve.

### 트리거별 로드 패턴

| 사용자 요청 | ToolSearch 쿼리 | 로드되는 tool |
|---|---|---|
| "MongoDB 컬렉션 schema 보여줘" | `ToolSearch select:mcp__mongodb__collection-schema,mcp__mongodb__list-collections` | mongodb schema 측 2개 |
| "Postgres 쿼리 plan 분석" | `ToolSearch select:mcp__postgres__explain_query,mcp__postgres__analyze_query_indexes` | postgres explain 측 2개 |
| "Redis 키 패턴 탐색" | `ToolSearch select:mcp__redis__scan_keys,mcp__redis__type` | redis scan 측 2개 |
| "Neo4j Cypher 실행" | `ToolSearch select:mcp__neo4j__read_neo4j_cypher` | neo4j read 1개 |
| "MongoDB find 들고 와" (keyword) | `ToolSearch +mongodb find` (max_results=5) | top-5 mongodb find 후보 |
| Bash `docker exec` fallback 만 필요 | (ToolSearch 불필요) | nothing — Bash 그대로 사용 |

### 원칙

1. **최소 로드**: 정확한 tool 이름 알면 `select:<name1>,<name2>` 형식 (exact match).
2. **keyword fallback**: 이름 불확실 시 `+<must_match>` keyword (top-N 후보 비교 후 1개 선택).
3. **WRITE 도구는 trigger 시점에만 로드**: insert-many / update-many / delete-many / set / hset / write_neo4j_cypher 는 사용자 confirm 후 ToolSearch 로 호출.
4. **Bash fallback 우선**: 가벼운 read query 는 docker exec 측 Bash 가 schema-free 빠름. MCP tool 은 structured pagination / explain / aggregate 측 *복합 query* 에 사용.

## 사용 가능한 DB

### Neo4j (Cypher)
```bash
docker exec neo4j cypher-shell -u neo4j -p neo4jpassword "<CYPHER_QUERY>"
```
- MCP 도구: `mcp__neo4j__read_neo4j_cypher`, `mcp__neo4j__write_neo4j_cypher` (defer_loading — ToolSearch 로 resolve)
- bolt://localhost:7687
- APT KG canonical store. Gate Check Hook (`apt-gate-check.sh`) 가 이 DB 조회.

### PostgreSQL (SQL)
```bash
docker exec postgresql psql -U postgres -d maindb -c "<SQL_QUERY>"
```
- 데이터베이스: maindb (메인), n8n (n8n용)
- MCP 도구: `mcp__postgres__execute_sql`, `mcp__postgres__explain_query` 등 9개 (defer_loading)

### MongoDB
```bash
docker exec mongodb mongosh -u mongo -p mongopassword --eval "<QUERY>"
```
- MCP 도구: `mcp__mongodb__find/aggregate/count/...` 11개 (defer_loading — 32+ schema 절감 큰 편)

### Redis
```bash
docker exec redis redis-cli -a redispassword <COMMAND>
```
- MCP 도구: `mcp__redis__get/hgetall/scan_keys/...` 12개 (defer_loading — 40+ schema 절감 가장 큰 편)

## 안전 규칙
- SELECT/READ 쿼리는 바로 실행
- INSERT/UPDATE/DELETE/DROP 등 쓰기 쿼리는 사용자 확인 후 실행
- 항상 쿼리 결과를 보기 좋게 포맷하여 출력
- WRITE MCP tool 은 confirm 직후 ToolSearch 로 schema 로드 → 실행

## Cross-ref

- MCP manifest 전체 (DB 외 Gmail / Drive / Calendar / Filesystem / Memory / Sequential-thinking 포함): `SKILLS/apt/references/mcp_manifest.yml`
- APT Gate Check Hook ToolSearch fallback 패턴: 같은 파일 §5

# KG: ATOM_Skill_db_query
# KG: rf-prom16-cc-eng-E3-S3-toolsearch-deferred-2026-05-14 (UNDERUTILIZED → ADDRESSED 2026-05-14)
# KG: seed-prom16-cceng-gap-E3.3 (defer_loading manifest 도입)
