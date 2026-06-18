"""v3.1 Reverse Orphan Scan — Code→KG blind-spot.

SKILL.md §"Reverse Orphan Scan":
코드에 있는 (function/class) 심볼 중 `# KG: xxx` 코멘트가 하나도 안 붙은 것 식별.
"""

from __future__ import annotations

from typing import Iterable

from engine.longinus_drift_audit.models import CodeSymbol


def scan_reverse_orphans(
    *,
    symbols: Iterable[CodeSymbol],
    skip_kinds: set[str] | None = None,
) -> list[str]:
    # KG: ATOM_Skill_longinus
    """Return list of sourcePath strings — symbols WITHOUT any `# KG: x` ref.

    skip_kinds: e.g. ``{'module'}`` to ignore module-level symbols.
    """
    if skip_kinds is None:
        skip_kinds = set()
    out: list[str] = []
    for s in symbols:
        if s.kind in skip_kinds:
            continue
        if not s.kg_refs:
            out.append(s.sourcePath)
    return out


def reverse_orphan_ratio(*, total_symbols: int, orphan_count: int) -> float:
    # KG: ATOM_Skill_longinus
    """orphan_count / total_symbols. 0.0 = full coverage, 1.0 = complete blind."""
    if total_symbols == 0:
        return 0.0
    return orphan_count / total_symbols
