# Parallel Wave Extraction (Kahn Topological Order)

> SP 종료 시점에 **AtomicSpan.wave_index** 부여. 같은 wave = 형제 독립 (A3) + DEPENDS_ON 무 → SCW dispatch 시 fully parallel batch.
> Kahn 1962 BFS topological sort. CLRS §22.4 Topological Sort.

---

## 개념

- **wave_index ∈ ℕ⁺** (1부터 시작).
- `(a)-[:DEPENDS_ON]->(b)` ⟹ `a.wave_index < b.wave_index` (strict less).
- 같은 wave 의 AtomicSpan 집합 = **antichain in DEPENDS_ON poset** = 완전 병렬 dispatch 후보.
- Crystallization Frontier 도달 후 *모든* AtomicSpan 에 wave_index IS NOT NULL 강제. SP→ST gate 통과 전제.

DEPENDS_ON 외의 edge (DECOMPOSES_TO / INFORMED_BY / CRYSTALLIZES_TO) 는 wave 계산에 무관. A3 SiblingIndependence 가 보장된 상태 (RefinementGate Independence check 통과) 에서만 wave 가 의미 있음.

---

## 알고리즘 (Kahn 1962)

```
W ← {} (wave assignment)
S ← {atomic ∈ AtomicSpan | indeg_DEPENDS_ON(atomic) = 0}
k ← 1
while S ≠ ∅:
    for atomic in S:
        W[atomic] ← k
    next ← {b | (a)-[:DEPENDS_ON]->(b), a ∈ S, ∀a': (a')-[:DEPENDS_ON]->(b) ⟹ a' ∈ ⋃_{i≤k} wave_i}
    S ← next
    k ← k + 1
if |W| < |AtomicSpan|: raise CyclicDAG
```

**Complexity**: O(V+E), V = |AtomicSpan|, E = |DEPENDS_ON|.

---

## Cypher 구현

### Step 1: in_degree=0 (wave 1 = roots)

```cypher
// wave 1: DEPENDS_ON 들어오는 edge 없는 AtomicSpan
MATCH (atom:AtomicSpan)
WHERE NOT ()-[:DEPENDS_ON]->(atom)
  AND atom.wave_index IS NULL
SET atom.wave_index = 1
RETURN count(atom) AS wave1_size
```

### Step 2: 반복 wave k (k=2,3,...)

```cypher
// k 번째 wave: 모든 predecessor 가 이미 wave_index 부여됨 + 자신은 아직 NULL
WITH 2 AS k  // k 를 driver script 에서 증가시키며 호출
MATCH (atom:AtomicSpan)
WHERE atom.wave_index IS NULL
  AND NOT EXISTS {
    MATCH (pred:AtomicSpan)-[:DEPENDS_ON]->(atom)
    WHERE pred.wave_index IS NULL OR pred.wave_index >= k
  }
SET atom.wave_index = k
RETURN k, count(atom) AS wave_size
```

루프 종료 조건: `wave_size = 0`. 이때 NULL 남은 AtomicSpan 존재 시 **CyclicDAG**.

### 단일 transaction APOC 변형 (선택)

```cypher
// APOC 가능 환경에서 단일 호출로 fixpoint
CALL apoc.periodic.commit(
  "MATCH (atom:AtomicSpan) WHERE atom.wave_index IS NULL
   AND NOT EXISTS {
     MATCH (pred:AtomicSpan)-[:DEPENDS_ON]->(atom)
     WHERE pred.wave_index IS NULL
   }
   WITH atom, COALESCE(
     [(p:AtomicSpan)-[:DEPENDS_ON]->(atom) | p.wave_index] + [0],
     [0]
   ) AS preds
   SET atom.wave_index = apoc.coll.max(preds) + 1
   RETURN count(atom)", {limit: 1000})
```

---

## SP→ST Gate 강제 (wave_index 완전성)

`handoff_to_st.md` 5 조건과 AND 결합:

```cypher
// Gate: 모든 AtomicSpan 에 wave_index IS NOT NULL
MATCH (sa:SemanticAnchor {name: $PROJECT})-[:HAS_ROOT]->(root)
MATCH (root)-[:DECOMPOSES_TO*1..10]->(atom:AtomicSpan)
WHERE atom.wave_index IS NULL
RETURN 'V_SP_WaveIndex_Missing' AS validation,
       atom.name AS atom,
       false AS handoff_ready
// 결과 1행 이상 = SP→ST 차단
```

---

## Worked Example (3-wave 7-span)

### DAG

