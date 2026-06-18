"""
edit_lens_line_range.py — HPW 2012 Edit Lens for line_range monoid (Wave 4).

Inner refinement layer for DeltaLens (delta_lens.py): tracks LineRange offset
under line insertion/deletion edits modeled as a signed-integer monoid action.

Mirrors LonginusBxDeltaLens.LineRange + lineShiftMonoid in Lean.

References:
    Hofmann, Pierce, Wagner. Edit Lenses. POPL 2012. DOI 10.1145/2103621.2103715.

# KG: ATOM_Skill_longinus, ap-longinus-v34-bx-lens-substitute-2026-05-20,
      seed-bx-edit-lens-hpw2012-linerange-2026-05-20,
      THEORY/LONGINUS/lean_audit/LonginusBxDeltaLens.lean
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LineRange:
    # KG: ATOM_Skill_longinus
    """An inclusive 1-indexed line range bound to a single KG node binding."""

    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        if self.start_line < 1:
            raise ValueError(f"start_line must be >= 1, got {self.start_line}")
        if self.end_line < self.start_line:
            raise ValueError(
                f"end_line ({self.end_line}) must be >= start_line ({self.start_line})"
            )

    def shift(self, offset: int) -> "LineRange":
        """Apply a signed line offset (positive = insertions above; negative = deletions)."""
        return LineRange(self.start_line + offset, self.end_line + offset)


class LineShiftMonoid:
    # KG: ATOM_Skill_longinus
    """The LineShift monoid: identity = 0, binary op = addition.

    Mirrors `lineShiftMonoid : DeltaMonoid` in Lean. Proven monoid laws
    (one_mul, mul_one, mul_assoc) in LonginusBxDeltaLens.lean Section 4.
    """

    @staticmethod
    def one() -> int:
        return 0

    @staticmethod
    def mul(a: int, b: int) -> int:
        return a + b

    @staticmethod
    def act(r: LineRange, shift: int) -> LineRange:
        return r.shift(shift)


@dataclass(frozen=True)
class EditLensLineRange:
    # KG: ATOM_Skill_longinus
    """HPW 2012 edit lens for LineRange under LineShift monoid action.

    The edit lens form `(put_left, put_right)` from HPW 2012 specializes here
    to a one-sided monoid action — the line_range is the view, the line shift
    is the edit on the source code text.
    """

    def apply_edit(self, r: LineRange, shift: int) -> LineRange:
        return LineShiftMonoid.act(r, shift)

    def verify_identity(self, r: LineRange) -> bool:
        """Identity edit (shift=0) leaves range unchanged."""
        return self.apply_edit(r, LineShiftMonoid.one()) == r

    def verify_composition(self, r: LineRange, s1: int, s2: int) -> bool:
        """Composition: apply(apply(r, s1), s2) == apply(r, mul(s1, s2))."""
        sequential = self.apply_edit(self.apply_edit(r, s1), s2)
        composed = self.apply_edit(r, LineShiftMonoid.mul(s1, s2))
        return sequential == composed
