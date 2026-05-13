---
name: longinus
kg_ref: ATOM_Skill_longinus
version: "3.2.0"
channel: stable
description: >
  롱기누스 방법론 v3.1 — 참조의 미학. KG 의미 계층을 소스코드까지 관통(貫通)시키는 참조 바인딩.
  v3: 7-Layer Reference Model + BX Lens Laws + Refinement Types + GED Drift 정량화.
  v3.1: Reverse Orphan Scan (Code→KG blind-spot fix) + Crate/Script-level binding + Taliban --lens longinus.
  Invoke when: ST→SCW 전환 후 코드가 물질화되었을 때, KG 노드와 소스코드 간 추적성 확보가 필요할 때,
  기존 코드베이스를 KG에 역매핑할 때, Contract-Code 정합성 감사(audit) 시.
  Enforces: 7-layer ref model, BX lens laws (GetPut/PutGet), branded types, GED drift metrics.
  # KG: ATOM_Skill_longinus, SA_methodology_v4_triple_upgrade, MIC_v1.ReasoningProtocol→KGFirstCheck_v1 (R1-R5 mandatory before any framing/diagnostic, lesson-ai-skipped-kg-check-before-framing-2026-04-29)
---

## 🔗 MIC Binding (SOLID-DIP)

**IS slot**: `KgCodeBinder` (MIC_v1.currentConcrete = "Longinus")

**역할 대체 가능성 (L 원칙)**: 미래에 다른 KG-code 바인딩 메커니즘(예: AST tagging)으로 교체 시 `MIC_v1.KgCodeBinder.currentConcrete` SET만.

# KG: MIC_v1, MethodologySlot:KgCodeBinder, lesson-apt-not-truly-jaebaeman-2026-04-14

---

# /longinus — 롱기누스 방법론: KG↔SourceCode 관통 바인딩

> **롱기누스의 창이 관절을 관통하듯, KG의 의미 계층 사이사이를 소스코드 참조로 꿰뚫는다.**
> Span → Twin → Contract → SourceCode — 어느 층에서 시작하든 코드까지, 코드에서 어느 층까지든 추적 가능.

---

## 참조의 미학 (Aesthetics of Reference)

> **최소 엔트로피로 최대 의미를 관통한다.**
> `# KG: lesson-xxx` 한 줄이 아름다운 이유 — 7개 의미 층위를 동시에 관통하기 때문이다.

---

## 7-Layer Reference Model (v3 신규)

CS에서 "참조"는 단일 개념이 아닌 **7개 독립 의미 층위의 번들**이다.
롱기누스의 이중 ref(sourceId+sourcePath)는 이 7개 층위를 동시에 관통한다.

| Layer | 이름 | 정의 | 롱기누스 대응 |
|:-----:|------|------|-------------|
| L1 | Address Indirection | 메모리 주소, 포인터 | sourcePath (파일:라인) |
| L2 | Lifetime/Scope | 참조의 유효 범위 | pierced_at / drift_detected |
| L3 | Type Permission | 소유권, 읽기/쓰기 권한 | Refinement Type (ValidSourceRef) |
| L4 | Semiotic Binding | 기표→기의 (Frege Sinn/Bedeutung) | sourceId = Sinn, sourcePath = Bedeutung |
| L5 | Distributed Identity | 합의 기반 참조 유효성 | KG MERGE (멱등, consensus) |
| L6 | Information Compression | 간접참조 = 중복제거 | `# KG: xxx` = Kolmogorov 압축 |
| L7 | Aesthetic/Intentional | 참조의 미학, 관통의 의도 | 최소 침습으로 최대 추적 |

**Drift는 각 Layer에서 다르게 발현한다:**

| Layer | Drift 유형 | 탐지 방법 |
|:-----:|-----------|----------|
| L1 | sourcePath 라인 번호 이동 | LSP/tree-sitter 심볼 추적 |
| L2 | 참조 유효 범위 초과 (파일 삭제) | `grep -rn` + 파일 존재 확인 |
| L3 | 타입 불일치 (함수 시그니처 변경) | AST semantic diff (GumTree) |
| L4 | 의미 변경 (리팩토링��로 이름 변경) | sourceId rename detection |
| L5 | KG 노드 삭제/이동 | MATCH (n {name: $id}) IS NULL |
| L6 | 중복 참조 발생 (같은 대상 다중 ref) | findingId hash collision check |
| L7 | 미학 위반 (과도한 참조, 노이즈) | pierce_rate < threshold |

