"""kg_binding_lenses.py — DeltaLens instances for KG binding (Wave 12c SRP split).

Single responsibility: get + lift definitions, exposed as DeltaLens
singletons. d-PutGet precondition enforced at lift boundary per Diskin 2011 §3.

# KG: ATOM_Skill_longinus, vr-longinus-v3.4-wave9-constrain-closure-naesengmoon-3lens-2026-05-20 (D3-w9-F2 SRP)
"""

from __future__ import annotations

from dataclasses import replace

from edit_lens_line_range import LineRange
from delta_lens import DeltaLens
from kg_binding_categories import (
    kg_binding_cat,
    kg_multi_binding_cat,
    line_range_cat,
    ranges_cat,
)
from kg_binding_delta import (
    KGBindingDelta,
    KGMultiBindingDelta,
    LineRangeDelta,
    RangesDelta,
)
from kg_binding_state import KGBindingState, KGMultiBindingState


def _kg_get(s: KGBindingState) -> LineRange:
    """Extract the line_range view from a KG binding state."""
    return s.range


def _kg_lift(s: KGBindingState, u: LineRangeDelta) -> KGBindingState:
    """Lift a LineRange delta to the source state by replacing `range` field.

    Precondition (d-PutGet): u.src must equal get(s) = s.range. If violated,
    the lens is being used outside its domain — raise to catch caller errors
    early (matches Diskin 2011 §3 lift partiality discipline).
    """
    if u.src != s.range:
        raise ValueError(f"d-PutGet precondition violated: u.src={u.src} != s.range={s.range}")
    return replace(s, range=u.tgt)


def _mb_get(s: KGMultiBindingState) -> tuple[LineRange, ...]:
    return s.ranges


def _mb_lift(s: KGMultiBindingState, u: RangesDelta) -> KGMultiBindingState:
    if u.src != s.ranges:
        raise ValueError(f"d-PutGet precondition violated: u.src={u.src} != s.ranges={s.ranges}")
    return replace(s, ranges=u.tgt)


kg_to_line_range_lens: DeltaLens[KGBindingState, LineRange, KGBindingDelta, LineRangeDelta] = (
    DeltaLens(
        source_cat=kg_binding_cat,
        view_cat=line_range_cat,
        get=_kg_get,
        lift=_kg_lift,
    )
)


kg_multi_to_ranges_lens: DeltaLens[
    KGMultiBindingState,
    tuple[LineRange, ...],
    KGMultiBindingDelta,
    RangesDelta,
] = DeltaLens(
    source_cat=kg_multi_binding_cat,
    view_cat=ranges_cat,
    get=_mb_get,
    lift=_mb_lift,
)
