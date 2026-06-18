---
name: taliban
kg_ref: ATOM_Skill_taliban
version: "3.2.0"
channel: stable
canonical_name: 나생문
aliases: [taliban, tlb, 88-taliban, Rashomon, naesengmoon]
provenance: AI_DERIVED_FROM_USER_PRIMARY  # SKILL.md = AI engineering; underlying methodology = user-primary mythology (12 apostles + 5 weapons). Per PseudepigraphaValidationGate-v1-2026-04-30.
description: >
  나생문 방법론 (Naesengmoon, 羅生門) — APT의 면역 시스템. 적대적 검증 프레임워크.
  Canonical = 나생문 (사용자 verdict 2026-05-19 PRIMARY), file name `taliban` = alias.
  렌즈셋 플러거블: --lens constitutional(기본 9), mathematical(113), solid(5), longinus(7), lakatos(4), formal-cathedral(5, over-formalization 탐지·escalate-to-oracle), 또는 KG에 등록된 임의 LensSet.
  Cardinality + lens 선택 = invocation-time user-choice flexible (사용자 verdict 2026-05-20 PRIMARY).
    N중 나생문 = N 독립 lens (simple 1:1, cardinality 자유 정수). lens 조합은 invocation-time 명시 (constitutional/mathematical/solid/longinus/lakatos/formal-cathedral 6종 또는 KG 등록된 임의 LensSet).
    formal-cathedral (형식 대성당 나생문, 2026-05-27): over-formalization 전담 탐지. verdict=escalate-to-oracle (판단렌즈 논증으로 PASS 불가, 컴파일러 나생문이 실측 때려야). smell≥2 → CONDITIONAL_BLOCK + 가장 싼 oracle falsifier 강제. KG: formal-cathedral-detection-2026-05-27 / 정의 THEORY/나생문/LENSES/formal-cathedral.md.
    Aggregation policy: UNANIMOUS_PASS default, MAJORITY / WEIGHTED는 user explicit alternative 허용.
    Timing axis (Wave 9 add, 2026-05-20): cross-agent-retroactive (default, /tlb subagent dispatch) / meta-sprint-self (apt-meta-review Constrain Layer 3) / pre-emit-gate (케르베로스 나생문 / Cerberus Naesengmoon, ~/.claude/hooks/placeholder_check.sh 3-head). naesengmoon-cerberus-variant-pre-emit-gate-2026-05-20.
    Lens-mix hardcoded default 측 deprecated (cardinality_naming_rule v1, lesson-naesengmoon-cardinality-3axis-collapse-drift-2026-05-19).
    orthogonality theorem 측 formal edge anchor demoted (lesson-naesengmoon-cardinality-direct-1to1-not-orthogonal-2026-05-19).
  Agent: canonical `naesengmoon-ensemble-critic` ↔ alias `taliban-ensemble-critic` (~/.claude/agents/, 1:1 mirror).
    재배맨 v2.1 SOP-based KG-resident SubagentTaskSpec — inline parent execution 측 ban (lesson-naesengmoon-inline-bypass-jaebaeman-sop-2026-05-19).
    SubagentTaskSpec spec: SYMPOSIUM/THEORY/나생문/SUBAGENT_SPEC.md.
  Invoke when: Span 검증, Contract 검증, 코드 리뷰, Phase 게이트 통과 판정,
  품질 감사(audit), 고무도장 방지, 기존 산출물 재검증, 메타 검증 시.
  Enforces: 렌즈셋 동적 로딩, GAN 원리 (Design=G, Naesengmoon=D),
  동시 출격, 만장일치 PASS, Anti-Rubber-Stamp (RTI/FVR), executor != reviewer D20.
  재배맨 SubagentTaskSpec 기반 자동 출격.
  # KG: ATOM_Skill_taliban, MIC_v1.ReasoningProtocol→KGFirstCheck_v1 (R1-R5 mandatory before any framing/diagnostic, lesson-ai-skipped-kg-check-before-framing-2026-04-29), naesengmoon-canonical-2026-05-19 (CanonicalName)
---

## 🎛 v26 A6 Resolve-Only

> 렌즈셋별 minCritics / min_findings_per_lens / rubber_stamp threshold — **하드코딩 금지**. MethodologyConfig slot resolve.

