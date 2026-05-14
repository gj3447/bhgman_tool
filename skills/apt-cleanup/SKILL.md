---
name: apt-cleanup
kg_ref: ATOM_Skill_apt_cleanup
version: "27.1.0"
channel: experimental
description: >
  APT Phase 6 Cleanup Gate — TDD REFACTOR phase의 cycle-level 거울. SA→SP→ST→SCW + meta-review 만으로는
  평면 누적 / fat file 못 막음 (atomic-span shipping = 1 task = 1 file 정규화 자체가 평면 누적 메커니즘).
  Robert Martin Package Principles (CCP/CRP/REP/ADP/SDP/SAP) 의 *folder-level* enforcement.
  4-tool ratchet (Tach / complexipy --ratchet / Lizard / vulture / deptry) + commit ratio metric (refactor:feature ≥ 0.2).
  Gate Check Hook Cypher 강제: 이전 N 사이클의 fat-file LOC + duplication ratio + dependency cycle 측정.
  Invoke when: SCW 완료 후 / N 사이클 누적 후 / "왜 폴더가 평면이지?" 의문 시 / "SOLID 했는데 폴더 개판" 진단 시.
  Enforces: CCP folder cohesion / CRP shared lifecycle / ADP no cycles / cycle-level ratchet.
  Active Weapons (2026-05-14): Harness 3-tier (IDE-host / runtime / managed) 매핑 진단 (Step 18 folder ↔ tier audit) + Taliban `/88-taliban <folder>` mathematical lens (Step 19-20 CCP/CRP/REP/ADP/SDP/SAP folder-level audit). hub-harness-3tier + hub-taliban-immunity resolve.
  # KG: ATOM_Skill_apt_cleanup, lesson-apt-phase6-cleanup-missing-2026-04-28, lesson-solid-class-level-vs-package-level-mismatch-2026-04-29
---

## 🔗 MIC Binding (SOLID-DIP)

**ROLE**: Phase 6 Cleanup Gate — APT cycle 의 6번째 phase (SA → SP → ST → SCW → meta-review → **cleanup**).
**POSITION**: TDD REFACTOR phase 의 cycle-level 거울 — 단일 file refactor 가 아닌 *folder/cycle 차원* 정리.

```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot {name:'CleanupGate'})
RETURN s.currentConcrete, s.invocation
```

# KG: MIC_v1, lesson-apt-phase6-cleanup-missing-2026-04-28

---

## ⚔ Active Weapons — Phase Cleanup (6/5, RFC2)

> Cleanup 측 활성 5무기 (parent /apt orchestrator §"5무기 Phase Integration Matrix" mirror).

| Step | Weapon | Invocation | Trigger | Output |
|------|--------|-----------|---------|--------|
| Step 18 (3-tier folder audit) | **Harness** | 3-tier mapping diagnosis: IDE-host (Cursor/Claude Code) / runtime (LangGraph/CrewAI/Google ADK) / managed (Anthropic Managed Agents) 측 폴더 배치 검사 | SCW FulfillmentGate APPROVED + N 사이클 누적 | tier 라벨 + 잘못 배치된 file 리포트 |
| Step 19 (4-tool ratchet) | **Taliban** (mathematical lens) + tool chain | `/88-taliban <folder> --lens mathematical` + `tach` (dep cycle) + `complexipy --ratchet` (complexity) + `lizard` (LOC) + `vulture` (dead code) + `deptry` (unused dep) | folder 평면 누적 의심 / fat-file 임계치 | 4-tool ratchet result (각 monotone decreasing 검증) |
| Step 20 (folder-level CCP/ADP gate) | **Taliban** (88-taliban) | mathematical lens 113 측 CCP/CRP/REP/ADP/SDP/SAP 위반 audit (Robert Martin Package Principles) | 4-tool ratchet PASS 후 final gate | `CleanupVerdict` PASS / NEEDS_REFACTOR / BLOCK (pass_count ≥ 5/7) |

