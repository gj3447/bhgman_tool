"""kg_binding_state.py — KG binding state types (Wave 12c SRP split).

Single responsibility: state representation only. No deltas, no categories,
no lenses, no registry side-effects.

# KG: ATOM_Skill_longinus, vr-longinus-v3.4-wave9-constrain-closure-naesengmoon-3lens-2026-05-20 (D3-w9-F2 SRP)
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.longinus_drift_audit.edit_lens_line_range import LineRange


@dataclass(frozen=True)
class KGBindingState:
    # KG: ATOM_Skill_longinus
    """A KG node binding state: (node_id, file_path, line_range)."""

    node_id: str
    file_path: str
    range: LineRange


@dataclass(frozen=True)
class KGMultiBindingState:
    # KG: ATOM_Skill_longinus
    """KG node bound to N line_range hooks. Models Longinus 1:N essence:
    a single KG node may correspond to multiple disjoint code spans."""

    node_id: str
    file_path: str
    ranges: tuple[LineRange, ...]
