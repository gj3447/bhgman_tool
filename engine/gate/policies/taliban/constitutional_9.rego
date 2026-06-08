# Taliban constitutional 9 lens — Rego policy
# RFC: rfc-apt-v27-A7 (Phase 2)
#
# 9 lens 만장일치 PASS 필수. 3-lens shortcut 차단.
# HR11: PASS verdict는 evidence_cited 의무 (anti-rubber-stamp).

package apt.taliban.constitutional

import rego.v1

lenses := {
	"evidence-backed",
	"non-rubber-stamp",
	"executor-not-equal-critic",
	"lensset-completeness",
	"min-findings-per-lens",
	"ground-truth-anchored",
	"post-gate-reflection",
	"longinus-binding-checked",
	"feedback-loop-instance",
}

default approve := false

# 만장일치 PASS
approve if {
	every lens in lenses {
		input.lens_results[lens].verdict == "PASS"
		input.lens_results[lens].evidence_cited == true
	}
}

# 3-lens shortcut 차단
deny[msg] if {
	count(input.lens_results) < 9
	msg := sprintf(
		"lensset-completeness 위반: %d/9 lens만 실행. RFC A6.1 + lesson-taliban-shortcut-antipattern-2026-04-21.",
		[count(input.lens_results)],
	)
}

# HR11 anti-rubber-stamp
deny[msg] if {
	some lens in lenses
	input.lens_results[lens].verdict == "PASS"
	not input.lens_results[lens].evidence_cited
	msg := sprintf("HR11 위반: lens '%s' PASS without evidence (RUBBER_STAMP)", [lens])
}

# executor != critic 검증
deny[msg] if {
	input.gate_decision.executor == input.gate_decision.critic
	msg := sprintf(
		"executor=critic 동일 (lesson-apt-vr-self-fulfilled-executor-reviewer-2026-04-16). actor=%s",
		[input.gate_decision.executor],
	)
}

# min_findings_per_lens 검증 (lens 당 evidence ≥ 1)
deny[msg] if {
	some lens in lenses
	count(input.lens_results[lens].evidence_findings) < 1
	msg := sprintf("min-findings 위반: lens '%s'에 evidence_findings 0건", [lens])
}
