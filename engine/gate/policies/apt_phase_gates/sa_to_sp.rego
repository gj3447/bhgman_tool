# APT Phase 1→2 gate (SA → SP) — Rego policy
# RFC: rfc-apt-v27-A9-opa-rego-full-2026-05-11
#
# SA→SP 전환 조건 (per apt-sa/references/handoff_to_sp.md 8-check + 3 A15 check):
# 1. SemanticAnchor 존재 + status='active'
# 2. Root Span 연결됨 (HAS_ROOT edge)
# 3. apt-progress.md 파일 존재 (filesystem check, application layer 측정 후 input)
# 4. Context Budget 할당 (context_budget_total NOT NULL)
# 5. 동일 앵커 중복 없음 (V-SA2)
# 6. Git commit 완료 (apt-progress.md)
# 7. Progressive Disclosure L1 로드됨 (apt-progress.md 안 L1 Span 목록 기재)
# 8. v27 A15: work_kind 분류 기록됨 (NEW/EXTEND/MAINTENANCE)
# 9. v27 A15: Phase Activation Matrix mode 결정 (FULL/SHORT_CIRCUIT/SKIP_TO_ST_DRIFT)

package apt.phase_gates.sa_to_sp

import rego.v1

default allow := false

# 기본 anchor 존재 + active
anchor_active if {
	input.sa.name != ""
	input.sa.status == "active"
}

# Root Span 연결
root_attached if {
	input.sa.root_span_name != ""
	input.sa.root_span_status == "open"
}

# Context Budget 할당
budget_allocated if {
	input.sa.context_budget_total != null
	input.sa.context_budget_total > 0
}

# 중복 앵커 없음
no_duplicate if {
	input.sa.duplicate_anchor_count == 0
}

# Progressive Disclosure L1 로드
pd_l1_loaded if {
	input.apt_progress.l1_span_count > 0
}

# A15 work_kind 기록됨
a15_workkind_set if {
	valid := {"NEW", "EXTEND", "MAINTENANCE"}
	input.sa.work_kind in valid
}

# A15 Phase Activation mode 결정
a15_mode_set if {
	valid := {"FULL", "SHORT_CIRCUIT", "SKIP_TO_ST_DRIFT"}
	input.sa.phase_activation_mode in valid
}

# Git commit done
git_committed if {
	input.apt_progress.git_committed == true
}

# 메인 allow
allow if {
	anchor_active
	root_attached
	budget_allocated
	no_duplicate
	pd_l1_loaded
	a15_workkind_set
	a15_mode_set
	git_committed
}

# Deny 메시지
deny contains msg if {
	not anchor_active
	msg := sprintf(
		"Anchor 비활성: name=%v status=%v (expected status='active')",
		[input.sa.name, input.sa.status],
	)
}

deny contains msg if {
	not root_attached
	msg := "Root Span 미연결 — V-SA3 NoRoot 위반"
}

deny contains msg if {
	not budget_allocated
	msg := "Context Budget 미할당 — V-SA4 NoBudget 위반"
}

deny contains msg if {
	not no_duplicate
	msg := sprintf(
		"중복 앵커 %d개 — V-SA2 DuplicateAnchor 위반",
		[input.sa.duplicate_anchor_count],
	)
}

deny contains msg if {
	not pd_l1_loaded
	msg := "Progressive Disclosure L1 미로드 — E-SA2 위반"
}

deny contains msg if {
	not a15_workkind_set
	msg := sprintf(
		"A15 work_kind 미지정 — V-SA5 NoWorkKindRecord 위반 (input=%v)",
		[input.sa.work_kind],
	)
}

deny contains msg if {
	not a15_mode_set
	msg := "A15 Phase Activation mode 미결정"
}

deny contains msg if {
	not git_committed
	msg := "apt-progress.md git commit 미완료"
}
