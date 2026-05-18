---
name: taliban
kg_ref: ATOM_Skill_taliban
version: "3.1.0"
channel: stable
description: >
  나생문 방법론 — APT의 면역 시스템. 적대적 검증 프레임워크.
  렌즈셋 플러거블: --lens constitutional(기본 9), mathematical(113), solid(5), 또는 KG에 등록된 임의 LensSet.
  Invoke when: Span 검증, Contract 검증, 코드 리뷰, Phase 게이트 통과 판정,
  품질 감사(audit), 고무도장 방지, 기존 산출물 재검증, 메타 검증 시.
  Enforces: 렌즈셋 동적 로딩, GAN 원리 (Design=G, Naesengmoon=D),
  동시 출격, 만장일치 PASS, Anti-Rubber-Stamp (RTI/FVR).
  재배맨 SubagentTaskSpec 기반 자동 출격.
  # KG: ATOM_Skill_taliban, MIC_v1.ReasoningProtocol→KGFirstCheck_v1 (R1-R5 mandatory before any framing/diagnostic, lesson-ai-skipped-kg-check-before-framing-2026-04-29)
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
출력: FullFindingRecord JSON (verdict: ✓/✗/N/A, evidence: 실측 결과 인용, provenance='재배맨-taliban').
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
