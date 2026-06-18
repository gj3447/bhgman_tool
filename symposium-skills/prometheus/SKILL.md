---
name: prometheus
kg_ref: ATOM_Skill_prometheus
version: "6.3.0"
channel: stable
provenance: AI_DERIVED_FROM_USER_PRIMARY  # SKILL.md = AI engineering; underlying methodology = user-primary mythology (12 apostles + 5 weapons). Per PseudepigraphaValidationGate-v1-2026-04-30.
description: >
  프로메테우스 방법론 v6.1 — **지식-행동 spiral** (Hegel reframe, NOT 단방향 "지식 선행").
  "바로 고치지 마" 유지 + "먼저 불(지식) 훔쳐와"는 thesis-antithesis-synthesis 첫 thesis.
  v6.1: OODA/Lean Startup 충돌 해소 — Hegel Phenomenology Begriff 자가운동.
  paralysis-by-analysis 회피: hot-fix latency critical 시 KG-skip + immediate action + post-hoc lesson 허용.
  사용법: `/prometheus <N> <problem>` (N=subagent 수, 생략 시 auto_estimate, default cfg slot).
  v6: Step 6.5 filesystem_dispersion + G6.5 gate (KG↔filesystem drift 차단).
  v5: SKILL.md는 프로토콜만, 내용물은 KG 정본(재배맨 원칙).
  v4: 부모 하계 Pre-fetch (MCP 우회) + Finding 중복 탐지 + 재배맨 MIC 참조.
  Enforces: 9+1 단계 사이클, haiku 병렬 subagent (N, 최대 100, default cfg slot),
  JSON 계약(FullFindingRecord), 부모 UNWIND 배치 write, W3C PROV provenance, filesystem dispersion gate.
  subagent 운용 = MIC_v1.SubagentSeeder (재배맨/SOP) 참조.
  # KG: ATOM_Skill_prometheus, MIC_v1.ReasoningProtocol→KGFirstCheck_v1 (R1-R5 mandatory, lesson-ai-skipped-kg-check-before-framing-2026-04-29), prometheus-grounding-2026-05-05
---

## 🔗 MIC Binding (SOLID-DIP)

**IS slot**: `ResearchProvider` (MIC_v1.currentConcrete = "Prometheus")
**USES slots**: SubagentSeeder (haiku 병렬 리서치 taskspec)

**역할 대체 가능성 (L 원칙)**: 미래에 다른 리서치 메커니즘으로 교체 시 `MIC_v1.ResearchProvider.currentConcrete` SET만.

# KG: MIC_v1, MethodologySlot:ResearchProvider, lesson-apt-not-truly-jaebaeman-2026-04-14

---

## 🎛 v26 A6 Resolve-Only

> N 상한, auto_estimate 밴드, consensus 임계값 등 모든 magic number는 `MethodologyConfig_default_v26` 슬롯에서 resolve. 본문 prose 직접 편집 금지 — KG 노드만 갱신.

```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})
      -[:HAS_SLOT]->(s:MethodologySlot {name:'MethodologyConfig'})
MATCH (cfg:MethodologyConfig {name: s.currentConcrete})
RETURN cfg.prometheus_n_max,           // 100
       cfg.prometheus_auto_estimate_small_min, cfg.prometheus_auto_estimate_small_max,    // 3,5
       cfg.prometheus_auto_estimate_medium_min, cfg.prometheus_auto_estimate_medium_max,  // 6,11
       cfg.prometheus_auto_estimate_large_min, cfg.prometheus_auto_estimate_large_max,    // 12,20
       cfg.prometheus_domain_strategy_manual_max,   // 5
       cfg.prometheus_domain_strategy_preset_max,   // 11
       cfg.prometheus_domain_strategy_axis_min,     // 12
       cfg.prometheus_consensus_min_findings,       // 3
       cfg.prometheus_terse_schema_threshold_n,     // 50
       cfg.prometheus_subagent_model               // 'haiku'
```

**Field map**: 본문에 박힌 숫자(`N ≤ 100`, `N ≤ 5`, `6 ≤ N ≤ 11`, `consensus 3개`, `N < 50 Full schema` 등)는 모두 위 cfg 필드의 표시값. 변경 필요 시 cfg 노드만 SET.

**Stale KG cleanup (2026-04-25)**: v1 PrometheusStep (discovery/recon/research/kg-build/plan/execute/verify, 7개) + v2 (ignite/recall/lower/upper/crystallize/design/execute/verify, 9개) 모두 :ARCHIVED. 현 SKILL.md v5 metaphor (Step 0/1/2/2.5/3/3.3/3.5/4/4.7/5/6/7)와 drift. 향후 v5 step 노드 재구축 필요 시 `prometheus-step-v5-*` 네이밍.

# KG: APT_v26_A6_2026-04-21, MethodologyConfig_default_v26 (15 prometheus_* 필드, 2026-04-25)

---

# /prometheus — 프로메테우스 방법론: 불(지식)을 먼저 훔쳐와라

> **프로메테우스(Prometheus) = 그리스어 "먼저 생각하는 자(先見者)".**
> 신에게서 불(지식)을 훔쳐 인간에게 준 타이탄.
> 행동 전에 지식을 확보하는 것이 본 방법론의 핵심.

---

## 왜 프로메테우스인가

문제를 만났을 때 **바로 고치려는 충동**이 가장 큰 적이다.

```
나쁜 패턴:  문제 발생 → 즉시 삽질 → 실패 → 더 삽질 → 시간 낭비
좋은 패턴:  문제 발생 → 기록 → 조사 → 리서치 → KG 구축 → 계획 → 실행 → 검증
```

프로메테우스는 **Step 3(병렬 리서치)**이 핵심이다.
haiku subagent N개를 동시에 풀어서 인터넷 전체에서 지식을 긁어온다.
그리고 그 지식을 **KG에 구조화**한 뒤, 그 위에서 판단한다.

---

## 사이클 개요 (Step 0~7)

```
Step 0: 호출 파싱 (/prom<N>)              ← v3 신설, 선행 파싱
   ↓ [Gate G0: N∈[1,100] + problem_text 존재]
Step 1: 발견 (불씨 포착)
   ↓ [Gate G1: Lesson 노드 생성 확인]
Step 2: 환경조사 (올림포스 정찰)
   ↓
Step 2.5: 하계 Pre-fetch (부모 KG 조회)   ← v4 신설
   ↓ [Gate G2.5: local_context JSON 준비 완료]
Step 3: 병렬 리서치 (불 훔치기) ← 핵심
   ↓ [Gate G3: N개 subagent 전원 JSON 수확 + 스키마 통과]
Step 3.3: Finding 중복 탐지               ← v4 신설
Step 3.5: 부모 UNWIND 배치 write        ← v3 신설, D1 concurrency 해결
   ↓ [Gate G3.5: ResearchFinding N건 KG 적재 확인]
Step 4: 집계/합의/충돌 탐지 (v3 재정의)
   ↓ [Gate G4: 충돌은 Naesengmoon --lens mathematical 경유 해소, 미해소 conflict=0]
Step 4.7: 씨앗 결정화 (SubagentTaskSpec 생성)
   ↓ [Gate G4.7: 모든 high-priority finding → 씨앗 매핑]
Step 5: 계획 수립 (횃불 경로 설계)
   ↓ [Gate G5: ActionPlan 노드 + child-task 링크 완료]
Step 6: 실행 (불 밝히기)
   ↓ [Gate G6: 실행 산출물이 Plan과 1:1 대응]
Step 6.5: filesystem dispersion (KG↔FS 거울)   ← v6 신설, slot resolve only
   ↓ [Gate G6.5: SOURCES.md + axis-split MD + _findings/raw-jsonl 충족]
Step 7: 검증 (불이 꺼지지 않는지 확인)
   ↓ (실패 시)
Step 2로 피드백 루프
```

### Gate Hook 강제 (v4 신규, lesson-prometheus-v4-structural-gaps-2026-04-17)

> v3까지는 Step들이 "권장"이었다. 결과: skip 발생 → ResearchFinding 누적, 씨앗 미결정화, Naesengmoon 우회, subagent 개별 KG write 착각, 부모 context 폭증.
> **v4부터는 위 Gate 중 하나라도 실패하면 다음 Step 진입 BLOCK**. Gate Check Hook(APT와 동일 패턴)이 각 Step 완료 시 검증 쿼리 실행.

