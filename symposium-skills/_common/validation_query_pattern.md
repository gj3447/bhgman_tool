# Validation Query Pattern (Cross-Skill Shared)

> APT 모든 phase에서 사용하는 `V-XX{N}` 검증 cypher 작성 규약. SKILL.md 본문 *내부* validation 패턴 단일 소스.

---

## Naming convention

```
V-{PHASE_PREFIX}{INDEX} — {invariant name}
```

| Phase | Prefix | 예시 |
|---|---|---|
| SA | `V-SA` | V-SA1 OrphanRoot, V-SA2 DuplicateAnchor |
| SP | `V-SP` | V-SP1 BranchingInvariant, V-SP2 SiblingDependency |
| ST | `V-ST` | V-ST1 ContractDraftAbandon, V-ST2 TwinWithoutContract |
| SCW | `V-SCW` | V-SCW1 SelfApproval, V-SCW2 KGRefMissing |
| _common | `V-XX` | V-CB1 Context Budget, V-PD1 Progressive Disclosure |

---

## 표준 cypher 양식

```cypher
-- V-{prefix}{N}: {one-line description of invariant}
MATCH (n:{Label})
WHERE {invariant_violation_predicate}
RETURN 'V_{prefix}{N}_{ShortName}' AS validation,
       n.name AS subject,
       {additional_evidence_fields}
```

### 4 mandatory parts

1. **Comment header**: `V-SA1: OrphanRoot — SA에 연결 안 된 Root Span 탐지`
2. **MATCH + WHERE**: invariant *위반*을 잡는 predicate (정상 케이스는 0행 반환)
3. **RETURN validation tag**: `'V_SA1_OrphanRoot'` (snake_case)
4. **Evidence fields**: subject name + 위반 detail

---

## 결과 해석

- **0행 반환** = invariant 충족 (PASS)
- **≥1행 반환** = invariant 위반 (FAIL) → fail-closed gate가 차단

```python
# Validator 패턴 (Python 예시)
def run_validation(query: str, expected_empty: bool = True) -> bool:
    rows = neo4j_run(query)
    if expected_empty:
        return len(rows) == 0
    else:
        return len(rows) > 0  # 일부 V는 "정상이면 행 있어야 함"
```

---

## phase별 V 목록 (대표)

| V tag | Phase | Invariant | reference |
|---|---|---|---|
| V-SA1 | SA | OrphanRoot — Root Span이 SA에 연결됨 | sa-specific |
| V-SA2 | SA | DuplicateAnchor — 동일 이름 SA 2개 이상 | sa-specific |
| V-SA3 | SA | NoRoot — active SA에 Root Span 없음 | sa-specific |
| V-SA4 | SA | NoBudget — Context Budget 미할당 | _common (V-CB1) |
| V-SP1 | SP | BranchingInvariant — 1개 자식 분해 (rename only) | sp-specific |
| V-SP2 | SP | SiblingDependency — 형제 간 DEPENDS_ON | sp-specific |
| V-SP3 | SP | NoInformedBy — Span에 INFORMED_BY ≥ N 미충족 | sp-specific |
| V14 | ST | CrystallizationHubIncomplete — hub의 4 role 누락 | st-specific |
| V15 | SCW | SelfApproval — executor == reviewer | scw-specific |
| V-CB1/2/3 | all | Context Budget 검증 | _common |
| V-PD1 | all | Progressive Disclosure 위반 | _common |

phase 고유 V는 해당 phase `references/{phase}_validation.md` 참조.

---

## 작성 anti-pattern

- **E-V1: 정상을 잡음** — `RETURN ... WHERE NOT violation`. 0행이 PASS여야 하는데 1행이 PASS. → MATCH로 *위반*을 잡아야 함.
- **E-V2: validation tag 누락** — `RETURN n.name AS subject` 만. tag 없으면 어떤 V인지 추적 불가.
- **E-V3: subject 누락** — `RETURN 'V_X_Y'` 만. 누가 위반했는지 모름.
- **E-V4: 1행만 반환 (LIMIT 1)** — 첫 위반만 발견. 모든 위반자 누락. → 일반적으로 LIMIT 없이.
- **E-V5: side-effect** — MERGE/SET/DELETE. validation query는 *읽기 전용*.