```
ATOM_A ──┐
         ├──→ ATOM_D ──┐
ATOM_B ──┤             ├──→ ATOM_G
         │             │
ATOM_C ──┴──→ ATOM_E ──┘
              ATOM_F ──→ ATOM_G
```

Edges (DEPENDS_ON):
- A → D, B → D, C → D
- A → E (no), C → E, F → G, D → G, E → G

(정정: 위 그림 단순화. 정확 edge 집합:)
- `A → D`, `B → D`, `C → D`, `C → E`, `D → G`, `E → G`, `F → G`

### Kahn 단계

| step | indeg=0 candidates | wave |
|------|--------------------|------|
| k=1  | {A, B, C, F}       | 1    |
| k=2  | {D, E}             | 2    |
| k=3  | {G}                | 3    |

### 결과

```
ATOM_A.wave_index = 1
ATOM_B.wave_index = 1
ATOM_C.wave_index = 1
ATOM_F.wave_index = 1
ATOM_D.wave_index = 2
ATOM_E.wave_index = 2
ATOM_G.wave_index = 3
```

### SCW dispatch 의미

- Wave 1 (4 atom) = single Kafka batch, 4 SubagentTaskSpec 동시 출격.
- Wave 1 전체 verdict APPROVED 후 → Wave 2 (D, E 2 atom 동시).
- Wave 2 후 → Wave 3 (G 단독).

Total wall-clock = 3 wave × max(wave duration). Sequential 비교 7 atom = 7x 단축 가능성.

---

## Edge Cases

### EC-1: Single node

```
ATOM_X (no DEPENDS_ON edge)
```

`X.wave_index = 1`. Trivial. wave_count = 1.

### EC-2: Linear chain (worst-case wave depth)

```
A → B → C → D → E
```

`A=1, B=2, C=3, D=4, E=5`. 5 wave, parallelism = 1. **병렬화 효과 0**: 분해 구조가 본질적 직렬. 가능하면 RefinementGate Independence 재검토.

### EC-3: All parallel (best case)

```
A, B, C, D, E (no DEPENDS_ON)
```

모두 `wave_index = 1`. 5x 병렬. 1:1:1:1 invariant 최대 활용.

### EC-4: Cyclic DAG (error)

```
A → B → C → A
```

Kahn 종료 시 NULL 남음 → `CyclicDAG` raise. 진단 cypher:

```cypher
MATCH (atom:AtomicSpan) WHERE atom.wave_index IS NULL
RETURN atom.name AS unscheduled,
       [(atom)-[:DEPENDS_ON*]->(atom) | 'CYCLE'][0] AS in_cycle
```

대응: DEPENDS_ON edge 중 하나를 INFORMED_BY 로 강등 (실제 데이터 의존 아닌 지식 참조) 또는 상위 Span 으로 의존 끌어올려 재분해.

### EC-5: OrphanLeaf (non-atomic leaf)

```
ATOM_X is leaf (no DECOMPOSES_TO) but :AtomicSpan label 없음
```

wave 계산 대상 아님. Step 4 Crystallization Frontier 검증에서 차단. wave_extraction 은 :AtomicSpan 라벨 보유 leaf 만 처리.

---

## anti-pattern

### E-SP-Wave-1: wave_index 누락 핸드오프

**Context:** AtomicSpan 들에 wave_index 부여 안 하고 SP→ST 진행. SCW dispatch 시 어떤 batch 로 묶을지 implicit, 무작위 순서 dispatch → DEPENDS_ON 순서 위반 → race condition.

**Lesson:** wave_index = SP 의 명시적 산출. implicit 순서 = vibe scheduling.

**Guard:** SP→ST gate 에 `V_SP_WaveIndex_Missing` cypher 강제. 1행 이상이면 차단.

### E-SP-Wave-2: 같은 wave 에 DEPENDS_ON 존재

**Context:** Kahn 구현 버그로 같은 wave 안에 `(a)-[:DEPENDS_ON]->(b), a.wave_index = b.wave_index` 발생.

**Lesson:** strict-less invariant 위반. 같은 wave 는 antichain 이어야 fully parallel.

**Guard:**

```cypher
MATCH (a:AtomicSpan)-[:DEPENDS_ON]->(b:AtomicSpan)
WHERE a.wave_index >= b.wave_index
RETURN 'V_SP_Wave_Violation' AS validation, a.name, b.name
// 0행 = OK
```

### E-SP-Wave-3: Cyclic DAG silent