# KG: lesson-cs-reference-semantics-2026-04-16, lesson-longinus-rigor-theories-2026-04-16

---

## BX Lens Laws (v3 신규)

롱기누스의 양방향 추적은 **Bidirectional Transformation(BX)** 이론의 Lens로 형식화된다.

```
GET: KG → Code  (sourceId/sourcePath로 코드 위치 조회)
PUT: Code → KG  (코드 변경 시 KG 참조 갱신)
```

### 3대 Lens Law

| Law | 정의 | 롱기누스 의미 | 위반 시 |
|-----|------|-------------|---------|
| **GetPut** | put(s, get(s)) = s | KG 조회 후 변경 없이 다시 쓰면 KG 불변 | Orphan edge 생성 |
| **PutGet** | get(put(s, v)) = v | 코드 변경→KG 갱신 후 조회하면 새 값 반환 | Stale reference |
| **PutPut** | put(put(s,v1),v2) = put(s,v2) | 연속 갱신 시 마지막 ��만 유효 | LWW conflict |

**Drift = Lens Law Violation.** 5종 drift를 law 위반으로 재정의:

| Drift Type | 위반 Law | 의미 |
|-----------|---------|------|
| Missing | PutGet | 코드 존재하나 KG에 ref 없음 |
| Orphan | GetPut | KG에 ref 있으나 코드에 대응 없음 |
| SigMismatch | PutGet | ref 있으나 시그니처 불일치 |
| PatternDiv | PutPut | 동일 대상에 상충하는 ref |
| LabelRot | PutPut | 라벨/이름 변경 미반영 |

# KG: finding_D20_bx_foundations, finding_D1_fv_algorithms

---

## Refinement Types for References (v3 신규)

sourceId/sourcePath는 **단순 문자열이 아닌 branded type**이다.

```typescript
// Branded Types (Zod-style)
type SourceId = string & { readonly __brand: 'SourceId' };
type SourcePath = string & { readonly __brand: 'SourcePath' };

// Refinement Type
type ValidSourceRef = {
  sourceId: SourceId;       // 의미적 식별자 (Frege Sinn)
  sourcePath: SourcePath;   // 물리적 위치 (Frege Bedeutung)
  resolvable: true;         // grep/LSP로 실제 존재 확인
  driftScore: 0;            // GED 기반 drift = 0
};
```

### SHACL Shape (KG 제약)

```turtle
:SourceCodeNodeShape a sh:NodeShape ;
  sh:targetClass :SourceCodeNode ;
  sh:property [
    sh:path :sourceId ;
    sh:minCount 1 ;
    sh:datatype xsd:string ;
    sh:pattern "^[A-Z][a-zA-Z0-9]*\\.[a-zA-Z][a-zA-Z0-9]*$" ;  # Module.function
  ] ;
  sh:property [
    sh:path :sourcePath ;
    sh:minCount 1 ;
    sh:pattern "^[a-zA-Z0-9/._-]+:[0-9]+(-[0-9]+)?$" ;  # file:line(-end)
  ] .
```

# KG: finding_D12_tt_foundations, finding_D14_tt_tools

---

## GED Drift Quantification (v3 신규)

Drift를 **Graph Edit Distance(GED)**�� 정량 측정한다.

```
GED(G_kg, G_code) = Σ(cost_insert + cost_delete + cost_relabel)

Drift Score = GED / max(|V_kg|, |V_code|)
```

| Drift Score | 상태 | 조치 |
|:-----------:|------|------|
| 0.00 | PIERCED (완전 관통) | 정상 |
| 0.01-0.05 | MINOR_DRIFT | 월간 audit에서 자동 보정 |
| 0.05-0.15 | MODERATE_DRIFT | 즉시 수동 검토 |
| > 0.15 | CRITICAL_DRIFT | 관통 해제, 재매핑 필수 |

### 주간 Drift Audit CronJob

```cypher
// 전체 pierce rate + drift score 대시보드
MATCH (ct:AptContract)-[:MATERIALIZES]->(src:SourceCodeNode)
WITH count(*) AS total,
     sum(CASE WHEN src.sourceId IS NOT NULL AND src.sourcePath IS NOT NULL THEN 1 ELSE 0 END) AS pierced,
     sum(CASE WHEN src.drift_detected = true THEN 1 ELSE 0 END) AS drifted
RETURN total, pierced, drifted,
       toFloat(pierced)/total * 100 AS pierce_rate_pct,
       toFloat(drifted)/total AS drift_ratio
```

