---
name: tpa-tcw
kg_ref: ATOM_Skill_tpa_tcw
version: "1.2.0"
channel: stable
provenance: AI_DERIVED_FROM_USER_PRIMARY  # SKILL.md = AI engineering; underlying methodology = user-primary mythology (12 apostles + 5 weapons). Per PseudepigraphaValidationGate-v1-2026-04-30.
description: >
  TPA TargetCodeWorld (TCW) — Phase 1/4. APT SCW 거울 (역순).
  외부/레거시 코드에서 실제 존재하는 모든 것을 기록. AST 기반 pub 심볼 추출.
  Unknown 발견시 ResearchProvider 자동 호출. 종료시 AdversarialValidator gate.
  Gate Check Hook 강제: TCW는 시작 스킬이라 pre-gate 없음. 종료시 VR 기록.
  # KG: ATOM_Skill_tpa_tcw, CONTRACT_AS_TPA_tcw_SKILL, TPA_methodology_v10
---

<!-- KG: TASK_AS_TPA_tcw_SKILL -->
<!-- KG: CONTRACT_AS_TPA_tcw_SKILL -->
<!-- KG: IMPLEMENTS_SHARED CONTRACT_SHARED_TPA_SubSkillTemplate -->

## 🔗 MIC Binding (SOLID-DIP)

**IS slot**: TPA_Phase (TCW, 1/4)
**USES slots**: SubagentSeeder (진입 taskspec), ResearchProvider (unknown), KgCodeBinder (SourceBinding), AdversarialValidator (종료 gate)

```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
WHERE s.name IN ['SubagentSeeder','ResearchProvider','KgCodeBinder','AdversarialValidator']
RETURN s.name, s.currentConcrete, s.invocation
```

> ⚠️ **본문의 `재배맨`/`Prometheus`/`Naesengmoon`/`Longinus`/`88-Naesengmoon`은 MIC slot의 현재 스냅샷.**
> 진짜 호출은 항상 `s.invocation` 경유 (`/tlb`, `/prom`, `/longinus`, `/88-taliban`, taskspec 조회).
> `MIC_v1` 업데이트(예: AdversarialValidator.currentConcrete = "FutureValidator")되면 본문 수정 불필요.

# KG: MIC_v1, lesson-tpa-surface-scan-shortcut-2026-04-15, lesson-skill-mic-slot-ref-weak-2026-04-15

---

# /tpa-tcw — TargetCodeWorld: 코드가 스스로 말하게

> **질문**: "이 코드에 실제로 존재하는 것은 무엇인가?"
> 가정 금지. grep 단독 금지. AST가 정본.

## ⛔ GATE CHECK (Hook 강제)

> `apt-gate-check.sh`가 자동 실행. 본 스킬은 **시작 스킬(Phase 1/4)**이므로 pre-gate 없음.
> 대신 **종료시 TCW Gate 기록** 필수 → 미기록 시 `/tpa-st` 진입 차단.

---

## 진입 의식 (재배맨 — 첫 동작 강제)

```cypher
MATCH (ts:SubagentTaskSpec {name:'taskspec-tpa-TCW', skill:'tpa'})
RETURN ts.checkItems, ts.cypherQueries, ts.expectedOutcome,
       ts.treasure_coverage_min, ts.parallelism_min
```

**taskspec 조회 스킵 = 재배맨 bypass = gap02 재발**. 스킬 진입 최초 호출이어야 함.

---

## 실행 순서

### 1. Target 확정
```
TARGET = $1 (path argument)
MERGE (exec:TPA_Execution {name:'TPA_exec_<target_id>_<date>'})
SET exec.target=$TARGET, exec.phase_current='TCW', exec.started_at=datetime(),
    exec.status='IN_PROGRESS_TCW'
```

### 2. AST 기반 심볼 추출 (grep 단독 금지)

**tree-sitter 또는 언어별 파서 필수**:
- JS/TS: `@babel/parser` 또는 tree-sitter-javascript
- Rust: `syn` crate 또는 tree-sitter-rust
- Python: `ast` 모듈
- Go: `go/ast`

**추출 대상**:
- `pub class / fn / struct / enum / trait / type / export default / module.exports`
- inheritance/extends/implements 그래프
- import/use 그래프
- docstring pre/postcondition 주석

### 3. Manifest Generation + 재배맨 병렬 분산 (LOC > 10K 시 필수)

<!-- KG: lesson-tpa-missing-manifest-step-2026-04-16, lesson-tpa-conceptual-vs-file-chunking-2026-04-16 -->

#### Step 3.0: Manifest 생성 (부모 필수 — 에이전트 위임 금지)