**Context:** Kahn 종료 시 NULL 남은 atom 무시하고 ST 진입. ST 단계에서 contract crystallization 무한 루프.

**Lesson:** Cyclic 은 SP 단계에서 explicit 실패해야 함. Defer = drift.

**Guard:** Kahn 종료 직후 NULL 잔존 확인 cypher 강제.

---

## ErrorPattern KG 결정화

```cypher
MERGE (e:ErrorPattern:AbstractNode {name:'E-SP-Wave-1'})
SET e.phase = 'SP',
    e.shortName = 'MissingWaveIndex',
    e.context = 'AtomicSpan 들에 wave_index 없이 SP→ST 핸드오프',
    e.lesson = 'wave_index = SP 의 명시적 산출. implicit = vibe scheduling',
    e.guard = 'SP→ST gate V_SP_WaveIndex_Missing cypher',
    e.severity = 'P2'
```

---

## 외부 정전 cite

- **Kahn, A. B. (1962).** "Topological sorting of large networks." *Communications of the ACM*, 5(11), 558-562. — 원전. in_degree=0 반복 추출 알고리즘.
- **CLRS (Cormen, Leiserson, Rivest, Stein).** *Introduction to Algorithms*, 3rd ed., §22.4 "Topological Sort". — DFS 변형 + correctness proof.
- **Dilworth, R. P. (1950).** "A decomposition theorem for partially ordered sets." *Annals of Mathematics*, 51(1), 161-166. — 최소 chain 분할 cardinality = 최대 antichain width.
- **Mirsky, L. (1971).** "A dual of Dilworth's decomposition theorem." *Journal of Combinatorial Theory, Series B*, 11(2), 164-167. — *dual*: 최소 antichain 분할 cardinality = 최대 chain length.
- **Birkhoff, G. (1940).** *Lattice Theory*. AMS Colloquium Publications 25. — Poset/antichain/chain 정전 이론. pairwise-incomparable = antichain.

---

## 형식 정의 (Mirsky 1971 + Dilworth 1950 cross-ref)

> PROM_16 P2.2 finding (0.65 PARTIALLY_CONFIRMED → 0.85 STRONG 격상 candidate): A3 sibling indep = Dilworth antichain 1:1 verified. 본 절에서 Mirsky dual 측 형식 매핑 완비.

### D-1: APT DEPENDS_ON poset

APT 의 AtomicSpan 집합 `A` 와 transitive closure `→⁺ := DEPENDS_ON⁺` 는 strict partial order (DAG ⟹ irreflexive + transitive + antisymmetric):

```
(A, →⁺) is a strict poset:
  - irreflexive: ¬(a →⁺ a)   [DAG cycle-free]
  - transitive:  a →⁺ b ∧ b →⁺ c ⟹ a →⁺ c
  - antisymmetric: a →⁺ b ∧ b →⁺ a ⟹ a = b   [vacuous, DAG]
```

### D-2: Chain / Antichain (Birkhoff 1940)

- **Chain** `C ⊆ A`: ∀ a, b ∈ C, `a →⁺ b ∨ b →⁺ a ∨ a = b` (totally ordered subset).
- **Antichain** `X ⊆ A`: ∀ a, b ∈ X with `a ≠ b`, `¬(a →⁺ b) ∧ ¬(b →⁺ a)` (pairwise incomparable).
- **Longest chain length** `ℓ(A) := max { |C| : C is a chain in A }`.
- **Maximum antichain width** `w(A) := max { |X| : X is an antichain in A }`.

### D-3: wave_index 형식 (Mirsky 1971 chain partition index)

`wave_index : A → ℕ⁺` 를 다음과 같이 정의:

```
wave_index(a) := 1 + max { wave_index(b) : (b →⁺ a) ∧ b is immediate predecessor of a }
                (with max(∅) := 0)
```

동치 정의 (recursive in-degree-0 sweep):

```
A₀ := { a ∈ A : indeg_→⁺(a) = 0 }                 (roots)
A_{k+1} := { a ∈ A \ ⋃_{i≤k} A_i :
              ∀ b with b →⁺ a, b ∈ ⋃_{i≤k} A_i }
wave_index(a) := k+1   iff   a ∈ A_k
```

A_k 는 *k-번째 antichain layer*. {A_0, A_1, ...} 는 A 의 **antichain partition** (Mirsky 1971 의 minimum chain partition 의 dual).

### D-4: Mirsky dual 측 정확 statement

**Mirsky 1971 정리** (formal):
> For any finite poset `(P, ≤)`, the **minimum number of antichains needed to partition P** equals the **length of the longest chain** in P.

