# APT v27 Harness Constrain Axis — fail-closed gate policy
# RFC: rfc-apt-v27-A7-gate-hook-fail-closed-4-layer-2026-04-30
#
# Fail-closed default: 5 core MethodologyConfig field 모두 채워졌고
# break-glass allowlist 위반 없으며 audit_id 발급된 경우만 allow.

package apt.harness.constrain

import future.keywords.if
import future.keywords.in
import future.keywords.every

# fail-closed: default deny
default allow := false

# Composition Root: KG MethodologyConfig 5 core field 필수
required_fields := {
  "vibe_coding_sweet_min",
  "vibe_coding_sweet_max",
  "lens_count_constitutional",
  "contract_default_fields",
  "st_decision_areas",
}

# 5 core field 모두 채워졌는지 검증
methodology_config_complete if {
  every f in required_fields {
    input.kg.methodology_config[f] != null
  }
}

# break-glass allowlist 위반 검사
violates_break_glass_allowlist if {
  input.gate_name in {"essential-infra-pod-bypass", "cluster-autoscaler-bypass"}
  not input.gate_decision.break_glass_token_valid
}

# Drift 탐지 (constrain 축 메트릭)
drift_detected if {
  input.kg.skill_md_inline_numbers_count > 0
}

drift_detected if {
  input.kg.cfg_orphan_field_count > 0
}

# 메인 allow 결정
allow if {
  methodology_config_complete
  not violates_break_glass_allowlist
  input.gate_decision.audit_id != ""
  not drift_detected
}

# Deny 메시지 (informational 모드 + structured logging용)
deny[msg] if {
  not methodology_config_complete
  msg := "MethodologyConfig 5 core field 미완성 (RFC A6.1 위반). Composition Root 실패."
}

deny[msg] if {
  violates_break_glass_allowlist
  msg := sprintf("break-glass allowlist 위반: %s에 valid token 없음", [input.gate_name])
}

deny[msg] if {
  drift_detected
  msg := sprintf("drift 탐지: inline_numbers=%d, orphan_fields=%d (RFC A6.1)", [
    input.kg.skill_md_inline_numbers_count,
    input.kg.cfg_orphan_field_count,
  ])
}

deny[msg] if {
  input.gate_decision.audit_id == ""
  msg := "audit_id 누락 (JFrog 패턴 위반). Layer 3 audit 강제."
}
