"""Tests for Forward Orphan Scan — Longinus Wave 6 (2026-05-14)."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.longinus_drift_audit import forward_orphan_scan
from engine.longinus_drift_audit.kg_client import MockKgClient
from engine.longinus_drift_audit.models import KnowledgeHubRecord


@pytest.fixture
def hubs_partial() -> list[KnowledgeHubRecord]:
    """Mix of fully-materialized + partially-orphan hubs."""
    return [
        # Fully resolved
        KnowledgeHubRecord(
            name="hub-fully-resolved",
            package_path="THEORY/X/",
            source_file="THEORY/X/README.md",
            ruflo_grade="STRONG",
        ),
        # Missing package_path (forward orphan)
        KnowledgeHubRecord(
            name="hub-no-path",
            source_file="THEORY/Y/README.md",
        ),
        # Missing both required fields
        KnowledgeHubRecord(name="hub-totally-orphan"),
    ]


class TestScanForwardOrphans:
    def test_resolved_hub_yields_no_orphan(self):
        hub = KnowledgeHubRecord(
            name="hub-ok",
            package_path="THEORY/Z/",
            source_file="THEORY/Z/README.md",
        )
        out = forward_orphan_scan.scan_forward_orphans([hub])
        assert out == []

    def test_missing_package_path_detected(self):
        hub = KnowledgeHubRecord(
            name="hub-no-path",
            source_file="x.md",
        )
        out = forward_orphan_scan.scan_forward_orphans([hub])
        assert len(out) == 1
        assert out[0].hub_name == "hub-no-path"
        assert out[0].missing_field == "package_path"
        assert out[0].lens_law_violated == "GetPut"

    def test_totally_orphan_yields_record_per_missing_field(self):
        hub = KnowledgeHubRecord(name="hub-empty")
        out = forward_orphan_scan.scan_forward_orphans([hub])
        # default required = (package_path, source_file)
        assert len(out) == 2
        missing_fields = {r.missing_field for r in out}
        assert missing_fields == {"package_path", "source_file"}

    def test_mixed_set(self, hubs_partial: list[KnowledgeHubRecord]):
        out = forward_orphan_scan.scan_forward_orphans(hubs_partial)
        names = [r.hub_name for r in out]
        # hub-no-path: 1 orphan (package_path)
        # hub-totally-orphan: 2 orphans (package_path + source_file)
        # hub-fully-resolved: 0
        assert names.count("hub-no-path") == 1
        assert names.count("hub-totally-orphan") == 2
        assert "hub-fully-resolved" not in names

    def test_custom_required_fields(self):
        hub = KnowledgeHubRecord(
            name="hub-x",
            package_path="THEORY/X/",
            source_file="x.md",
            # ruflo_grade missing
        )
        out = forward_orphan_scan.scan_forward_orphans(
            [hub],
            required_fields=("ruflo_grade",),
        )
        assert len(out) == 1
        assert out[0].missing_field == "ruflo_grade"


class TestRatio:
    def test_zero_total(self):
        assert forward_orphan_scan.forward_orphan_ratio(total_hubs=0, orphan_count=0) == 0.0

    def test_full_orphan(self):
        assert forward_orphan_scan.forward_orphan_ratio(total_hubs=7, orphan_count=7) == 1.0

    def test_partial(self):
        assert forward_orphan_scan.forward_orphan_ratio(total_hubs=10, orphan_count=3) == 0.3


class TestResolveForwardOrphan:
    def test_resolve_writes_to_kg(self, tmp_path: Path):
        # Create the target dir on FS so verification passes
        target = tmp_path / "THEORY" / "X"
        target.mkdir(parents=True)
        kg = MockKgClient(hubs=[KnowledgeHubRecord(name="hub-x")])
        ok = forward_orphan_scan.resolve_forward_orphan(
            kg=kg,
            hub_name="hub-x",
            package_path="THEORY/X/",
            source_file="THEORY/X/README.md",
            ruflo_grade="STRONG",
            fs_root=tmp_path,
        )
        assert ok is True
        stored = kg.hubs["hub-x"]
        assert stored.package_path == "THEORY/X/"
        assert stored.source_file == "THEORY/X/README.md"
        assert stored.ruflo_grade == "STRONG"

    def test_resolve_skips_if_path_does_not_exist(self, tmp_path: Path):
        kg = MockKgClient(hubs=[KnowledgeHubRecord(name="hub-y")])
        ok = forward_orphan_scan.resolve_forward_orphan(
            kg=kg,
            hub_name="hub-y",
            package_path="THEORY/Y/",  # missing on FS
            fs_root=tmp_path,
        )
        assert ok is False
        assert kg.hubs["hub-y"].package_path is None  # not written

    def test_resolve_without_fs_root_skips_check(self):
        kg = MockKgClient(hubs=[KnowledgeHubRecord(name="hub-z")])
        ok = forward_orphan_scan.resolve_forward_orphan(
            kg=kg,
            hub_name="hub-z",
            package_path="THEORY/Z/",
        )
        assert ok is True


class TestBulkResolve:
    def test_bulk_resolve_writes_all(self, tmp_path: Path):
        # Create dirs for all 7 Wave 6 canonical hubs (subset)
        subset = ["APT", "TPA", "LONGINUS"]
        for sub in subset:
            (tmp_path / "THEORY" / sub).mkdir(parents=True)
        kg = MockKgClient(
            hubs=[KnowledgeHubRecord(name=f"hub-{n.lower()}-methodology") for n in subset]
        )
        resolutions = {
            f"hub-{n.lower()}-methodology": {
                "package_path": f"THEORY/{n}/",
                "source_file": f"THEORY/{n}/README.md",
            }
            for n in subset
        }
        out = forward_orphan_scan.bulk_resolve(
            kg=kg,
            resolutions=resolutions,
            fs_root=tmp_path,
        )
        assert all(out.values())
        for n in subset:
            stored = kg.hubs[f"hub-{n.lower()}-methodology"]
            assert stored.package_path == f"THEORY/{n}/"

    def test_bulk_resolve_handles_missing_package_path(self):
        kg = MockKgClient(hubs=[KnowledgeHubRecord(name="hub-x")])
        out = forward_orphan_scan.bulk_resolve(
            kg=kg,
            resolutions={"hub-x": {"package_path": None}},
        )
        assert out["hub-x"] is False


class TestWave6Canon:
    def test_wave6_resolutions_has_7_hubs(self):
        # LONGINUS_BINDING.md Wave 6 §"Forward Orphan Resolved" → 7 hubs
        assert len(forward_orphan_scan.WAVE6_HUB_RESOLUTIONS) == 7
        names = set(forward_orphan_scan.WAVE6_HUB_RESOLUTIONS.keys())
        expected = {
            "hub-apt-methodology",
            "hub-tpa-methodology",
            "hub-jaebaeman-sop",
            "hub-taliban-immunity",
            "hub-prometheus-research",
            "hub-longinus-reference",
            "hub-harness-3tier",
        }
        assert names == expected

    def test_wave6_resolutions_all_have_package_path(self):
        for hub_name, fields in forward_orphan_scan.WAVE6_HUB_RESOLUTIONS.items():
            assert fields.get("package_path"), f"Wave 6 canon entry {hub_name} missing package_path"
            assert fields["package_path"].startswith("THEORY/"), (
                f"Wave 6 canon entry {hub_name} package_path should be THEORY/-prefixed"
            )
