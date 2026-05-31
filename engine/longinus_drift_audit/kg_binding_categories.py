"""kg_binding_categories.py — DeltaCategory instances for KG binding (Wave 12c SRP split).

Single responsibility: identity + composition for each (state, delta) pair,
exposed as DeltaCategory singletons. No lenses, no registry.

# KG: ATOM_Skill_longinus, vr-longinus-v3.4-wave9-constrain-closure-naesengmoon-3lens-2026-05-20 (D3-w9-F2 SRP)
"""

from __future__ import annotations

from engine.longinus_drift_audit.edit_lens_line_range import LineRange
from engine.longinus_drift_audit.delta_lens import DeltaCategory
from engine.longinus_drift_audit.kg_binding_delta import (
    KGBindingDelta,
    KGMultiBindingDelta,
    LineRangeDelta,
    RangesDelta,
)
from engine.longinus_drift_audit.kg_binding_state import KGBindingState, KGMultiBindingState


def _kg_id(s: KGBindingState) -> KGBindingDelta:
    return KGBindingDelta(src=s, tgt=s)


def _kg_compose(d1: KGBindingDelta, d2: KGBindingDelta) -> KGBindingDelta:
    if d1.tgt != d2.src:
        raise ValueError(f"KGBinding composition mismatch: d1.tgt={d1.tgt} != d2.src={d2.src}")
    return KGBindingDelta(src=d1.src, tgt=d2.tgt)


def _lr_id(s: LineRange) -> LineRangeDelta:
    return LineRangeDelta(src=s, tgt=s)


def _lr_compose(d1: LineRangeDelta, d2: LineRangeDelta) -> LineRangeDelta:
    if d1.tgt != d2.src:
        raise ValueError(f"LineRange composition mismatch: d1.tgt={d1.tgt} != d2.src={d2.src}")
    return LineRangeDelta(src=d1.src, tgt=d2.tgt)


def _mb_id(s: KGMultiBindingState) -> KGMultiBindingDelta:
    return KGMultiBindingDelta(src=s, tgt=s)


def _mb_compose(d1: KGMultiBindingDelta, d2: KGMultiBindingDelta) -> KGMultiBindingDelta:
    if d1.tgt != d2.src:
        raise ValueError("KGMultiBinding composition mismatch")
    return KGMultiBindingDelta(src=d1.src, tgt=d2.tgt)


def _rd_id(s: tuple[LineRange, ...]) -> RangesDelta:
    return RangesDelta(src=s, tgt=s)


def _rd_compose(d1: RangesDelta, d2: RangesDelta) -> RangesDelta:
    if d1.tgt != d2.src:
        raise ValueError("RangesDelta composition mismatch")
    return RangesDelta(src=d1.src, tgt=d2.tgt)


kg_binding_cat: DeltaCategory[KGBindingState, KGBindingDelta] = DeltaCategory(
    id_delta=_kg_id,
    compose=_kg_compose,
    source=lambda d: d.src,
    target=lambda d: d.tgt,
)

line_range_cat: DeltaCategory[LineRange, LineRangeDelta] = DeltaCategory(
    id_delta=_lr_id,
    compose=_lr_compose,
    source=lambda d: d.src,
    target=lambda d: d.tgt,
)

kg_multi_binding_cat: DeltaCategory[KGMultiBindingState, KGMultiBindingDelta] = DeltaCategory(
    id_delta=_mb_id,
    compose=_mb_compose,
    source=lambda d: d.src,
    target=lambda d: d.tgt,
)

ranges_cat: DeltaCategory[tuple[LineRange, ...], RangesDelta] = DeltaCategory(
    id_delta=_rd_id,
    compose=_rd_compose,
    source=lambda d: d.src,
    target=lambda d: d.tgt,
)
