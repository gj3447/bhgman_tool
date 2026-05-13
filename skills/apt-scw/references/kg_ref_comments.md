# KG Reference Comments (Phase-Specific)

> 모든 소스 파일에 KG 추적 주석 mandatory. 코드 → 명세 추적성. FulfillmentGate check 4.

---

## 표준 형식

```python
# KG: TASK_xxx           ← 이 파일이 구현하는 Task
# KG: CONTRACT_xxx       ← 준수하는 Contract

def my_function(input: InputType) -> OutputType:
    """
    # KG: CONTRACT_xxx (input_type -> output_type)
    """
    ...
```

---

## 규칙

1. **파일 최상단**에 TASK와 CONTRACT 참조 mandatory
2. **핵심 함수** docstring 또는 주석에 Contract 타입 매핑
3. FulfillmentGate check 4가 존재 확인
4. 누락 = "단절된 구현" — 코드 → 명세 추적 불가
5. **Longinus 7-Layer Reference Model** 정합 (LP1 binding)

---

## Longinus 7-Layer 통합

KG ref comment는 Longinus L1-L7 중 L3 (소스 파일 binding) 의 핵심 진입점.

```python
# KG: TASK_UserProfile_Create
# KG: CONTRACT_UserProfile_Create
# KG: ATOM_UserProfile_Create
# KG: CYCLE_2026-05-11_UserProfile
```

multiple ref 가능 — atom + cycle + contract 모두 추적.

---

## 검증 (FulfillmentGate check 4)

```bash
# pre-commit hook 또는 CI check
#!/bin/bash
SOURCE_FILE=$1
TASK=$(grep -E "^# KG: TASK_" "$SOURCE_FILE" | head -1)
CONTRACT=$(grep -E "^# KG: CONTRACT_" "$SOURCE_FILE" | head -1)

if [[ -z "$TASK" ]] || [[ -z "$CONTRACT" ]]; then
  echo "FulfillmentGate-4 FAIL: $SOURCE_FILE missing KG refs"
  echo "  TASK ref: ${TASK:-MISSING}"
  echo "  CONTRACT ref: ${CONTRACT:-MISSING}"
  exit 1
fi

# KG existence check
TASK_NAME=$(echo "$TASK" | sed 's/^# KG: //')
CONTRACT_NAME=$(echo "$CONTRACT" | sed 's/^# KG: //')

if ! cypher-shell "MATCH (n {name:'$TASK_NAME'}) RETURN n LIMIT 1" | grep -q "n"; then
  echo "FulfillmentGate-4 FAIL: KG node $TASK_NAME does not exist"
  exit 1
fi
```

---

## 검증 cypher

```cypher
-- V-SCW-KGRef-1: SourceCodeNode에 ref comment 없음
MATCH (src:SourceCodeNode)
WHERE src.kg_refs IS NULL OR size(src.kg_refs) < 2
RETURN 'V_SCW_KGRef_Missing' AS validation,
       src.name AS source,
       coalesce(size(src.kg_refs), 0) AS ref_count

-- V-SCW-KGRef-2: ref'd Contract가 실제로 KG에 존재 안 함
MATCH (src:SourceCodeNode)
UNWIND src.kg_refs AS ref_name
WHERE ref_name STARTS WITH 'CONTRACT_'
  AND NOT EXISTS { MATCH (:AptContract {name: ref_name}) }
RETURN 'V_SCW_KGRef_DanglingContract' AS validation,
       src.name AS source, ref_name AS dangling_ref
```

---

## 언어별 예시

### TypeScript

```typescript
// KG: TASK_UserProfile_Create
// KG: CONTRACT_UserProfile_Create

export async function createUserProfile(form: RegistrationForm): Promise<UserProfile> {
  /**
   * # KG: CONTRACT_UserProfile_Create (RegistrationForm -> UserProfile)
   */
  // ...
}
```

### Rust

```rust
// KG: TASK_UserProfile_Create
// KG: CONTRACT_UserProfile_Create

/// # KG: CONTRACT_UserProfile_Create (RegistrationForm -> UserProfile)
pub async fn create_user_profile(form: RegistrationForm) -> Result<UserProfile, AuthError> {
    // ...
}
```

# KG: APT_SCW_KGRefComments_canonical, Longinus_L3_canonical
