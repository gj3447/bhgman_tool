"""Tests for kg_binding_delta_lens.py — non-trivial DeltaLens instances (Wave 6c).

Covers:
- 1:1 KG node ↔ single LineRange binding (kg_to_line_range_lens)
- 1:N KG node ↔ multiple LineRange tuple (kg_multi_to_ranges_lens)
- d-PutGet, d-GetPut/d-PutId verification on real binding states
- d-PutGet precondition violation (caller error)
- d-PutPut style composition on multi-binding (state-level)

# KG: ATOM_Skill_longinus, ap-longinus-v34-bx-lens-substitute-2026-05-20,
      vr-longinus-v3.4-bx-lens-substitute-naesengmoon-3lens-2026-05-20 (F4/F6/M3/M4)
"""

from __future__ import annotations

import pytest

from edit_lens_line_range import LineRange
from kg_binding_delta_lens import (
    KGBindingState,
    KGMultiBindingState,
    LineRangeDelta,
    RangesDelta,
    kg_binding_cat,
    kg_multi_to_ranges_lens,
    kg_to_line_range_lens,
    ranges_cat,
)


# --------------------------------------------------------------------------
# 1:1 KGBinding ↔ LineRange tests
# --------------------------------------------------------------------------


def _binding(node_id: str, start: int, end: int) -> KGBindingState:
    return KGBindingState(node_id=node_id, file_path="/tmp/foo.py", range=LineRange(start, end))


def test_kg_to_line_range_putget_on_real_binding() -> None:
    """d-PutGet: lifting a non-trivial view delta gives a state with that target range."""
    s = _binding("Foo.bar", 10, 42)
    u = LineRangeDelta(src=LineRange(10, 42), tgt=LineRange(15, 47))
    assert kg_to_line_range_lens.verify_putget(s, u) is True


def test_kg_to_line_range_getput_on_real_binding() -> None:
    """d-GetPut / d-PutId: identity view delta lifts to identity source state."""
    for node_id, start, end in [("A.b", 1, 5), ("Bar.zz", 100, 200), ("X", 7, 7)]:
        s = _binding(node_id, start, end)
        assert kg_to_line_range_lens.verify_getput(s) is True


def test_kg_to_line_range_lift_actually_changes_range() -> None:
    """Concrete spot-check: lift moves range from (10,42) to (15,47) preserving node_id/path."""
    s = _binding("Foo.bar", 10, 42)
    u = LineRangeDelta(src=LineRange(10, 42), tgt=LineRange(15, 47))
    s_prime = kg_to_line_range_lens.lift(s, u)
    assert s_prime.node_id == "Foo.bar"
    assert s_prime.file_path == "/tmp/foo.py"
    assert s_prime.range == LineRange(15, 47)


def test_kg_to_line_range_lift_rejects_mismatched_source() -> None:
    """d-PutGet precondition: lift raises if u.src != get(s)."""
    s = _binding("Foo.bar", 10, 42)
    u_wrong = LineRangeDelta(src=LineRange(99, 99), tgt=LineRange(15, 47))
    with pytest.raises(ValueError, match="d-PutGet precondition"):
        kg_to_line_range_lens.lift(s, u_wrong)


# --------------------------------------------------------------------------
# 1:N KGMultiBinding ↔ Ranges tests (Longinus essence — multi-valued correspondence)
# --------------------------------------------------------------------------


def _multi(node_id: str, *ranges: tuple[int, int]) -> KGMultiBindingState:
    return KGMultiBindingState(
        node_id=node_id,
        file_path="/tmp/cluster.py",
        ranges=tuple(LineRange(a, b) for a, b in ranges),
    )


def test_kg_multi_putget_on_two_disjoint_ranges() -> None:
    """1:N (KG node 1개 ↔ 2 disjoint ranges): d-PutGet under range tuple update."""
    s = _multi("Cluster.foo", (10, 20), (100, 130))
    new = (LineRange(15, 25), LineRange(105, 135))
    u = RangesDelta(src=s.ranges, tgt=new)
    assert kg_multi_to_ranges_lens.verify_putget(s, u) is True


def test_kg_multi_getput_on_three_ranges() -> None:
    """1:N (3 ranges): d-PutId / d-GetPut."""
    s = _multi("X.cluster", (1, 5), (50, 70), (200, 250))
    assert kg_multi_to_ranges_lens.verify_getput(s) is True


def test_kg_multi_putget_on_empty_ranges() -> None:
    """Edge case: KG node bound to zero ranges (orphan / deletion candidate)."""
    s = _multi("Orphan.node")
    u = RangesDelta(src=(), tgt=(LineRange(1, 10),))
    assert kg_multi_to_ranges_lens.verify_putget(s, u) is True


def test_kg_multi_lift_preserves_node_id_and_path() -> None:
    """Concrete spot-check on 1:N lift: only ranges change."""
    s = _multi("Foo", (10, 20), (30, 40))
    new = (LineRange(11, 21), LineRange(31, 41), LineRange(50, 60))  # +1 range added
    u = RangesDelta(src=s.ranges, tgt=new)
    s_prime = kg_multi_to_ranges_lens.lift(s, u)
    assert s_prime.node_id == "Foo"
    assert s_prime.file_path == "/tmp/cluster.py"
    assert s_prime.ranges == new


# --------------------------------------------------------------------------
# d-PutPut style: sequential composition equals composed lift (state-level)
# --------------------------------------------------------------------------


def test_kg_multi_sequential_lift_equals_composed_lift() -> None:
    """d-PutPut state-level: lift(lift(s, u1), u2) == lift(s, compose(u1, u2)).

    Where compose(u1, u2) is the view-side composition (src=u1.src, tgt=u2.tgt)
    when u1.tgt == u2.src. This is the Longinus-side validation of Wave 6b's
    Lean d-PutPut axiom on the multi-binding instance.
    """
    s = _multi("Foo", (10, 20), (30, 40))
    mid = (LineRange(11, 21), LineRange(31, 41))
    final = (LineRange(15, 25), LineRange(35, 45))

    u1 = RangesDelta(src=s.ranges, tgt=mid)
    u2 = RangesDelta(src=mid, tgt=final)

    # Sequential path
    sequential = kg_multi_to_ranges_lens.lift(kg_multi_to_ranges_lens.lift(s, u1), u2)
    # Composed path (view-cat compose)
    composed_u = ranges_cat.compose(u1, u2)
    composed = kg_multi_to_ranges_lens.lift(s, composed_u)

    assert sequential == composed


# --------------------------------------------------------------------------
# Category laws spot-check (delta categories themselves)
# --------------------------------------------------------------------------


def test_kg_binding_cat_compose_chains_endpoints() -> None:
    a = _binding("A", 1, 5)
    b = _binding("A", 1, 7)
    c = _binding("A", 1, 9)
    from kg_binding_delta_lens import KGBindingDelta

    d1 = KGBindingDelta(src=a, tgt=b)
    d2 = KGBindingDelta(src=b, tgt=c)
    composed = kg_binding_cat.compose(d1, d2)
    assert composed.src == a and composed.tgt == c


def test_kg_binding_cat_compose_rejects_mismatched_endpoints() -> None:
    a = _binding("A", 1, 5)
    b = _binding("A", 1, 7)
    c = _binding("A", 1, 9)
    from kg_binding_delta_lens import KGBindingDelta

    d1 = KGBindingDelta(src=a, tgt=b)
    d2 = KGBindingDelta(src=c, tgt=a)  # c != b → mismatch
    with pytest.raises(ValueError, match="composition mismatch"):
        kg_binding_cat.compose(d1, d2)
