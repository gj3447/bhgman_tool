"""Tests for delta_lens.py — Diskin 2011 asymmetric delta lens (Wave 3).

Verifies the two laws (d-PutGet, d-GetPut) on the identity delta lens witness
over the trivial integer delta category.

# KG: ATOM_Skill_longinus, ap-longinus-v34-bx-lens-substitute-2026-05-20,
      THEORY/LONGINUS/lean_audit/LonginusBxDeltaLens.lean
"""

from __future__ import annotations

from engine.longinus_drift_audit.delta_lens import (
    IntDelta,
    identity_delta_lens,
    int_delta_cat,
)


def test_identity_lens_putget_holds() -> None:
    """d-PutGet: lifting view delta `u` yields source state whose get == target(u)."""
    lens = identity_delta_lens(int_delta_cat())
    s = 7
    u = IntDelta(src=7, tgt=42)
    assert lens.verify_putget(s, u) is True


def test_identity_lens_getput_holds_for_multiple_states() -> None:
    """d-GetPut: identity view delta lifts to identity source for any state."""
    lens = identity_delta_lens(int_delta_cat())
    for s in (-5, 0, 1, 99, 12345):
        assert lens.verify_getput(s) is True, f"d-GetPut failed at s={s}"


def test_delta_category_id_target_equals_source() -> None:
    """Sanity: identity delta on a state s has src == tgt == s."""
    cat = int_delta_cat()
    for s in (0, 3, -2):
        d = cat.id_delta(s)
        assert d.src == s and d.tgt == s


def test_delta_category_compose_chains_endpoints() -> None:
    """Sanity: compose(d1, d2) takes src from d1, tgt from d2."""
    cat = int_delta_cat()
    d1 = IntDelta(src=1, tgt=2)
    d2 = IntDelta(src=2, tgt=5)
    composed = cat.compose(d1, d2)
    assert composed.src == 1 and composed.tgt == 5