**Cleanup 진입 hub**: `hub-harness-3tier` (3계층 매핑 정전) + `hub-taliban-immunity` (folder-level audit).

**Anti-pattern**: SOLID 클래스 분리 했는데 폴더 평면 dump = CCP 위반. atomic-span shipping (1 task = 1 file 정규화) 자체가 평면 누적 메커니즘 — Cleanup phase 없으면 누적 무한.

**Two-tier cleanup** (RFC2): local mini-RGR (SA→SP / SP→ST / ST→SCW transition 측 RED/GREEN/REFACTOR 3-beat) + global Phase 6 (cross-phase view, cycle-level ratchet). 둘 다 enforce.

# KG: hub-harness-3tier, hub-taliban-immunity, MIC_v1.Harness, MIC_v1.AdversarialValidator (LensSet mathematical), rfc-apt-two-tier-cleanup-2026-04-29

---

# /apt-cleanup — Phase 6: 평면 누적 막는 cycle-level Cleanup Gate

> **에이전트가 SOLID 만 따르면 클래스/함수 단위는 깨끗해진다. 그런데 분리한 클래스를 어디 폴더 넣을지 규칙이 없으면 평면에 다 던진다.**
> SOLID는 *class-level*. Package Principles (CCP/CRP/REP/ADP/SDP/SAP) 가 *folder-level*. 별개 layer.
> APT atomic-span shipping = "1 task → 1 file" 정규화가 평면 누적 메커니즘 그 자체.

---

## Why Phase 6 (학문 grounding)

### TDD 의 RED-GREEN-REFACTOR 3-phase

```
RED:     test 작성 (실패)
GREEN:   minimum code (테스트 통과)
REFACTOR: 누적 정리 ← APT 에 *없는* phase
```

APT cycle SA → SP → ST → SCW + meta-review = RED + GREEN + meta. **REFACTOR 거울 부재** — 매 사이클 끝에 *cycle-level* 누적 정리 phase 가 없음 → 매 task 가 파일 1개씩 던지면서 평면 누적.

### Robert Martin 6 Package Principles — folder-level

| Principle | 의미 | Phase 6 enforcement |
|---|---|---|
| **CCP** Common Closure | 같이 변하는 것 같이 묶어라 | 같은 commit 에 자주 등장하는 file 들 → 같은 folder 권장 |
| **CRP** Common Reuse | 같이 재사용되는 것 같이 | import 그래프 cluster → folder 경계 |
| **REP** Reuse-Release Equivalence | 재사용 단위 = 릴리즈 단위 | folder = atomic versioning unit (semver scope) |
| **ADP** Acyclic Dependencies | 폴더 의존 cycle 금지 | `tach` import-linter cycle 검출 |
| **SDP** Stable Dependencies | 안정적인 쪽으로 의존 | instability metric I = Ce/(Ca+Ce) |
| **SAP** Stable Abstractions | 안정 = 추상도 비례 | abstractness A = abstract/total ratio |

### Stevens-Myers-Constantine (1974) Cohesion/Coupling
모든 architecture 이론의 뿌리. LCOM (Chidamber-Kemerer 1994) 으로 정량화.

### GitClear 2024 — 산업 evidence
Copilot/AI agent 도입 후 *code churn 증가* 보고. atomic-span shipping smell 직접 evidence.

→ details: [`references/principles.md`](references/principles.md) (lazy load).

---

## 0. HARD RULES (cleanup gate 강제)

| # | Rule | Enforcement |
|---|---|---|
| C1 | **Phase 6 entry 는 SCW 완료 + meta-review 직전** | apt-meta-review 호출 *전* cleanup-gate 통과 강제 |
| C2 | **이전 N=5 사이클 누적 metric ratchet** | 새 fat file > prev → BLOCK. duplication ratio > prev → BLOCK |
| C3 | **commit ratio refactor:feature ≥ 0.2** | 5 feat commit 당 1 refactor commit 최소 |
| C4 | **folder cycle 0 (ADP)** | tach 에러 시 BLOCK |
| C5 | **fat file LOC threshold = MethodologyConfig.cleanup_fat_file_threshold** | default 500 (apt vibe_coding_sweet 와 동일) |