| Gate | 검증 쿼리 (Neo4j) | BLOCK 조건 |
|---|---|---|
| G1 | `MATCH (l:Lesson {problem:$text}) RETURN count(l)` | 0 = BLOCK |
| G3 | subagent JSON count == N | 불일치 = BLOCK, 재호출 |
| G3.5 | `MATCH (rf:ResearchFinding {cycle_id:$cid}) RETURN count(rf)` | < N = BLOCK |
| G4 | `MATCH (c:Conflict {cycle_id:$cid, status:'open'}) RETURN count(c)` | > 0 = Naesengmoon 경유 필수 |
| G4.7 | high-priority finding N중 씨앗 매핑률 | < 100% = BLOCK |
| G5 | `MATCH (ap:ActionPlan {cycle_id:$cid})-[:HAS_CHILD]->() RETURN count(*)` | 0 = BLOCK |
| G6.5 | slot resolve `MIC_v1.FilesystemDispersionPolicy` → policy fields 충족 검증 (SOURCES.md exists ∧ axis≥cfg.prometheus_md_axis_threshold면 axis-split MD count=axis_count ∧ N≥cfg.prometheus_findings_jsonl_threshold면 `_findings/` count=N) | 미충족 = BLOCK |

**skip 요청**: 사용자가 명시적으로 `/prom --skip-gate Gx` 플래그 주면 override. 로그: AptDecisionLog with override_reason.

---

### Step 0: 호출 파싱 — N 파라미터화

<!-- # KG: SPAN_L1_n_parser, CONTRACT_SPAN_L1_n_parser, CONTRACT_SharedType_NValue -->

`$ARGUMENTS`의 **첫 토큰이 정수이면 N으로 사용**, 아니면 `auto_estimate`.
v3 TOE-스케일 대응 (최대 N=100) 핵심.

**사용법:**

```
/prometheus <N> <problem>       # N 명시 (예: /prometheus 16 "문제")
/prometheus <problem>           # N 없음 → auto_estimate
```

**파싱 규칙:**

```
match = re.match(r'^\s*(\d+)\s+(.+)$', $ARGUMENTS)
if match:
    N = int(match.group(1))
    problem = match.group(2)
else:
    problem = $ARGUMENTS
    N = auto_estimate(problem)
```

**예시:**

| 입력 | 파싱 결과 |
|---|---|
| `/prometheus 16 "docker vs k8s"` | N=16, problem="docker vs k8s" |
| `/prometheus 100 "TOE 아키텍처"` | N=100, problem="TOE 아키텍처" |
| `/prometheus "n8n 에러"` | auto_estimate → N∈[3,5] (단일 서비스) |
| `/prometheus 3 간단히` | N=3, problem="간단히" |

**auto_estimate:**

| 문제 규모 | N | 판정 기준 |
|---|---|---|
| 소 | `cfg.prometheus_auto_estimate_small_min`~`max` (3~5) | 단일 서비스/API/컨테이너 |
| 중 | `cfg.prometheus_auto_estimate_medium_min`~`max` (6~11) | 다중 서비스 상호작용 |
| 대 | `cfg.prometheus_auto_estimate_large_min`~`max` (12~20) | 아키텍처/TOE/다층 분석 |

**상한: N ≤ `cfg.prometheus_n_max`** (현재 100). 초과 시 경고 후 clamp.

**도메인 생성 전략:**

| N | 전략 |
|---|---|
| N ≤ 5 | 수동 템플릿 (원인분석 / 공식문서 / 커뮤니티) |
| 6 ≤ N ≤ 11 | 프리셋 (네트워크 / 스토리지 / 앱 / 인증 / 모니터링 / 보안 / 성능 / 운영 …) |
| N ≥ 12 | **axis × sub-axis 교차표** |

**axis × sub-axis 교차표 (N ≥ 12):**

- **axis**: 네트워크 / 스토리지 / 앱 / 인증 / 모니터링 / 보안 / 성능 / 운영 …
- **sub-axis**: 공식문서 / 커뮤니티사례 / 벤치마크 / 대안기술 / 함정패턴 / 최신트렌드 …

N=16 → 4 axis × 4 sub-axis = 16 도메인. N=100 → 10×10 (필요 시 축 확장).

---

### Step 1: 발견 — Lesson 즉시 기록

문제를 인지한 순간, **기억에 의존하지 않고 즉시 KG에 기록**.

```cypher
MERGE (l:AbstractNode:Lesson {name: $lesson_name})
SET l.category = $category,
    l.problem = $problem,
    l.wrongAssumption = $wrong_assumption,
    l.truth = $truth,
    l.solution = null,          // 아직 모름
    l.severity = $severity,     // CRITICAL / HIGH / MEDIUM / LOW
    l.lakatos_mechanism = $lakatos_mechanism,  // HR20 필수 (RFC v27 §2.2, 2026-06-01~): monster-barring/exception-barring/concept-stretching/lemma-incorporation/proof-analysis. 누락 시 t_lesson_lakatos_mechanism_required_v27 차단
    l.resolved = false,
    l.createdAt = datetime()
RETURN l.name
```

**severity 기준:**
- CRITICAL: 서비스 다운, 데이터 손실 위험
- HIGH: 기능 장애, 외부 접근 불가
- MEDIUM: 성능 저하, 부분 기능 이상
- LOW: 개선 사항, 비기능적 문제

---

### Step 2: 환경조사 — 현재 상태 파악

**해결 시도 전에 반드시** 현재 환경을 이해한다.

```bash
# 서비스 상태
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 설정 파일 확인
cat docker-compose.yml | grep -A5 $SERVICE

# 로그 확인
docker logs --tail 50 $CONTAINER

# 네트워크 상태
docker network ls && docker network inspect $NETWORK
```

**원칙**: 환경 조사 없이 해결 시도 금지. "고쳐봤는데 안 돼요"가 아니라 "현재 상태가 이런데, 원인이 뭘까요"가 올바른 순서.

---

### Step 2.5: 하계 Pre-fetch — 부모가 KG를 대신 조회 (v4 신규)

<!-- # KG: SPAN_prometheus_v4_prefetch_protocol, SA_methodology_v4_triple_upgrade -->

