# ADR: PROV-O / nanopub export — provenance interop로 vendor-silo 회피

- **Status**: PRELIMINARY (propose, awaiting user CANONICAL verdict)
- **Date proposed**: 2026-05-30
- **KG ref**: `consensus-prom6-bhgman-paths-2026-05-30`, `bhgman-tool-academic-significance-2026-05-30`
- **Parent constraints**:
  - `adr-seven-commander-legion-architecture-2026-05-27` (in-process, KG substrate)
  - significance assessment: `docs/ACADEMIC_POSITIONING.md` (genuine whitespace = per-finding KG provenance loop)
- **Authority**: 사용자 발화 2026-05-30 "PROV-O에 정리 + bhgman_tool에 내용 정리" (PROM-6 cycle 후속)

---

## Context

bhgman_tool의 *진짜 차별성* = **per-finding KG provenance loop** (ephemeral agent finding을
durable·citable·cross-run-queryable KG 노드로 결정화). 이 주장의 치명적 약점: provenance가
bhgman 자기 Neo4j 인스턴스 안에만 살면 — bhgman이 LangSmith/AgentOps를 비판하는 바로 그
**"vendor silo"** 가 된다 (`docs/ACADEMIC_POSITIONING.md` §4 critical weakness).

PROM-6 (`consensus-prom6-bhgman-paths-2026-05-30`)이 두 significance 경로를 비교:
- 경로 A (SWE-bench adapter): **category trap** — "KG가 coding 돕는다"(이미 CodexGraph/RepoGraph/
  KGCompass가 입증)를 보일 뿐, provenance 주장 측정 못 함. $150-300/5일/Docker.
- 경로 B (PROV-O export, **본 ADR**): vendor-silo 비판 제거 + FAIR-citable. **weekend/$0/no-infra.**

학문적 정합: bhgman finding 노드("원자적 assertion + citation + provenance")는
**nanopublication** (Groth et al. 2010)과 *구조적 동형*이고, 전체는 W3C **PROV-O** +
**PROV-AGENT** (arXiv:2508.02866) 패턴에 1:1 매핑됨. EU AI Act Art.12 (Aug 2026 시행, 고위험 AI
로깅 강제)와도 결을 같이함.

---

## Decision

**PROV-O를 core export layer로, nanopub·RO-Crate를 선택적 상위 레이어로 추가한다.**
SWE-bench는 차별성 검증엔 채택하지 않음 (category trap).

### 스키마 매핑 (bhgman KG → W3C PROV-O)

| bhgman 노드/엣지 | PROV-O 개념 |
|---|---|
| `ResearchFinding` (FullFindingRecord) | `prov:Entity` |
| `findingId` (sha256[:16]) | Entity URI / nanopub Trusty URI seed |
| `agentId` (subagent) | `prov:SoftwareAgent` / PROV-AGENT `AIAgent` |
| `CycleResult` / `cycle_id` | `prov:Activity` |
| `researchedAt` | `prov:generatedAtTime` |
| `citation_url` / references | `prov:hadPrimarySource` |
| `sourceKgBindings` | `prov:used` |
| `GERMINATED_FROM` edge | `prov:wasDerivedFrom` |
| `SubagentTaskSpec` (seed) | `prov:Plan` |
| confidence/domain/rootCause | literals (`bhgman:` namespace) |

### MVP (leanest, weekend = 2-3일, pure-python, 외부 서비스 0)

`bhgman export-prov <cycle_id>` CLI subcommand:
1. Neo4j에서 `cycle_id`의 모든 `ResearchFinding` + `GERMINATED_FROM` 엣지 query.
2. 각 finding → `prov.ProvDocument` (Entity/Activity/Agent + wasGeneratedBy/wasAttributedTo/
   wasDerivedFrom/used/hadPrimarySource).
3. Turtle(.ttl) emit (stdout 또는 파일). `--nanopub` 플래그 시 TriG 4-graph(assertion/
   provenance/pubinfo/head), publish 없이 로컬만.
- **deps** (pure-python): `prov==2.1.1`, `rdflib>=7`, (선택)`nanopub>=2.1`, `neo4j`(기존), `click`(기존).
- **validate**: rdflib round-trip parse + `prov` lib PROV-DM constraint check + (선택) ttl.summerofcode.be.

### 레이어링 (점진)
PROV-O Turtle (core, 즉시) → nanopub Trusty-URI atomic publication (per-finding, 외부 발행 시) →
RO-Crate per-cycle archive (`ro-crate-metadata.json` zip, 재현성 패키징).

---

## Consequences

### 버는 것
- "vendor silo" 비판 **제거** — provenance가 W3C 표준으로 export되어 3rd party 소비 가능 (in principle).
- finding이 **FAIR-citable** (Findable/Accessible/Interoperable/Reusable).
- PROV-AGENT (2025) 대비 차별점(domain-KG + citation_url anchoring) 방어 가능해짐.
- 낮은 비용·위험 (weekend, $0, infra 0) — SWE-bench($300/5일/Docker) 대비 압도적.

### 안 사는 것 (정직)
- **adoption gap을 ZERO 해결** — export 포맷이 user를 만들지 못함. interop은 adoption의
  *downstream*이지 upstream 아님 (OpenAPI spec이 API consumer를 만들지 않듯).
- **현재 pull하는 consumer audience 없음**: nanopub network는 bioinfo 편중, EU AI Act는
  high-risk 분류만(연구 methodology assistant는 거의 해당 안 됨), open-science는 *published
  scientific claim*을 원하지 tool-cycle provenance가 아님.
- presentation을 강화하지 substance(방법론 자체의 epistemic 강도)는 아님.

### 따라서 — priority
1. **본 ADR(PROV-O export) 먼저** — 최저위험 defensive move, vendor-silo 비판 차단.
2. SWE-bench는 차별성엔 skip (category trap). coding 신호 원하면 50-instance pilot을
   *"orchestration이 coding 안 망친다"* 로만 좁게 frame.
3. **진짜 "does bhgman matter" 검증 = provenance-audit protocol** (3rd party가 KG만으로 결정
   재구성·post-hoc 정정 가능한가) **+ 외부 user ≥1.** 어느 벤치도 측정 못 함. ← 별도 작업.

> 핵심: PROV-O export는 *해야 할* 낮은-비용 위생 작업이지만, *그것만으로* significance를
> 입증하지 못한다. significance는 벤치가 아니라 adoption + audit 질문이다.