```cypher
// 렌즈셋별 lens_min_critics + findings 임계치
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v26'})
RETURN cfg.lens_min_critics_constitutional, cfg.lens_min_critics_mathematical,
       cfg.lens_min_critics_solid, cfg.lens_min_critics_longinus,
       cfg.lens_min_critics_constitutional_sp_focused,
       cfg.min_findings_per_lens_tier1, cfg.min_findings_per_lens_tier2,
       cfg.rubber_stamp_conflict_floor

// LensSet 구체 정의 (deprecated 차단)
MATCH (ls:LensSet {name:$lensName}) WHERE ls.deprecated <> true
RETURN ls.lensCount, ls.minCritics, ls.lenses

// v0.8.A1 ensemble concern-coverage (2026-05-05 wired, RFC + agent dispatch)
// — 단일 LensSet borderline (constitutional 0.74) → ensemble UNION coverage>=0.8
// — Pirsig holistic synthesis: 같은 Concern은 max(weight) lens가 cover
MATCH (rfc:MethodologyRFC {name:'rfc-taliban-v08-concern-coverage-2026-05-04'})
RETURN rfc.status, rfc.amendment_a1_2026_05_04
// agent: ~/.claude/agents/taliban-ensemble-critic.md (ensemble dispatch + USED_LENS auto-bind)
// gate: APT_GATE_VERSION=v08-A1 (apt-gate-check.sh dual-mode)
```

## 🌐 v0.8.A1 Ensemble Mode (opt-in)

> 단일 LensSet 발동 시 concern-coverage 0.74-0.41 BORDERLINE/FAIL.
> ensemble (constitutional + longinus + lens-set-lakatos + lensset-solid 4개)이 default 권장.

**발동 옵션:**
- **자동 ensemble**: `Agent(subagent_type="taliban-ensemble-critic", prompt=...)` — `~/.claude/agents/taliban-ensemble-critic.md` agent가 4 LensSet 자동 dispatch + USED_LENS edge 자동 박기 + Pirsig synthesis verdict
- **명시 lens 지정**: `/taliban --lens constitutional --lens longinus --lens lakatos --lens solid <target>` — 4 LensSet ensemble 명시
- **Legacy 단일**: `/taliban --lens constitutional <target>` — v0.7 모드 (lensCount>=9 단일, BORDERLINE 위험)

**KG VR 자동 기록 (D20 정합):**
- `vr.gate_version='v08-A1'`, `vr.coverage_score=0.0-1.0`, `vr.holistic_synthesis=...`
- `vr.executor != vr.reviewer` 강제 (parent-claude vs taliban-ensemble-critic agent)
- 4 USED_LENS edge 자동 (constitutional/longinus/lakatos/solid)

# KG: rfc-taliban-v08-concern-coverage-2026-05-04, pirsig-holistic-synthesis-layer-v0.8-2026-05-05, lesson-taliban-v08-single-lensset-insufficient-2026-05-04, patch-apt-gate-check-v08-A1-flag-2026-05-05

# KG: APT_v26_A6_2026-04-21, MethodologyConfig_default_v26

---

## 🔗 MIC Binding (SOLID-DIP)

**IS slot**: `AdversarialValidator` (MIC_v1.currentConcrete = "Naesengmoon")
**USES slots**: SubagentSeeder (렌즈셋별 병렬 출격 via taskspec)

