"""TPA FulfillmentGate — APT 7-check gate parity for the reverse loop (TCW→ST→SP→TA).

The forward APT SCW phase ships a 7-check FulfillmentGate (executor!=critic, LensSet
completeness, prior VR APPROVED, ...). The reverse TPA loop had NONE: `run_tpa` defaulted
to `gate=None`, so `engine.legion.Legion.run` advanced every stage unconditionally — a
`_degraded` TCW extraction (code_root missing) or a 0-symbol recovery still reported a
green `completed=True` run. That is the "FulfillmentGate 부재" gap the PROM 16 v2 code-to-KG
cycle isolated as TPA's real bottleneck (parsing was never the problem):

    seed-tpa-fulfillmentgate-hardening-2026-07-13 (HIGH)

This module supplies the missing gate. It is a `legion.GateFn` — `(ctx) -> (bool, str)` —
that Legion calls after each stage. It enforces the per-phase POSTCONDITION and emits an
auditable `PhaseReceipt`, reusing the APT verdict algebra (`apt_engine/gate.py`,
adr-apt-gate-semantics-2026-05-25): **SKIP is never PASS**; only PASS is a clean unlock.

7-check parity (mirror of the SCW FulfillmentGate, adapted to the deterministic reverse loop):
  1. provides-key present in ctx                (Legion pre-checks; re-asserted here)
  2. stage output not `_degraded`               (engine failure => FAIL, never silent-green)
  3. phase postcondition predicate satisfied     (per-phase: symbols>0 / contracts / groups / drift)
  4. verdict algebra: SKIP != PASS               (Verdict.unlocks_downstream)
  5. CONDITIONAL advances but is flagged          (follow-up recorded in the receipt)
  6. phases evaluated in canonical TCW→ST→SP→TA order (index tracking; order is load-bearing)
  7. one auditable PhaseReceipt emitted per phase (provenance for the FulfillmentGate trace)

Honest boundary (adr-apt-tpa-engine-substrate-scope-2026-06-14): this gate enforces the
DETERMINISTIC postconditions only. Per-phase Naesengmoon adversarial review and Longinus
auto-bind (the rest of the seed) are LLM/KG-side hooks that layer ON TOP of this scaffold
and are left as follow-ups (seed-tpa-fulfillmentgate-hardening-2026-07-13, parts 2-3).

# KG: seed-tpa-fulfillmentgate-hardening-2026-07-13, adr-apt-gate-semantics-2026-05-25,
#     lesson-prom16-code-to-kg-v2-joern-scip-graphrag-2026-07-13,
#     adr-apt-tpa-engine-substrate-scope-2026-06-14
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "Verdict",
    "PhaseReceipt",
    "REVERSE_POSTCONDITIONS",
    "evaluate_postcondition",
    "TpaFulfillmentGate",
]


class Verdict(str, Enum):
    """Reverse-loop gate verdict — same algebra as APT `apt_engine.gate.Verdict`."""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    CONDITIONAL = "CONDITIONAL"

    @property
    def unlocks_downstream(self) -> bool:
        """APT parity: only PASS is a clean unlock. SKIP != PASS; CONDITIONAL needs follow-up."""
        return self is Verdict.PASS

    @property
    def advances_loop(self) -> bool:
        """Whether the reverse loop may continue past this phase.

        PASS and CONDITIONAL advance (CONDITIONAL is flagged, not blocked — a vacuous
        recovery, e.g. a module with no callables, must not sink the whole cycle). SKIP
        and FAIL halt the run — SKIP is explicitly NOT an advance (gate-semantics ADR).
        """
        return self in (Verdict.PASS, Verdict.CONDITIONAL)


@dataclass(frozen=True)
class PhaseReceipt:
    """One auditable line of the FulfillmentGate trace: what a phase's postcondition returned."""

    phase: str
    verdict: Verdict
    reason: str


