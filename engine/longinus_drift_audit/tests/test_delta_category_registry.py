"""Tests for delta_category_registry.py — Wave 9c DIP refactor.

Verifies:
- DeltaCategoryRegistryProto Protocol contract (register/get/has/names)
- DefaultDeltaCategoryRegistry round-trip
- Singleton default_registry contains the 4 Wave 6c categories
- Duplicate register raises ValueError (idempotency contract)
- Unknown get raises KeyError
- Test isolation via fresh registry instance (DIP enabler)

# KG: ATOM_Skill_longinus, ap-longinus-v34-bx-lens-substitute-2026-05-20,
      vr-longinus-v3.4-wave6-8-followup-naesengmoon-3lens-2026-05-20 D3-DIP-FAIL resolution
"""

from __future__ import annotations

import pytest

from engine.longinus_drift_audit.delta_category_registry import (
    DefaultDeltaCategoryRegistry,
    DeltaCategoryRegistryProto,
    default_registry,
)
from engine.longinus_drift_audit.delta_lens import DeltaCategory, int_delta_cat


def test_default_registry_has_4_wave6c_categories() -> None:
    """default_registry singleton contains the 4 Wave 6c category registrations."""
    expected = {"kg_binding", "line_range", "kg_multi_binding", "ranges"}
    # kg_binding_delta_lens must be imported to trigger registration
    from engine.longinus_drift_audit import kg_binding_delta_lens  # noqa: F401

    assert expected.issubset(set(default_registry.names()))


def test_default_registry_get_returns_DeltaCategory_instance() -> None:
    from engine.longinus_drift_audit import kg_binding_delta_lens  # noqa: F401

    cat = default_registry.get("kg_binding")
    assert isinstance(cat, DeltaCategory)


def test_default_registry_has_known_name() -> None:
    from engine.longinus_drift_audit import kg_binding_delta_lens  # noqa: F401

    assert default_registry.has("ranges") is True
    assert default_registry.has("nonexistent_cat") is False


def test_default_registry_unknown_get_raises_keyerror() -> None:
    with pytest.raises(KeyError, match="not registered"):
        default_registry.get("absolutely_unknown_category")


def test_fresh_registry_round_trip() -> None:
    """Test isolation: fresh DefaultDeltaCategoryRegistry independent of singleton."""
    reg = DefaultDeltaCategoryRegistry()
    assert reg.names() == []

    reg.register("ints", int_delta_cat())
    assert reg.has("ints") is True
    assert reg.get("ints") is int_delta_cat()


def test_fresh_registry_duplicate_register_raises_valueerror() -> None:
    reg = DefaultDeltaCategoryRegistry()
    reg.register("a", int_delta_cat())
    with pytest.raises(ValueError, match="already registered"):
        reg.register("a", int_delta_cat())


def test_default_registry_satisfies_protocol() -> None:
    """default_registry must satisfy the DeltaCategoryRegistryProto Protocol."""
    assert isinstance(default_registry, DeltaCategoryRegistryProto)


def test_fresh_registry_unregister_is_idempotent_for_unknown() -> None:
    reg = DefaultDeltaCategoryRegistry()
    # Should not raise on unknown name
    reg.unregister("never_registered")
    assert reg.names() == []