**문제**: subagent는 MCP 상속 안 됨 (GH #13605). KG 직접 조회 불가.
**해결**: **부모가 Step 2.5에서 하계 context를 조회** → subagent prompt에 JSON으로 주입.

```cypher
// 2.5-1. 기존 ResearchFinding 조회 (중복 방지)
MATCH (l:Lesson)-[:HAS_RESEARCH]->(rf:ResearchFinding)
WHERE l.name CONTAINS $problem_keyword
   OR rf.domain CONTAINS $problem_keyword
RETURN rf.name, rf.domain, rf.oneLineSummary, rf.confidence
ORDER BY rf.researchedAt DESC LIMIT 30

// 2.5-2. 관련 Lesson 조회 (기존 지식)
MATCH (l:Lesson)
WHERE l.problem CONTAINS $problem_keyword
   AND (l.resolved IS NULL OR l.resolved = false)
RETURN l.name, l.problem, l.severity LIMIT 10

// 2.5-3. 기존 Seeds 조회 (재사용 가능한 씨앗)
MATCH (ts:SubagentTaskSpec)
WHERE ts.skill = 'prometheus' AND ts.status = 'READY'
  AND (ts.description CONTAINS $problem_keyword OR ts.role CONTAINS $problem_keyword)
RETURN ts.name, ts.role, ts.priority LIMIT 10
```

**주입 형식** (subagent prompt에 추가):
```
기존_지식(하계): {
  "existing_findings": [{"name":"...", "domain":"...", "summary":"..."}],
  "open_lessons": [{"name":"...", "problem":"...", "severity":"..."}],
  "ready_seeds": [{"name":"...", "role":"..."}]
}
이미 조사된 내용과 중복되지 않는 새로운 관점을 조사하세요.
```

**효과**: subagent가 이미 KG에 있는 지식을 **볼 수 있음** → 중복 리서치 방지 → 엔트로피 감소.

---

### Step 3.3: Finding 중복 탐지 (v4 신규)

<!-- # KG: SPAN_prometheus_v4_dedup_detector -->

Step 3.5 UNWIND 전, 신규 finding이 기존 KG와 중복인지 검사.

```cypher
// 3.3-1. findingId 해시 충돌 체크
MATCH (rf:ResearchFinding {name: $new_finding_id})
RETURN rf IS NOT NULL AS already_exists

// 3.3-2. domain + recommendation 유사도 체크
MATCH (rf:ResearchFinding)
WHERE rf.domain = $new_domain
  AND rf.oneLineSummary CONTAINS $keyword
RETURN rf.name, rf.oneLineSummary LIMIT 5
```

**결정 로직**:
| 상황 | 조치 |
|------|------|
| findingId 충돌 | MERGE (기존 노드 갱신, 생성 안 함) |
| domain + 유사 summary | 기존 finding에 `alternatives` 추가만 |
| 신규 | 정상 MERGE |

# KG: finding_D17_swt_algorithms, lesson-longinus-rigor-theories-2026-04-16

---

### Step 3: 병렬 리서치 — 불 훔치기 (핵심)

<!-- # KG: SPAN_L1_subagent_prompt, CONTRACT_SPAN_L1_subagent_prompt, CONTRACT_SharedType_FullFindingRecord, taskspec-prometheus-matrix-research-v1 -->

> **v5 변경**: Prompt 본문은 SKILL.md에 없다. KG `SubagentTaskSpec` 씨앗이 정본.
> SKILL.md 수정 없이 KG 씨앗만 업데이트하면 전체 시스템에 즉시 반영된다.

#### 3-0. KG 씨앗 Pre-fetch (부모 책무) — **MANDATORY (drift block)**

> **v6.3 (2026-05-14) 강제 격상**: Step 3-0 = **MANDATORY**. SKIP = SKILL.md DRIFT (`lesson-prometheus-v5-kg-reference-lift-2026-04-18` 위반 — "SKILL.md = 프로토콜만, 내용물 = KG 정본"). main Claude prompt 측 axis hardcode = ANTI-PATTERN.
> **부모는 Agent 출격 전에 반드시 KG에서 씨앗을 조회한다.** 조회 SKIP / NULL 결과 무시 후 진행 = HARD VIOLATION. 아래 cypher 3 query 모두 실행 후 결과를 prompt 조립에 주입해야 한다. `mcp__neo4j__read_neo4j_cypher`:

```cypher
// Matrix Template (JSON 계약 + 수행 절차) — MANDATORY query #1
MATCH (mt:SubagentTaskSpec {name: 'taskspec-prometheus-matrix-research-v1'})
RETURN mt.description AS template_desc

// Axis 씨앗 (도메인 지침) — N≥12일 때 axis_label로 매칭 — MANDATORY query #2
MATCH (ax:SubagentTaskSpec {skill:'prometheus'})
WHERE ax.axis_label IN ['history','principle','implementation','storage',
                         'query-schedule','limitations','connections','applications']
RETURN ax.name, ax.axis_label, ax.description

// Sub-axis 씨앗 (렌즈 지침) — MANDATORY query #3
MATCH (sa:SubagentTaskSpec {skill:'prometheus'})
WHERE sa.sub_axis_label IN ['official-docs','community-cases','benchmarks','alternatives',
                             'pitfalls','trends-2026','theory','critique']
RETURN sa.name, sa.sub_axis_label, sa.description
```

**부족/부재한 씨앗 발견 시 처리**:
- query #1 (`taskspec-prometheus-matrix-research-v1`) 결과 NULL → **즉시 MERGE** 후 진행:
  ```cypher
  MERGE (mt:SubagentTaskSpec {name: 'taskspec-prometheus-matrix-research-v1'})
  ON CREATE SET mt.skill='prometheus', mt.role='matrix-template',
                mt.status='READY', mt.description=$template_body, mt.createdAt=datetime()
  ```
- query #2/#3 (axis / sub-axis) 결과 부족 → `taskspec-prometheus-axis-<label>` / `taskspec-prometheus-subaxis-<label>` 직접 MERGE. SKILL.md 본문 수정 금지.

#### 3-0-A. Anti-Pattern Detection (drift block, v6.3 신설)

> Step 3-0 spec 위반 측 자주 발생 drift pattern. main Claude 측 Step 3-0 SKIP 후 axis 측 prompt hardcode → KG 씨앗 정전 우회 → 다음 cycle에서 stale axis 측 propagation. **자체 진단 checklist**:

| 패턴 (anti-pattern) | drift type | 정정 (mandatory action) |
|---|---|---|
| main prompt 측 axis label 직접 hardcode (`axis_label = ['history','principle',...]` Python list 등) | Step 3-0 SKIP | KG seed pre-fetch (query #2) mandatory, hardcode 제거 |
| sub-axis 측 manual 작성 (prompt 내 description 직접 서술) | Step 3-1 violation | `taskspec-prometheus-subaxis-<label>` KG 조회, 결과 NULL 시 MERGE |
| `model="haiku"` only, `seed_bundle` 부재 (axis_seed / sub_axis_seed / template_seed 미주입) | Step 3-5 violation | 9-field seed_bundle (재배맨 v2.2) mandatory |
| matrix-template description SKILL.md에 inline 복제 | v5 reference-lift 위반 | KG 씨앗만 정본, 복제 즉시 삭제 |
| query 결과 NULL 무시 후 default 측 진행 | drift hide | NULL 시 MERGE + provenance edge (`MERGED_FOR_CYCLE`) 필수 |
| Step 3-0 cypher SKIP, axis 측 prompt 직접 작성 | foundation violation | 본 cycle 즉시 ABORT + retroactive KG seed MERGE + cycle 재실행 |

**자가검증 cypher** (cycle 종료 시 sanity-check):
```cypher
// 본 cycle 측 출격 측 axis seed 측 :GERMINATED_FROM_AXIS edge 존재 여부
MATCH (rf:ResearchFinding {cycle_id:$cycle_id})
WHERE NOT (rf)-[:GERMINATED_FROM_AXIS]->()
RETURN count(rf) AS drift_count
// drift_count > 0 → Step 3-0 SKIP 의심 → lesson-prom-manual-axis-drift 측 기록
```

# KG: rf-prom-manual-axis-drift-2026-05-14, lesson-prometheus-v5-kg-reference-lift-2026-04-18 (강제 격상)

#### 3-1. 도메인 분배 — **KG seed mandatory (v6.3)**

> **모든 N 범위에서 axis 선택은 Step 3-0 query #2/#3 결과로부터 derive 되어야 한다.** main Claude 측 axis label 직접 hardcode (Python list / prompt inline 등) = Step 3-0 SKIP drift. KG에 없는 axis 사용 시 `taskspec-prometheus-axis-<label>` 측 즉시 MERGE 필수.

| N 범위 | 분배 전략 | 씨앗 선택 (모두 KG seed 필수) |
|---|---|---|
| N ≤ 5 | 수동 도메인 템플릿 | 부모가 KG axis 1-5개 자율 선택 — 부재 시 MERGE 후 진행 |
| 6 ≤ N ≤ 11 | 프리셋 도메인 | KG axis 6-11개 (sub-axis=default: official+critique 혼합) — hardcode 금지 |
| N ≥ 12 | **axis × sub-axis 교차표** | KG 씨앗 `axis_label × sub_axis_label` 조합 (Step 3-0 query #2 × #3 cartesian) — 교차표 자체도 KG seed 측 derive 필수 |

**위반 시**: Step 3-0-A anti-pattern table 측 row 1 (axis hardcode) 발동 → cycle ABORT + retroactive MERGE.

#### 3-2. findingId 결정적 해시 (멱등 MERGE 보장)

```
findingId = "finding_" + sha256(problem + "::" + domain + "::" + str(idx))[:16]
```

동일 `(problem, domain, idx)` → 동일 findingId. 재실행 시 MERGE로 중복 노드 생성 안 함.

#### 3-3. Subagent 출력 계약 — FullFindingRecord JSON

**계약 스키마는 `taskspec-prometheus-matrix-research-v1.description` 이 정본.** SKILL.md에 복제하지 않는다.

**N에 따른 schema variant (v5 신규)**:

| N 범위 | Schema | 필드 |
|---|---|---|
| N < 50 | **Full** | findingId, domain, rootCause, recommendation, alternatives[], references[], caveats, confidence, oneLineSummary, agentId, researchedAt, sourceKgBindings[] (12개) |
| N ≥ 50 | **Terse** | findingId, domain, oneLineSummary, confidence, recommendation(<200자), agentId (6개) |

Terse 모드 근거: N=100일 때 full schema면 ~500KB context, terse는 ~150KB (60% 절감). 상세는 KG 정본에만 유지, 부모가 재요약 가능.

부모는 Step 3-0 pre-fetch 시 `N`을 확인해 matrix-template의 올바른 schema variant를 subagent prompt에 주입.

#### 3-4. 단일 경로 원칙 — KG write는 **부모만**

- **subagent는 KG에 직접 write 하지 않는다** (JSON 반환만).
- 이유:
  1. Claude Code Agent tool subagent는 MCP 자동 상속 ✗ (GH #13605, #34935)
  2. N개 동시 KG write 시 Lesson 노드 lock 경합 (Neo4j 5.x deadlock)
- 부모가 Step 3.5에서 **UNWIND 단일 트랜잭션**으로 배치 MERGE.

##### 3-4-A. WRITE_DEFERRED_TO_PARENT (PROM 16 T3 ship 2026-05-24)

> **2026-05-24 정전화**: PROM 16 `cycle-prom16-subagent-drift-2026-05-24` 측 instance #4 누적
> (5 RF claim vs 0 actual / 30 SCN+RS claim vs 28/21 actual / 78 prop claim vs ai_proposed_direction null).
> Naesengmoon constitutional CONDITIONAL_APPROVED 0.72. 정전 anchor:
> `lesson-subagent-self-drift-kg-write-prom16-2026-05-24`.

**subagent prompt body 측 명시 (mandatory)**:

```
**WRITE_DEFERRED_TO_PARENT**: 너는 KG에 직접 write 할 수 없다. cypher MERGE 의도를
`kg_write_intent_json` field 에 JSON 으로 반환만 한다. 실제 write 는 parent 가 Step 3.5
UNWIND batch MERGE 로 수행한다. 금지 표현: `kg_writes_done=true` / "MERGE 완료" /
"N개 노드 생성" / "write 성공". 위반 시 parent ReconciliationNode 발동 + claim 폐기.
```

**FullFindingRecord JSON 의 cypher write intent**: `sourceKgBindings[]` 측 cypher 의도만 기록,
실제 MERGE 는 parent Step 3.5 UNWIND 가 수행. subagent JSON 의 `kg_writes_done`-류 field 는
contract 위반 = parent validation FAIL.

**Parent collect 직후 mandatory cypher count spot-check**:
```cypher
MATCH (rf:ResearchFinding) WHERE rf.cycleId=$cid OR rf.agentId CONTAINS $aid
RETURN count(rf) AS actual
// subagent claim 과 actual 불일치 시 ReconciliationNode MERGE + re-MERGE
```

# KG: lesson-subagent-self-drift-kg-write-prom16-2026-05-24, consensus-report-prom16-subagent-drift-2026-05-24

#### 3-5. 부모 Dispatch 패턴 (Jaebaeman 정석) — **9-field seed_bundle MANDATORY (v6.3)**

**기본 절차**: → **재배맨 SKILL.md Phase 2 Dispatch** 참조 (정본).
공통: Pre-fetch(2-1) → Prompt 조립(2-2) → Agent 호출(2-3) → 씨앗 상태 전이(2-4) → HARD CONSTRAINTS.

**Prometheus 특화**: `seed_bundle` 조립 (재배맨 v2.2 측 9-field) + N≥50 terse schema 선택.

> **MANDATORY**: 아래 9 field 모두 채운 seed_bundle 만이 valid dispatch. `model="haiku"` only 측 axis hardcode prompt = Step 3-0/3-5 동시 위반 (Step 3-0-A row 3 발동).

```python
for idx in 0..N-1:
    bundle = {
      # 1. axis seed (KG MANDATORY)
      axis_seed       : axes[idx_axis],            # Step 3-0 query #2 결과
      # 2. sub-axis seed (KG MANDATORY)
      sub_axis_seed   : subaxes[idx_sub],          # Step 3-0 query #3 결과
      # 3. template seed (KG MANDATORY)
      template_seed   : 'taskspec-prometheus-matrix-research-v1',
      # 4. schema variant (N-aware)
      schema_variant  : 'terse' if N >= 50 else 'full',
      # 5. cycle provenance
      cycle_id        : $cycle_id,
      # 6. findingId (deterministic hash, Step 3-2)
      finding_id      : "finding_" + sha256(problem + "::" + domain + "::" + str(idx))[:16],
      # 7. parent lesson (Step 1 측 결정화 lesson)
      parent_lesson   : $parent_lesson_name,
      # 8. agent dispatch metadata (재배맨 v2.2)
      agent_id        : f"prom-{cycle_id}-{idx}",
      # 9. model / token budget
      model_spec      : { name:'haiku', max_tokens: 4096 if schema_variant=='terse' else 8192 }
    }
    # 재배맨 Phase 2-2 prompt 조립에 bundle.description들 주입 (전체 복제 X, id 참조 O)
    # 재배맨 Phase 2-3 Agent 호출
```

**dispatch 후 provenance edges (Step 3.5 UNWIND 시 추가)**:
`GERMINATED_FROM_AXIS` (rf → axis_seed) + `GERMINATED_FROM_SUBAXIS` (rf → sub_axis_seed) + `USED_TEMPLATE` (rf → template_seed) — Step 3-0-A 측 self-verify cypher 가 이 3 edge 존재 여부로 drift 판정.

부모는 N개 subagent의 JSON 수집 후 **Step 3.5**로 일괄 KG write.
ResearchFinding에 `GERMINATED_FROM_AXIS` + `GERMINATED_FROM_SUBAXIS` + `USED_TEMPLATE` 엣지 추가 (Prometheus 고유 provenance).

---

### Step 3.5: 부모 UNWIND 배치 write

<!-- # KG: SPAN_L1_parent_batch_write, CONTRACT_SPAN_L1_parent_batch_write -->

**기본 패턴**: → **재배맨 SKILL.md Phase 4-1 UNWIND 배치 MERGE** 참조 (정본).
공통 UNWIND MERGE + provenance + status='RESEARCHED' + 동시성 처리.

**Prometheus 특화 확장** (재배맨 Phase 4 뒤에 이어붙임):

```cypher
// 재배맨 Phase 4 UNWIND 완료 후, Prometheus 고유: PromBatchWrite gate marker
WITH l, count(r) AS writtenCount
MERGE (bw:PromBatchWrite {cycle_id: $cycle_id})
SET bw.writtenCount  = writtenCount,
    bw.expectedCount = $N,
    bw.completedAt   = datetime(),
    bw.verified      = (writtenCount = $N)
MERGE (l)-[:HAS_BATCH_WRITE]->(bw)
// 각 RF에 cycle_id 전파
WITH l
MATCH (l)-[:HAS_RESEARCH]->(rf:ResearchFinding)
WHERE rf.cycle_id IS NULL
SET rf.cycle_id = $cycle_id
RETURN writtenCount, bw.verified AS gate_passed
```

**동시성/DeadlockDetected/N=100 상한** 정책 → 재배맨 Phase 4-1 참조.

#### Gate 3.5 — 강제 검증 (v5 신규)

Step 3.5 완료 직후, **Step 4 진입 전에 반드시** 다음 쿼리로 검증:

```cypher
MATCH (bw:PromBatchWrite {cycle_id: $cycle_id})
RETURN bw.verified AS gate_passed,
       bw.writtenCount AS actual,
       bw.expectedCount AS expected
```

- `gate_passed=true` → Step 4 진입 허가
- `gate_passed=false` → Step 3 재호출 (부족분 subagent 재출격) + gate 재검증
- `PromBatchWrite` 노드 자체 부재 → UNWIND 실패. 트랜잭션 재시도 (exponential backoff).

**왜 강제인가**: v4에서 partial write가 은폐되어 Step 4 집계가 잘못된 데이터로 진행. v5 gate로 즉시 감지 + 자동 재시도.

---

### Step 4: 집계/합의/충돌 탐지

<!-- # KG: SPAN_L1_conflict_detection, CONTRACT_SPAN_L1_conflict_detection -->

Step 3.5에서 KG에 이미 적재된 N개 ResearchFinding을 **집계**한다. v2의 "수동 수집"은 폐기 — v3는 **자동 합의/충돌 탐지**.

**출력**: ConsensusReport
```
{
  consensus:  [<공통 결론 finding 그룹>],     // 3개 이상이 동의 → 높은 신뢰도
  conflicts:  [<상반 결론 pair>],              // 2vs2 이상 → 추가 리서치 필요
  singletons: [<단독 결론 finding>],           // 1건 → 신뢰도 주의 태그
  summary: {consensusCount, conflictCount, singletonCount, totalFindings}
}
```

#### 4-1. 합의 탐지 (consensus)

공통 recommendation 키워드가 3개 이상 finding에 등장 → 높은 신뢰 그룹.

```cypher
MATCH (l:Lesson {name: $lesson_name})-[:HAS_RESEARCH]->(r:ResearchFinding)
WITH l, r.recommendation AS rec, collect(r.name) AS findings
WHERE size(findings) >= 3
RETURN rec AS consensusRecommendation, findings AS consensusFindings, size(findings) AS agreeCount
ORDER BY agreeCount DESC
```

(단순 문자열 매칭 한계 시 → KARMA-style LLM 토론 fallback)

#### 4-2. 충돌 탐지 (conflict)

두 findings의 recommendation이 의미적으로 상반 → 충돌 pair.

```cypher
MATCH (l:Lesson {name: $lesson_name})-[:HAS_RESEARCH]->(r1:ResearchFinding)
MATCH (l)-[:HAS_RESEARCH]->(r2:ResearchFinding)
WHERE r1.name < r2.name  // 중복 pair 제거
  AND toLower(r1.recommendation) <> toLower(r2.recommendation)
  AND r1.confidence IN ['HIGH', 'MEDIUM'] AND r2.confidence IN ['HIGH', 'MEDIUM']
RETURN r1.name AS findingA, r1.recommendation AS recA,
       r2.name AS findingB, r2.recommendation AS recB,
       r1.agentId + ' vs ' + r2.agentId AS agents
LIMIT 20
```

상반 여부 판정은 LLM(부모 Claude)가 pair 단위로 재검토. 충돌이 확정되면 → 추가 리서치 또는 실험 필요 (ActionPlan에 반영).

#### 4-3. 단독 탐지 (singleton)

1개 finding만 있는 domain → low-confidence 태그.

```cypher
MATCH (l:Lesson {name: $lesson_name})-[:HAS_RESEARCH]->(r:ResearchFinding)
WITH l, r.domain AS domain, collect(r) AS findings
WHERE size(findings) = 1
RETURN domain, findings[0].name AS singletonFinding, findings[0].confidence AS currentConfidence
```

단독 finding은 ActionPlan에 반영 시 "저신뢰 근거" 플래그를 명시.

#### 4-4. LLM 토론 fallback (KARMA-style)

문자열 매칭으로 합의/충돌이 모호할 때, 부모 Claude가 findings을 읽고 토론식 판정:
- 3개 finding이 "UNWIND 배칭" vs "Redis Stream"처럼 **대안 관계**인가 **상반 관계**인가
- 판정을 KG ConflictResolution 노드로 기록

---

### Step 4.7: 씨앗 결정화 (Seed Crystallization)

<!-- # KG: SPAN_L1_step4_7_doc, CONTRACT_SPAN_L1_step4_7_doc, CONTRACT_SharedType_SeedTaskSpec -->

Step 4 집계 결과를 **재배맨 씨앗(SubagentTaskSpec)**으로 결정화. **프로메테우스의 진짜 산출**은 이 씨앗. ResearchFinding은 원료, SubagentTaskSpec이 완제품.

> **프랙탈 순환의 닫힘 지점.**
> 프로메테우스 → (재배맨/RAG + 롱기누스/실측) → edge data → 하네스↔나생문 GAN → **검증된 씨앗** → KG 심기 → 다음 재배맨이 조회 → 재귀.
> 이 Step이 없으면 ResearchFinding은 일회용으로 죽고 프랙탈이 끊긴다.

**하이퍼그래프 주석**: SubagentTaskSpec은 본래 하이퍼그래프(N:N multi-relation entity)의 degenerate 표현. 현재 Neo4j는 interim. 미래 TypeDB/HyperGraphDB 마이그레이션 여지.

#### 4.7-1. 결정화 매핑 규칙

| Step 4 분류 | priority | germinationMethod | 재배맨 운명 |
|---|---|---|---|
| **consensus** (3+ 동의) | HIGH | `consensus` | 즉시 재사용 — 검증된 지식 |
| **conflict** (상반 pair) | EXPLORATION | `conflict` | 추가 탐색 — 둘 중 진실 가려내기 |
| **singleton** (1건) | VERIFY | `singleton` | 확인 요청 — 다른 에이전트 중복 검증 |

#### 4.7-2. 씨앗 생성 Cypher (consensus → HIGH)

```cypher
MATCH (l:Lesson {name: $lesson_name})-[:HAS_RESEARCH]->(r:ResearchFinding)
WITH l, r.recommendation AS rec, collect(r) AS rfs
WHERE size(rfs) >= 3
UNWIND rfs AS rf
MERGE (ts:AbstractNode:SubagentTaskSpec {
  name: 'seed-rf-' + rf.domain + '-' + toString(timestamp())
})
SET ts.skill = 'prometheus',
    ts.role = '(consensus) ' + rf.domain + ' — ' + rf.oneLineSummary,
    ts.description = rf.recommendation,
    ts.input = rf.rootCause,
    ts.output = rf.alternatives,
    ts.priority = 'HIGH',
    ts.germinationMethod = 'consensus',
    ts.sourceRF = rf.name,
    ts.hypergraph_shape = 'N:N-multi-relation',
    ts.status = 'READY',
    ts.createdAt = datetime()
MERGE (ts)-[:GERMINATED_FROM]->(rf)
RETURN count(ts) AS consensusSeedsPlanted
```

#### 4.7-3. 씨앗 생성 Cypher (conflict → EXPLORATION)

```cypher
MATCH (l:Lesson {name: $lesson_name})-[:HAS_RESEARCH]->(rA:ResearchFinding)
MATCH (l)-[:HAS_RESEARCH]->(rB:ResearchFinding)
WHERE rA.name < rB.name
  AND toLower(rA.recommendation) <> toLower(rB.recommendation)
  AND rA.confidence IN ['HIGH','MEDIUM'] AND rB.confidence IN ['HIGH','MEDIUM']
MERGE (ts:AbstractNode:SubagentTaskSpec {
  name: 'seed-conflict-' + rA.domain + '-vs-' + rB.domain + '-' + toString(timestamp())
})
SET ts.skill = 'prometheus',
    ts.role = '(conflict) ' + rA.domain + ' vs ' + rB.domain,
    ts.description = '상반 추천 해소: ' + rA.recommendation + ' ↔ ' + rB.recommendation,
    ts.priority = 'EXPLORATION',
    ts.germinationMethod = 'conflict',
    ts.sourceRF = [rA.name, rB.name],
    ts.hypergraph_shape = 'N:N-multi-relation',
    ts.status = 'READY',
    ts.createdAt = datetime()
MERGE (ts)-[:GERMINATED_FROM]->(rA)
MERGE (ts)-[:GERMINATED_FROM]->(rB)
RETURN count(ts) AS explorationSeedsPlanted
```

#### 4.7-4. 씨앗 생성 Cypher (singleton → VERIFY)

```cypher
MATCH (l:Lesson {name: $lesson_name})-[:HAS_RESEARCH]->(r:ResearchFinding)
WITH l, r.domain AS domain, collect(r) AS rfs
WHERE size(rfs) = 1
WITH rfs[0] AS rf
MERGE (ts:AbstractNode:SubagentTaskSpec {name: 'seed-verify-' + rf.domain + '-' + toString(timestamp())})
SET ts.skill = 'prometheus',
    ts.role = '(verify) ' + rf.domain + ' 확인',
    ts.description = '단독 finding 중복 검증: ' + rf.recommendation,
    ts.priority = 'VERIFY',
    ts.germinationMethod = 'singleton',
    ts.sourceRF = rf.name,
    ts.hypergraph_shape = 'N:N-multi-relation',
    ts.status = 'READY',
    ts.createdAt = datetime()
MERGE (ts)-[:GERMINATED_FROM]->(rf)
RETURN count(ts) AS verifySeedsPlanted
```

#### 4.7-5. 프랙탈 depth 제한

무한 증식 방지: 각 씨앗은 `depth` 속성. 부모 씨앗(현재 세대)에서 새 씨앗 발아 시 `depth+1`.

```cypher
// 새 씨앗 생성 시 depth 체크
MATCH (parentTs:SubagentTaskSpec {name: $parent_seed})
WITH coalesce(parentTs.depth, 0) + 1 AS newDepth
WHERE newDepth <= 3  // 최대 3세대 증식
// ... 새 씨앗 MERGE with depth=newDepth
```

#### 4.7-6. 재배맨 호출 시 씨앗 재활용

다음 `/prometheus` 또는 `/prom` 호출 시, Step 2(환경조사) 단계에서 **기존 씨앗 조회**:

```cypher
// 관련 도메인 READY 씨앗 조회 — 상계(RAG) 재사용
MATCH (ts:SubagentTaskSpec {skill: 'prometheus'})
WHERE ts.status = 'READY'
  AND ts.domain IN $currentDomains
  AND (ts.depth IS NULL OR ts.depth < 3)
RETURN ts.name, ts.role, ts.description, ts.priority, ts.sourceRF
ORDER BY ts.priority, ts.createdAt DESC
LIMIT 10
```

조회된 씨앗은 **Step 3 subagent 호출 시 프롬프트에 참조로 주입** (전체 복제 금지, id만). 재배맨이 subagent 내부에서 `MATCH (ts:SubagentTaskSpec {name: $seed_id})` 쿼리해 상세 로직 로드.

#### 4.7-7. Skip 방지 — ORPHANED_RAW 정책 (v5 신규)

**Step 4.7을 skip하면 ResearchFinding이 고아가 된다.** 인류가 게임 외 해머인지 모르는 상태.

씨앗 생성 완료 후 검증:

```cypher
// Step 4.7 완료 시 생성된 씨앗 수 확인
MATCH (l:Lesson {name: $lesson_name})-[:HAS_RESEARCH]->(rf:ResearchFinding)
OPTIONAL MATCH (rf)<-[:GERMINATED_FROM]-(ts:SubagentTaskSpec)
WITH rf, count(ts) AS seeds_from_this_rf
WHERE seeds_from_this_rf = 0
SET rf.status = 'ORPHANED_RAW',
    rf.orphaned_reason = 'Step 4.7 skipped or no crystallization pattern matched',
    rf.orphaned_at = datetime()
RETURN count(rf) AS orphaned_count
```

`ORPHANED_RAW` finding은 **다음 cycle Step 2.5 pre-fetch에서 재방문 후보**로 자동 포함. 고아 방지 = 지식 누수 방지.

---

### Step 5: 계획 수립 — ActionPlan 생성

**계획 없이 실행 금지.** KG에 구축된 지식 위에서 판단.

```cypher
MATCH (l:Lesson {name: $lesson_name})
MERGE (p:AbstractNode:ActionPlan {name: $plan_name})
SET p.phase = $phase,              // ACTION / FUTURE / MAINTAIN / DONE
    p.priority = $priority,        // HIGH / MEDIUM / LOW / RESOLVED
    p.action = $action,            // 구체적 실행 방법
    p.dependencies = $dependencies, // 선행 조건 list
    p.estimatedEffort = $effort,   // 예상 소요
    p.rollback = $rollback,        // 롤백 방법
    p.createdAt = datetime()
MERGE (l)-[:HAS_PLAN]->(p)
RETURN p.name
```

**phase 분류:**
| Phase | 의미 | 언제 |
|-------|------|------|
| ACTION | 지금 실행 | 긴급 + 준비 완료 |
| FUTURE | 나중 실행 | 선행 조건 미충족 |
| MAINTAIN | 현상 유지 | 현재로 충분 |
| MONITOR | 관찰 중 | 추이 지켜보기 |
| DONE | 완료 | 실행 + 검증 끝 |

---

### Step 6: 실행 — 계획대로

```cypher
// 실행 시작 — plan phase 업데이트
MATCH (p:ActionPlan {name: $plan_name})
SET p.phase = 'ACTION', p.startedAt = datetime()

// 실행 완료 — lesson resolved
MATCH (l:Lesson {name: $lesson_name})
SET l.resolved = true,
    l.resolvedAt = datetime(),
    l.resolvedBy = $resolution_description
MATCH (p:ActionPlan {name: $plan_name})
SET p.phase = 'DONE'
```

---

### Step 6.5: filesystem dispersion — KG ↔ FS 거울 (v6 신설)

<!-- # KG: rfc-prom-filesystem-dispersion-2026-04-29, FilesystemDispersionPolicy slot, lesson-prom-output-coverage-too-lean-2026-04-29 -->

> **본문은 thin pointer.** 정책 자체는 KG slot에 박혀있음. 본 step은 slot resolve만 한다.
> v5까지 KG-first 설계 그대로. KG ↔ filesystem drift만 차단.

#### 6.5-1. Slot resolve (필수 선행)

```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})
      -[:HAS_SLOT]->(s:MethodologySlot {name:'FilesystemDispersionPolicy'})
MATCH (p:FilesystemDispersionPolicy {name: s.currentConcrete})
RETURN p.layer_l1_documents, p.layer_l2_axis_split,
       p.layer_l3_cell_dump, p.layer_l4_kg_first,
       p.layer_l5_minio_mirror_optional, p.layer_l6_source_upper_world_ref,
       p.layer_l7_skill_crystallization, p.gate_g6_filesystem_coverage

MATCH (cfg:MethodologyConfig {name: 'MethodologyConfig_default_v26'})
RETURN cfg.prometheus_md_dispersion_required,         // true
       cfg.prometheus_md_axis_threshold,              // 4
       cfg.prometheus_findings_jsonl_threshold,       // 32
       cfg.prometheus_md_dispersion_artifacts         // [SOURCES.md, INDEX.md, axis-split-md, _findings/raw-jsonl, minio-mirror]
```

#### 6.5-2. 행동 (slot policy 따라)

`cfg.prometheus_md_dispersion_required = true`이면 다음 산출 강제 (slot 필드 1:1 매핑):

| Layer | 산출 | 조건 |
|---|---|---|
| L1 | `THEORY/<topic>/{INDEX.md, PROM_<N>_REPORT.md, SOURCES.md}` | 항상 |
| L2 | `<axis-letter>_<axis-name>.md` per axis | `axis_count ≥ cfg.prometheus_md_axis_threshold` (default 4) |
| L3 | `_findings/<findingId>.json` per ResearchFinding | `N ≥ cfg.prometheus_findings_jsonl_threshold` (default 32) |
| L4 | KG nodes/edges (기존 v5 design) | 항상 (정전) |
| L5 | MinIO mirror `<bucket>/apt-papers/<topic>/` | optional, canon-track 주제일 때 `mc cp -r` |
| L6 | `:UpperWorldRef` (학술/책/OSS/산업) `binding=upper-world-only` | 인용된 모든 1차 소스 |
| L7 | 새 `/apt-*` skill 결정화 | 5+ HIGH consensus seed 발생 시 (skill-creator pattern) |

→ **본문은 위 표만 노출. 임계값/policy 변경 = KG `MethodologyConfig_default_v26` SET, 본문 손대지 말 것** (APT v26 A6 resolve-only 원칙).

#### 6.5-3. Gate G6.5 검증

Step 6.5 완료 직후, Step 7 진입 전 강제 검증:

```cypher
MATCH (l:Lesson {cycle_id: $cycle_id})
OPTIONAL MATCH (l)-[:HAS_RESEARCH]->(rf:ResearchFinding)
WITH l, count(rf) AS N, count(DISTINCT split(rf.subAxis,'')[0]) AS axis_count

MATCH (cfg:MethodologyConfig {name: 'MethodologyConfig_default_v26'})

// filesystem 측 카운트는 호출자(부모 Claude)가 ls 결과로 주입
WITH l, N, axis_count, cfg, $sources_md_exists AS sources_exists,
     $axis_split_md_count AS axis_md_n, $findings_jsonl_count AS jsonl_n

WITH l,
     (sources_exists = true) AS l1_pass,
     (axis_count < cfg.prometheus_md_axis_threshold OR axis_md_n = axis_count) AS l2_pass,
     (N < cfg.prometheus_findings_jsonl_threshold OR jsonl_n = N) AS l3_pass

MERGE (g65:DispersionGateResult {cycle_id: l.cycle_id})
SET g65.l1_documents_pass = l1_pass,
    g65.l2_axis_split_pass = l2_pass,
    g65.l3_findings_jsonl_pass = l3_pass,
    g65.gate_passed = (l1_pass AND l2_pass AND l3_pass),
    g65.checkedAt = datetime()
RETURN g65.gate_passed AS gate_passed
```

- `gate_passed=true` → Step 7 진입 허가
- `gate_passed=false` → 부족 layer 보강 후 재검증 (`/prom --skip-gate G6.5` override 가능, 단 KG `AptDecisionLog`에 사유 기록 필수)

#### 6.5-4. KG Bootstrap (slot 미설치 환경)

slot이 부재하면 본 step은 no-op (v5와 동일 동작). 첫 호출 시 다음 cypher로 slot 설치 (idempotent):

```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})
MERGE (s:MethodologySlot {name:'FilesystemDispersionPolicy'})
  ON CREATE SET s.currentConcrete = 'PromV5_FilesystemDispersion_v1',
                s.added_by_rfc = 'rfc-prom-filesystem-dispersion-2026-04-29',
                s.createdAt = datetime()
MERGE (mic)-[:HAS_SLOT]->(s)
```

→ slot/policy 노드 자체 정의는 `rfc-prom-filesystem-dispersion-2026-04-29` MethodologyRFC 노드 참조.

---

### Step 7: 검증 — 4단계 + Naesengmoon **user-explicit 출격** (v6.4, 2026-05-30 사용자 정정)

> **v6.4 정전 (2026-05-30)**: 사용자 verdict 측 "나생문이랑 prom 이랑 별개로 주면 안돼냐 ㅇㅇ" — **Naesengmoon ⊥ PROM 분리**. v5 측 *자동 출격* 측 retract. 사용자 측 explicit 발화 시에만 dispatch (`/tlb` 또는 `/naesengmoon` separate skill). PROM 본 사이클 측 Step 7-A 측 *optional*, 사용자 측 별도 호출 시 진행. KG: `naesengmoon-prom-decoupled-2026-05-30`.

#### 7-A. Naesengmoon 적대적 검증 (v6.4 — user-explicit only, OPTIONAL)

인프라 테스트 전 **Prometheus-Naesengmoon GAN 루프** 측 완결 측 *사용자 explicit dispatch 시에만*. 자동 출격 대상 (사용자 `/tlb <cycle_id>` 또는 `/naesengmoon` 측 호출 시):

| 대상 | 기준 | Lens |
|---|---|---|
| 대표 ResearchFinding | `confidence='HIGH'` AND consensus 그룹 | `constitutional` |
| ActionPlan | 생성된 모든 plan | `constitutional` |
| HIGH-priority Seeds | `priority IN ['HIGH','CRITICAL']` | `constitutional` |

**Scope 정책**: 기본은 HIGH-priority만. 전체 scope는 `--taliban-full` flag로 명시.

```cypher
// Step 7-A: Naesengmoon 대상 조회
MATCH (l:Lesson {name: $lesson_name})
OPTIONAL MATCH (l)-[:HAS_RESEARCH]->(rf:ResearchFinding {confidence:'HIGH'})
OPTIONAL MATCH (l)-[:HAS_PLAN]->(ap:ActionPlan)
OPTIONAL MATCH (l)-[:GENERATES_SEED]->(ts:SubagentTaskSpec)
WHERE ts.priority IN ['HIGH','CRITICAL']
RETURN collect(DISTINCT rf.name) AS finding_targets,
       collect(DISTINCT ap.name) AS plan_targets,
       collect(DISTINCT ts.name) AS seed_targets
```

**user-explicit 출격 (v6.4)**: `/taliban --lens constitutional <target>` 각 target에 대해 사용자 측 명시적 발화 시 호출. PROM 본 cycle 측 Step 7-A skip 가능 (사용자 default behavior). 사용자 측 verdict trigger 시 진행. Rubber-stamp 방지 — RTI/FVR 통과 못 하면 Step 7-B 진입 불가 (단 본 Step 7-A 측 user-explicit dispatch 시에만 적용).

#### 7-B. 4단계 실측 검증

| # | 단계 | 방법 | 신뢰도 |
|---|------|------|--------|
| 1 | 내부 테스트 | localhost, docker exec | 최저 |
| 2 | 외부 테스트 | MacBook(다른 네트워크), Tailscale SSH | 중간 |
| 3 | 스트레스 테스트 | hey/curl 부하, Pod 삭제 복원력 | 높음 |
| 4 | 글로벌 테스트 | check-host.net (30+ 서버) | 최고 |

```bash
# Level 4: 글로벌 검증 (가장 확실)
rid=$(curl -s "https://check-host.net/check-http?host=http://metahumotonic.com/$PATH&max_nodes=5" \
  -H "Accept: application/json" | python3 -c "import json,sys; print(json.load(sys.stdin)['request_id'])")
sleep 8
curl -s "https://check-host.net/check-result/$rid" -H "Accept: application/json"
```

**검증 실패 시** → Step 2(환경조사)로 피드백 루프. 새로운 정보로 리서치 보강.

#### 7-C. Threshold instrument sync (자동, PROM 16 P3(a) 2026-05-30 wire)

사이클 종료 직후 KG에 새로 쓰인 `:ValidationResult` 노드들을 instrument log에 incremental sync. ROC Youden J / Bayesian MAP derivation의 데이터 누적이 자동으로 진행되도록 함. dispatch_id dedup으로 idempotent — 매 사이클 끝에 안전하게 실행.

```bash
cd /Users/lagyeongjun/CD/bhgman_tool
source .venv/bin/activate
python -m engine.legion.threshold_derivation.backfill_kg \
    --bolt bolt://100.64.0.3:7687 --password "$NEO4J_PASSWORD"
```

출력 예시 (사이클 종료 직후):
```
Existing entries: 762 (incremental dedup active)
  prometheus.research_finding_count ← KG.findings_count  fetched=290  new=3  dup=287  ambig=0
  naesengmoon.confidence_proxy       ← KG.confidence      fetched=38   new=3  dup=35   ambig=0
TOTAL new=6 duplicates=820 ambiguous=110
```

`new>0`이면 새 데이터로 다음 사이클 ROC re-derive 가능 — 자동화의 핵심. 첫 backfill 결과 + ROC 결과는 KG `backfill-kg-vr-instrument-log-2026-05-30`.

---

## ResearchFinding Lifecycle

→ **재배맨 SKILL.md `Finding Lifecycle` 섹션 참조** (v5: 정본 승격, 모든 소비자 공유).
`RESEARCHED → CRYSTALLIZED / ABSORBED_INTO_PLAN / ORPHANED_RAW / ARCHIVED`

---

## 기존 오답노트 조회

```cypher
// 미해결 CRITICAL/HIGH
MATCH (l:Lesson)
WHERE (l.resolved IS NULL OR l.resolved = false)
  AND l.severity IN ['CRITICAL', 'HIGH']
RETURN l.name, l.problem, l.severity
ORDER BY l.severity

// 리서치 + 계획 포함 전체
MATCH (l:Lesson)
OPTIONAL MATCH (l)-[:HAS_RESEARCH]->(r:ResearchFinding)
OPTIONAL MATCH (l)-[:HAS_PLAN]->(p:ActionPlan)
RETURN l.name, l.severity, l.resolved,
       r.recommendation, p.phase, p.priority
ORDER BY l.severity

// 실행 대기 계획만
MATCH (l:Lesson)-[:HAS_PLAN]->(p:ActionPlan)
WHERE p.phase = 'ACTION'
RETURN l.name, l.problem, p.action, p.priority
```

---

## 다른 방법론과의 관계

```
프로메테우스 (지식 획득 사이클)
  ├── 하네스의 Inform + Correct 축 담당
  ├── 나생문: Naesengmoon finding → Lesson 생성 → 프로메테우스 발동
  ├── 롱기누스: 프로메테우스가 구축한 KG를 코드까지 관통
  └── APT: 모든 Phase에서 횡단적으로 발동 가능
```

---

## What NOT To Do

| 금지 | 이유 | 대안 |
|------|------|------|
| 리서치 없이 바로 고치기 | 무지한 삽질 | Step 3 먼저 |
| 단일 에이전트만 리서치 | 편향된 관점 | 도메인별 병렬 |
| 리서치 결과를 채팅에만 남기기 | 다음 세션에서 소실 | KG에 ResearchFinding |
| 계획 없이 실행 | 삽질 재발 | Step 5 ActionPlan 필수 |
| 내부 테스트만으로 "해결" 선언 | NAT hairpinning은 외부 아님 | 4단계 검증 필수 |
| Lesson 기록 안 하기 | 같은 실수 반복 | Step 1 즉시 기록 |

---

*프로메테우스는 코카서스 산에 묶여 매일 간을 쪼이는 벌을 받았다.
그래도 불을 훔쳐온 것은 후회하지 않았다. 지식의 가치는 그만한 값어치가 있다.*

---

## 🌱 재배맨 v2 (MIC Slot Reference — 로직 복제 금지)

> Prometheus의 subagent 운용 = **MIC_v1.SubagentSeeder** slot resolve.
> 재배맨이 바닥(foundation). Prometheus는 도메인 특화 호출 패턴.

### Slot Resolve (v5: 공용 템플릿 참조)

MIC slot resolve 로직은 **`taskspec-mic-slot-resolve-v1` (namespace=methodology-meta)** 씨앗이 정본.
Prometheus/Naesengmoon/Solve 등 모든 스킬이 동일 씨앗 참조 (drift 방지).

```cypher
// v5: KG에서 공용 템플릿 로드
MATCH (mst:SubagentTaskSpec {name:'taskspec-mic-slot-resolve-v1', skill:'methodology-meta'})
RETURN mst.description AS resolve_protocol
```

### 부모 Pre-fetch (v4 핵심 — Step 2.5에서 실행)
```cypher
// 부모가 subagent 출격 전 하계 context 조회 → prompt에 주입
MATCH (l:Lesson)-[:HAS_RESEARCH]->(rf:ResearchFinding)
WHERE l.name CONTAINS $keyword RETURN rf.name, rf.domain, rf.oneLineSummary LIMIT 20
MATCH (ts:SubagentTaskSpec {skill:'prometheus'}) WHERE ts.status='READY'
RETURN ts.name, ts.role LIMIT 10
```

### WorkBuffer 연속성
```cypher
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb
```

# KG: ATOM_재배맨_v2_prometheus, SA_methodology_v4_triple_upgrade

---

## History

> Repo-level changes: [`/CHANGELOG.md`](../CHANGELOG.md). Per-commit: `git log -- prometheus/SKILL.md`.
> 학문 grounding: [`/PROM_16_SKILL_VERSIONING_REPORT.md`](../PROM_16_SKILL_VERSIONING_REPORT.md).

| Version | Date | Summary | KG Ref |
|---|---|---|---|
| **v6.3** | 2026-05-14 | Step 3-0 KG seed Pre-fetch **MANDATORY 격상** + Step 3-0-A Anti-Pattern Detection section 신설 (6-row drift table + self-verify cypher). Step 3-1 도메인 분배 측 KG seed mandatory 명시 (axis hardcode 금지). Step 3-5 9-field seed_bundle (재배맨 v2.2) 명시. 본 세션 (2026-05-14) 측 5 prom cycle 모두 Step 3-0 SKIP drift 측 instance — `lesson-prometheus-v5-kg-reference-lift-2026-04-18` ("SKILL.md = 프로토콜만, 내용물 = KG 정본") 위반 인정. SKILL.md 본문 정정 X (drift는 SKIP 측 발생), Step 3-0/3-0-A enforcement 강화로 mandatory 격상. | `rf-prom-manual-axis-drift-2026-05-14`, `lesson-prometheus-v5-kg-reference-lift-2026-04-18` (강제 격상), `taskspec-prometheus-matrix-research-v1` (정본 cement) |
| **v6** | 2026-04-29 | Step 6.5 filesystem_dispersion sub-step + G6.5 gate 신설. KG-first 설계 그대로, KG↔FS drift만 차단. 본문은 thin pointer — 정책은 `MIC_v1.FilesystemDispersionPolicy` slot + `MethodologyConfig_default_v26.prometheus_md_*` 4 field. APT v26 A6 resolve-only 준수. cycle `prom64-pkgdisc-2026-04-29`가 evidence — 1 .md만 default 산출되던 문제(KG 152 nodes 풍부 ↔ filesystem 1 .md lean) 해소. | `rfc-prom-filesystem-dispersion-2026-04-29`, `lesson-prom-output-coverage-too-lean-2026-04-29`, `verdict-user-prom-too-lean-2026-04-29`, `rootcause-prom-filesystem-dispersion-missing-2026-04-29`, `FilesystemDispersionPolicy` slot, `PromV5_FilesystemDispersion_v1` policy |
| **v5** | 2026-04-18 | Step 3 prompt 본문을 KG 씨앗 (axis/sub-axis/matrix-template) 으로 lift. SKILL.md = 프로토콜만, 내용물 = KG 정본 (재배맨 원칙 준수). PrometheusStep v5 (Step 0/1/2/2.5/3/3.3/3.5/4/4.7/5/6/7) | `lesson-prometheus-v5-kg-reference-lift-2026-04-18`, `lesson-prometheus-v26-a6-step-drift-2026-04-25` |
| **v4** | 2026-04-17 | 부모 하계 Pre-fetch (MCP 우회, GH #13605 대응) + Finding 중복 탐지 + 재배맨 MIC 참조 + Gate Hook 강제 | `lesson-prometheus-v4-structural-gaps-2026-04-17`, `SPAN_prometheus_v4_prefetch_protocol`, `SA_methodology_v4_triple_upgrade` |
| **v3** | (~2026-04 mid) | TOE-스케일 N=100 대응. axis × sub-axis 교차표. UNWIND 단일 트랜잭션 D1 concurrency 해결. KARMA-style consensus/conflict 자동 탐지 | — |
| **v2** | (~2026-04 early) | ignite/recall/lower/upper/crystallize/design/execute/verify 9-step | (archived) `PrometheusStep` v2 nodes |
| **v1** | (older) | 7-step (discovery/recon/research/kg-build/plan/execute/verify) | (archived) `PrometheusStep` v1 nodes |

→ Stale KG cleanup (2026-04-25): v1+v2 PrometheusStep 노드 :ARCHIVED.

# KG history: ATOM_Skill_prometheus / lesson-prom16-skill-versioning-academic-2026-04-29

---

## Measurement & Conditional Dispatch (2026-05-30 추가)

사용자 정전 정정 2026-05-30 (`user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30`): 7군단장 측 *고정 USES edge* retract → *measurement-driven conditional dispatch*. 본 commander도 `measure()` + `decide_dispatch()` API를 따른다.

### 본 commander metric & threshold

- 정전 SPEC: `SYMPOSIUM/THEORY/00_공통/7CMD_NEED_BASED_DISPATCH_SPEC.md` §3 Table
- 구현: `bhgman_tool/engine/legion/measurement.py` — 본 commander의 prometheusMeasurement class
- KG: `:MeasurementFunction` + `:DispatchThreshold` nodes (parent: `7cmd-measurement-driven-conditional-dispatch-2026-05-30`)

### Stevens scale type & 학문 grounding

각 metric의 Stevens 1946 scale type (nominal/ordinal/interval/ratio)을 `:MeasurementFunction.scale` field에 기록.
Goodhart drift (1975) mitigation은 Naesengmoon meta-check 또는 cycle-end invocation-log empirical reconcile (`lesson-occam-proxy-strength-needs-empirical-spot-check-2026-05-28`).

### Dispatch 정전

`measure()` → threshold-gated need detection → 다른 commander conditional invocation (Hades realization pattern universalized, parent `hades-canonical-2026-05-27`).
고정 USES는 *historical provenance only* (`:DispatchEvent` runtime record).

# KG: 7cmd-measurement-driven-conditional-dispatch-2026-05-30, user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30, hades-canonical-2026-05-27, mf-prometheus-*