**동적 resolution**:
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot {name:'AdversarialValidator'})
RETURN s.currentConcrete, s.invocation
```

**역할 대체 가능성 (L 원칙)**: 미래에 Naesengmoon 대신 다른 적대적 검증기로 교체 시 `MIC_v1.AdversarialValidator.currentConcrete` SET만. 소비자 skill은 본문 수정 불필요.

# KG: MIC_v1, ATOM_Skill_taliban, MethodologySlot:AdversarialValidator, lesson-apt-skill-drift-audit-2026-04-17

---

# /taliban — 적대적 검증 프레임워크: "이거 진짜 맞아?"

> **다른 방법론들이 "잘 만들자"라면, 나생문만 "이거 틀렸어"라고 말하는 놈이다.**
> Design = Generator, Naesengmoon = Discriminator. GAN의 적대적 협력.

---

## 입력

```
/taliban <target> [--lens <lensset>] [--depth quick|standard|deep]
```

- `target`: 검증 대상 (KG 노드 이름 또는 자유 텍스트)
- `--lens`: 렌즈셋 선택 (기본: `constitutional`)
  - `constitutional` — 9-lens, APT 산출물 품질 감사 (기본값)
  - `mathematical` — 113-lens, 수학적 구조 메타 검증 (정전: `THEORY/TALIBAN/113_LENS_TAXONOMY.md` — 13 domain × {8,9,10} = 113 enumerated, KG `LensSet:mathematical {count:113, closed:'2026-05-02'}`)
  - `solid` — 5-lens, SOLID 원칙 검증
  - 기타 KG에 `LensSet` 노드로 등록된 임의 렌즈셋
- `--depth`: quick(핵심만) | standard(전체, 기본) | deep(전체 + 교차 분석)

### 별칭 (thin alias)
- `/tlb <target>` = `/taliban <target>`
- `/88-taliban <target>` = `/taliban <target> --lens mathematical`

---

## 나생문이란 무엇인가

APT의 **유일한 적대적(adversarial) 역할**. 만드는 쪽이 아니라 **부수는 쪽**.

- Design이 Span을 분해하면 → Naesengmoon이 "이 분해 맞아?" 공격
- Design이 Contract를 쓰면 → Naesengmoon이 "이 명세 허술해" 공격
- Design이 코드를 짜면 → Naesengmoon이 "이 테스트 부족해" 공격
- 시스템/방법론 자체 → Naesengmoon이 "수학적으로 건전해?" X-ray

**GAN 원리**: Naesengmoon의 엄격도 ∝ 산출물의 정교도. 서로 강해진다.
**종료 조건**: Nash 균형 — 더 이상 새로운 맹점을 못 찾을 때.

---

## 출격 프로토콜 (모든 렌즈셋 공통)

### Step 0: 렌즈셋 결정

```cypher
// --lens 파라미터로 LensSet 로드
MATCH (ls:LensSet {name: 'lensset-' + $lens_param})
RETURN ls.name, ls.displayName, ls.lensCount, ls.tier, ls.description
```

`--lens` 생략 시 기본값 = `constitutional`.

### Step 1: 검증 대상 로드

```cypher
// KG에서 대상 로드
MATCH (target {name: $target_name})
RETURN target.name, labels(target), properties(target)
```

KG에 없으면 사용자 설명 기반으로 진행.

### Step 1.5: Steelman Preflight — **MANDATORY (drift block, lesson-naesengmoon-strawman-via-literal-formalization-2026-05-28)**

> **본 step 측 SKIP 시 strawman 적대 검증 발생**. 즉 target 의 *literal formalization* 만 공격하고 *weakest defensible form* 공격 안 함 → 진짜 defect 아닌 표면 over-formalization 만 까는 결과.
> 정전 사례 (2026-05-28): `lesson-trust-equals-inbound-citation-density-2026-05-28` 의 ≡ 기호가 사용자 casual 발화의 over-formalization 이었고, 나생문 L2 lens 가 ≡ 강식 literal 공격 → 사용자 "내가 그런 말 한 적 없다" 측 strawman 판정.

**Steelman 4 step**:
1. **target.literal_form** 추출 — KG 노드의 `truth` / `claim` / 정의 field 그대로.
2. **target.original_utterance 추적** — user_verdict 측 verbatim 또는 source 가 user direct utterance 인 경우 그 발화 원본 로드:
   ```cypher
   OPTIONAL MATCH (target)-[:CANONIZED_BY|ELABORATES*1..2]-(uu:UserUtterance)
   RETURN uu.verbatim, uu.user_verdict
   ```
3. **weakest_defensible_form 도출** — literal vs original 사이의 *가장 약한 defensible 해석*. 흔한 over-formalization 패턴:
   - 사용자 "X 자체가 Y" → AI 측 `X ≡ Y` (identity) — 실제는 monotone 또는 ⊇ 충분.
   - 사용자 "X 면 보통 Y" → AI 측 `∀X. Y` (universal) — 실제는 ∃ 또는 statistical.
   - 사용자 "X 가 Y 의 원인" → AI 측 `X ⟹ Y` (necessary+sufficient) — 실제는 contributing factor.
4. **공격 target swap** — Step 2 이후 모든 lens 측 *steelmanned form* 공격. literal form 공격은 *추가 정보* 로만 기록 (parent over-formalization detect 용).

**결정 분기**:
| 측 시나리오 | 측 verdict |
|---|---|
| steelmanned form 측 통과 + literal form 측 실패 | `STRAWMAN_DETECTED` → AdversarialChallenge target *parent over-formalization*, 측 user claim 아님 |
| 둘 다 실패 | 진짜 defect, lens 정상 verdict |
| 둘 다 통과 | clean, lens 정상 verdict |
| steelmanned form 측 실패 | strong defect, lens 정상 verdict |

**의무 cypher 기록**:
```cypher
MERGE (sp:SteelmanPreflight {name:'sp-' + $target_name + '-' + $cycle_id})
SET sp.literal_form = $literal,
    sp.original_utterance = $verbatim,
    sp.weakest_defensible_form = $steelmanned,
    sp.attacked_form = 'steelmanned',
    sp.over_formalization_detected = $bool,
    sp.checkedAt = datetime()