---

## 통합 검증 실행

phase 종료 시 모든 V 일괄 실행:

```cypher
CALL {
  // V-SA1
  MATCH (root:AptSpan) WHERE root.depth = 0 AND NOT ()-[:HAS_ROOT]->(root)
  RETURN 'V_SA1_OrphanRoot' AS v, root.name AS subject
  UNION ALL
  // V-SA2
  MATCH (sa:SemanticAnchor) WITH sa.name AS n, count(sa) AS cnt WHERE cnt > 1
  RETURN 'V_SA2_DuplicateAnchor' AS v, n AS subject
  // ... 추가 V
}
RETURN v, subject ORDER BY v
```

`v` 컬럼이 비어있으면 모든 invariant PASS. fail-closed gate가 RETURN 비어있을 때만 통과.

---

## Academic Grounding

Validation Query Pattern은 *프로그램 검증 이론*에서 결정화:

### 1. Floyd-Hoare Logic (Floyd 1967, Hoare 1969)

> Floyd, R. W. (1967). *Assigning Meanings to Programs*. Mathematical Aspects of Computer Science, 19, 19-32.
>
> Hoare, C. A. R. (1969). *An axiomatic basis for computer programming*. Communications of the ACM, 12(10), 576-580.

핵심: 프로그램을 *Hoare triple* `{P} f {Q}`로 검증. precondition 만족 시 postcondition 보장.

→ 모든 V-XX validation은 *invariant 위반*을 잡는 predicate. `MATCH WHERE violation_pred RETURN ...` 형식은 본질적으로 Hoare 후행 술어 `¬Q` 검사.

### 2. Dijkstra's Guarded Commands (Dijkstra 1976)

> Dijkstra, E. W. (1976). *A Discipline of Programming*. Prentice-Hall.

핵심: 비결정적 프로그램을 *guard + command* 쌍으로. 모든 guard가 false면 abort (정상 종료 ≠ 진행).

→ V-XX cypher의 "0행 반환 = PASS" 컨벤션이 정확히 Dijkstra guard 의미. RETURN 비어있을 때만 gate 통과 = guard satisfied.

### 3. Weakest Precondition (Dijkstra 1975)

> Dijkstra, E. W. (1975). *Guarded commands, nondeterminacy and formal derivation of programs*. CACM, 18(8), 453-457.

`wp(S, Q)` = command S 실행 후 postcondition Q를 보장하는 *가장 약한* precondition.

→ 통합 검증 cypher의 `CALL { UNION ALL ... } RETURN`이 wp 계산과 동형 — 모든 V-XX의 OR composition.

### 4. Property-Based Testing (Hughes 2000)

> Hughes, J. (2000). *QuickCheck: a lightweight tool for random testing of Haskell programs*. ICFP 2000.

핵심: *example-based* 테스트 대신 *property* 명시 → random data로 반증 시도.

→ V-XX cypher가 "임의 노드에 대해 invariant 성립"을 검사하는 패턴. 단일 example case가 아닌 *모든 매칭 노드*에 대한 universal predicate.

### 5. Anti-pattern: E-V1 의 academic 근거

E-V1 ("정상을 잡음")은 Karnaugh map *complement* 오류. 진리표 작성 시 truth/falsity 혼동.

> Karnaugh, M. (1953). *The Map Method for Synthesis of Combinational Logic Circuits*. AIEE Transactions, 72(9), 593-599.

→ V-XX 작성 시 *invariant violation*을 *match*하는 것이 디폴트. Karnaugh complement 실수 방지.

# KG: APT_Validation_pattern_canonical, lesson-floyd-hoare-grounding-2026-05-11
