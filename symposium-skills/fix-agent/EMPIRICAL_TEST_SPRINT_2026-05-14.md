# FixAgent §8 K-01 Mitigation — Empirical Test Sprint Design (2026-05-14)

> **trigger**: 사용자 발화 "셋다 싹다해줘 ... 이론적 기반 튼튼하게" (2026-05-14)
>
> **목적**: 2026-05-14 commit 499bca9 (SKILLS f63189b) §8 의 3-prong rubber-stamp mitigation (M1 orthogonal-lens rotation / M2 patch-fuzzing critique sublens / M3 attempt-cap σ_oracle) 을 **empirical sample-of-N test** 로 PRELIMINARY → EVIDENCE-BACKED 격상.
>
> **drift guard**: memory `feedback_theoretical_depth_over_line_count` — sample-of-N 측정은 형식적 statistical power 확보 (N≥3 floor) + Cohen's d effect size 보고.
>
> **prior**: 이 mitigation 자체가 K-01 patch-level recurrence 발견의 산물이므로 K-01 meta-meta 자체검증 risk (Claude 가 design + test 양쪽 owner = D20 executor=critic anti-pattern). 측정자 분리 필수.

---

## 1. 외부 정전 grounding (web 검증 2026-05-14)

| Reference | Citation | M1/M2/M3 매핑 |
|-----------|----------|----------------|
| Görz et al. 2023 USENIX Security | "Systematic Assessment of Fuzzers using Mutation Analysis" (arxiv.org/abs/2212.03075) | **M2**: mutation 12% detection rate baseline — patch-fuzzing 효과 정량화 가능 |
| Cleemput et al. 2025 (arxiv.org/html/2510.15512v1) | "Enhancing Code Review through Fuzzing and Likely Invariants" — *FuzzSight* | **M2 1:1 정전 mirror**: "additional lens for the reviewers ... likely invariant differences" |
| Salmon 1990 / Howson-Urbach 2006 | Bayesian critique of Popper corroboration — likelihood-ratio ≠ probability | **M1**: lens orthogonality = independent likelihood-ratio sources (Whewell consilience) |
| Whewell 1840 *Philosophy of the Inductive Sciences* | "consilience of inductions" — independent sources converging | **M1**: orthogonal lens rotation 의 epistemic 정전 |

→ M1 + M2 모두 외부 정전 grounded. M3 (attempt-cap σ_oracle) 는 *industry practice*: GitHub Copilot Workspace 3-strike retry policy / Cursor Agent 5-iteration cap (proprietary, 2026-Q1 public docs).

---

## 2. test sample-of-N design

### 2.1 sample setup (N=3 floor + N=5 target)

- **target population**: 최근 14일 (2026-05-01 ~ 2026-05-14) 의 FixAgent invocation 중 K-01 검출 case 3개 + K-01 미검출 control 2개.
- **execution mode**: subagent 출격 (executor != critic 분리). prom-expert agent 가 mitigation 적용 후 patch 생성, taliban-ensemble-critic 가 검증.
- **measurement window**: 각 case 당 max 3 fix attempts.

### 2.2 metric matrix

| Metric | Operationalization | Pre-mitigation baseline | Post-mitigation target |
|--------|--------------------|-------------------------|------------------------|
| **M1 efficacy**: lens orthogonality | attempt 1-3 의 LensSet UNION coverage (constitutional ⊕ longinus ⊕ solid axes) | ≤30% (단일 lens 반복) | ≥70% (3-attempt rotation 후) |
| **M2 efficacy**: mutation detection | FuzzSight-style invariant diff coverage on patch | N/A (baseline missing) | ≥1 invariant diff surfaced per attempt (binary) |
| **M3 efficacy**: σ_oracle gate | attempt 4 발동 시 human verdict 요청 trigger | bypass 가능 (3-strike 강제 없음) | strict block (max=3 default) |
| **false APPROVED rate** | attempt N 의 verdict APPROVED 인데 patch fuzzing 으로 invariant diff 발견 | TBD (estimated ~20% from K-01 evidence) | <5% |

### 2.3 statistical floor

