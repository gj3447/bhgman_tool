"""kg_binding_delta_lens.py — facade re-export after Wave 12c SRP split.

Backward-compatible surface for callers using the pre-split public API. The
implementation now lives in 5 SRP-split modules:

    kg_binding_state            — state dataclasses
    kg_binding_delta            — delta dataclasses
    kg_binding_categories       — DeltaCategory singletons + id/compose
    kg_binding_lenses           — DeltaLens singletons + get/lift
    kg_binding_registry_install — Wave 9c DIP side-effect (import-time)

New callers should import directly from the SRP-split modules. The facade
remains the canonical re-export point for tests + downstream tools that
predate the split.

References:
    Diskin, Xiong, Czarnecki. JOT 10(6):1-25, 2011.
    Martin, R.C. 2017. Clean Architecture. Ch.7 SRP.

# KG: ATOM_Skill_longinus, ap-longinus-v34-bx-lens-substitute-2026-05-20,
      seed-bx-delta-lens-diskin-primary-2026-05-20,
      vr-longinus-v3.4-bx-lens-substitute-naesengmoon-3lens-2026-05-20 (F4, F6, M3, M4),
      vr-longinus-v3.4-wave9-constrain-closure-naesengmoon-3lens-2026-05-20 (D3-w9-F2 SRP fix)
"""

from __future__ import annotations

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
from kg_binding_lenses import (
    kg_multi_to_ranges_lens,
    kg_to_line_range_lens,
)
from kg_binding_state import KGBindingState, KGMultiBindingState

import kg_binding_registry_install  # noqa: F401  (import for side-effect)


__all__ = [
    "KGBindingDelta",
    "KGBindingState",
    "KGMultiBindingDelta",
    "KGMultiBindingState",
    "LineRangeDelta",
    "RangesDelta",
    "kg_binding_cat",
    "kg_multi_binding_cat",
    "kg_multi_to_ranges_lens",
    "kg_to_line_range_lens",
    "line_range_cat",
    "ranges_cat",
]