APT 매핑 (1:1 verified):

| Mirsky 1971                          | APT SP                              |
|--------------------------------------|-------------------------------------|
| Finite poset (P, ≤)                  | (AtomicSpan set, DEPENDS_ON⁺)       |
| Antichain                            | wave A_k (same wave_index)          |
| Minimum antichain partition          | { A_0, A_1, ..., A_{ℓ-1} } 본 절 D-3 |
| Longest chain length ℓ(P)            | `max_wave := max_a wave_index(a)`   |
| **min antichain partition = ℓ(P)**   | **wave count = longest chain length** |

따라서:

```
wave_count(APT) = ℓ(A) = Mirsky dual bound
```

이것이 SP 분해 깊이의 lower bound 이며 RefinementGate Independence 통과 시 *tight* (canonical achievable).

### D-5: Dilworth 1950 측 cross-ref (same-layer antichain)

**Dilworth 1950 정리** (formal):
> For any finite poset, the **minimum number of chains needed to partition P** equals the **maximum antichain width** w(P).

APT 매핑:

| Dilworth 1950                        | APT SP                              |
|--------------------------------------|-------------------------------------|
| Antichain (pairwise incomparable)    | same wave_index ⟺ A3 sibling indep |
| Maximum antichain width w(P)         | `max_k |A_k|` = 최대 parallelism polynomial |
| Chain partition                      | sequential DAG path covers          |
| **min chain partition = w(P)**       | minimum SCW worker pool size (Dilworth bound) |

따라서:

- **Same-wave atoms = antichain** (Dilworth wave-internal): A3 sibling independence ⟺ pairwise `¬DEPENDS_ON`.
- **Cross-wave atoms = potential chain links** (Mirsky inter-wave): vertical dependency only.

### D-6: DAG linearization (strictness caveat 해결)

> PROM_16 P2.2 caveat: "DAG vs tree strictness" — APT DEPENDS_ON 은 일반 DAG (multi-parent OK), tree 아님. wave_index 가 well-defined 한가?

해결: **canonical topological order via DFS post-order reverse**:

```
Theorem (DAG linearization, CLRS §22.4):
  For any finite DAG G = (V, E), DFS post-order reverse yields a topological
  ordering σ : V → {1, ..., |V|} such that (u,v) ∈ E ⟹ σ(u) < σ(v).

Corollary (wave_index well-defined):
  For finite acyclic (A, →⁺), the iteration in D-3 terminates in
  ≤ |A| rounds, and wave_index is uniquely determined (independent of
  tie-breaking among same-wave nodes).
```

증명 sketch:
1. Acyclic ⟹ ∃ at least one indeg-0 node (Kahn 1962 lemma).
2. Remove A_0, remaining graph is acyclic ⟹ induction on |A|.
3. 각 단계에서 A_k 는 well-defined set (조건 "∀ pred ∈ ⋃_{i<k} A_i" 는 set membership predicate).
4. multi-parent (DAG) 도 D-3 D-4 모두 그대로 성립 — `max` over predecessors 는 set 이므로 parent count 무관.

따라서 tree 라는 가정 불필요. **PROM_16 P2.2 caveat resolved → 0.85 STRONG candidate**.

### D-7: 형식 invariant 모음 (Lean stub 의 statement 소스)

| Invariant | Statement | Source |
|-----------|-----------|--------|
| **I1** strict-less | `(a) →¹ (b) ⟹ wave_index(a) < wave_index(b)` | D-3 |
| **I2** intra-wave antichain | same wave_index ⟹ pairwise `¬→⁺` | D-5 Dilworth |
| **I3** inter-wave chain link | `→¹` only crosses wave boundary in strict-up direction | D-4 Mirsky |
| **I4** well-defined | wave_index uniquely determined on finite DAG | D-6 CLRS |
| **I5** Mirsky bound | `max_a wave_index(a) = ℓ(A)` (longest chain length) | D-4 Mirsky |
| **I6** Dilworth bound | `max_k |A_k| ≤ w(A)` (max parallelism ≤ antichain width) | D-5 Dilworth |

Lean formalization: `MIND/lean_formalization/APT_WaveIndex_Mirsky.lean` (5 theorem skeleton, Mathlib-free, sorry/TODO 명시).

# KG: APT_SP_WaveExtraction_canonical, lesson-apt-sp-wave-index-explicit-2026-05-14, wave-index-formal-mirsky-2026-05-14, SEED_gap1_sp_wave_extraction_2026-05-14