MERGE (target)-[:STEELMANNED_BY]->(sp)
```

**위반 시**: 본 cycle 의 ValidationResult 측 `steelman_skipped=true` 자동 tag → 추후 retroactive strawman audit 대상.

### Step 2: 렌즈 정의 로드

```cypher
// LensSet에 속한 모든 렌즈 로드
MATCH (ls:LensSet {name: 'lensset-' + $lens_param})-[:HAS_LENS]->(lens)
RETURN lens.name, lens.displayName, lens.category, lens.coreQuestion, lens.rules, lens.description
ORDER BY lens.category, lens.index
```

### Step 3: 재배맨 출격 (SubagentTaskSpec 씨앗 로드)

```cypher
// 해당 렌즈셋의 TaskSpec 씨앗 로드
MATCH (ls:LensSet {name: 'lensset-' + $lens_param})-[:HAS_TASKSPEC]->(ts:SubagentTaskSpec)
WHERE ts.status = 'READY'
RETURN ts.name, ts.role, ts.prompt_template
```

씨앗이 있으면 → 재배맨 프로토콜로 subagent 병렬 출격.
씨앗이 없으면 → 렌즈 정의 기반으로 직접 병렬 평가.

**각 subagent 출격 템플릿 (3줄 prompt):**
```
역할: Naesengmoon Discriminator (lens={lens_id}, agentId=D<idx>).
TaskSpec: MATCH (ts:SubagentTaskSpec {name: $taskspec_name}) RETURN *
실측 권한: Bash + CLI + MCP(neo4j/redis/postgres/mongodb).
Target: $TARGET.
출력: FullFindingRecord JSON (verdict: ✓/✗/N/A, evidence: 실측 결과 인용, provenance='재배맨-taliban',
      kg_write_intent_json: ValidationResult MERGE 의도만 — write 자체는 parent Step 5 수행).

**WRITE_DEFERRED_TO_PARENT (PROM 16 T3 2026-05-24 ship)**: 너는 KG 에 직접 write 할 수 없다.
ValidationResult / verdict 노드 MERGE 의도는 `kg_write_intent_json` field 에 JSON 으로만 반환.
실제 write 는 parent 가 Step 5 에서 수행. 금지 표현: `kg_writes_done=true` / "MERGE 완료" /
"verdict 기록 완료" / "VR 노드 생성" 류 claim. 단일 예외: `naesengmoon-ensemble-critic` agent
(~/.claude/agents/ 측 자체 mcp__neo4j__write_neo4j_cypher access 명시) — 그 경우도 parent
spot-check cypher count match mandatory.
```

### Step 4: 결과 집계

**렌즈셋 tier에 따라 집계 규칙 분기:**

#### Tier 1 (constitutional 등 — 산출물 검증): 만장일치

```
IF ANY lens returns REJECTED:
    → 전체 REJECTED (만장일치 필수)
    → REJECTED 사유 + 수정 지침 반환
ELIF ALL lenses return APPROVED:
    → 전체 APPROVED → 다음 Phase 진행 가능
```

#### Tier 2 (mathematical 등 — 메타 검증): 본질/우연 분류

```
모든 ✗에 대해:
IF "이 성질을 만족시키면 대상의 정체성이 바뀌는가?"
  → YES: 본질적 ✗ (수용, 바꾸면 안 됨)
  → NO:  우연적 ✗ (공략 대상, 개선 계획 수립)

우연적 ✗ = 0 → CLEAN_PASS
우연적 ✗ > 0 → HAS_ACCIDENTAL (개선 큐)
```

### Step 5: KG에 검증 결과 기록

```cypher
MERGE (vr:AbstractNode:ValidationResult {name: 'VR_' + $target + '_' + $lensset + '_' + $timestamp})
SET vr.verdict = $verdict,
    vr.lensSet = $lensset,
    vr.findings = $findings,
    vr.lens_results = $lens_results,
    vr.rejected_by = $rejected_lenses,
    vr.holds_count = $holds,
    vr.notHolds_count = $notHolds,
    vr.na_count = $na,
    vr.essential_notHolds = $essential,
    vr.accidental_notHolds = $accidental,
    vr.project = $project,
    vr.validated_at = datetime()