---

## Cycle 흐름

```
SA → SP → ST → SCW → [PHASE 6 CLEANUP GATE] → meta-review → next cycle
                              ↓
                       4-tool ratchet
                              ↓
                       PASS → continue
                       FAIL → halt + spec for refactor commit
```

---

## 4-Tool Ratchet (top-level)

| Tool | 측정 | Phase 6 정책 |
|---|---|---|
| **tach** | folder import cycle | 0 cycles (HARD) |
| **complexipy --ratchet** | function cyclomatic complexity | 이전 사이클 max ratchet down |
| **lizard** | function LOC, CCN | 함수 LOC ≤ 50 / CCN ≤ 10 |
| **vulture** | dead code | unused > 0 → 신규 dead = BLOCK |
| **deptry** | unused/missing deps | 0 (HARD) |

→ 도구별 사용법 + ratchet 패턴: [`references/tools.md`](references/tools.md).

---

## CanonicalServiceTemplate (folder taxonomy)

새 service/skill 생성 시 권장 layout (Vertical Slice + Bounded Context):

```
<service-name>/
├── domain/          # entities, value objects, domain events (no IO)
├── application/     # use cases, commands, queries (orchestration)
├── infrastructure/  # adapters (DB, HTTP, MQ) — IO at boundary
├── api/             # entry point (REST/GraphQL/gRPC)
└── tests/           # mirror domain/application structure
```

