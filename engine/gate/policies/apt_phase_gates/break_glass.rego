# Break-glass allowlist override — Rego policy
# RFC: rfc-apt-v27-A9-opa-rego-full-2026-05-11 §5
#
# Production gate fail 시 hot-fix path. 허용된 actor + reason + expiry 모두 충족 시 override.
# 모든 override는 audit log (Kafka BreakGlassActivated event 발행 의무).

package apt.break_glass

import future.keywords.if
import future.keywords.in

default allow_override := false

# 허용 actor 목록 (KG :BreakGlassAllowlist 노드 또는 정적 list)
allowed_emergency_overrides := {
  "cluster-autoscaler",
  "essential-infra-pod",
  "dr-recovery-agent",
  "kg-restore-agent",
  "schema-migration-bot",
}

# 모든 조건 충족
allow_override if {
  input.actor in allowed_emergency_overrides
  input.override_reason != ""
  count(input.override_reason) >= 20  # reason 최소 20자 (E-SA-Drift-2 회피)
  time.now_ns() < input.override_expires_at
}

# Deny
deny[msg] {
  not input.actor in allowed_emergency_overrides
  msg := sprintf(
    "Actor '%s' not in break-glass allowlist (%d allowed)",
    [input.actor, count(allowed_emergency_overrides)],
  )
}

deny[msg] {
  input.actor in allowed_emergency_overrides
  count(input.override_reason) < 20
  msg := sprintf(
    "override_reason 길이 부족 (%d < 20자) — E-SA-Drift-2 회피",
    [count(input.override_reason)],
  )
}

deny[msg] {
  input.actor in allowed_emergency_overrides
  time.now_ns() >= input.override_expires_at
  msg := "override 만료 — break-glass session expired"
}

# Audit event (Kafka BreakGlassActivated 발행용)
audit_event := {
  "event": "BreakGlassActivated",
  "actor": input.actor,
  "gate_name": input.gate_name,
  "override_reason": input.override_reason,
  "override_expires_at": input.override_expires_at,
  "approved": allow_override,
  "deny_reasons": deny,
  "timestamp_ns": time.now_ns(),
}
