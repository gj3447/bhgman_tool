# FulfillmentGate (SCW → Fulfilled) — 7 Checks Rego policy
# RFC: rfc-apt-v27-A7-gate-hook-fail-closed-4-layer-2026-04-30 + apt-scw/references/fulfillment_gate.md
#
# 7 mandatory checks (ALL must pass for Contract.status: Active→Fulfilled):
# 1. All acceptance tests pass
# 2. Output type matches contract.output_type
# 3. Pre/postconditions checked in code
# 4. KG reference comments present (# KG: TASK_xxx, CONTRACT_xxx)
# 5. Complexity within threshold (lines ≤ cfg.complexity_threshold)
# 6. Test-Contract alignment (postcondition verified by tests)
# 7. NFR assertions pass (latency/memory/accuracy benchmarks if set)

package apt.fulfillment_gate

import future.keywords.if
import future.keywords.in

default allow := false

# Check 1: 모든 acceptance test PASS
check_1_all_tests_pass if {
  input.test_run.passed == input.test_run.total_tests
  input.test_run.failed == 0
  input.test_run.skipped == 0
}

# Check 2: output type 일치
check_2_output_type_matches if {
  input.actual.output_type == input.contract.output_type
}

# Check 3: pre/post conditions in code
check_3_pre_post_in_code if {
  input.actual.precondition_check_present == true
  input.actual.postcondition_check_present == true
}

# Check 4: KG refs present (string substring check via contains)
check_4_kg_refs if {
  contains(input.actual.kg_refs_in_source, "TASK_")
  contains(input.actual.kg_refs_in_source, "CONTRACT_")
}

# Check 5: complexity threshold
check_5_complexity if {
  input.actual.lines <= input.config.complexity_threshold
}

# Check 6: test-contract alignment
check_6_alignment if {
  input.actual.test_assertion_count > 0
  input.actual.postcondition_verified == true
}

# Check 7: NFR pass (only if NFR set)
nfr_required if {
  input.contract.nfr_latency_p99_ms != null
}

nfr_required if {
  input.contract.nfr_memory_mb != null
}

check_7_nfr if {
  not nfr_required
}

check_7_nfr if {
  input.contract.nfr_latency_p99_ms == null
  input.contract.nfr_memory_mb == null
}

check_7_nfr if {
  input.contract.nfr_latency_p99_ms != null
  input.actual.latency_p99_ms <= input.contract.nfr_latency_p99_ms
}

# 메인 allow — 7/7 모두 통과
allow if {
  check_1_all_tests_pass
  check_2_output_type_matches
  check_3_pre_post_in_code
  check_4_kg_refs
  check_5_complexity
  check_6_alignment
  check_7_nfr
}

# Per-check deny
deny[msg] {
  not check_1_all_tests_pass
  msg := sprintf(
    "Check 1 FAIL: tests passed %d/%d (failed=%d skipped=%d)",
    [
      input.test_run.passed,
      input.test_run.total_tests,
      input.test_run.failed,
      input.test_run.skipped,
    ],
  )
}

deny[msg] {
  not check_2_output_type_matches
  msg := sprintf(
    "Check 2 FAIL: output_type mismatch — expected '%s', got '%s'",
    [input.contract.output_type, input.actual.output_type],
  )
}

deny[msg] {
  not check_3_pre_post_in_code
  msg := "Check 3 FAIL: precondition/postcondition assertions missing in source code"
}

deny[msg] {
  not check_4_kg_refs
  msg := "Check 4 FAIL: # KG: TASK_xxx / # KG: CONTRACT_xxx comments missing (Longinus L3 binding violation)"
}

deny[msg] {
  not check_5_complexity
  msg := sprintf(
    "Check 5 FAIL: %d lines > %d threshold — AP5 Monolith Creep, SP 재분해 필요",
    [input.actual.lines, input.config.complexity_threshold],
  )
}

deny[msg] {
  not check_6_alignment
  msg := "Check 6 FAIL: Test-Contract alignment 위반 (AP8 Trivial Tests)"
}

deny[msg] {
  not check_7_nfr
  msg := sprintf(
    "Check 7 FAIL: NFR latency_p99 %.1fms > threshold %dms (AP9 NFR Amnesia)",
    [input.actual.latency_p99_ms, input.contract.nfr_latency_p99_ms],
  )
}

# Audit metadata
audit := {
  "gate_name": "FulfillmentGate",
  "checks_total": 7,
  "checks_passed": count([c |
    c := [
      check_1_all_tests_pass,
      check_2_output_type_matches,
      check_3_pre_post_in_code,
      check_4_kg_refs,
      check_5_complexity,
      check_6_alignment,
      check_7_nfr,
    ][_]
    c == true
  ]),
  "verdict": (allow_verdict),
  "deny_reasons": deny,
}

allow_verdict := "APPROVED" if allow
allow_verdict := "REJECTED" if not allow