CCP: 같은 domain entity 변경 → 같은 folder. CRP: domain/* 만 import 하는 application/* 분리.
→ 자세한 spec + anti-pattern: [`references/template.md`](references/template.md).

---

## Cleanup Gate Cypher (Hook)

```cypher
// 이전 N=5 사이클 metric 비교 (ratchet)
MATCH (cur:CleanupRun {cycle_id: $current})
MATCH (prev:CleanupRun) WHERE prev.completed_at < cur.completed_at
WITH cur, prev ORDER BY prev.completed_at DESC LIMIT 5
WITH cur, collect(prev) AS history
WITH cur, history,
     [p IN history | p.fat_files_count] AS fat_history,
     [p IN history | p.duplication_ratio] AS dup_history,
     [p IN history | p.dead_code_count] AS dead_history
WITH cur, history,
     reduce(m=0, x IN fat_history | CASE WHEN x>m THEN x ELSE m END) AS prev_fat_max,
     reduce(m=0.0, x IN dup_history | CASE WHEN x>m THEN x ELSE m END) AS prev_dup_max,
     reduce(m=0, x IN dead_history | CASE WHEN x>m THEN x ELSE m END) AS prev_dead_max
RETURN cur.fat_files_count <= prev_fat_max AS fat_ratchet_ok,
       cur.duplication_ratio <= prev_dup_max AS dup_ratchet_ok,
       cur.dead_code_count <= prev_dead_max AS dead_ratchet_ok,
       cur.tach_cycles = 0 AS adp_ok,
       cur.deptry_count = 0 AS deps_ok
```

→ Gate logic detail: [`references/gate.md`](references/gate.md).

---

## Output (CleanupRun KG node)

```cypher
MERGE (cr:AbstractNode:CleanupRun {name: 'cleanup-' + $cycle_id})
SET cr.cycle_id = $cycle_id,
    cr.fat_files_count = $fat_count,
    cr.fat_files = $fat_paths,
    cr.duplication_ratio = $dup_ratio,
    cr.dead_code_count = $vulture_count,
    cr.tach_cycles = $tach_cycles,
    cr.deptry_count = $deptry_count,
    cr.complexipy_max = $complexipy_max,
    cr.lizard_loc_max = $lizard_loc_max,
    cr.commit_ratio_refactor_feature = $commit_ratio,
    cr.gate_passed = $gate_passed,
    cr.refactor_recommendations = $recs,
    cr.completed_at = datetime()
```

→ 메트릭 수집 자동화: [`references/metrics.md`](references/metrics.md).

---

## Lazy-load reference files (Progressive Disclosure)

| File | Topic | Read when |
|---|---|---|
| [`references/principles.md`](references/principles.md) | Robert Martin 6 Package Principles + Stevens-Myers-Constantine + LCOM 학문 grounding | 학술 인용 / 사용자 질문 시 |
| [`references/tools.md`](references/tools.md) | 4-tool ratchet (tach/complexipy/lizard/vulture/deptry) 사용법 + ratchet 패턴 | tool 호출 시 |
| [`references/template.md`](references/template.md) | CanonicalServiceTemplate (Vertical Slice + Bounded Context) layout + anti-pattern | 새 service 생성 시 |
| [`references/gate.md`](references/gate.md) | Phase 6 Gate Cypher 전체 + override flow + escalation | gate fail 시 |
| [`references/metrics.md`](references/metrics.md) | CleanupRun KG schema + collection script + dashboard query | metric 분석 시 |

---

## 다른 skill 과의 관계

```
APT cycle:
  apt-sa     → identity/anchor
  apt-sp     → recursive Span decomposition
  apt-st     → crystallization (Contract + Task)
  apt-scw    → TDD implementation (1 task = 1 file)
                                       ↓ atomic-span shipping (평면 누적!)
  apt-cleanup ← Phase 6 — cycle-level REFACTOR phase (4-tool ratchet)
                                       ↓ pass
  apt-meta-review → methodology meta-improvement

orthogonal: harness (4-Axis Constrain), longinus (KG-code binding),
            taliban (--lens solid for class-level vs --lens longinus for ref drift)
```

---

## What NOT To Do

| 금지 | 이유 | 대안 |
|---|---|---|
| 매 task 끝마다 cleanup | overhead 폭발 | cycle 끝 (SCW 완료 후) 1회 |
| LLM "SOLID 하게" 만 지시 | class-level 통과해도 folder-level 실패 | Package Principles 명시 + Phase 6 강제 |
| fat file 즉시 split | premature abstraction risk | 누적 N 사이클 후 ratchet 기반 split |
| commit ratio 무시 | feature 만 누적 = Goodhart 자기파괴 | refactor:feature ≥ 0.2 minimum |

---

*atomic-span shipping 이 평면 누적의 원인이고, Phase 6 가 그 정정 메커니즘이다.
SOLID 가 못 잡는 것은 Phase 6 + 4-tool ratchet 이 잡는다.*

---

## History

> Repo-level changes: [`/CHANGELOG.md`](../CHANGELOG.md). Per-commit: `git log -- apt-cleanup/SKILL.md`.

| Version | Date | Summary | KG Ref |
|---|---|---|---|
| **v1.0.0** | 2026-04-29 | Phase 6 Cleanup Gate spec materialization. lesson-apt-phase6-cleanup-missing-2026-04-28 의 solution → 새 skill 결정화. 4-tool ratchet + CanonicalServiceTemplate + Cypher gate hook | `lesson-apt-phase6-cleanup-missing-2026-04-28`, `lesson-prismv2-services-flat-layout-decay-20260428`, `lesson-solid-class-level-vs-package-level-mismatch-2026-04-29` |

→ Channel: **experimental** — prismv2 첫 적용 + N=5 사이클 ratchet evidence 누적 후 → beta. 정전화 후 → stable.

# KG history: ATOM_Skill_apt_cleanup / lesson-prom16-skill-versioning-academic-2026-04-29 / lesson-prom16-skillver-progressive-disclosure-drift-2026-04-29