MERGE (target {name: $target_name})
MERGE (target)-[:HAS_VALIDATION]->(vr)
```

---

## Anti-Rubber-Stamp (고무도장 방지)

Naesengmoon이 무조건 APPROVED 찍으면 의미 없다. **모든 렌즈셋 공통.**

### RTI (Review Thoroughness Index)

```
RTI = findings_count / target_complexity
- RTI < 0.1 → 의심: 검증이 너무 피상적
- RTI 0.1~0.5 → 정상 범위
- RTI > 0.5 → 산출물이 심각하게 문제있거나 검증이 과도
```

### FVR (Finding Validation Rate)

```
FVR = valid_findings / total_findings
- FVR < 0.3 → 의심: finding이 대부분 거짓양성
- FVR 0.3~0.8 → 정상
- FVR > 0.8 → 대부분 진짜 문제 = 산출물 품질 낮음
```

### ⛔ HARD BLOCK: findings IS NOT NULL 강제

**ValidationResult 기록 전 반드시 확인:**

```
IF vr.findings IS NULL OR vr.findings = [] AND vr.verdict = 'APPROVED':
    → AUTOMATIC RUBBER_STAMP REJECTION
    → findings=null APPROVED는 KG에 기록 금지
    → 최소 1개 이상의 finding 또는 명시적 "근거 있는 0-finding" 선언 필수
```

**"근거 있는 0-finding" 선언 형식** (APPROVED 시 findings=[] 허용되는 유일한 케이스):

```cypher
SET vr.findings = [],
    vr.zero_finding_rationale = '재검증(v2): 이전 REJECTED VR의 4개 finding 전부 수정 확인됨. 새 맹점 없음.',
    vr.prior_vr = 'VR_XXX_v1'  // 수정 전 REJECTED VR 참조
```

재검증이 아닌 **최초 검증에서 findings=[] = HARD BLOCK.** 예외 없음.

### HR11: 증거 필수

**증거 없는 APPROVED = RUBBER_STAMP 위반.** subagent는 반드시 실측 결과 인용:
- Bash 출력 (error 라인, 0 exit code 등)
- CLI 도구 결과 (eslint count, mypy 오류 등)
- MCP 쿼리 반환값 (노드 수, 속성 값)

인용 없는 판정은 **자동 REJECTED** 처리.

### Defect Injection

의도적으로 알려진 결함을 산출물에 삽입 → Naesengmoon이 찾는지 확인.
못 찾으면 → 해당 lens 신뢰도 하락 → 재교정 필요.

---

## D20 적대적 라운드 (4단계)

모든 APT 게이트에 필수인 적대적 검증 프로세스:

```
1. Design agent 제안      → "이렇게 분해/명세/구현했다"
2. Critic agent 공격      → 다른 모델, 최소 3개 finding 필수
3. Ground truth 확인      → 테스트 실행, 실제 검증
4. sigma_oracle(인간) 판정 → 양쪽 보고서 보고 최종 결정
```

**규칙:**
- Critic은 **반드시 다른 모델** (같은 모델 = 같은 맹점, D22 증명)
- Critic은 최소 **3개 finding** 필수 (0개 = rubber stamp 의심)
- executor ≠ reviewer (자기 승인 금지)
- **D20 session boundary** (lesson-apt-sa-gate-rejected-v0.5-d20-loop-2026-04-17): parent가 같은 Claude 세션 안에서 subagent(다른 모델)를 dispatch해도 "부분 충족". parent가 문제 프레이밍·prompt·해석을 통제하므로 진짜 independence는 (a) 다른 Claude 세션 OR (b) sigma_oracle(인간) 명시 동의 필요. 같은 세션 re-gate 시 VR에 `d20_bypass` 필드로 사유 명시 (예: `sigma_oracle-consent-<trace>`).
- **sigma_oracle 옵션 (b) 명시 동의**: 사용자가 REJECTED verdict + findings 확인 **후에** "계속 진행" 류 발화 → Step 4 오라클 판정 충족. `VR.sigma_oracle_consent` 필드에 user-utterance 원문 기록. 우발적 동의는 무효 — 발화 시점이 findings 인지 후여야 함.

---

## Empirical Discriminator — 실측 검증

나생문은 단순 텍스트/KG 검증에 머물지 않는다. **실측까지 내려가 Discriminator 역할** 수행.

### 허용 도구 (subagent 출격 시)

| 도구 | 용도 | 예시 |
|---|---|---|
| **Bash** | 컴파일/테스트 실행, 스크립트 실측 | `npm test`, `pytest`, `lake build`, `cargo check` |
| **CLI** | 분석 프로그램 호출 | `eslint`, `mypy`, `shellcheck`, `hadolint` |
| **MCP neo4j** | KG 상태 직접 조회 | `mcp__neo4j__read_neo4j_cypher` |
| **MCP redis/postgres/mongodb** | DB 상태 실측 | 실제 데이터 존재 여부, TTL, 제약 위반 검증 |

---

## 렌즈셋 추가 방법 (OCP — 열린 확장)

새 렌즈셋 추가 = **KG에 3종 노드 MERGE만.** SKILL.md 수정 불필요.

### 1. LensSet 노드

```cypher
MERGE (ls:AbstractNode:LensSet {name: 'lensset-solid'})
SET ls.displayName = 'SOLID 5-Lens',
    ls.description = 'SOLID 원칙 기반 설계 검증',
    ls.lensCount = 5,
    ls.tier = 1,
    ls.isDefault = false,
    ls.createdAt = datetime()
