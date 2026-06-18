# 1:1:1:1 Cardinality Invariant (Phase-Specific)

> AtomicSpan ≡ Contract ≡ SemanticTask ≡ SubagentTaskSpec ≡ 1 file.
> ST→SCW 진입 차단 게이트. 누락 = SCW executor 가 KG 정본 없이 코드 작성 = 롱기누스 추적 불가.

---

## 정전 (User verdict, 2026-05-14)

```
AtomicSpan ≡ Contract ≡ SemanticTask ≡ SubagentTaskSpec ≡ 1 file
```

4개 항이 모두 **isomorphic 1:1:1:1** 로 묶여야 SCW 진입 가능. SharedType 예외만 1 Contract : N AtomicSpan 허용 (그리고 그것도 `c.shared = true` 명시 시에만).

---

## DbC Grounding (Meyer 1992)

Bertrand Meyer, *"Applying 'Design by Contract'"* (IEEE Computer, Oct 1992):

> "Each routine must carry an explicit specification of what it does — precondition, postcondition, and class invariant. Without this specification, software construction is reduced to *empirical assembly*, with verification impossible at scale."

APT 매핑:
- **routine** ↔ `AtomicSpan` (D(S) recursion 의 terminal leaf, 1 file 단위 작업)
- **explicit specification** ↔ `:AptContract` 노드 (typed DTO + pre/postcondition + acceptance_criteria)
- **assignable work unit** ↔ `:SemanticTask` (impact_tests + estimated_lines + target_file)
- **executable directive** ↔ `:SubagentTaskSpec` (재배맨 v2 9-field seed)

→ AtomicSpan 하나만 있고 Contract/Task/Seed 가 없으면 = "routine without contract" = Meyer 가 *empirical assembly* 라 비판한 상태. SCW executor 가 KG 비참조 코드를 작성하게 됨.

### Class Invariant 차원 (cardinality 자체)

Meyer §III: "Class invariants must hold *between* method invocations." APT 차원에서는 **ST phase boundary** 가 invariant checkpoint:

```
ST exit → SCW entry 사이:
  ∀ atomic: |{c : (atomic)-[:HAS_CONTRACT]->(c)}| = 1  (or shared=true)
            |{t : (atomic)-[:HAS_TASK]->(t)}|     = 1
            |{s : (atomic)-[:HAS_SEED]->(s)}|     = 1
```

위반 시 ST phase 자체가 미완성 상태 → SCW 진입 불가.

---

## Worked Example 1 — 정상 case (1:1:1:1 모두 채워짐)

### Setup

3 AtomicSpan: `ATOM_UserCreate`, `ATOM_UserRead`, `ATOM_UserUpdate`. 각각 1 Contract + 1 Task + 1 Seed.

```cypher
// 3 AtomicSpan 생성
UNWIND ['ATOM_UserCreate', 'ATOM_UserRead', 'ATOM_UserUpdate'] AS atom_name
MATCH (root:Span {name: 'SPAN_UserCRUD_root'})
MERGE (a:AtomicSpan {name: atom_name})
SET a.is_atomic = true,
    a.target_file = 'src/user/' + toLower(replace(atom_name, 'ATOM_User', '')) + '.py'
MERGE (root)-[:DECOMPOSES_TO]->(a)

// 각 AtomicSpan 에 1 Contract + 1 Task + 1 Seed binding
WITH a
MERGE (c:AptContract {name: 'CONTRACT_' + substring(a.name, 5)})
SET c.input_type = 'UserCreateReq',
    c.output_type = 'UserResponse',
    c.shared = false,
    c.status = 'Active'
MERGE (a)-[:HAS_CONTRACT]->(c)

MERGE (t:SemanticTask {name: 'TASK_' + substring(a.name, 5)})
SET t.estimated_lines = 80,
    t.impact_tests = 'tests/user/test_' + toLower(substring(a.name, 5)) + '.py',
    t.target_file = a.target_file
MERGE (a)-[:HAS_TASK]->(t)

MERGE (s:SubagentTaskSpec {name: 'SEED_' + substring(a.name, 5)})
SET s.skill = 'apt-scw',
    s.status = 'READY',
    s.role = 'executor'
MERGE (a)-[:HAS_SEED]->(s)
```

### Gate Check 결과

```cypher
// 1:1:1:1 invariant gate query 실행 (SKILL.md 본문 cypher)
// 결과:
gate_passed: true
violations_total: 0
missing_atomicspans: []
reason: 'OK — ST→SCW handoff permitted (1:1:1:1 invariant satisfied)'
```

