# Boundary Mold (apt-st) Detail (Phase-Specific)

> apt-st는 6 architectural molds 중 *Boundary*. 명세 권위 (specification authority).

---

## Role

**Specification authority.** Approved AtomicSpans를 받아 SemanticTwins (Contract + Task)로 결정화. *soft meaning* 이 *hard specification* 으로 굳는 자리.

---

## Tools

| Tool | Purpose |
|---|---|
| Contract Registry | Create, amend, version AptContracts |
| Twin Registry | Lifecycle: draft → crystallized → implemented → validated → stale → broken |
| Hub Manager | CrystallizationEvent hub 생성/검증 ([crystallization_hub.md](crystallization_hub.md)) |
| NFR Configurator | 환경별 `nfr_*` 속성 설정 ([nfr_env_variants.md](nfr_env_variants.md)) |

---

## Decides vs NOT Decides

### Decides
- typed interface (input_type, output_type)
- pre/postconditions
- NFR constraints
- composition topology (SEQUENCED_WITH)
- hardware requirements (REQUIRES_HARDWARE)

### Does NOT Decide
- *how* to implement → Execution (apt-scw)
- 분해가 옳은가 → Intent (apt-sp)
- 승인/거부 → Governance (apt)

---

## Feedback Into Boundary

Assurance (apt-scw)가 보낼 수 있는 feedback:
- `contract_gap` (postcondition 불완전)
- `type_mismatch` (실제 데이터 타입 ≠ 선언)
- `edge_case` (acceptance_criteria 누락 시나리오)
- `nfr_violation` (NFR 임계값 미달)

각각의 Boundary 대응:
1. publish `ContractAmended` Kafka event
2. update Contract 필드
3. re-run tau_check
4. re-activate (Active 전이)

자세한 amendment 패턴: [amendment_scenarios.md](amendment_scenarios.md)

---

## 6 Molds Cross-Reference

| # | Mold | Command | Role |
|---|------|---------|------|
| 1 | Governance | `/apt` | Oversight: approvals, gates, config |
| 2 | Intent | `/apt-sp` | Planning: decompose, explore, link |
| 3 | **Boundary** | **`/apt-st`** | **Specification: crystallize, compose, specify** |
| 4 | Execution | `/apt-scw` | Building: TDD implement, lock/unlock |
| 5 | Assurance | `/apt-scw` | Quality: verify, fulfill, feedback |
| 6 | Memory | cross-cuts | Knowledge: tiers, context, reflection |

apt-scw는 Execution + Assurance 둘 다. 같은 phase의 두 측면.

---

## anti-pattern

### E-ST-Mold-1: Boundary가 Execution 결정 침범
**Context:** Contract에 "implement with sorted dict" 같은 구현 방식 명시.
**Lesson:** *what* (Contract) 와 *how* (구현) 분리. Boundary는 명세, Execution은 구현.
**Guard:** Contract semantic_meaning 검토 — 구현 동사 ("sort", "loop", "iterate") 발견 시 경고.

### E-ST-Mold-2: Boundary가 Intent 결정 침범
**Context:** ST가 Span 분해 변경 시도. 자식 atom 합치거나 분해.
**Lesson:** 분해는 SP의 권위. ST는 *받은 atom*에만 작용.
**Guard:** ST cypher가 AptSpan/AtomicSpan 노드 *수정* 차단. ST는 SemanticTwin/Task/Contract만 생성/수정.

# KG: APT_ST_BoundaryMold_canonical