```

### 2. LensDefinition 노드 + 연결

```cypher
MERGE (ld:AbstractNode:LensDefinition {name: 'lens-solid-srp'})
SET ld.displayName = 'SRP', ld.index = 1,
    ld.coreQuestion = '단일 책임을 가지는가?',
    ld.rules = 'Single Responsibility Principle ...',
    ld.category = 'solid'
WITH ld
MATCH (ls:LensSet {name: 'lensset-solid'})
MERGE (ls)-[:HAS_LENS]->(ld)
```

### 3. SubagentTaskSpec 씨앗 (선택사항)

```cypher
MERGE (ts:AbstractNode:SubagentTaskSpec {name: 'taskspec-taliban-solid-srp'})
SET ts.skill = 'taliban', ts.lensSet = 'solid', ts.status = 'READY',
    ts.prompt_template = '...'
WITH ts
MATCH (ls:LensSet {name: 'lensset-solid'})
MERGE (ls)-[:HAS_TASKSPEC]->(ts)
```

이후 `/taliban <target> --lens solid` 하면 자동 인식.

---

## 능동 렌즈 (Local N-lens) — 프로젝트별 동적 추가

기본 LensSet 위에 프로젝트가 채택한 validator를 동적 추가:

```cypher
// 프로젝트의 ADOPTS_VALIDATOR 조회 → 추가 lens
MATCH (anchor:SemanticAnchor {name: $project})-[:ADOPTS_VALIDATOR]->(v)
RETURN v.name AS validator, v.rules AS rules, v.lens_count AS lenses
```

예: MinecraftWASM → ECS + WASM + WebGL = +3 lens.

---

## 다른 방법론과의 관계

```
나생문 (면역 시스템)
  ├── 하네스의 Verify 축 실체
  ├── 프로메테우스: Naesengmoon finding이 Lesson 생성 촉발 가능
  ├── 롱기누스: Consistency lens가 sourceId/sourcePath drift 탐지
  └── APT: 매 Phase 게이트마다 Naesengmoon 통과 필수
```

---

## 메타사이클 연계 (--lens mathematical 전용)

같은 대상에 반복 적용하면 수렴:

```
1회차: 인상비평 (haiku 병렬) → 초기 판정
2회차: 분석기계 (형식 매핑) → 고무도장 제거, ✓ 감소
3회차: Lean 컴파일러 → 증명 가능한 것만 ✓, sorry = 미증명
4회차: 우연적 ✗ 공략 → 개선 → 재검증
수렴: 우연적 ✗ = 0 → CLEAN_PASS
```

---

## What NOT To Do

| 금지 | 이유 | 대안 |
|------|------|------|
| 일부 lens만 실행 | 부분 검증 = 맹점 | 선택한 LensSet 전부 실행 |
| 다수결로 PASS | 8/9 APPROVED여도 1 REJECTED면 실패 (Tier 1) | 만장일치 |
| 같은 모델로 Critic | 같은 맹점 공유 (D22) | 다른 모델 필수 |
| 0개 finding으로 APPROVED | 고무도장 | 최소 3개 finding |
| finding 무시하고 진행 | 면역 결핍 | 모든 finding 처리 후 재검증 |
| executor가 reviewer 겸임 | 자기 승인 = 면역 무력화 | 분리 의무 |
| 렌즈 추가에 SKILL.md 수정 | OCP 위반 | KG에 LensSet 노드 추가 |

---

*Naesengmoon은 적이 아니다. 적이 들어오기 전에 약점을 찾아주는 내부 면역 시스템이다.*
*렌즈는 갈아 끼우는 것이다. 프레임워크를 복제하지 마라.*

---

## 재배맨 v3 (MIC Slot Reference — 로직 복제 금지)

> 이 스킬의 subagent 운용은 **MIC_v1.SubagentSeeder** slot을 통해 resolve된다.

### Slot Resolve
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot {name:'SubagentSeeder'})
RETURN s.currentConcrete, s.invocation, s.protocol
```