→ `/apt-scw` 진입 허용. SCW executor 3 명 병렬 dispatch 가능.

---

## Worked Example 2 — 누락 case (BLOCKED)

### Setup

3 AtomicSpan 중 `ATOM_UserUpdate` 만 Task 생성 누락 (ST 작성자가 깜빡함).

```cypher
// ATOM_UserUpdate 의 HAS_TASK 관계만 의도적으로 누락
// (위 example 1 과 동일하되 마지막 MERGE (t:SemanticTask ...) 블록을 ATOM_UserUpdate 에 대해 skip)
MATCH (a:AtomicSpan {name: 'ATOM_UserUpdate'})-[r:HAS_TASK]->()
DELETE r
```

### Gate Check 결과

```cypher
// 결과:
gate_passed: false
violations_total: 1
missing_atomicspans: [
  {atomic: 'ATOM_UserUpdate', missing: 'MissingTask'}
]
reason: 'BLOCKED — 1:1:1:1 cardinality violated. Run /apt-st to crystallize missing bindings.'
```

→ `permissionDecision: deny` 발동. `/apt-scw` 호출 차단. `/apt-st` 재실행 → `ATOM_UserUpdate` 에 SemanticTask 생성 후 재시도.

### Remediation cypher

```cypher
MATCH (a:AtomicSpan {name: 'ATOM_UserUpdate'})
MERGE (t:SemanticTask {name: 'TASK_UserUpdate'})
SET t.estimated_lines = 80,
    t.impact_tests = 'tests/user/test_update.py',
    t.target_file = a.target_file,
    t.description = 'PUT /users/{id} — partial update with optimistic locking',
    t.acceptance_criteria = 'test_user_update_returns_updated_resource AND test_user_update_rejects_stale_version'
MERGE (a)-[:HAS_TASK]->(t)
```

재실행 → gate_passed=true.

---

## Worked Example 3 — SharedType 예외 (1:N 허용)

### Setup

`CONTRACT_DBPort_Read` 가 3 AtomicSpan (`ATOM_UserRead`, `ATOM_OrderRead`, `ATOM_InvoiceRead`) 에 공유됨. `shared=true` 명시.

```cypher
// SharedType Contract 생성 (shared=true)
MERGE (c:AptContract {name: 'CONTRACT_DBPort_Read'})
SET c.input_type = 'Tuple[Table, PrimaryKey]',
    c.output_type = 'Optional[Record]',
    c.shared = true,
    c.access_rights_closure = 'read-only, no-side-effects, idempotent',
    c.status = 'Active'

// 3 AtomicSpan 모두 같은 Contract 공유
UNWIND ['ATOM_UserRead', 'ATOM_OrderRead', 'ATOM_InvoiceRead'] AS atom
MATCH (a:AtomicSpan {name: atom})
MATCH (c:AptContract {name: 'CONTRACT_DBPort_Read'})
MERGE (a)-[:HAS_CONTRACT]->(c)

// 각 AtomicSpan 은 여전히 자기 SemanticTask + SubagentTaskSpec 1:1 유지
// (Contract 만 공유, Task/Seed 는 각 atomic 별 고유)
```

### Gate Check 결과

**Primary gate query** (SKILL.md 본문):
```
gate_passed: true  (각 atomic 에 1 Contract + 1 Task + 1 Seed 모두 존재)
violations_total: 0
```

**SharedType N:1 secondary check** (별도 검증):
```cypher
// shared=true 이므로 V_ST_Cardinality_NonSharedMultiplex 발동하지 않음.
MATCH (a1:AtomicSpan)-[:HAS_CONTRACT]->(c:AptContract)<-[:HAS_CONTRACT]-(a2:AtomicSpan)
WHERE a1.name < a2.name
  AND (c.shared IS NULL OR c.shared = false)
RETURN c.name
// → 빈 결과 (CONTRACT_DBPort_Read 는 shared=true 이므로 제외).
```

→ Gate 통과. SCW 진입 허용. SCW executor 3 명이 같은 `CONTRACT_DBPort_Read` 인터페이스를 구현 (Contract Sandwich 패턴).

### Anti-case: shared 플래그 누락

`c.shared = true` 설정 안 했는데 N AtomicSpan 에 같은 Contract 가 걸린 경우:
```
V_ST_Cardinality_NonSharedMultiplex:
  contract: 'CONTRACT_DBPort_Read'
  atomic_spans: ['ATOM_UserRead', 'ATOM_OrderRead', 'ATOM_InvoiceRead']
  remediation: 'Set c.shared=true OR split Contract per AtomicSpan'
```

