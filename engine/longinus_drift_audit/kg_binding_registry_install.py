"""kg_binding_registry_install.py — Wave 9c DIP registration side-effect (Wave 12c SRP split).

Single responsibility: side-effect that registers the 4 module-level
DeltaCategory singletons to the default registry. Import this module
explicitly to trigger registration (the facade `kg_binding_delta_lens` does
so for backward compatibility).

# KG: ATOM_Skill_longinus, vr-longinus-v3.4-wave9-constrain-closure-naesengmoon-3lens-2026-05-20 (D3-w9-F2 SRP)
"""

from __future__ import annotations

from engine.longinus_drift_audit.delta_category_registry import default_registry
from engine.longinus_drift_audit.kg_binding_categories import (
    kg_binding_cat,
    kg_multi_binding_cat,
    line_range_cat,
    ranges_cat,
)


def install(registry=default_registry) -> None:
    # KG: ATOM_Skill_longinus
    """Register 4 KG-binding categories. Idempotent on re-import."""
    pairs = (
        ("kg_binding", kg_binding_cat),
        ("line_range", line_range_cat),
        ("kg_multi_binding", kg_multi_binding_cat),
        ("ranges", ranges_cat),
    )
    for name, cat in pairs:
        try:
            registry.register(name, cat)
        except ValueError:
            pass


install()