**에이전트에게 "디렉토리 스캔해"는 모호한 지시다. 반드시 명시적 파일 목록을 준다.**

```bash
# 1. 전체 파일 목록 수집 (production only — test/fixture 명시 제외)
# KG: lesson-tpa-loc-test-included-2026-04-16
find $TARGET -name '*.rs' \
  -not -path '*/target/*' \
  -not -path '*/tests/*' \
  -not -path '*/test/*' \
  -not -path '*/fixtures/*' \
  -not -path '*/benches/*' \
  | sort > /tmp/manifest.txt

# 2. 파일별 LOC 측정
while read f; do echo "$(wc -l < "$f") $f"; done < /tmp/manifest.txt | sort -rn > /tmp/manifest_loc.txt

# 3. 총 LOC 확인 (production LOC)
total_loc=$(awk '{s+=$1} END {print s}' /tmp/manifest_loc.txt)

# 4. ⚠️ 교차 검증 — 에이전트 보고 숫자를 절대 무비판 신뢰하지 마라
# KG: lesson-tpa-tcw-no-cross-verify-2026-04-16
grep -r 'pub struct' --include='*.rs' $TARGET | grep -v '/target/' | grep -v '/tests/' | wc -l  # → pub struct 실측
grep -r 'pub trait' --include='*.rs' $TARGET | grep -v '/target/' | grep -v '/tests/' | wc -l   # → pub trait 실측
grep -r 'pub enum' --include='*.rs' $TARGET | grep -v '/target/' | grep -v '/tests/' | wc -l    # → pub enum 실측
# 에이전트 합산과 ±10% 이내 일치 확인. 불일치 시 보충 스캔.
```

#### Step 3.0-A: Manifest ↔ KG 정합 + #KG referent 검증 (TPA-D1/D5 fix, 2026-06-01)

<!-- KG: TPA-D1-2026-06-01, TPA-D5-2026-06-01 (:MethodologyDefect), lesson-tpa-dogfood-spacegirl-defects-2026-06-01 -->

> **결함 출처**: spacegirl_tool 도그푸드 — `__init__.py` 가 manifest·KG 양쪽서 누락(orphan)됐는데 Gate Hook 부재로 미차단(D1). 그리고 `# KG:` 주석 referent의 *실존*을 ST가 확인 안 해 binding 없는데 confirmed 오판(D5).

**D1 — manifest는 패키지 파일 *전체*(엔트리포인트 포함)로 만들고 KG와 대조**:

```bash
# __init__.py / mod.rs / index.ts 등 엔트리포인트도 manifest에 포함 (이전엔 누락)
# (production 한정은 유지, 단 __init__/__main__ 류 패키지 엔트리는 제외하지 말 것)
manifest_count=$(wc -l < /tmp/manifest.txt)
```
```cypher
// KG HAS_SOURCE 수와 manifest 수 대조 → 불일치 = orphan/missing flag
MATCH (proj:SoftwareProject {name:$project})-[:HAS_SOURCE]->(scn:SourceCodeNode)
RETURN count(scn) AS kg_sources    // != manifest_count → TR_ManifestKgMismatch 위반
```

**D5 — `# KG:` referent 실존 자동 확인** (TCW 수확 시 mandatory):

```bash
# 각 파일의 # KG: 주석에서 referent name 추출
grep -rhoE '# KG:[^#]*' $TARGET | grep -oE '[A-Za-z0-9_가-힣-]{6,}' | sort -u > /tmp/kg_referents.txt
```
```cypher
// 추출된 referent 가 KG에 실재하나 — 없으면 dangling 바인딩
UNWIND $referents AS ref
OPTIONAL MATCH (n {name:ref})
WITH ref, n WHERE n IS NULL
RETURN collect(ref) AS dangling_referents   // 비어있지 않으면 TR_DanglingKgRef 위반 flag
```
- `dangling_referents` 비어있지 않음 → 해당 `# KG:` 는 "binding confirmed" 로 세지 **않음**. ST coverage 에서 제외 + lesson 기록.

#### Step 3.1: 에이전트 수 결정 (LOC 상한 기반)

| 모델 | 에이전트당 LOC 상한 | 근거 |
|------|-------------------|------|
| haiku | **5K** | 8K+에서 품질 저하, 파일 드롭 시작 |
| sonnet | **10K** | 15K+에서 우선순위 낮은 파일 탈락 |
| opus | **20K** | 대규모 컨텍스트 처리 가능 |

```
N_agents = ceil(total_loc / LOC_LIMIT_PER_MODEL)
# 예: 39K LOC + sonnet → ceil(39000/10000) = 4 agents
# 예: 39K LOC + haiku → ceil(39000/5000) = 8 agents
```

