# KG Mutation Admission Control — Rego policy
# RFC: rfc-apt-v27-A9-opa-rego-full-2026-05-11 §2 admission_control.rego
#
# 위험한 KG mutation을 *진입 전*에 차단. 4 분류:
# 1. silent FSM transition (Contract status 변경하면서 Kafka event 미발행) — V-FSM4
# 2. self-approval (V15 — executor == reviewer)
# 3. terminal escape (Rejected/Archived → 다른 상태로 변경)
# 4. resolve-only 위반 (magic number 본문 hardcoded, v26 A6)

package apt.kg.admission

import future.keywords.if
import future.keywords.in

default allow_mutation := false

# Violation 검출

# V-FSM4: silent FSM transition
deny_silent_fsm[msg] {
  input.mutation.target_label == "AptContract"
  input.mutation.action == "SET"
  input.mutation.new.status != input.mutation.old.status
  input.mutation.new.status in {"Active", "Fulfilled", "Amended", "Rejected", "Archived"}
  not input.related_kafka_event
  msg := sprintf(
    "V-FSM4: silent transition %s → %s without Kafka event (Contract %s)",
    [input.mutation.old.status, input.mutation.new.status, input.mutation.target_name],
  )
}

# V15: self-approval
deny_self_approval[msg] {
  input.mutation.target_label == "AptSpan"
  input.mutation.action == "APPROVED_BY"
  input.mutation.reviewer == input.mutation.executor
  msg := sprintf(
    "V15: executor '%s' == reviewer '%s' (D20 violation)",
    [input.mutation.executor, input.mutation.reviewer],
  )
}

# V-FSM3: terminal escape
terminal_states := {"Rejected", "Archived"}

deny_terminal_escape[msg] {
  input.mutation.target_label == "AptContract"
  input.mutation.old.status in terminal_states
  input.mutation.new.status != input.mutation.old.status
  msg := sprintf(
    "V-FSM3: terminal state '%s' escape attempt → '%s'. Create new Contract instead.",
    [input.mutation.old.status, input.mutation.new.status],
  )
}

# v26 A6: resolve-only — magic number hardcode 차단
core_magic_numbers := {"200", "500", "9", "7", "8"}

deny_hardcoded_magic[msg] {
  input.mutation.target_label == "Skill"
  input.mutation.action == "SET_BODY"
  some n in core_magic_numbers
  contains(input.mutation.new.body, n)
  not contains(input.mutation.new.body, sprintf("{{cfg.%s}}", [n]))
  msg := sprintf(
    "v26 A6 violation: bare '%s' in SKILL.md body (use {{cfg.X}} marker)",
    [n],
  )
}

# Aggregated denies — sets (use |, not array.concat)
deny := deny_silent_fsm | deny_self_approval | deny_terminal_escape | deny_hardcoded_magic

# Allow only if zero denies
allow_mutation if {
  count(deny) == 0
}

# Audit
audit := {
  "mutation": input.mutation,
  "verdict": (mutation_verdict),
  "deny_count": count(deny),
  "deny_messages": deny,
  "checked_at_ns": time.now_ns(),
}

mutation_verdict := "ALLOW" if allow_mutation
mutation_verdict := "DENY" if not allow_mutation