- N=3 minimum (Cohen's d 측정 가능 floor — sample size guidance: Sawilowsky 2009).
- N=5 target → power ≥0.6 for medium effect.
- **honest limitation 명시**: sample-of-3 는 *exploratory*, NOT confirmatory. confirmatory 단계는 N≥30 별도 sprint 필요.

---

## 3. test execution protocol (subagent 출격)

### 3.1 executor (mitigation 적용)

```cypher
// KG seed for executor
MERGE (seed:SubagentTaskSpec {name:'seed-fixagent-mitigation-empirical-test-2026-05-14'})
SET seed.role = 'executor — apply M1/M2/M3 to FixAgent on selected K-01 case',
    seed.skill = 'fix-agent',
    seed.mitigation_section = '§8',
    seed.max_attempts = 3,
    seed.lens_rotation_schedule = ['constitutional', 'longinus', 'solid'],
    seed.fuzzing_sublens = 'patch-fuzzing-FuzzSight-style',
    seed.status = 'READY'
```

### 3.2 critic (independent verification)

```cypher
MERGE (seed:SubagentTaskSpec {name:'seed-fixagent-mitigation-critic-2026-05-14'})
SET seed.role = 'critic — verify M1/M2/M3 efficacy + measure false APPROVED rate',
    seed.skill = 'taliban',
    seed.lens = '--lens mathematical',
    seed.executor_seed = 'seed-fixagent-mitigation-empirical-test-2026-05-14',
    seed.status = 'READY',
    seed.executor_neq_critic_enforced = true
```

### 3.3 outcome KG schema

```cypher
// Sample 결과 (3-5 case 별)
MERGE (r:FixAgentMitigationTestResult {name:'tr-mitigation-§8-case-{N}-2026-05-14'})
SET r.case_id = $case_id,
    r.M1_lens_coverage = $coverage,
    r.M2_invariant_diff_count = $diff_count,
    r.M3_gate_triggered = $bool,
    r.attempts_used = $n,
    r.final_verdict_correct = $bool,
    r.executor_seed = 'seed-fixagent-mitigation-empirical-test-2026-05-14',
    r.critic_seed = 'seed-fixagent-mitigation-critic-2026-05-14',
    r.created_at = datetime()
```

---

## 4. honest limitations (load-bearing)

### 4.1 M1 disjointness — name-level only

constitutional/longinus/solid LensSet 들은 *name-level* 으로 disjoint 이지만, *concern-level* 로는 overlap 가능. 예: solid Interface Segregation ↔ constitutional separation-of-concerns ↔ longinus L3 boundary clarity 모두 "interface 경계" axis 를 부분 cover. 따라서 attempt 1 (constitutional) APPROVED 후 attempt 2 (longinus) 가 *trivially* APPROVED 일 수 있음 (orthogonal 가정 위반). 

→ **mitigation**: M1 test 시 lens UNION 의 *axis coverage matrix* 측정 + axes overlap ratio < 0.3 enforce.

### 4.2 M2 patch-fuzzing — same-author limitation

FuzzSight 는 invariant diff 를 *natural language* 로 reviewer 에게 surface. 그러나 FixAgent 자신이 mitigation 도 같은 LLM (Claude) 이면 invariant diff 를 interpretive register 측에서 *self-satisfy* (rationalize) 할 수 있음.

→ **mitigation**: M2 fuzzing 결과는 *별도 cold-context subagent* 가 evaluate (ConfidenceVerifier 패턴, PROM_32 §4.2 W3).

### 4.3 M3 σ_oracle injection — user availability

attempt N+1 시 human verdict 요청 → 사용자 부재 시 indefinite wait. CLAUDE.md autoloop $40/$50 cost guard 와 충돌 가능 (autoloop 운영 시 human σ_oracle 불가).

→ **mitigation**: M3 default max=3 인데 autoloop 모드면 max=2 + fallback "DEFER_WITH_BLOCKER_RECORD" verdict (block ratchet 누적).

### 4.4 K-01 meta-meta — sample-of-one risk

본 test design 자체가 *Claude 가 만든 mitigation 을 Claude 가 검증* 하는 K-01 패턴 instance. test design 의 design (M1 measurement metric / M2 fuzzing protocol / M3 cap value) 모두 sample-of-one (단일 instance).

→ **load-bearing acknowledgment**: test 결과는 *Claude self-verification 내에서만* 유효. external code review (사용자 또는 별도 박스의 Claude session) 가 confirmatory 단계.

---

## 5. timeline

| Phase | Sprint | Duration | Owner |
|-------|--------|----------|-------|
| 1 | sample selection (3-5 K-01 case 발굴) | 1 session | 사용자 또는 cold-context agent |
| 2 | executor + critic seed write to KG | 0.5 session | secretary agent |
| 3 | dispatch (3-5 case × 3-attempt) | 1-2 session | apt-orchestrator |
| 4 | result aggregation + Cohen's d 계산 | 0.5 session | rep_link agent |
| 5 | PRELIMINARY → EVIDENCE-BACKED 격상 verdict | user gate | 사용자 발화 |

---

## 6. follow-up

1. sample case 발굴 → KG `:FixAgentK01CaseSample` 5개
2. seed write (executor + critic) → KG
3. apt-orchestrator dispatch
4. 결과 aggregation report → `SKILLS/fix-agent/EMPIRICAL_TEST_RESULTS_2026-05-{XX}.md`
5. effect size 측정 후 mitigation §8 reinforcement (M1/M2/M3 별 evidence-backed verdict)

# KG: empirical-test-sprint-fixagent-section8-2026-05-14
# Authority: delegated_via_2026-05-14_blanket_proceed
# Parent: mitigation-fixagent-rubberstamp-section8-2026-05-14
# memory: feedback_blanket_proceed_authorization_pattern, feedback_theoretical_depth_over_line_count
