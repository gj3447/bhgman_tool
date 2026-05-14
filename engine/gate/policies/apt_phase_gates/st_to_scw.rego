# APT Phase 3→4 gate (ST → SCW) — Rego policy
# RFC: rfc-apt-v27-A9-opa-rego-full-2026-05-11
#
# ST→SCW 전환 조건:
# 1. 모든 AtomicSpan에 :SemanticTwin CRYSTALLIZES_TO 연결됨
# 2. 각 Twin에 HAS_CONTRACT (AptContract 1+) + HAS_TASK (SemanticTask 1+)
# 3. Contract status = 'Active' (Draft/Rejected 차단)
# 4. tau_check 5/5 PASS (input/output concrete, pre/post boolean, semantic_meaning ≥20자)
# 5. Task impact_tests 비어있지 않음 + NEW_FILE 마커 OR 실제 경로
# 6. v27 A2 ContractSchema (9-axis DbC) 또는 default 7-field 충족
# 7. 8 ST Decision Areas Tier 1 5/8 채워짐 (Cover Scope Exhaustive)

package apt.phase_gates.st_to_scw

import future.keywords.if
import future.keywords.in
import future.keywords.every

default allow := false

# 모든 AtomicSpan에 Twin 연결
all_atoms_have_twin if {
  every atom in input.st.atoms {
    atom.has_twin == true
  }
}

# Twin마다 Contract + Task 존재
all_twins_have_contract_task if {
  every twin in input.st.twins {
    twin.has_contract == true
    twin.has_task == true
  }
}

# Contract status='Active'
all_contracts_active if {
  every ct in input.st.contracts {
    ct.status == "Active"
  }
}

# tau_check 5/5 PASS
tau_check_pass if {
  every ct in input.st.contracts {
    ct.tau_check_pass == true
  }
}

# Task impact_tests 충족
impact_tests_set if {
  every t in input.st.tasks {
    count(t.impact_tests) > 0
  }
}

# Contract field 충족 (default 7 또는 v2 9)
contract_fields_complete if {
  every ct in input.st.contracts {
    expected := input.config.contract_default_fields
    ct.field_count >= expected
  }
}

# 8 ST Decision Areas Tier 1 (5/8) 충족
st_decision_areas_tier1_complete if {
  count(input.st.decision_areas_completed) >= input.config.st_tier1_count
}

# 메인 allow
allow if {
  all_atoms_have_twin
  all_twins_have_contract_task
  all_contracts_active
  tau_check_pass
  impact_tests_set
  contract_fields_complete
  st_decision_areas_tier1_complete
}

deny[msg] {
  not all_atoms_have_twin
  missing := [a.name | a := input.st.atoms[_]; not a.has_twin]
  msg := sprintf("Twin 미생성 atoms: %v", [missing])
}

deny[msg] {
  not all_twins_have_contract_task
  msg := "Twin → Contract/Task 연결 누락 (V14_HUB_MISSING_ROLE)"
}

deny[msg] {
  not all_contracts_active
  msg := "Contract status != 'Active' (Draft/Rejected 잔존)"
}

deny[msg] {
  not tau_check_pass
  msg := "tau_check 5/5 PASS 안 됨 (input/output abstract 또는 prose precondition)"
}

deny[msg] {
  not impact_tests_set
  msg := "Task.impact_tests 비어있음 (V_SCW_TDAD_EmptyImpactTests)"
}

deny[msg] {
  not contract_fields_complete
  msg := sprintf(
    "Contract field 수 부족 (expected=%d default)",
    [input.config.contract_default_fields],
  )
}

deny[msg] {
  not st_decision_areas_tier1_complete
  msg := sprintf(
    "ST Decision Areas Tier 1 미충족 — %d/%d (lesson-st-cover-tier1-complete-2026-04-29)",
    [count(input.st.decision_areas_completed), input.config.st_tier1_count],
  )
}
