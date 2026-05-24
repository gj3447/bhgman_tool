# ADR: APT execution engine scope — OUT-OF-SCOPE for bhgman_tool

- **Status**: ACCEPTED (per cycle-bhgman-apt-completeness-remediation-2026-05-25 WQI F3)
- **Date**: 2026-05-25
- **KG ref**: `wqi-bhgman-apt-F3-apt-engine-scope-decision-2026-05-25`
- **Parent cycle**: `cycle-bhgman-apt-completeness-remediation-2026-05-25`
- **Authority**: cycle plan §critical-path recommends Option A; user verdict 2026-05-25 ("Session 2 이어서 F3→F6→F9") blanket-proceed authorization

---

## Context

Naesengmoon constitutional verdict (`vr-bhgman-tool-apt-completeness-naesengmoon-constitutional-2026-05-25`, completeness 0.42 PARTIAL) flagged ambiguity over what an "APT engine" means inside `bhgman_tool`. Two readings coexisted:

1. `bhgman_tool/skills/apt*` (now symlinks to SERVER/.claude/skills/apt-* per F1 ADR-equivalent `decision-bhgman-apt-skills-symlink-to-server-2026-05-25`) — *skill definitions* only, no runtime.
2. A separate APT phase-gate runtime (resolver + gate endpoint + OPA) — was the user's expectation that bhgman_tool ship one?

Evidence on what already exists:
- `SYMPOSIUM/THEORY/APT/resolver_prototype/` — 9/9 pytest pass on dgx (Python 3.12 venv).
- `SYMPOSIUM/THEORY/APT/gate_endpoint_prototype/` — 6/6 pytest pass + OPA 0.66 policy coverage on dgx.
- Memory `reference_symposium_monorepo_mirror.md`: Mac edit → auto push → dgx WT runtime. APT prototype lives on dgx.
- `bhgman_tool/engine/` contains `longinus_drift_audit/`, `dispatch_audit/`, etc — Longinus + dispatch tooling, NOT an APT phase engine.

Per `feedback_layer_split_symposium_vs_bhgman_tool.md` (2026-05-13 USER_PRIMARY):

> SYMPOSIUM = paper layer. bhgman_tool = tool layer. ruflo/LangGraph/CrewAI same-layer comparison is **bhgman_tool only**. SYMPOSIUM/THEORY direct comparison = category error.

bhgman_tool sits beside LangGraph et al — agent-tooling layer. APT phase-gate runtime sits in SYMPOSIUM/dgx as research-validation infrastructure.

## Decision

**APT execution engine is OUT-OF-SCOPE for `bhgman_tool`.**

- `bhgman_tool/skills/apt*` = thin skill markdown only (symlinks to SERVER canonical).
- APT phase-gate runtime (resolver + gate endpoint + OPA) lives in `SYMPOSIUM/THEORY/APT/{resolver,gate_endpoint}_prototype/` and runs on dgx.
- `bhgman_tool/engine/` reserved for tool-layer engines (Longinus drift audit, dispatch audit, embedding channel, etc).

Rejected alternative B (port resolver + gate to `bhgman_tool/engine/apt/`):
- Duplicates the working dgx prototype — drift risk per `feedback_canon_propagation_simultaneous.md`.
- Conflates research-validation infrastructure with tool-layer ergonomics.
- No bhgman_tool consumer needs in-process APT gate (skills are invoked by Claude Code IDE-host, not by bhgman_tool engine code).

## Consequences

- **Positive**: Clear layer split preserved. SYMPOSIUM dgx remains single source of truth for APT runtime. bhgman_tool stays focused on tool-layer engines.
- **Positive**: F6 ADR set drops "port resolver to bhgman" branch; F6 will author dgx-runtime-delegation ADR instead (documenting cross-repo delegation contract).
- **Negative (acknowledged)**: Anyone using bhgman_tool standalone (without SYMPOSIUM) cannot invoke an APT phase gate. Acceptable because bhgman_tool is sibling to SYMPOSIUM, not a replacement.
- **Out of scope**: This ADR does **not** preclude bhgman_tool importing the prototype as a library later if a tool-layer consumer emerges. Reopen via new ADR if that happens.

## Rollback

Revert by deleting this ADR and re-evaluating Option B. Original cycle WQI `wqi-bhgman-apt-F3-apt-engine-scope-decision-2026-05-25` retains action_detail with both A and B descriptions.

# KG: wqi-bhgman-apt-F3-apt-engine-scope-decision-2026-05-25, cycle-bhgman-apt-completeness-remediation-2026-05-25, vr-bhgman-tool-apt-completeness-naesengmoon-constitutional-2026-05-25