### 렌즈셋별 씨앗 로드
```cypher
MATCH (ls:LensSet {name: 'lensset-' + $lens})-[:HAS_TASKSPEC]->(ts:SubagentTaskSpec)
WHERE ts.status = 'READY'
RETURN ts.name, ts.role, ts.prompt_template
```

### WorkBuffer 연속성
```cypher
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb
```

# KG: ATOM_Skill_taliban, ATOM_재배맨_v3_taliban, lensset-constitutional, lensset-mathematical

---

## 🪝 MCTS 훅 주입 (post-verdict)
<!-- # KG: CONTRACT_ATOM_P4_A1_mcts_hook, ATOM_P4_A1_mcts_hook, SPAN_P4_LoopClosure -->

Gate 판정 `APPROVED/CONDITIONAL_PASS/REJECTED/DEFERRED` 기록 직후, **부모 Claude가 MCP로** 아래 hook을 실행한다 (subagent는 MCP 상속 없음).

### Reward 매핑
```python
from reward_mapping import map_verdict_to_reward, TalibanVerdict, VerdictEnum
reward = map_verdict_to_reward(TalibanVerdict(
    verdict=VerdictEnum[$verdict_label],
    confidence=$confidence,
    lens_coverage={lens: score for lens, score in $lens_scores.items()},
))
```
정책: APPROVED → +1.0 base, CONDITIONAL_PASS → +0.5 base, REJECTED → -0.5 base, DEFERRED → 0.0. confidence 곱셈 + per-lens +0.05 bonus (cap 0.3). 최종 clamp `[-0.5, +1.3]`.

### KG write (mcts_hook_update.cypher 실행)
```
Bash: cat /Users/lagyeongjun/CD/SERVER/03_SCRIPTS/jaebaeman/mcts_hook_update.cypher 로드 후
MCP mcp__neo4j__write_neo4j_cypher 에 params={seed,reward,verdict,confidence,workBuffer} 전달.
```

Postcondition: `ts.visits = prev+1 AND ts.rewards = prev + reward AND EXISTS HarvestEvent HARVESTED→ts`.

### UCB1 lazy query (다음 선택 시)
다음 `/prom` 또는 `/apt-sa` Step 2.5에서 `ucb1_lazy_query.cypher`로 top-k 씨앗 조회:
```
UCB1 = avg_reward + sqrt(2 * ln(N_total) / visits)
visits = 0 → 1e18 (explore-first sentinel)
```

**루프 폐쇄의 심장**: 이 훅이 돌아야 재배맨이 학습한다 (visits 누적 → UCB1 signal → 다음 선택).

---

## History

> Repo-level changes: [`/CHANGELOG.md`](../CHANGELOG.md). Per-commit: `git log -- taliban/SKILL.md`.
> 학문 grounding: [`/PROM_16_SKILL_VERSIONING_REPORT.md`](../PROM_16_SKILL_VERSIONING_REPORT.md).

| Version | Date | Summary | KG Ref |
|---|---|---|---|
| **v3** | 2026-04-21~24 | LensSet 플러거블 (constitutional 9 / mathematical 113 / solid 5 / longinus 임의 등록 가능). 재배맨 SubagentTaskSpec 씨앗 기반 자동 출격. UCB1 lazy query (visits→reward signal) | `ATOM_Skill_taliban`, `lesson-feedback-is-emergent-not-weapon-2026-04-16` |
| **v2** | (~2026-04 mid) | --lens mathematical 5-round meta-verification (260✓→102✓ honest convergence). RTI/FVR (Rubber-Stamp 방지). HR11 evidence-backed verdicts. AptDecisionLog with override_reason | — |
| **v1** | (older) | 9 lens constitutional (GAN 의 D 역할, 만장일치 PASS) | — |

→ APT v22 Gate Check enforcement 의 면역계 mechanism. 88-taliban (v3) = `--lens mathematical` 별칭, tlb (v3) = thin alias.

# KG history: ATOM_Skill_taliban / lesson-prom16-skill-versioning-academic-2026-04-29

---

## Naesengmoon Customization Axes (Wave 9 2026-05-20)

> 사용자 통찰 2026-05-20: "케르베로스 나생문 만들면 되지 나생문이 customizing 가능한 건데". 나생문은 *plugin-style framework* — 5 axes로 invocation-time customizable. Cerberus는 새 무기가 아니라 *timing axis의 새 variant*.

