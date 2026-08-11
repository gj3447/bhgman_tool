"""ValidationResult honesty fields — dispatch + HSWM absorb (2026-07-22).

Locks from:
  - lesson-naesengmoon-100x-fs-automation-not-n-dispatch-2026-07-15
  - ABSORB_CONTRACT_v1 / hswm-solid-absorb skill
  - PROM SKILL.md v6.4.1 pointer

VR props that parent/UNWIND must be able to stamp. Missing HSWM fields when
``hswm_mode`` is claimed non-off is a soft warning; fake N중 is hard-fail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Dispatch honesty (existing P0)
DISPATCH_MODES = frozenset({
    "AGENT_TOOL_N",
    "ENGINE_DISPATCH",
    "PARENT_HYBRID_10x100",
    "PARENT_SYNTHESIS",
    "HYBRID_20LLM_80SCAN",
    "FS_AUTOMATION",
    "FS_AUTOMATION+hostile",
    "GRID_SCAN",
    "SINGLE",
    "UNKNOWN",
})

# N중 labels that require real parallel dispatch
N_JUNG_MODES = frozenset({"AGENT_TOOL_N", "ENGINE_DISPATCH"})

HSWM_MODES = frozenset({"off", "flat_L4", "optin_weave"})
READOUTS = frozenset({"flat", "flat_L4", "structure", "unknown"})


@dataclass(frozen=True)
class VrHonesty:
    """Stamp onto ValidationResult.props."""

    dispatch_mode: str = "UNKNOWN"
    subagent_count: int = 0
    n_eff: float | None = None
    automation_flag: bool = False
    hswm_mode: str = "off"
    traversal_mu: float = 0.0
    readout: str = "flat_L4"
    claimed_n: int | None = None
    aggregation_policy: str = ""
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_props(self) -> dict[str, Any]:
        props: dict[str, Any] = {
            "dispatch_mode": self.dispatch_mode,
            "subagent_count": int(self.subagent_count),
            "automation_flag": bool(self.automation_flag),
            "hswm_mode": self.hswm_mode,
            "traversal_mu": float(self.traversal_mu),
            "readout": self.readout,
        }
        if self.n_eff is not None:
            props["n_eff"] = round(float(self.n_eff), 4)
        if self.claimed_n is not None:
            props["claimed_n"] = int(self.claimed_n)
        if self.aggregation_policy:
            props["aggregation_policy"] = self.aggregation_policy
        if self.notes:
            props["honesty_notes"] = self.notes
        props.update(self.extra)
        return props


def validate_vr_honesty(props: dict[str, Any]) -> list[str]:
    """Return list of hard violations (empty = ok). Soft warnings not included."""
    violations: list[str] = []
    mode = str(props.get("dispatch_mode") or "UNKNOWN")
    count = int(props.get("subagent_count") or 0)
    claimed = props.get("claimed_n")
    if claimed is not None:
        claimed = int(claimed)

    # Fake N중: claim AGENT_TOOL_N / ENGINE with count mismatch
    if mode in N_JUNG_MODES:
        if claimed is not None and count != claimed:
            violations.append(
                f"fake_n_jung: dispatch_mode={mode} claimed_n={claimed} subagent_count={count}"
            )
        if count < 1:
            violations.append(f"fake_n_jung: {mode} requires subagent_count>=1 got {count}")

    # GRID_SCAN must not be labeled as N중 mode
    if mode in {"GRID_SCAN", "FS_AUTOMATION", "FS_AUTOMATION+hostile"}:
        if claimed is not None and claimed >= 10 and count <= 1:
            # calling it high-N while automation is the classic lie
            if props.get("label_n_jung") or props.get("cardinality_claim", 0) >= 10:
                violations.append("grid_scan_labeled_as_n_jung")

    hswm = str(props.get("hswm_mode") or "off")
    if hswm not in HSWM_MODES:
        violations.append(f"bad_hswm_mode:{hswm}")

    mu = float(props.get("traversal_mu", 0) or 0)
    if hswm in {"flat_L4", "optin_weave"} and mu > 0:
        violations.append("traversal_mu_nonzero_with_hswm_ship_mode")

    readout = str(props.get("readout") or "unknown")
    if readout not in READOUTS:
        violations.append(f"bad_readout:{readout}")

    # structure readout as deploy default is banned when hswm_mode is flat_L4 ship
    if hswm == "flat_L4" and readout == "structure":
        violations.append("structure_readout_with_flat_L4_mode")

    return violations


def merge_honesty_into_kg_shape(
    shape: dict[str, Any],
    honesty: VrHonesty,
    *,
    hard_fail: bool = True,
) -> dict[str, Any]:
    """Merge honesty props into ConsensusResult.to_kg_shape output."""
    props = dict(shape.get("props") or {})
    props.update(honesty.to_props())
    viol = validate_vr_honesty(props)
    if viol and hard_fail:
        raise ValueError("VR honesty violations: " + "; ".join(viol))
    if viol:
        props["honesty_violations"] = viol
    out = dict(shape)
    out["props"] = props
    return out


def default_hswm_ship_honesty(
    *,
    dispatch_mode: str,
    subagent_count: int,
    claimed_n: int | None = None,
    n_eff: float | None = None,
    automation_flag: bool = False,
    notes: str = "",
) -> VrHonesty:
    """Factory for absorb-default ship stamps."""
    return VrHonesty(
        dispatch_mode=dispatch_mode,
        subagent_count=subagent_count,
        claimed_n=claimed_n if claimed_n is not None else subagent_count,
        n_eff=n_eff,
        automation_flag=automation_flag,
        hswm_mode="flat_L4",
        traversal_mu=0.0,
        readout="flat_L4",
        notes=notes,
    )
