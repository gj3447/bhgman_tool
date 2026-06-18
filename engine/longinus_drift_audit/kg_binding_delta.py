"""kg_binding_delta.py — KG binding delta types (Wave 12c SRP split).

Single responsibility: delta (state-pair) representation. No categories, no
lenses, no registry.

# KG: ATOM_Skill_longinus, vr-longinus-v3.4-wave9-constrain-closure-naesengmoon-3lens-2026-05-20 (D3-w9-F2 SRP)
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.longinus_drift_audit.edit_lens_line_range import LineRange
from engine.longinus_drift_audit.kg_binding_state import KGBindingState, KGMultiBindingState


@dataclass(frozen=True)
class KGBindingDelta:
    # KG: ATOM_Skill_longinus
    """A delta between two KGBindingState values (state pair)."""

    src: KGBindingState
    tgt: KGBindingState


@dataclass(frozen=True)
class KGMultiBindingDelta:
    # KG: ATOM_Skill_longinus
    src: KGMultiBindingState
    tgt: KGMultiBindingState


@dataclass(frozen=True)
class LineRangeDelta:
    # KG: ATOM_Skill_longinus
    """A delta between two LineRange values."""

    src: LineRange
    tgt: LineRange


@dataclass(frozen=True)
class RangesDelta:
    # KG: ATOM_Skill_longinus
    """Delta on a tuple of line ranges (view side of the multi-binding lens)."""

    src: tuple[LineRange, ...]
    tgt: tuple[LineRange, ...]