### 5 axes

| Axis | 옵션 | Default | 비고 |
|---|---|---|---|
| **lens** | constitutional / mathematical / solid / longinus / lakatos / KG-registered | constitutional | `--lens X` 명시 |
| **cardinality** | N ∈ ℤ⁺ (simple 1:1) | 3 (3중) | `--cardinality N` 또는 자동 derive |
| **aggregation** | UNANIMOUS_PASS / MAJORITY / WEIGHTED | UNANIMOUS_PASS | Tier 1 strict |
| **timing** | cross-agent-retroactive / meta-sprint-self / **pre-emit-gate** | cross-agent-retroactive | Wave 9 add |
| **dispatch** | subagent dispatch (Agent tool) / hook trigger / module-import-time | subagent dispatch | timing에 따라 자동 |

### Timing variants (3개)

| Variant | 시점 | trigger | 산출물 |
|---|---|---|---|
| **cross-agent-retroactive** (default) | 작업 후 | parent dispatch via Agent tool | post-hoc ValidationResult, /tlb dispatch |
| **meta-sprint-self** | sprint 끝 | MetaReview SKILL.md mandate | apt-meta-review의 recursive self-meta-naesengmoon |
| **pre-emit-gate** (Cerberus) | 송신 전 | hook trigger every Write/Submit | placeholder_check.sh 3-head, hard-block on fail |

### Cerberus Naesengmoon (pre-emit-gate variant) — 3 heads

| Head | 검사 | 구현 |
|---|---|---|
| **(1) regex/syntactic** | 금지된 문자/패턴 (e.g., isolated banned char) | `~/.claude/hooks/placeholder_check.sh` (Wave 9 enhanced with COUNT_ISOLATED ≥3 threshold) |
| **(2) semantic overclaim** | "다 됐다" / "완벽" / "전부" 류 과장 | `numeric_check.sh` (pending install) |
| **(3) coherence claim-vs-KG** | 보고 숫자가 KG 실제값과 mismatch | `coherence_check.sh` (pending install) |

Aggregation: any head fail → submit hard-block + force rewrite.

### Naming hierarchy

- **Family root**: `naesengmoon-family-taxonomy-2026-05-20` (NaesengmoonFamily node)
- **Canonical**: `naesengmoon-canonical-2026-05-19` (Naesengmoon framework)
- **Variants (현재 3개)**:
  - `naesengmoon-ensemble-critic` (cross-agent-retroactive, canonical agent)
  - `apt-meta-review recursive self-meta-naesengmoon` (meta-sprint-self, Constrain Layer 3)
  - `naesengmoon-cerberus-variant-pre-emit-gate-2026-05-20` (pre-emit-gate, NaesengmoonVariant node)

# KG: naesengmoon-family-taxonomy-2026-05-20, naesengmoon-cerberus-variant-pre-emit-gate-2026-05-20, lesson-naesengmoon-gap-retroactive-only-2026-05-20

---

## Measurement & Conditional Dispatch (2026-05-30 추가)

사용자 정전 정정 2026-05-30 (`user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30`): 7군단장 측 *고정 USES edge* retract → *measurement-driven conditional dispatch*. 본 commander도 `measure()` + `decide_dispatch()` API를 따른다.

### 본 commander metric & threshold

- 정전 SPEC: `SYMPOSIUM/THEORY/00_공통/7CMD_NEED_BASED_DISPATCH_SPEC.md` §3 Table
- 구현: `bhgman_tool/engine/legion/measurement.py` — 본 commander의 talibanMeasurement class
- KG: `:MeasurementFunction` + `:DispatchThreshold` nodes (parent: `7cmd-measurement-driven-conditional-dispatch-2026-05-30`)

### Stevens scale type & 학문 grounding

각 metric의 Stevens 1946 scale type (nominal/ordinal/interval/ratio)을 `:MeasurementFunction.scale` field에 기록.
Goodhart drift (1975) mitigation은 Naesengmoon meta-check 또는 cycle-end invocation-log empirical reconcile (`lesson-occam-proxy-strength-needs-empirical-spot-check-2026-05-28`).

### Dispatch 정전

`measure()` → threshold-gated need detection → 다른 commander conditional invocation (Hades realization pattern universalized, parent `hades-canonical-2026-05-27`).
고정 USES는 *historical provenance only* (`:DispatchEvent` runtime record).

# KG: 7cmd-measurement-driven-conditional-dispatch-2026-05-30, user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30, hades-canonical-2026-05-27, mf-taliban-*