# Canonical reverse phase order and the ctx key each phase must have provided.
# Mirrors engine.tpa.reverse_phase_detect (TCW→ST→SP→TA) and tpa_orchestrator._STAGES.
REVERSE_POSTCONDITIONS: tuple[tuple[str, str], ...] = (
    ("TCW", "tcw_result"),
    ("ST", "contracts"),
    ("SP", "patterns"),
    ("TA", "drift_report"),
)
_KEY_BY_PHASE: dict[str, str] = dict(REVERSE_POSTCONDITIONS)


def _is_degraded(value: object) -> bool:
    return isinstance(value, dict) and value.get("mode") == "degraded"


def evaluate_postcondition(phase: str, ctx: dict) -> tuple[Verdict, str]:
    """Pure: (phase, accumulated ctx) -> (verdict, reason). No side effects.

    Checks 1-3 of the parity list per phase. Missing key or `_degraded` output is FAIL;
    a real-but-empty recovery (0 contracts / 0 pattern groups) is CONDITIONAL, not FAIL.
    """
    key = _KEY_BY_PHASE.get(phase)
    if key is None:
        return Verdict.FAIL, f"unknown reverse phase {phase!r}"
    value = ctx.get(key)
    if value is None:
        return Verdict.FAIL, f"{phase} postcondition unmet: no {key!r} in context"
    if _is_degraded(value):
        reason = value.get("reason", "degraded") if isinstance(value, dict) else "degraded"
        return Verdict.FAIL, f"{phase} engine degraded: {reason}"

    if phase == "TCW":
        n = int(value.get("symbol_count", 0) or 0)
        if n > 0:
            return Verdict.PASS, f"extracted {n} CodeSymbol"
        return Verdict.FAIL, "TCW extracted 0 symbols — no code world to recover"
    if phase == "ST":
        n = int(value.get("count", 0) or 0)
        if n > 0:
            return Verdict.PASS, f"recovered {n} Contract candidate(s)"
        return Verdict.CONDITIONAL, "no callable/class symbols to recover (vacuous structure)"
    if phase == "SP":
        groups = value.get("groups") or {}
        if groups:
            return Verdict.PASS, f"recovered pyramid over {len(groups)} kind(s)"
        return Verdict.CONDITIONAL, "empty pyramid (no symbol kinds grouped)"
    if phase == "TA":
        n = int(value.get("drift_count", 0) or 0)
        return Verdict.PASS, f"measured {n} drift(s)"

    return Verdict.FAIL, f"no postcondition rule for {phase!r}"


class TpaFulfillmentGate:
    """Stateful `legion.GateFn` enforcing the reverse postconditions, in phase order.

    Legion calls the gate once after each stage with the accumulated context but does not
    pass the stage identity. Reverse stage order is load-bearing (tcw→st→sp→ta), so the
    Nth invocation is the Nth phase; a FAIL halts the run, so the index never runs ahead of
    a real stage. Read `.receipts` for the per-phase FulfillmentGate trace.
    """

    _ORDER: tuple[str, ...] = tuple(phase for phase, _ in REVERSE_POSTCONDITIONS)

    def __init__(self) -> None:
        self.receipts: list[PhaseReceipt] = []
        self._i = 0

    def __call__(self, ctx: dict) -> tuple[bool, str]:
        phase = self._ORDER[self._i] if self._i < len(self._ORDER) else f"phase#{self._i}"
        self._i += 1
        verdict, reason = evaluate_postcondition(phase, ctx)
        self.receipts.append(PhaseReceipt(phase, verdict, reason))
        return verdict.advances_loop, f"{phase}:{verdict.value}:{reason}"

    @property
    def all_passed(self) -> bool:
        """True only if every evaluated phase returned a clean PASS (CONDITIONAL is not clean)."""
        return bool(self.receipts) and all(r.verdict is Verdict.PASS for r in self.receipts)

    @property
    def blocked_at(self) -> str | None:
        """The first phase whose verdict halted the loop (FAIL/SKIP), or None."""
        for r in self.receipts:
            if not r.verdict.advances_loop:
                return r.phase
        return None
