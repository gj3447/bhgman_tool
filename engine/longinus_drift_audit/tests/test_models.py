from __future__ import annotations

import pytest

from engine.longinus_drift_audit.models import (
    AuditReport,
    DriftRecord,
    DriftType,
    ReferenceLayer,
    ReferenceSite,
)


class TestReferenceSite:
    def test_basic(self):
        rs = ReferenceSite(sourceId="lesson-foo-2026-05-12", sourcePath="src/foo.py:42")
        assert rs.file == "src/foo.py"
        assert rs.line_start == 42
        assert rs.line_end is None

    def test_range_path(self):
        rs = ReferenceSite(sourceId="lesson-x-2026", sourcePath="src/bar.py:100-150")
        assert rs.line_start == 100
        assert rs.line_end == 150

    def test_invalid_path_rejected(self):
        with pytest.raises(ValueError, match="sourcePath"):
            ReferenceSite(sourceId="lesson-x", sourcePath="path with spaces")

    def test_directory_path_accepted(self):
        rs = ReferenceSite(
            sourceId="ATOM_dir_07projects_apt_specs",
            sourcePath="07_PROJECTS/APT/specs",
        )
        assert rs.is_directory_path is True
        assert rs.file == "07_PROJECTS/APT/specs"
        with pytest.raises(ValueError, match="line_start undefined"):
            _ = rs.line_start
        with pytest.raises(ValueError, match="line_end undefined"):
            _ = rs.line_end

    def test_file_path_not_directory_shape(self):
        rs = ReferenceSite(sourceId="lesson-foo-2026", sourcePath="src/foo.py:42")
        assert rs.is_directory_path is False

    def test_module_dot_symbol(self):
        rs = ReferenceSite(sourceId="Prometheus.cycle_runner", sourcePath="x.py:1")
        assert rs.sourceId.startswith("Prometheus")

    def test_digit_leading_kg_name_accepted(self):
        # KG canonical names legitimately start with a digit — `longinus bind`
        # crashed on these before the validator was relaxed (2026-06-02).
        for sid in (
            "7cmd-measurement-driven-conditional-dispatch-2026-05-30",
            "88-taliban-mathematical-lens",
            "333q-demo-ghz",
        ):
            assert ReferenceSite(sourceId=sid, sourcePath="x.py:1").sourceId == sid

    def test_unicode_korean_kg_name_accepted(self):
        for sid in ("재배맨-v2-subagent-runtime-protocol", "나생문-canonical-2026-05-19"):
            assert ReferenceSite(sourceId=sid, sourcePath="x.py:1").sourceId == sid


class TestDriftRecord:
    def test_minimal(self):
        d = DriftRecord(
            drift_type=DriftType.MISSING,
            sourceId="x",
            layer_violated=ReferenceLayer.L5_DISTRIBUTED,
            lens_law_violated="PutGet",
        )
        assert d.drift_type == DriftType.MISSING
        assert d.detected_at  # ISO timestamp populated

    def test_all_drift_types(self):
        assert {d.value for d in DriftType} == {
            "Missing",
            "Orphan",
            "SigMismatch",
            "PatternDiv",
            "LabelRot",
            "DispatchDrift",
        }


class TestAuditReport:
    def test_clean_report(self):
        r = AuditReport(audit_id="a1")
        assert r.total_drifts == 0
        assert r.is_clean is True

    def test_with_drifts(self):
        r = AuditReport(audit_id="a1", drifts_by_type={"Missing": 3, "Orphan": 1})
        assert r.total_drifts == 4
        assert r.is_clean is False

    def test_reverse_orphan_breaks_clean(self):
        r = AuditReport(audit_id="a1", reverse_orphans=["x.py:1"])
        assert r.total_drifts == 0
        assert r.is_clean is False