# KG: finding_D9_gt_algorithms, finding_D8_gt_foundations

---

## 왜 롱기누스인가

APT의 ST(SemanticTwin)는 **의미**를 결정화하고, SCW(SourceCodeWorld)는 **코드**를 물질화한다.
그런데 이 둘 사이에 **참조가 없으면** AI는 맥락을 잃는다:

- "이 Contract가 어떤 코드로 구현됐지?" → 모름
- "이 함수가 어떤 Contract에서 나왔지?" → 모름
- "Contract 변경 시 어떤 파일을 수정해야 하지?" → 추측만 가능

롱기누스 방법론은 이 **단절을 관통**한다. KG 노드마다 두 가지 ref를 꽂아넣어서
**semantic ↔ implementation** 양방향 추적을 보장한다.

---

## 이중 참조 (Dual Ref) 구조

모든 SCW 결과물에 두 가지 ref를 부여한다:

| Ref | 설명 | 예시 |
|-----|------|------|
| **`sourceId`** | 코드 내용의 식별자 — 함수명, 클래스명, 모듈 식별자 | `LoginService.authenticate` |
| **`sourcePath`** | 코드의 물리적 위치 — file:line | `src/auth/login.ts:42` |

```
KG Layer:        [Span] → [Twin] → [Contract] → [SourceCodeNode]
                                                      ↓
Longinus Ref:                              sourceId: "LoginService.authenticate"
                                           sourcePath: "src/auth/login.ts:42"
                                                      ↓
Physical Layer:                            실제 파일의 실제 라인
```

---

## Step 1: 관통 대상 식별

SCW에서 `ContractMaterialized` 후, 또는 기존 코드를 KG에 역매핑할 때 실행.

```cypher
// 아직 롱기누스 ref가 없는 SourceCodeNode 찾기
MATCH (ct:AptContract)-[:MATERIALIZES]->(src:SourceCodeNode)
WHERE src.sourceId IS NULL OR src.sourcePath IS NULL
RETURN ct.name AS contract, src.file_path AS file, ct.status
```

---

## Step 2: sourceId 결정

코드의 **의미적 식별자**를 결정한다. 함수/클래스/모듈 수준에서 가장 구체적인 이름.

**규칙:**
- 함수 단위 구현 → `ModuleName.functionName` (예: `AuthService.login`)
- 클래스 단위 구현 → `ClassName` (예: `UserProfileValidator`)
- 모듈 전체 → `module_name` (예: `auth_middleware`)
- 중첩 → dot notation (예: `OrderProcessor.Validator.check`)

**금지:**
- 파일명 그대로 쓰기 (`login.ts` ← 이건 sourcePath 역할)
- 추상적 이름 (`handler`, `processor`, `service` 단독)

---

## Step 3: sourcePath 결정

코드의 **물리적 위치**. `file_path:start_line` 형식.

**규칙:**
- 프로젝트 루트 기준 상대경로 사용
- 라인 번호는 함수/클래스 **선언 시작 라인**
- 범위가 넓으면 `file_path:start-end` (예: `src/auth/login.ts:42-87`)

```bash
# sourcePath 자동 추출 예시
grep -n "def authenticate\|function authenticate\|authenticate(" src/auth/login.ts
# → src/auth/login.ts:42
```

---

## Step 4: KG에 관통 ref 기록

```cypher
// SourceCodeNode에 이중 ref 설정
MATCH (ct:AptContract {name: $contract_name})-[:MATERIALIZES]->(src:SourceCodeNode)
SET src.sourceId   = $sourceId,       // e.g. "LoginService.authenticate"
    src.sourcePath = $sourcePath,     // e.g. "src/auth/login.ts:42"
    src.pierced_at = datetime()       // 관통 시점
RETURN ct.name, src.sourceId, src.sourcePath
```

