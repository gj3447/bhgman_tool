"""Tests for edit_lens_line_range.py — HPW 2012 edit lens for line_range (Wave 4).

# KG: ATOM_Skill_longinus, ap-longinus-v34-bx-lens-substitute-2026-05-20,
      THEORY/LONGINUS/lean_audit/LonginusBxDeltaLens.lean
"""

from __future__ import annotations

import pytest

from edit_lens_line_range import EditLensLineRange, LineRange, LineShiftMonoid


def test_line_range_construction_rejects_zero_start() -> None:
    with pytest.raises(ValueError):
        LineRange(start_line=0, end_line=5)


def test_line_range_construction_rejects_inverted_range() -> None:
    with pytest.raises(ValueError):
        LineRange(start_line=10, end_line=5)


def test_line_shift_monoid_identity_is_zero() -> None:
    assert LineShiftMonoid.one() == 0


def test_line_shift_monoid_associativity_explicit() -> None:
    """(a + b) + c == a + (b + c) for several triples."""
    for a, b, c in [(1, 2, 3), (-5, 10, -3), (0, 0, 0), (100, -50, 25)]:
        lhs = LineShiftMonoid.mul(LineShiftMonoid.mul(a, b), c)
        rhs = LineShiftMonoid.mul(a, LineShiftMonoid.mul(b, c))
        assert lhs == rhs, f"associativity failed at ({a},{b},{c})"


def test_edit_lens_identity_shift_leaves_range() -> None:
    lens = EditLensLineRange()
    r = LineRange(start_line=10, end_line=42)
    assert lens.verify_identity(r) is True


def test_edit_lens_composition_associative_over_shifts() -> None:
    """Shifts that keep intermediate state valid (start_line >= 1)."""
    lens = EditLensLineRange()
    r = LineRange(start_line=100, end_line=200)
    for s1, s2 in [(5, 7), (-3, 10), (0, 8), (15, -20), (-50, 75)]:
        assert (
            lens.verify_composition(r, s1, s2) is True
        ), f"composition failed at shifts ({s1}, {s2})"


def test_line_range_shift_arithmetic_matches_expected() -> None:
    """Concrete spot-check: 10-42 shifted +5 should be 15-47."""
    r = LineRange(start_line=10, end_line=42)
    shifted = r.shift(5)
    assert shifted == LineRange(start_line=15, end_line=47)


def test_negative_shift_below_one_rejected_by_dataclass() -> None:
    """Shifting a range below start_line=1 must raise ValueError."""
    r = LineRange(start_line=3, end_line=10)
    with pytest.raises(ValueError):
        r.shift(-5)  # would yield start_line=-2
