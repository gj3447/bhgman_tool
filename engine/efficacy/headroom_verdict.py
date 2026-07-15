"""HeadroomVerdict — an OO invariant-checker that GATES the lean-headroom write-up.

Built RED-first against positive-invariant TDD contracts logged to the KG before any code
(TDD:headroom_verdict:{runs_positive, tally_conservation, non_ties_consistent,
p_two_sided_bounded}). It consumes `analyze_lean_headroom.analyze_paths(...)` output and refuses
to construct a verdict from a batch that violates a conservation/bounds invariant — so a corrupt
or partial JSONL batch raises instead of silently yielding a number (verify-before-writeup, the
H2 reproducibility lesson expressed as positive TDD).

# KG: TDD:headroom_verdict:runs_positive, TDD:headroom_verdict:tally_conservation,
#     TDD:headroom_verdict:non_ties_consistent, TDD:headroom_verdict:p_two_sided_bounded,
#     project_bhgman_efficacy_verdict_operational_substrate_2026_06_02 (H2 headroom)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class InvariantViolation(ValueError):
    """A positive-invariant TDD contract was violated by the batch — refuse the write-up."""


@dataclass(frozen=True)
class HeadroomVerdict:
    """The repair-vs-bestN headroom verdict for one JSONL batch, with its invariants enforced."""

    runs: int
    wins: int  # repair_gt_bestN
    ties: int
    losses: int  # bestN_gt_repair
    p_two_sided: float
    # prereg §4 controls (default None → old call sites / legacy batches construct unchanged):
    repair_vs_decoy: dict[str, Any] | None = None  # P2: {wins, ties, losses, p}
    repair_vs_plain: dict[str, Any] | None = None  # P3: {wins, ties, losses, p}
    decoy_equiv_bestN: bool | None = None  # P2: TOST decoy≈bestN
    token_parity: dict[str, Any] | None = None  # P4: repair_vs_bestN ratios

    @staticmethod
    def _norm_pair(block: dict[str, Any] | None, arm_a: str, arm_b: str) -> dict[str, Any] | None:
        """Normalize an analyze pairwise block ({a}_gt_{b}/ties/{b}_gt_{a}/p_two_sided) → {wins,
        ties, losses, p}, or None when absent."""
        if not block:
            return None
        return {
            "wins": int(block.get(f"{arm_a}_gt_{arm_b}", 0)),
            "ties": int(block.get("ties", 0)),
            "losses": int(block.get(f"{arm_b}_gt_{arm_a}", 0)),
            "p": float(block.get("p_two_sided", 1.0)),
        }

    @classmethod
    def from_analysis(cls, result: dict[str, Any]) -> "HeadroomVerdict":
        """Build + validate from `analyze_paths` output; raise InvariantViolation on any breach.
        Populates the prereg §4 control fields when present; leaves them None on a legacy batch."""
        rvb = result.get("repair_vs_bestN_headroom") or {}
        wins = int(rvb.get("repair_gt_bestN", 0))
        losses = int(rvb.get("bestN_gt_repair", 0))
        dvb = result.get("decoy_vs_bestN_headroom") or {}
        tost = dvb.get("tost") or {}
        parity = (result.get("token_parity") or {}).get("repair_vs_bestN")
        verdict = cls(
            runs=int(result.get("runs", 0)),
            wins=wins,
            ties=int(rvb.get("ties", 0)),
            losses=losses,
            p_two_sided=float(rvb.get("p_two_sided", 1.0)),
            repair_vs_decoy=cls._norm_pair(
                result.get("repair_vs_decoy_headroom"), "repair", "decoy"
            ),
            repair_vs_plain=cls._norm_pair(
                result.get("repair_vs_plain_headroom"), "repair", "plain"
            ),
            decoy_equiv_bestN=tost.get("equivalent") if tost else None,
            token_parity=parity,
        )
        verdict._check(non_ties=int(rvb.get("non_ties", wins + losses)))
        return verdict

    def _check(self, non_ties: int) -> None:
        # each clause mirrors one KG-logged TDD:headroom_verdict:*_positive contract
        if self.runs < 1:
            raise InvariantViolation(f"runs must be >= 1 (runs_positive); got {self.runs}")
        if self.wins + self.ties + self.losses != self.runs:
            raise InvariantViolation(
                f"tally conservation: {self.wins}+{self.ties}+{self.losses} != runs {self.runs}"
            )
        if non_ties != self.wins + self.losses:
            raise InvariantViolation(
                f"non_ties {non_ties} != wins+losses {self.wins + self.losses} (non_ties_consistent)"
            )
        if not 0.0 <= self.p_two_sided <= 1.0:
            raise InvariantViolation(
                f"p_two_sided must be a probability in [0,1] (p_two_sided_bounded); got {self.p_two_sided}"
            )
        self._check_pair("repair_vs_decoy", self.repair_vs_decoy)
        self._check_pair("repair_vs_plain", self.repair_vs_plain)
        self._check_parity()

    def _check_pair(self, name: str, pair: dict[str, Any] | None) -> None:
        """A present pairwise control must conserve its tally against runs and bound its p."""
        if pair is None:
            return
        total = pair["wins"] + pair["ties"] + pair["losses"]
        if total != self.runs:
            raise InvariantViolation(f"{name} tally conservation: {total} != runs {self.runs}")
        if not 0.0 <= pair["p"] <= 1.0:
            raise InvariantViolation(f"{name} p must be a probability in [0,1]; got {pair['p']}")

    def _check_parity(self) -> None:
        """Present token-parity ratios must be non-negative (a compute ratio cannot be < 0)."""
        if not self.token_parity:
            return
        for key in ("calls_ratio", "tokens_ratio"):
            val = self.token_parity.get(key)
            if val is not None and val < 0:
                raise InvariantViolation(f"token_parity.{key} must be >= 0; got {val}")

    @property
    def direction(self) -> str:
        if self.wins > self.losses:
            return "repair_favored"
        if self.losses > self.wins:
            return "bestN_favored"
        return "inconclusive"

    def significant(self, alpha: float = 0.05) -> bool:
        """Two-sided sign test significant at alpha (strict)."""
        return self.p_two_sided < alpha

    @property
    def summary(self) -> str:
        sig = "SIGNIFICANT" if self.significant() else "NULL"
        return (
            f"headroom repair-vs-bestN: {self.wins}W/{self.ties}T/{self.losses}L over {self.runs} runs, "
            f"p={self.p_two_sided:.4g} → {sig} ({self.direction})"
        )

    @staticmethod
    def _pair_pass(pair: dict[str, Any] | None, alpha: float) -> str:
        """Tri-state for a 'treatment favored' pairwise control: PASS iff wins>losses AND p<alpha."""
        if pair is None:
            return "ABSENT"
        if pair["wins"] > pair["losses"] and pair["p"] < alpha:
            return "PASS"
        return "FAIL"

    def _p2_oracle_signal(self, alpha: float) -> str:
        """P2 (K4): the win is oracle-CONTENT iff repair>decoy (p<alpha) AND decoy≈bestN (TOST). A
        decoy that is NOT equivalent to bestN (decoy hurt, or decoy≈repair) fails — the isolation
        did not hold."""
        if self.repair_vs_decoy is None or self.decoy_equiv_bestN is None:
            return "ABSENT"
        edge = self.repair_vs_decoy["wins"] > self.repair_vs_decoy["losses"]
        if edge and self.repair_vs_decoy["p"] < alpha and self.decoy_equiv_bestN:
            return "PASS"
        return "FAIL"

    def _p4_parity(self, parity_bound: float) -> str:
        """P4: repair must not buy a compute discount vs bestN — calls- AND tokens-ratio within
        [1/bound, bound]. usage_hidden (backend surfaced no tokens) → ABSENT, never a fake PASS."""
        if not self.token_parity or self.token_parity.get("usage_hidden"):
            return "ABSENT"
        lo, hi = 1.0 / parity_bound, parity_bound
        for key in ("calls_ratio", "tokens_ratio"):
            val = self.token_parity.get(key)
            if val is None:
                return "ABSENT"
            if not lo <= val <= hi:
                return "FAIL"
        return "PASS"

    def confirm_conditions(self, alpha: float = 0.05, parity_bound: float = 1.25) -> dict[str, Any]:
        """Map the prereg §4 CONFIRM conditions P1–P5 to tri-state {PASS, FAIL, ABSENT}.

        `confirm` is True only if P1–P4 all PASS. HONESTY (prereg §4 + §6): a True here still only
        moves the cognitive claim per the pre-registration; it does NOT propagate to any positive/
        efficacy channel while the claim is held at :VerdictPending, and P5 (raw-JSONL provenance) is
        filled by the run tooling, not this in-memory verdict. P1 is the per-run sign test only; the
        K1 ≥5-live-discriminating-tasks power gate is a BAND property checked against the frozen band,
        not here."""
        p1 = "PASS" if (self.direction == "repair_favored" and self.significant(alpha)) else "FAIL"
        conditions: dict[str, Any] = {
            "P1_edge": p1,
            "P2_oracle_signal": self._p2_oracle_signal(alpha),
            "P3_bhgman_specific": self._pair_pass(self.repair_vs_plain, alpha),
            "P4_parity": self._p4_parity(parity_bound),
            "P5_provenance": "ABSENT",  # filled by run tooling (committed raw JSONL), not this verdict
        }
        conditions["confirm"] = all(
            conditions[k] == "PASS"
            for k in ("P1_edge", "P2_oracle_signal", "P3_bhgman_specific", "P4_parity")
        )
        return conditions


__all__ = ["HeadroomVerdict", "InvariantViolation"]
