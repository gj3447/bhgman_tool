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

    @classmethod
    def from_analysis(cls, result: dict[str, Any]) -> "HeadroomVerdict":
        """Build + validate from `analyze_paths` output; raise InvariantViolation on any breach."""
        rvb = result.get("repair_vs_bestN_headroom") or {}
        wins = int(rvb.get("repair_gt_bestN", 0))
        losses = int(rvb.get("bestN_gt_repair", 0))
        verdict = cls(
            runs=int(result.get("runs", 0)),
            wins=wins,
            ties=int(rvb.get("ties", 0)),
            losses=losses,
            p_two_sided=float(rvb.get("p_two_sided", 1.0)),
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


__all__ = ["HeadroomVerdict", "InvariantViolation"]