**역방향 — 코드에도 KG ref 주석 삽입** (SCW의 FulfillmentGate Check #5와 연동):

```python
# KG: CT_Project_Auth | ST_Project_Auth | TASK_Project_Auth
# LONGINUS: sourceId=AuthService.login, sourcePath=src/auth/login.py:15
def login(email: str, password: str) -> AuthResult:
    ...
```

---

## Step 5: 관통 체인 완성도 검증

Span부터 SourceCode까지 **전체 체인이 끊김 없이 관통**되었는지 검증.

```cypher
// 관통 완성도 체크 — 끊어진 체인 탐지
MATCH (atom:AtomicSpan)-[:CRYSTALLIZES_TO]->(twin:SemanticTwin)
MATCH (twin)-[:HAS_CONTRACT]->(ct:AptContract)
OPTIONAL MATCH (ct)-[:MATERIALIZES]->(src:SourceCodeNode)
WITH atom.name AS span, twin.name AS twin, ct.name AS contract,
     src.sourceId AS sourceId, src.sourcePath AS sourcePath,
     CASE
       WHEN src IS NULL THEN 'NO_SOURCE'
       WHEN src.sourceId IS NULL THEN 'NO_ID'
       WHEN src.sourcePath IS NULL THEN 'NO_PATH'
       ELSE 'PIERCED'
     END AS status
RETURN span, twin, contract, sourceId, sourcePath, status
ORDER BY status DESC
```

**관통 상태 분류:**

| Status | 의미 | 조치 |
|--------|------|------|
| `PIERCED` | 완전 관통 — 양쪽 ref 모두 존재 | 정상 |
| `NO_PATH` | sourceId는 있으나 위치 미지정 | sourcePath 추가 |
| `NO_ID` | 위치는 있으나 의미 식별자 없음 | sourceId 추가 |
| `NO_SOURCE` | SourceCodeNode 자체가 없음 | SCW 미완료 — `/apt-scw` 먼저 |

---

## Step 5b: Reverse Orphan Scan (Code → KG blind-spot fix, v3.1)

> **Why added**: v3 Step 5의 pierce 쿼리는 KG에서 시작한다(`MATCH (atom:AtomicSpan)...`).
> KG에 노드가 아예 **없으면** 쿼리 결과가 0 rows로 조용히 pass되어 **Missing drift** 탐지 실패.
> 실제 사고: `lesson-333-crate-spans-orphan-longinus-2026-04-18` — 11개 crate `// KG: SPAN_*`
> 주석 달고 Taliban 통과했지만 KG엔 단 1개도 없었음.

**반대 방향 검증** — 소스에서 `// KG:` / `# KG:` 토큰을 모두 추출한 뒤 각 노드가 KG에 실제로 존재하는지 MATCH.

```bash
# 1. 코드에서 모든 KG ref 토큰 추출
rg -oN '(?://|#)\s*KG:\s*([A-Za-z0-9_\-\.]+(?:\s*,\s*[A-Za-z0-9_\-\.]+)*)' \
   --glob '!target' --glob '!node_modules' \
   -r '$1' path/to/project \
  | tr ',' '\n' | awk '{$1=$1}1' | sort -u > /tmp/code_refs.txt
```

```cypher
// 2. 각 ref가 KG에 존재하는지 확인 (parameterize $refs from /tmp/code_refs.txt)
// ⚠️ Label-less MATCH는 548K+ 노드 그래프에서 타임아웃 (실측: 30s 초과).
//    반드시 인덱싱된 label union 으로 필터.
WITH $refs AS refs
MATCH (n) WHERE (n:AbstractNode OR n:AptSpan OR n:AtomicSpan OR n:AptContract
                 OR n:SemanticTask OR n:ActionPlan OR n:Lesson OR n:WorkBuffer
                 OR n:LensSet OR n:ResearchFinding OR n:SubagentTaskSpec
                 OR n:KnowledgeNode OR n:Sprint OR n:SourceCodeNode)
  AND n.name IN refs
WITH refs, collect(n.name) AS found
RETURN found AS existing,
       [x IN refs WHERE NOT x IN found] AS orphans,
       size(found) AS foundCount,
       size([x IN refs WHERE NOT x IN found]) AS orphanCount
```

**Orphan 판정**: `exists = false` ⇒ **Missing drift** (GetPut 위반의 역방향 case). 해결:
- 의도된 노드면 MERGE 생성 + 상위 엔터티(ActionPlan/Contract)에 INFORMED_BY/MATERIALIZES 엣지 연결
- 오타/레거시면 주석 제거 또는 이름 교정

---

## Crate/Script-Level Binding (v3.1)

> **Why added**: v3 예제는 함수·클래스 단위 `SourceCodeNode + MATERIALIZES`. 그러나 Rust crate 하나,
> bash script 하나가 통째로 한 AptSpan을 구현하는 케이스(monorepo 레이어링)는 형식 없음.

**Pattern**: crate·module·script 루트 파일 최상단에 `// KG: SPAN_xxx` 한 줄만 박는다.
해당 AptSpan 노드는 `crate`·`sourcePath`·`testCount` 속성으로 전체 crate를 대표한다.

```cypher
MERGE (s:AptSpan:AtomicSpan {name:$span})
SET s.crate = $crate,          // '333-transport'
    s.sourcePath = $path,      // '~/.../333-transport/src/lib.rs' (line 없음 = 파일 전체)
    s.layer = $layer,          // 'L1' / 'L5+L0' / 'harness'
    s.pattern = $pattern,
    s.testCount = $tests,
    s.status = 'complete'
WITH s
MATCH (p:ActionPlan {name:$plan})
MERGE (s)-[:INFORMED_BY]->(p)
```

**Pierce 판정(crate-level)**: `sourcePath`는 file-only (line 생략 허용), 대신 `crate` 속성 필수. 함수 단위 드릴다운이 필요하면 `SourceCodeNode` 서브그래프를 **나중에** 추가.

---

## Taliban 연동 (v3.1 신규)

> **Why added**: Fulfillment Gate가 `// KG:` 문자열 존재만 보고 통과시켜서 orphan을 양산.

**lens_longinus LensSet** 제안 — Taliban 렌즈셋 플러거블(`/taliban --lens longinus`)에 세 개 규칙:

1. **L-1 Code→KG Resolve**: 변경된 파일의 모든 `(?://|#)\s*KG:\s*<id>` 토큰 추출 → KG MATCH. 하나라도 `exists=false` ⇒ **BLOCK**.
2. **L-2 Dual-Ref Completeness**: 각 SourceCodeNode가 `sourceId ∧ sourcePath` 둘 다 보유. 하나만 있으면 **CONDITIONAL**.
3. **L-3 Plan Linkage**: 신규 AptSpan은 최소 1개 ActionPlan으로 `INFORMED_BY` 엣지 보유. 고립 span ⇒ **CONDITIONAL**.

Gate Check Hook에서 SCW→Fulfillment 전환 시 자동 실행. 기존 `--lens constitutional`와 AND 결합.

---

## Step 6: Drift 탐지 (코드 변경 후 KG 동기화)

코드가 변경되면 sourcePath의 라인 번호가 밀린다. 주기적으로 검증.

```bash
# sourcePath 유효성 검증 — 해당 라인에 sourceId가 실제로 존재하는지
grep -n "$sourceId" "$sourcePath_file" | head -1
# 결과가 sourcePath_line과 다르면 → drift 발생
```

```cypher
// Drift 플래그 설정
MATCH (src:SourceCodeNode {name: $src_name})
WHERE src.sourcePath IS NOT NULL
SET src.drift_detected = true,
    src.drift_at = datetime(),
    src.old_sourcePath = src.sourcePath
// 이후 새 위치로 sourcePath 업데이트
```

**Drift 해소:**
1. `grep -rn` 으로 sourceId의 현재 위치 탐색
2. sourcePath 업데이트
3. `drift_detected = false` 리셋

---

## 역매핑 (기존 코드 → KG)

새 프로젝트가 아닌, **기존 코드베이스를 KG에 매핑**할 때의 절차.

```
1. 프로젝트 소스 파일 스캔
2. 함수/클래스 단위로 sourceId 후보 추출
3. 각 후보에 대해:
   a. KG에 SourceCodeNode MERGE
   b. sourceId, sourcePath 설정
   c. 대응되는 Contract가 있으면 MATERIALIZES 연결
   d. Contract가 없으면 → 역으로 Contract 초안 생성 (ST로 에스컬레이션)
```

```cypher
// 역매핑: 코드에서 KG로
MERGE (src:SourceCodeNode {file_path: $file_path})
SET src.sourceId   = $sourceId,
    src.sourcePath = $sourcePath,
    src.pierced_at = datetime(),
    src.reverse_mapped = true   // 역매핑임을 표시
// Contract 연결 (있으면)
WITH src
OPTIONAL MATCH (ct:AptContract {target_file: $file_path})
FOREACH (_ IN CASE WHEN ct IS NOT NULL THEN [1] ELSE [] END |
  MERGE (ct)-[:MATERIALIZES]->(src)
)
RETURN src.sourceId, src.sourcePath, ct.name AS linked_contract
```

---

## 관통 통계 대시보드

```cypher
// 프로젝트별 관통률
MATCH (ct:AptContract)
OPTIONAL MATCH (ct)-[:MATERIALIZES]->(src:SourceCodeNode)
WITH ct.name AS contract,
     CASE WHEN src.sourceId IS NOT NULL AND src.sourcePath IS NOT NULL
          THEN 1 ELSE 0 END AS pierced
RETURN count(*) AS total_contracts,
       sum(pierced) AS pierced_count,
       toFloat(sum(pierced)) / count(*) * 100 AS pierce_rate_pct
```

---

## What NOT To Do

| 금지 | 이유 | 대안 |
|------|------|------|
| sourceId에 파일명 사용 | sourcePath와 역할 중복 | 함수/클래스 의미명 사용 |
| sourcePath 없이 sourceId만 | 절반 관통 = 추적 불가 | 반드시 이중 ref |
| 라인 번호 생략 | 파일만으로는 대형 파일에서 위치 특정 불가 | `file:line` 필수 |
| drift 무시 | 코드 변경 후 KG가 거짓말 | 주기적 drift 검증 |
| 코드 주석 없이 KG만 업데이트 | 양방향이어야 함 | `# LONGINUS:` 주석도 삽입 |
| Contract 없이 관통 | 의미 없는 ref | ST 완료 후 관통 |

---

## Session Continuity

롱기누스 작업 후 `apt-progress.md`에 기록:

```markdown
### Longinus Piercing Progress
- [x] CT_Project_Auth → AuthService.login (src/auth/login.py:15) PIERCED
- [x] CT_Project_Profile → UserProfile.update (src/user/profile.py:33) PIERCED
- [ ] CT_Project_Search → (SCW 미완료, NO_SOURCE)
- Pierce Rate: 66% (2/3)
```

---

*롱기누스의 창은 한 번 꽂으면 뽑히지 않는다. KG와 코드 사이의 참조도 마찬가지다.*

---

## 🌱 재배맨 v2 (MIC Slot Reference — 로직 복제 금지)

> 이 스킬의 subagent 운용은 **MIC_v1.SubagentSeeder** slot을 통해 resolve된다.
> 아래는 thin resolver. 로직 복제 = drift 유발 = Longinus L7(미학) 위반.

### Slot Resolve
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot {name:'SubagentSeeder'})
RETURN s.currentConcrete, s.invocation, s.protocol
```

### 부모 Pre-fetch (v2 — MCP 우회)
```cypher
// 부모가 subagent 출격 전 하계 context 조회 → prompt에 주입
MATCH (l:Lesson)-[:HAS_RESEARCH]->(rf:ResearchFinding)
WHERE l.name CONTAINS $keyword
RETURN rf.name, rf.domain, rf.oneLineSummary LIMIT 20
// 기존 seeds
MATCH (ts:SubagentTaskSpec {skill:'longinus'}) WHERE ts.status='READY'
RETURN ts.name, ts.role LIMIT 10
```

### WorkBuffer 연속성
```cypher
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb
```

# KG: ATOM_재배맨_v2_longinus, SA_methodology_v4_triple_upgrade

---

## History

> Repo-level changes: [`/CHANGELOG.md`](../CHANGELOG.md). Per-commit: `git log -- longinus/SKILL.md`.
> 학문 grounding: [`/PROM_16_SKILL_VERSIONING_REPORT.md`](../PROM_16_SKILL_VERSIONING_REPORT.md).

| Version | Date | Summary | KG Ref |
|---|---|---|---|
| **v3.1** | 2026-04 후반 | Reverse Orphan Scan (Code→KG blind-spot fix) + Crate/Script-level binding + Taliban `--lens longinus` | `ATOM_Skill_longinus`, `lesson-longinus-rigor-theories-2026-04-16` |
| **v3** | 2026-04 mid | 7-Layer Reference Model + BX Lens Laws (GetPut/PutGet) + Refinement Types + GED Drift 정량화 | `SA_methodology_v4_triple_upgrade` |
| **v2** | (~2026-04 early) | KG → 코드 binding (Layer L1 Document ~ L7 CodeBinding) ReferenceSite 패턴 | — |
| **v1** | (older) | 7층 Reference Model 초안 (의미 계층 → 소스코드 관통) | — |

→ ReferenceSite 패턴 (sourcePath/sourceId/layer/binding_state/anchor_strategy) — 7-Layer KG 결정화. PROM 16 / PROM 64 모두 Longinus binding 활용 (L1-L3 active).

# KG history: ATOM_Skill_longinus / lesson-prom16-skill-versioning-academic-2026-04-29
