"""
tree_sitter_adapter.py — Optional tree-sitter source-delta adapter (Wave 7a).

Converts tree-sitter `getChangedRanges` output into Longinus `RangesDelta`
suitable for feeding into `kg_multi_to_ranges_lens.lift`. Graceful import:
if `tree_sitter` is not installed, the adapter degrades to a stub that
documents the expected interface without runtime failure.

References:
    tree-sitter `getChangedRanges` (GitHub: tree-sitter/tree-sitter)
    Diskin-Xiong-Czarnecki 2011 — delta lens source-delta semantics

# KG: ATOM_Skill_longinus, ap-longinus-v34-bx-lens-substitute-2026-05-20,
      seed-bx-delta-lens-diskin-primary-2026-05-20 (Wave 3 deferred tree-sitter),
      vr-longinus-v3.4-bx-lens-substitute-naesengmoon-3lens-2026-05-20 (F1 resolve)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from edit_lens_line_range import LineRange
from kg_binding_delta_lens import RangesDelta


@dataclass(frozen=True)
class TSChangedRange:
    """A tree-sitter changed range — start_byte/end_byte plus start/end row.

    Mirrors `TSRange` in tree-sitter Python bindings. Row indices are 0-indexed
    in tree-sitter; we convert to 1-indexed `LineRange` for Longinus convention.
    """

    start_row_0: int
    end_row_0: int
    start_byte: int
    end_byte: int


def ts_range_to_line_range(r: TSChangedRange) -> LineRange:
    """Convert a tree-sitter 0-indexed row range to a Longinus 1-indexed LineRange."""
    return LineRange(start_line=r.start_row_0 + 1, end_line=r.end_row_0 + 1)


def changed_ranges_to_view_delta(
    old_ranges: Sequence[LineRange],
    new_ranges: Sequence[LineRange],
) -> RangesDelta:
    """Build a view-side delta tuple from before/after LineRange sequences.

    Caller obtains `old_ranges` from the prior KG binding state and `new_ranges`
    from rerunning the parse after applying tree-sitter edits. This is the
    primary feeding function for `kg_multi_to_ranges_lens.lift`.
    """
    return RangesDelta(src=tuple(old_ranges), tgt=tuple(new_ranges))


def is_tree_sitter_available() -> bool:
    """Soft check for tree_sitter installation; never raises."""
    try:
        import tree_sitter  # noqa: F401

        return True
    except ImportError:
        return False


def example_workflow_doc() -> str:
    """Return a docstring-style example of the expected integration flow.

    Returned as text rather than executed because tree-sitter usage requires
    a grammar binary which we do not bundle in this prototype.
    """
    return """
    Example: tree-sitter Python file edit → Longinus delta lens lift

        from tree_sitter import Parser, Language
        from tree_sitter_python import language as py_language
        from tree_sitter_adapter import (
            TSChangedRange, ts_range_to_line_range, changed_ranges_to_view_delta,
        )
        from kg_binding_delta_lens import kg_multi_to_ranges_lens, KGMultiBindingState

        # 1) Parse old code, record line_ranges per KG node
        # 2) Apply edit (insertion / deletion / modification)
        # 3) Re-parse with `tree.edit(...)` then `new_tree = parser.parse(new_src, tree)`
        # 4) ranges = new_tree.changed_ranges(tree)  # tree-sitter API
        # 5) Convert each TSRange to LineRange
        # 6) Build RangesDelta(src=old_ranges, tgt=new_ranges)
        # 7) kg_multi_to_ranges_lens.lift(old_kg_state, ranges_delta) → new KG state

    Reference: tree-sitter docs §"Incremental Parsing"
    """