→ 의도가 sandwich 면 `SET c.shared = true, c.access_rights_closure = '...'`. 그 외엔 atomic 별 Contract 로 분리.

---

## apt-gate-check.sh 패치 예시

기존 `apt-gate-check.sh` (v0.7/v0.8-A1 dual-mode) 에 ST→SCW 게이트 함수 추가. shell 함수로 wrapping.

```bash
#!/usr/bin/env bash
# apt-gate-check.sh — ST→SCW 1:1:1:1 cardinality gate
# KG: span-gap2-st-1to1-cardinality-gate-2026-05-14

check_st_cardinality_invariant() {
  local project="$1"
  local cypher_file="$(mktemp).cypher"

  cat >"$cypher_file" <<'CYPHER'
MATCH (sa:SemanticAnchor {name: $PROJECT})-[:HAS_ROOT]->(root)
MATCH (root)-[:DECOMPOSES_TO*1..10]->(atomic:AtomicSpan)
WHERE atomic.is_atomic = true
OPTIONAL MATCH (atomic)-[:HAS_CONTRACT]->(c:AptContract)
OPTIONAL MATCH (atomic)-[:HAS_TASK]->(t:SemanticTask)
OPTIONAL MATCH (atomic)-[:HAS_SEED]->(s:SubagentTaskSpec)
WITH atomic, c, t, s,
     CASE WHEN c IS NULL THEN 'MissingContract'
          WHEN t IS NULL THEN 'MissingTask'
          WHEN s IS NULL THEN 'MissingSeed'
          ELSE 'OK' END AS missing_kind
WITH atomic, missing_kind
WHERE missing_kind <> 'OK'
WITH collect({atomic: atomic.name, missing: missing_kind}) AS violations,
     count(*) AS missing_count
RETURN missing_count AS missing,
       violations AS detail
CYPHER

  local result
  result=$(cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
    --param "PROJECT => '$project'" --format plain \
    <"$cypher_file" 2>&1)

  rm -f "$cypher_file"

  local missing_count
  missing_count=$(echo "$result" | awk 'NR==2 {print $1}')

  if [[ "$missing_count" == "0" ]]; then
    echo "OK — ST→SCW handoff permitted (1:1:1:1 invariant satisfied)"
    return 0
  else
    cat <<EOF
{
  "permissionDecision": "deny",
  "gate": "ST_CardinalityInvariant",
  "reason": "BLOCKED — 1:1:1:1 cardinality violated ($missing_count AtomicSpan)",
  "detail": $(echo "$result" | awk 'NR==2 {$1=""; print}'),
  "remediation": "Run /apt-st to crystallize missing Contract/Task/Seed bindings."
}
EOF
    return 1
  fi
}

# PreToolUse hook (apt-scw 호출 직전)
case "$APT_GATE_PHASE" in
  ST_TO_SCW)
    check_st_cardinality_invariant "$PROJECT" || exit 1
    # 기존 v0.7/v0.8-A1 LensSet completeness / ValidationResult APPROVED 등 후속 게이트 호출
    check_st_validation_approved "$PROJECT" || exit 1
    ;;
esac
```

### Integration with v0.7/v0.8-A1

기존 LensSet completeness gate + ValidationResult APPROVED gate **이전** 에 cardinality invariant 가 실행되어야 함. 순서:

```
1. check_st_cardinality_invariant   (NEW, GAP-2)
2. check_lensset_completeness        (v0.7 floor, lensCount >= 9)
3. check_concern_coverage            (v0.8-A1 ensemble UNION >= 0.8)
4. check_validation_result_approved  (Naesengmoon APPROVED VR 존재)
```

1번 실패하면 2-4 실행 의미 없음 (Contract/Task 자체가 누락된 상태에서 LensSet 검증은 무의미).

---

## Cross-references

- SKILL.md 본문: "🔒 1:1:1:1 Cardinality Invariant Gate (ST→SCW 진입 차단)" 섹션
- SharedType detection: `MIC_v1.ContractSchema` slot (SKILL.md v26 A6)
- Contract Sandwich N:1 정합성: [`contract_sandwich.md`](contract_sandwich.md)
- SubagentTaskSpec 9-field schema: 재배맨 SKILL.md
- 외부 학문 grounding: Meyer (1992) *"Applying Design by Contract"* IEEE Computer 25(10):40-51

# KG: span-gap2-st-1to1-cardinality-gate-2026-05-14, lesson-st-1to1-cardinality-canon-2026-05-14, ATOM_ST_CardinalityInvariantGate
