"""Forward Orphan Scan — Longinus Wave 6 (2026-05-14) absorption.

Paradigm shift (vs Reverse Orphan):
    reverse (v3.1): code symbol → KG ref → exists?       (PutGet, BX Lens)
                    Code → KG blind-spot.
    forward (v3.2 Wave 6): KG hub → ``package_path`` → disk exists?
                    KG → Code blind-spot. GetPut violation.

SYMPOSIUM Wave 6 motivating instance: 7 :KnowledgeHub nodes (hub-apt-methodology,
hub-tpa-methodology, hub-jaebaeman-sop, hub-taliban-immunity,
hub-prometheus-research, hub-longinus-reference, hub-harness-3tier) all lacked
``package_path`` + ``ruflo_grade``. Resolution = set package_path on every hub.

This module turns that one-shot resolution into a reusable audit + auto-fix loop.

# KG: lesson-longinus-wave6-full-symposium-binding-2026-05-14
# KG: longinus-forward-orphan-scan-2026-05-14
# KG: span-bhgman-longinus-wave6-absorb-2026-05-14
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional

from engine.longinus_drift_audit.kg_client import KgClient
from engine.longinus_drift_audit.models import (
    ForwardOrphanRecord,
    KnowledgeHubRecord,
    ReferenceLayer,
)

logger = logging.getLogger(__name__)


# ─── Detection ────────────────────────────────────────────────────────────


REQUIRED_HUB_FIELDS: tuple[str, ...] = ("package_path", "source_file")
"""Fields that every materialized :KnowledgeHub MUST carry.

`ruflo_grade` is *recommended* (industry-grade rating) but not strictly required.
"""


def scan_forward_orphans(
    hubs: Iterable[KnowledgeHubRecord],
    *,
    required_fields: Iterable[str] = REQUIRED_HUB_FIELDS,
) -> list[ForwardOrphanRecord]:
    # KG: ATOM_Skill_longinus
    """Detect :KnowledgeHub nodes missing required materialization fields.

    Returns one ForwardOrphanRecord per (hub, missing_field) pair — a single hub
    missing both ``package_path`` and ``source_file`` yields 2 records.
    """
    req = tuple(required_fields)
    out: list[ForwardOrphanRecord] = []
    for hub in hubs:
        for field in req:
            value = getattr(hub, field, None)
            if not value:
                out.append(
                    ForwardOrphanRecord(
                        hub_name=hub.name,
                        missing_field=field,
                        layer_violated=ReferenceLayer.L3_TYPE,
                        lens_law_violated="GetPut",
                    )
                )
    return out


def forward_orphan_ratio(*, total_hubs: int, orphan_count: int) -> float:
    # KG: ATOM_Skill_longinus
    """Forward orphan / total hubs ratio. 0.0 = perfect materialization."""
    if total_hubs == 0:
        return 0.0
    return orphan_count / total_hubs


# ─── Resolution (auto-fix) ────────────────────────────────────────────────


def resolve_forward_orphan(
    *,
    kg: KgClient,
    hub_name: str,
    package_path: str,
    source_file: str | None = None,
    ruflo_grade: str | None = None,
    fs_root: Path | str | None = None,
) -> bool:
    # KG: ATOM_Skill_longinus
    """Write package_path/source_file/ruflo_grade onto a :KnowledgeHub.

    If `fs_root` is given, verify the path actually exists on disk before writing
    (GetPut law — we should not assert a hub points to a missing folder).
    Returns False if filesystem verification fails.
    """
    if fs_root is not None:
        root = Path(fs_root)
        candidate = root / package_path
        if not candidate.exists():
            logger.warning(
                "resolve_forward_orphan: %s package_path=%s does not exist under %s",
                hub_name,
                package_path,
                root,
            )
            return False
    kg.set_knowledge_hub_path(
        name=hub_name,
        package_path=package_path,
        source_file=source_file,
        ruflo_grade=ruflo_grade,
    )
    return True


def bulk_resolve(
    *,
    kg: KgClient,
    resolutions: dict[str, dict[str, Optional[str]]],
    fs_root: Path | str | None = None,
) -> dict[str, bool]:
    # KG: ATOM_Skill_longinus
    """Apply multiple forward orphan resolutions in one call.

    `resolutions` shape:
        {
          "hub-apt-methodology": {
              "package_path": "THEORY/APT/",
              "source_file":  "THEORY/APT/README.md",
              "ruflo_grade":  "STRONG",
          },
          ...
        }
    """
    out: dict[str, bool] = {}
    for hub_name, fields in resolutions.items():
        pkg = fields.get("package_path")
        if not pkg:
            out[hub_name] = False
            continue
        out[hub_name] = resolve_forward_orphan(
            kg=kg,
            hub_name=hub_name,
            package_path=pkg,
            source_file=fields.get("source_file"),
            ruflo_grade=fields.get("ruflo_grade"),
            fs_root=fs_root,
        )
    return out


# ─── Wave 6 canonical resolutions (golden values from LONGINUS_BINDING.md) ──


WAVE6_HUB_RESOLUTIONS: dict[str, dict[str, str]] = {
    "hub-apt-methodology": {
        "package_path": "THEORY/APT/",
        "source_file": "THEORY/APT/README.md",
    },
    "hub-tpa-methodology": {
        "package_path": "THEORY/TPA/",
        "source_file": "THEORY/TPA/README.md",
    },
    "hub-jaebaeman-sop": {
        "package_path": "THEORY/재배맨/",
        "source_file": "THEORY/재배맨/README.md",
    },
    "hub-taliban-immunity": {
        "package_path": "THEORY/TALIBAN/",
        "source_file": "THEORY/TALIBAN/README.md",
    },
    "hub-prometheus-research": {
        "package_path": "THEORY/PROMETHEUS/",
        "source_file": "THEORY/PROMETHEUS/README.md",
    },
    "hub-longinus-reference": {
        "package_path": "THEORY/LONGINUS/",
        "source_file": "THEORY/LONGINUS/README.md",
    },
    "hub-harness-3tier": {
        "package_path": "THEORY/HARNESS/",
        "source_file": "THEORY/HARNESS/README.md",
    },
}


# KG: longinus-forward-orphan-scan-2026-05-14
# KG: lesson-longinus-wave6-full-symposium-binding-2026-05-14
