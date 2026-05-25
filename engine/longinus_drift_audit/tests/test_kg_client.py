"""Neo4jKgClient read-path hardening — _coerce_enum graceful degradation.

Naesengmoon re-validation v2 findings:
  ac-bhgman-cd3eeaa-sibling-list_reference_site_states-goodhart (HIGH) +
  ac-bhgman-cd3eeaa-list_reference_site_states-drops-status-layer (MED).

KG ReferenceSite nodes carry free-form layer strings ('tool', 'PromReport_v1',
'L3', …) and non-enum sha256 statuses ('OK', 'PENDING_COMPUTE', …). Strict
construction would silently drop ~130 rows — including valid DIRECTORY_SKIP
sites whose status must survive so verify_baseline skips them instead of
false-flagging FILE_MISSING. _coerce_enum keeps valid members and degrades the
rest to None (→ field default) rather than rejecting the whole row.
"""

from __future__ import annotations

from kg_client import _coerce_enum
from models import ReferenceLayer, Sha256Status


class TestCoerceEnum:
    def test_valid_member_kept(self):
        assert _coerce_enum("DIRECTORY_SKIP", Sha256Status) == "DIRECTORY_SKIP"
        assert _coerce_enum("L3_TypePermission", ReferenceLayer) == "L3_TypePermission"

    def test_invalid_status_degrades_to_none(self):
        # real non-enum values observed in KG
        for bad in ("OK", "PENDING_COMPUTE", "REBASELINED"):
            assert _coerce_enum(bad, Sha256Status) is None

    def test_freeform_layer_degrades_to_none(self):
        # real free-form layer strings observed in KG
        for bad in ("tool", "PromReport_v1", "L3", "L7_FullStack_DirCluster"):
            assert _coerce_enum(bad, ReferenceLayer) is None

    def test_none_passthrough(self):
        assert _coerce_enum(None, Sha256Status) is None
        assert _coerce_enum(None, ReferenceLayer) is None
