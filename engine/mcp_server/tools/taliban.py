"""MCP tool — `taliban_lens_check`.

KG: span-mcp-tool-taliban-lens-check-2026-05-13 (:AtomicSpan)

Returns LensSet membership and coverage axes for adversarial validation. Mirrors the
SYMPOSIUM Taliban v0.8 LensSet canonical (constitutional / mathematical / solid / longinus).

Honest limitations (Goodhart safeguard):
- Static lens registry — keeps the tool offline-runnable but means the registry can drift
  from the live KG. Cross-check against SYMPOSIUM canon when a lens is added.
- `coverage_score` is NOT returned. The tool refuses to flatten lens count into a single
  number; consumers must inspect the lens list to judge fitness.
- `--lens all` returns UNION; cross-lens deduplication is per-name, not semantic.
"""
from __future__ import annotations

from typing import Any

# Mirror SYMPOSIUM canonical LensSet — keep in sync with KG queries:
#   MATCH (ls:LensSet) WHERE ls.deprecated <> true RETURN ls.name, ls.lens_count
# KG: lesson-taliban-lens-pluggable-refactor-2026-04-16, LensSet UNION coverage canon
LENS_REGISTRY: dict[str, dict[str, Any]] = {
    "constitutional": {
        "lens_count": 9,
        "min_critics": 3,
        "description": "Default 9-axis constitutional lens for artifact validation.",
        "axes": [
            "correctness", "completeness", "consistency", "efficiency", "maintainability",
            "safety", "evidence", "compositional", "fail_modes",
        ],
    },
    "mathematical": {
        "lens_count": 113,
        "min_critics": 7,
        "description": "Meta-verification 113-axis lens (use for methodology meta-checks only).",
        "axes": [],  # 113 axes — not enumerated in skeleton (see KG)
        "kg_ref": "lens-set-mathematical-113-axis",
    },
    "solid": {
        "lens_count": 5,
        "min_critics": 2,
        "description": "SOLID class-level lens (SRP/OCP/LSP/ISP/DIP).",
        "axes": ["SRP", "OCP", "LSP", "ISP", "DIP"],
    },
    "longinus": {
        "lens_count": 7,
        "min_critics": 2,
        "description": "Longinus 7-Layer Reference Model lens.",
        "axes": [
            "L1_Symbol", "L2_Source", "L3_Path", "L4_Crate", "L5_ReferenceSite",
            "L6_Sha256Baseline", "L7_AestheticIntentional",
        ],
    },
}

_HR12_NOTE = (
    "HR12: never mix tiers. constitutional = artifact validation. mathematical = methodology "
    "meta-verification only. cross-tier application is BLOCKED at the Taliban gate."
)


def _normalize(name: str) -> str:
    return name.strip().lower()


def _lens_payload(name: str) -> dict[str, Any]:
    raw = LENS_REGISTRY[name]
    return {
        "name": name,
        "lens_count": raw["lens_count"],
        "min_critics": raw["min_critics"],
        "description": raw["description"],
        "axes": raw["axes"],
        "kg_ref": raw.get("kg_ref"),
    }


def taliban_lens_check_impl(lens: str = "all") -> dict[str, Any]:
    """Return lens registry information.

    `lens` accepts a registered name or "all" for the UNION. Unknown name → ValueError.
    """
    if not isinstance(lens, str):
        raise TypeError(f"lens must be a string, got {type(lens).__name__}")

    target = _normalize(lens)

    if target == "all":
        lenses = [_lens_payload(n) for n in sorted(LENS_REGISTRY)]
        union_axes_with_origin: list[dict[str, str]] = []
        seen: set[str] = set()
        for payload in lenses:
            for axis in payload["axes"]:
                if axis in seen:
                    continue
                seen.add(axis)
                union_axes_with_origin.append({"axis": axis, "from_lens": payload["name"]})
        return {
            "mode": "union",
            "lenses": lenses,
            "union_axes": union_axes_with_origin,
            "union_axis_count_partial": len(union_axes_with_origin),
            "hr12_note": _HR12_NOTE,
            "note": (
                "mathematical lens (113 axes) is not enumerated in the skeleton — see KG for "
                "the full list. union_axis_count_partial counts only the enumerated axes."
            ),
        }

    if target not in LENS_REGISTRY:
        raise ValueError(
            f"unknown lens: {lens!r}. registered: {sorted(LENS_REGISTRY)} (or 'all')."
        )

    payload = _lens_payload(target)
    payload["hr12_note"] = _HR12_NOTE
    payload["mode"] = "single"
    return payload


def register(mcp: Any) -> None:
    """Attach `taliban_lens_check` tool to the FastMCP instance."""
    @mcp.tool()
    def taliban_lens_check(lens: str = "all") -> dict[str, Any]:
        """Return Taliban LensSet membership and axes (skeleton — static registry).

        Args:
            lens: one of {constitutional, mathematical, solid, longinus, all}

        Returns: LensCheckReport dict.
        """
        return taliban_lens_check_impl(lens)
