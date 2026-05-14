# APT Phase 2→3 gate (SP → ST) — Rego policy
# RFC: APT v26 A3/A5 + rfc-apt-v27-A7 (Phase 2 sub)
#
# SP→ST 전환 조건:
# 1. 모든 leaf Span이 C(S) 5-predicate 통과 (AtomicSpan 라벨)
# 2. LensSet completeness (constitutional 9 lens 모두 적용)
# 3. δ_infra exception은 별도 path (ATOM_APT_delta_infra_exception_2026-04-21)
# 4. Crystallization Frontier 충족 — 모든 leaf = AtomicSpan

package apt.phase_gates.sp_to_st

import future.keywords.if
import future.keywords.in
import future.keywords.every

default allow := false

# C(S) 5-predicate 검증
cs_predicate_fields := {
  "objective",
  "definition",
  "keyAssertion",
  "verification",
  "c_s_predicate",
}

all_leaves_atomic if {
  every leaf in input.sp.leaves {
    leaf.is_atomic == true
    every f in cs_predicate_fields {
      leaf[f] != null
    }
  }
}

# LensSet completeness (constitutional 9 만장일치)
lensset_complete if {
  input.taliban_verdict == "APPROVED"
  input.taliban_lens_count == 9
}

# Crystallization Frontier 충족
crystallization_frontier_reached if {
  count(input.sp.leaves) >= 1
  count([leaf | leaf := input.sp.leaves[_]; not leaf.is_atomic]) == 0
}

# 메인 allow
allow if {
  all_leaves_atomic
  lensset_complete
  crystallization_frontier_reached
}

# Deny 메시지
deny[msg] if {
  not all_leaves_atomic
  non_atomic := [leaf.name | leaf := input.sp.leaves[_]; not leaf.is_atomic]
  msg := sprintf("AtomicSpan 미완성 leaves: %v. D(S) 재귀 분해 필요.", [non_atomic])
}

deny[msg] if {
  not lensset_complete
  msg := sprintf(
    "LensSet completeness 위반: taliban_verdict=%s, lens_count=%d/9 (3-lens shortcut 의심)",
    [input.taliban_verdict, input.taliban_lens_count],
  )
}

deny[msg] if {
  not crystallization_frontier_reached
  msg := "Crystallization Frontier 미도달 — 일부 leaf가 still non-atomic"
}