> ⚠️ **N_agents Agent() 호출은 반드시 jaebaeman Phase 2 (single-message multi-call) 규약을 따른다** — N개 모두 하나의 assistant message tool_use array 안에 emit. for-loop turn 분산 = sequential drift (GH#29181), file-bucket parallelism 자체가 무효. 정전: `SKILLS/jaebaeman/references/phases.md §Phase 2 L36-65`.
>
> # KG: finding-prom16-parallelism-bhgman-dep-D4 (GAP-2 patch, 2026-05-19)

#### Step 3.2: 파일 단위 균등 분배 (디렉토리 단위 아님!)

<!-- KG: lesson-tpa-directory-instruction-ambiguity-2026-04-16 -->

**규칙: 개념 영역이 아닌 파일 목록으로 분할. 경계 겹침 = 0.**

```python
# 의사코드: 파일별 LOC 내림차순 → 라운드로빈 분배
files = sorted(manifest_loc, key=lambda x: x.loc, reverse=True)
buckets = [[] for _ in range(N_agents)]
bucket_sizes = [0] * N_agents

for file in files:
    min_bucket = argmin(bucket_sizes)
    buckets[min_bucket].append(file.path)
    bucket_sizes[min_bucket] += file.loc
```

#### Step 3.3: 에이전트 프롬프트에 파일 목록 직접 주입

```
역할: TPA TCW AST scanner (agentId=D{idx})
스캔 대상 파일 (정확히 이 파일들만 읽을 것):
  - /path/to/file1.rs (523 lines)
  - /path/to/file2.rs (891 lines)
  - /path/to/file3.rs (142 lines)
  ... (총 {len} 파일, {loc} LOC)

⚠️ feature-gated 코드(#[cfg(feature=...)])도 동등하게 스캔할 것. 축약 금지.
⚠️ feature flag 목록도 보고할 것.
```

#### Step 3.4: 부모 post-dispatch 커버리지 검증

```
dispatched_files = union(agent_0_files, agent_1_files, ..., agent_N_files)
manifest_files = set(manifest.txt)

assert dispatched_files == manifest_files, f"COVERAGE GAP: {manifest_files - dispatched_files}"
# 불일치 시 보충 에이전트 출격
```

#### Step 3.5: 에이전트 결과 수거 + 교차 검증

<!-- KG: lesson-tpa-tcw-no-cross-verify-2026-04-16 -->

```
→ 각 agent: FullFindingRecord JSON 반환 (provenance='재배맨-tpa-tcw')
→ 부모: 에이전트 합산 vs grep 실측 교차 검증 (±10% 허용)
→ 불일치 시: 보충 스캔 또는 수치 교정
→ 검증 통과 후: UNWIND 단일 트랜잭션으로 KG merge
```

**⚠️ 에이전트 보고 숫자를 절대 무비판 신뢰하지 마라.**
에이전트는 자기 담당 파일만 세고 전체를 안 본다. 부모가 grep 실측으로 반드시 교차 검증.

### 4. Unknown 발동 (gap01)

```cypher
MATCH (s:MethodologySlot {name:'ResearchProvider'})
RETURN s.invocation AS auto_call
```
각 unknown (모르는 lib/protocol/pattern)에 대해 `{auto_call} <unknown>` 호출.
결과는 KnowledgeNode로 저장 + TCW_Result에 `INFORMED_BY`.

### 5. 결과 기록

```cypher
MERGE (tcw:TPA_TCW_Result {name:'TCW_<target>_<date>'})
SET tcw.sourcePath=$TARGET,
    tcw.sourceId='tpa-tcw-'+$target_id,
    tcw.totalFiles=$n, tcw.totalLOC=$loc, tcw.language=$lang,
    tcw.pubSymbols=$sym_count,  // AST 카운트, grep 아님
    tcw.inheritance_tree_nodes=$ih,
    tcw.import_graph_edges=$ie,
    tcw.subsystems=[...], tcw.architectural_guess=$guess,
    tcw.architectural_hypotheses=[H1,H2,...],
    tcw.unknown_research_called=$count,
    tcw.skipped_files=0,  // ZERO ONLY
    tcw.parallelism_used=$N
MERGE (exec)-[:PHASE_OUTPUT {order:1}]->(tcw)
```

---

## FulfillmentGate TCW (9 checks — v3)

<!-- KG: lesson-taliban-not-auto-triggered-2026-04-16, lesson-tpa-tcw-no-cross-verify-2026-04-16 -->

1. [ ] **AST 파서 사용됨** (grep 단독 → FAIL)
2. [ ] **skipped_files = 0** (모든 대상 파일 스캔)
3. [ ] **unknown_dirs 전부 ResearchProvider 처리** (outstanding = 0)
4. [ ] **architectural_guess + hypotheses 채워짐** (최소 3개 H)
5. [ ] **taskspec.checkItems 전부 pass**
6. [ ] **treasure_coverage_min 만족** (기본 0.9)
7. [ ] **TCW_Result + PHASE_OUTPUT order=1 엣지 존재 + sourcePath+sourceId SET 확인**
8. [ ] **grep 교차 검증 완료** — 에이전트 합산 vs grep 실측 ±10% 이내 (pub struct/trait/enum 각각)
9. [ ] **Naesengmoon subagent 최소 1개 독립 실행 완료** — VR.provenance MUST contain 'subagent' (인라인 APPROVED 금지)

하나라도 실패 → `status='INCOMPLETE'` 기록 후 중단.

---

## 종료 의식 — Naesengmoon subagent 자동 출격 (강제, 선택 아님)

<!-- KG: lesson-taliban-not-auto-triggered-2026-04-16, lesson-tpa-gate-self-approved-2026-04-16 -->

**⚠️ 부모가 직접 APPROVED 찍는 것은 금지. Naesengmoon subagent를 반드시 출격시켜라.**
**⚠️ 사용자가 "확인해봐"라고 안 해도 자동으로 실행해야 한다.**

```
# 1. 자동 Naesengmoon subagent 출격 (최소 1개, 권장 3개)
Agent(model=sonnet, prompt="You are an ADVERSARIAL REVIEWER. Verify TPA TCW claims...")

# 2. subagent 결과로만 VR 생성 (부모 인라인 판정 금지)
# VR.provenance MUST be 'subagent-taliban-*', NOT 'inline-parent'
```

```cypher
MERGE (vr:ValidationResult {name:'VR_TPA_TCW_<target>_<date>', phase:'TCW'})
SET vr.verdict=$subagent_verdict,  // subagent가 결정, 부모가 결정 아님
    vr.evidence=$subagent_evidence,
    vr.validated_at=datetime(),
    vr.provenance='subagent-taliban-tcw',  // 'inline' 이면 Hook에서 차단
    vr.validator='Naesengmoon-9lens'
MATCH (exec:TPA_Execution {name:'TPA_exec_<target>_<date>'})
MERGE (exec)-[:HAS_VALIDATION]->(vr)
```

**APPROVED 아니면 `/tpa-st` Gate Check에서 차단됨.**
**provenance가 'subagent-*'가 아니면 향후 Hook 업데이트에서 차단 예정.**

---

## Treasure Coverage

taskspec.treasure_coverage_min ≥ 0.9 (권장). 아래 두 treasure 강제:
- KgCodeBinder: 파일 스캔 95%+ 바인딩
- ResearchProvider: unknown 100% 리서치

미만이면 phase FAIL, VR verdict=REJECTED.

---

## What NOT to Do

| 금지 | 이유 | KG ref |
|---|---|---|
| grep 단독 스캔 | 주석/문자열 오인 → false symbol | |
| skipped_files > 0에 gate PASS | 부분 스캔 = 사각지대 | |
| unknown skip | 지식 공백 누적 | |
| Naesengmoon gate 셀프 APPROVED | rubber-stamp (D20 위반) | |
| ValidationResult 직접 verdict 작성 | AdversarialValidator 실제 호출해야 함 | |
| 재배맨 taskspec 조회 생략 | 컨텍스트 오염 + 병렬 기회 상실 | |
| **디렉토리명으로 에이전트 지시** | 하위 디렉토리 재귀 탐색 안 됨. "all .rs in dir" → `ls`만 실행 | lesson-tpa-directory-instruction-ambiguity-2026-04-16 |
| **개념 영역 분할** | 경계 겹침 → 양쪽 다 스킵. 파일 목록 분할만 허용 | lesson-tpa-conceptual-vs-file-chunking-2026-04-16 |
| **feature-gated 코드 축약** | `#[cfg(feature)]`는 미래 핵심이거나 분기 아키텍처. 동등 스캔 필수 | lesson-tpa-feature-gate-blind-spot-2026-04-16 |
| **manifest 없이 에이전트 출격** | 부모가 find 안 하고 에이전트에 발견 위임 → 누락 불가피 | lesson-tpa-missing-manifest-step-2026-04-16 |
| **에이전트당 LOC 상한 초과** | haiku 5K, sonnet 10K 초과 시 자연 탈락 발생 | lesson-tpa-context-saturation-dropout-2026-04-16 |

---

## Post-Gate Reflection (TR9 — 필수)

매 gate 통과 후 아래 형식으로 reflection 작성. 미작성 = INCOMPLETE_GATE.

```
REFLECTION:
  DISCOVERED: <이번 phase에서 발견한 핵심>
  LESSON: <lesson-name 또는 "신규 없음">
  QUALITY_ACTION: <333에 적용할 구체적 개선안>
  NEXT_GATE_CHECKS: <다음 gate에서 추가로 확인할 것>
```

---

## Lesson 자동 생성 (TR10)

QualityGap 또는 AntiPattern 발견 시 즉시:
```cypher
MERGE (l:AbstractNode:Lesson {name:'lesson-tpa-tcw-<finding>-<date>'})
SET l.category='tpa-tcw', l.problem=$problem,
    l.severity=$severity, l.resolved=false, l.createdAt=datetime()
```

---

## References

- `../tpa/references/shared_subskill_template.md` — 6 섹션 공통 템플릿
- `../tpa/references/tcw_playbook.md` — 언어별 AST 레시피 (향후 작성)
- Prior execution: `TPA_exec_puter_2026-04-15` (SURFACE_SCAN, 반례)
- Mirror: `apt-scw` (4/4, 생성)
- Gap lessons: `lesson-tpa-gap-01~08`, `lesson-tpa-surface-scan-shortcut-2026-04-15`

---

## 🌱 재배맨 바인딩 (KG-first Subagent 재배)

> **원칙**: SKILL.md는 **얇은 엔트리**. 긴 로직은 KG `SubagentTaskSpec` 씨앗에 보관. Subagent에 SKILL.md 전체 주입 금지(Anti-Context-Rot). KG 조회 → 97% 컨텍스트 절감.

### 세션 진입 시 (자동 로드)
```cypher
// WorkBuffer 복원
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb
// 진행 중인 TPA Execution
MATCH (e:TPA_Execution) WHERE e.phase_current='TCW' AND e.status='IN_PROGRESS_TCW'
RETURN e.name, e.target, e.started_at ORDER BY e.started_at DESC LIMIT 3
// TCW 씨앗
MATCH (ts:SubagentTaskSpec {skill:'tpa', phase:'TCW'})
RETURN ts.name, ts.checkItems, ts.parallelism_min, ts.treasure_coverage_min
```

### Subagent 출격 템플릿 (3줄 — KG가 본체)
```
역할: TPA TCW AST scanner (agentId=D<idx>)
TaskSpec: MATCH (ts:SubagentTaskSpec {name:'taskspec-tpa-TCW'}) RETURN ts.checkItems, ts.cypherQueries, ts.expectedOutcome, ts.parallelism_min
Target: $TARGET_SUBDIR. 출력: FullFindingRecord JSON (provenance='재배맨-tpa-tcw', sourceKgBindings=[ts.name]).
```

- 부모는 결과 UNWIND 단일 트랜잭션으로 KG merge
- SKILL.md 본문 복제 금지 (drift 방지)

### 새 씨앗 심기 (TaskSpec 템플릿)
```cypher
MERGE (ts:SubagentTaskSpec {name:$name})
SET ts.skill='tpa', ts.phase='TCW',
    ts.displayName=$display, ts.description=$desc,
    ts.checkItems=$checks, ts.cypherQueries=$queries,
    ts.expectedOutcome=$outcome,
    ts.parallelism_min=$N, ts.treasure_coverage_min=$cov,
    ts.status='READY', ts.createdAt=datetime()
```

### 세션 종료 시 (연속성 보장)
```cypher
MATCH (w:WorkBuffer) WHERE w.status='CURRENT' SET w.status='ARCHIVED', w.archived_at=datetime()
MERGE (wb:WorkBuffer {name:$next_name})
SET wb.status='CURRENT', wb.phase='TPA TCW in progress', wb.pending=$pending, wb.updated_at=datetime()
```

---

## MIC Binding Disclaimer

> 이 SKILL.md에서 "Prometheus", "Naesengmoon", "88-Naesengmoon", "Longinus", "재배맨" 등의
> concrete 이름은 MIC_v1 MethodologySlot의 **현재 바인딩(currentConcrete)**이다.
> Slot이 다른 concrete로 교체되면 이 파일의 이름도 drift한다.
> 정본 해석: `MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s) RETURN s.name, s.currentConcrete`
> 유틸리티: `03_SCRIPTS/db/resolve_mic_slot.cypher`
> # KG: lesson-skill-mic-slot-ref-weak-2026-04-15

# KG: ATOM_재배맨_autoboot_tpa-tcw
