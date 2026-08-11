"""RED tests for VR honesty + HSWM fields."""
from __future__ import annotations

import pytest

from engine.naesengmoon.vr_honesty import (
    VrHonesty,
    default_hswm_ship_honesty,
    merge_honesty_into_kg_shape,
    validate_vr_honesty,
)


def test_ok_agent_tool_n():
    h = default_hswm_ship_honesty(
        dispatch_mode="AGENT_TOOL_N", subagent_count=10, claimed_n=10, n_eff=3.2
    )
    assert validate_vr_honesty(h.to_props()) == []


def test_fake_n_jung_count_mismatch():
    props = default_hswm_ship_honesty(
        dispatch_mode="AGENT_TOOL_N", subagent_count=1, claimed_n=100
    ).to_props()
    v = validate_vr_honesty(props)
    assert any("fake_n_jung" in x for x in v)


def test_traversal_mu_nonzero_blocked_for_flat_l4():
    h = VrHonesty(
        dispatch_mode="SINGLE",
        subagent_count=1,
        hswm_mode="flat_L4",
        traversal_mu=1.0,
        readout="flat_L4",
    )
    v = validate_vr_honesty(h.to_props())
    assert any("traversal_mu" in x for x in v)


def test_structure_readout_with_flat_l4_blocked():
    h = VrHonesty(
        dispatch_mode="SINGLE",
        subagent_count=1,
        hswm_mode="flat_L4",
        readout="structure",
    )
    v = validate_vr_honesty(h.to_props())
    assert any("structure_readout" in x for x in v)


def test_merge_hard_fail():
    shape = {"name": "VR_x", "labels": ["ValidationResult"], "props": {"verdict": "PASS"}}
    h = default_hswm_ship_honesty(
        dispatch_mode="AGENT_TOOL_N", subagent_count=0, claimed_n=10
    )
    with pytest.raises(ValueError, match="honesty"):
        merge_honesty_into_kg_shape(shape, h, hard_fail=True)


def test_merge_ok():
    shape = {"name": "VR_x", "labels": ["ValidationResult"], "props": {"verdict": "PASS"}}
    h = default_hswm_ship_honesty(dispatch_mode="AGENT_TOOL_N", subagent_count=10)
    out = merge_honesty_into_kg_shape(shape, h)
    assert out["props"]["hswm_mode"] == "flat_L4"
    assert out["props"]["traversal_mu"] == 0.0
    assert out["props"]["subagent_count"] == 10
