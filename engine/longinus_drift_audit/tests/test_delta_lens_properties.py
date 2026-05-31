"""Property-based tests for DeltaLens (heavy test sprint, 2026-05-20).

Uses Hypothesis to generate random KGBindingState / KGMultiBindingState +
LineRange / RangesDelta and verifies the 4 Diskin axioms across the sample
space. Catches edge cases that hand-written tests miss.

References:
    Hypothesis 6.x property-based testing
    Diskin-Xiong-Czarnecki 2011 — 4 lens laws

# KG: ATOM_Skill_longinus, ap-longinus-v34-bx-lens-substitute-2026-05-20,
      vr-longinus-v3.4-bx-lens-substitute-naesengmoon-3lens-2026-05-20 (heavy test sprint)
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from engine.longinus_drift_audit.edit_lens_line_range import (
    EditLensLineRange,
    LineRange,
    LineShiftMonoid,
)
from engine.longinus_drift_audit.kg_binding_delta_lens import (
    KGBindingState,
    KGMultiBindingState,
    LineRangeDelta,
    RangesDelta,
    kg_multi_to_ranges_lens,
    kg_to_line_range_lens,
    ranges_cat,
)


# --------------------------------------------------------------------------
# Strategies (random generators)
# --------------------------------------------------------------------------


@st.composite
def line_ranges(draw, max_line: int = 10_000) -> LineRange:
    start = draw(st.integers(min_value=1, max_value=max_line))
    end = draw(st.integers(min_value=start, max_value=max_line))
    return LineRange(start_line=start, end_line=end)


@st.composite
def kg_binding_states(draw) -> KGBindingState:
    node_id = draw(st.text(min_size=1, max_size=20))
    file_path = draw(st.text(min_size=1, max_size=50))
    r = draw(line_ranges())
    return KGBindingState(node_id=node_id, file_path=file_path, range=r)


@st.composite
def kg_multi_binding_states(draw, max_ranges: int = 5) -> KGMultiBindingState:
    node_id = draw(st.text(min_size=1, max_size=20))
    file_path = draw(st.text(min_size=1, max_size=50))
    ranges = tuple(draw(st.lists(line_ranges(), min_size=0, max_size=max_ranges)))
    return KGMultiBindingState(node_id=node_id, file_path=file_path, ranges=ranges)


# --------------------------------------------------------------------------
# Property: d-PutGet on 1:1 KGBinding ↔ LineRange
# --------------------------------------------------------------------------


@given(s=kg_binding_states(), new_r=line_ranges())
@settings(max_examples=200, deadline=None)
def test_property_putget_1to1(s: KGBindingState, new_r: LineRange) -> None:
    """∀ s, new_r: lifting LineRangeDelta(get(s), new_r) yields state with range=new_r."""
    u = LineRangeDelta(src=s.range, tgt=new_r)
    assert kg_to_line_range_lens.verify_putget(s, u) is True


# --------------------------------------------------------------------------
# Property: d-GetPut / d-PutId on 1:1
# --------------------------------------------------------------------------


@given(s=kg_binding_states())
@settings(max_examples=200, deadline=None)
def test_property_getput_1to1(s: KGBindingState) -> None:
    """∀ s: identity view delta lifts to identity source."""
    assert kg_to_line_range_lens.verify_getput(s) is True


# --------------------------------------------------------------------------
# Property: d-PutGet on 1:N (multi-binding)
# --------------------------------------------------------------------------


@given(s=kg_multi_binding_states(), new_ranges=st.lists(line_ranges(), min_size=0, max_size=5))
@settings(max_examples=200, deadline=None)
def test_property_putget_1toN(s: KGMultiBindingState, new_ranges: list[LineRange]) -> None:
    u = RangesDelta(src=s.ranges, tgt=tuple(new_ranges))
    assert kg_multi_to_ranges_lens.verify_putget(s, u) is True


# --------------------------------------------------------------------------
# Property: d-GetPut on 1:N
# --------------------------------------------------------------------------


@given(s=kg_multi_binding_states())
@settings(max_examples=200, deadline=None)
def test_property_getput_1toN(s: KGMultiBindingState) -> None:
    assert kg_multi_to_ranges_lens.verify_getput(s) is True


# --------------------------------------------------------------------------
# Property: d-PutPut composition on 1:N (state-level)
# --------------------------------------------------------------------------


@given(
    s=kg_multi_binding_states(),
    mid=st.lists(line_ranges(), min_size=0, max_size=5),
    final=st.lists(line_ranges(), min_size=0, max_size=5),
)
@settings(max_examples=200, deadline=None)
def test_property_putput_1toN_composition(
    s: KGMultiBindingState, mid: list[LineRange], final: list[LineRange]
) -> None:
    """d-PutPut: lift(lift(s, u1), u2) == lift(s, compose(u1, u2))."""
    mid_t = tuple(mid)
    final_t = tuple(final)

    u1 = RangesDelta(src=s.ranges, tgt=mid_t)
    u2 = RangesDelta(src=mid_t, tgt=final_t)

    sequential = kg_multi_to_ranges_lens.lift(kg_multi_to_ranges_lens.lift(s, u1), u2)
    composed = kg_multi_to_ranges_lens.lift(s, ranges_cat.compose(u1, u2))

    assert sequential == composed


# --------------------------------------------------------------------------
# Property: LineShift monoid associativity (LineShiftMonoid law)
# --------------------------------------------------------------------------


@given(
    a=st.integers(min_value=-10_000, max_value=10_000),
    b=st.integers(min_value=-10_000, max_value=10_000),
    c=st.integers(min_value=-10_000, max_value=10_000),
)
@settings(max_examples=300, deadline=None)
def test_property_line_shift_associativity(a: int, b: int, c: int) -> None:
    lhs = LineShiftMonoid.mul(LineShiftMonoid.mul(a, b), c)
    rhs = LineShiftMonoid.mul(a, LineShiftMonoid.mul(b, c))
    assert lhs == rhs


# --------------------------------------------------------------------------
# Property: edit lens line_range composition equals direct shift
# --------------------------------------------------------------------------


@given(
    r=line_ranges(max_line=5_000),
    s1=st.integers(min_value=-100, max_value=100),
    s2=st.integers(min_value=-100, max_value=100),
)
@settings(max_examples=200, deadline=None)
def test_property_edit_lens_composition(r: LineRange, s1: int, s2: int) -> None:
    """Composition: apply(apply(r, s1), s2) == apply(r, s1 + s2), if both intermediate
    and final states remain valid (start_line >= 1)."""
    lens = EditLensLineRange()
    # Skip if intermediate or final shift would invalidate LineRange invariants
    if r.start_line + s1 < 1 or r.start_line + s1 + s2 < 1:
        return  # invariant guard — skip invalid composition path
    assert lens.verify_composition(r, s1, s2) is True


# --------------------------------------------------------------------------
# Property: PutGet precondition violation always raises
# --------------------------------------------------------------------------


@given(s=kg_binding_states(), wrong_src=line_ranges(), wrong_tgt=line_ranges())
@settings(max_examples=100, deadline=None)
def test_property_putget_precondition_violation_raises(
    s: KGBindingState, wrong_src: LineRange, wrong_tgt: LineRange
) -> None:
    """If u.src != s.range, lift must raise (caller error)."""
    if wrong_src == s.range:
        return  # skip the case where it accidentally matches
    u_wrong = LineRangeDelta(src=wrong_src, tgt=wrong_tgt)
    with pytest.raises(ValueError, match="d-PutGet precondition"):
        kg_to_line_range_lens.lift(s, u_wrong)
