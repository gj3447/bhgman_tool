# engine/ — 비행기맨 #4 산하 엔진 지도

> 한눈에: **7 군단장(LegionCommander) + 오케스트레이션/인프라 + KG 백엔드 + 증명/효능**.
> 결정론 코어가 정체성이고 LLM은 옵션 enrichment (A/B falsifier 근거).
> CLI 진입점: `cli/` (`bhgman-tool <verb>`). 합성 진입점: `legion/` (`legion run`).

## 7 군단장 (능동동사 직교 7축)

| dir | 동사 | 한 줄 | 비고 |
|---|---|---|---|
| `prometheus/` | 획득 | 경계축 ingest — 외부 지식 → KG (결정론) | LLM은 옵션 (`agents/`) |
| `eureka/` | 발견·창조 | 귀납→추상. FCA/AMIE3/Leiden-LLM. AbstractClass + GENERALIZES | 📖 자체 README |
| `longinus_*` | 연결 | code↔KG / KG↔KG 바인딩 + drift 감지 | ⚠ **아래 2개 구분** |
| `occam/` | 정리 | KG 노드 dedup + supersession σ 스코어링 (삭제 X, 아카이빙) | `--local` neo4j-free |
| `naesengmoon/` | 검증 | 적대적 ensemble critic — n_eff 탈상관 | 6 lens |
| `jaebaeman/` | 출격 | 계획→씨앗 (meta-planning → seed) + dispatch SOP | |
| `hades/` | 실현 | ACCEPTED 추상 → 구체 코드 (libcst rewriter). eureka의 dual | neo4j-free |

### ⚠ longinus 이름 함정 (둘은 다른 것)
- `longinus_drift/` — **작은 drift 감지부** (`ged_drift_detector` / `nightly_drift_check`). eureka에서 분리돼 나온 조각 (eureka-l8-rectification split, pyproject root-scan).
- `longinus_drift_audit/` — **프로덕션 7-layer 감사 러너** (BX lens / GED / reverse orphan / sha256 baseline / 병렬). 📖 자체 README. 정본 구현.

## 오케스트레이션 & 인프라

| dir | 한 줄 |
|---|---|
| `cli/` | umbrella CLI — `bhgman-tool` 7 verb 진입점 |
| `legion/` | 7군단장 합성 + HMAC tamper-evident audit trail (`legion run`) |
| `agents/` | Anthropic API 런타임 + 3 LLM 군단장 (키 없으면 skill-route) |
| `mcp_server/` | MCP 프로토콜 서버 (9 tool). 자체 venv/lock (standalone subpkg) |
| `gate/` | APT v27 A7 — fail-closed HTTP gate (Polly v8 chain). 📖 자체 README |
| `resolver/` | APT v27 A6 — pre-prompt resolver (Jinja2+Neo4j). 📖 자체 README |

## KG 백엔드 & 메모리

| dir | 한 줄 |
|---|---|
| `kg_local/` | 로컬 JSON KG (`~/.bhgman/kg.json`) — neo4j-free, MERGE 멱등 |
| `memory/` | 경량 in-memory 벡터 스토어 (APT phase context + lesson 영속) |
| `code_to_kg/` | tree-sitter 소스 → KG 심볼 ingest (롱기누스 역방향). 📖 자체 README |

## 증명·증거·내보내기

| dir | 한 줄 |
|---|---|
| `efficacy/` | A/B falsification 실험 — base-LLM vs bhgman (📖 자체 README, `SWEEP_RESULTS.md`) |
| `harness/` | 하네스 형식론 — 3계층/4축 진단 엔진 (결정론) |
| `provexport/` | KG findings → W3C PROV-O / nanopub (ADRs/prov-o-nanopub-export) |

---
*이 파일은 지도(view)일 뿐 — 실제 정본은 각 dir의 코드 + KG. 새 subdir 추가 시 위 표 한 줄 갱신.*
