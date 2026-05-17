"""E2E LonginusAudit — code root + KG refs → AuditReport."""

from __future__ import annotations

from pathlib import Path

from audit_runner import LonginusAudit
from kg_client import MockKgClient
from models import KgRefRecord


def _seed_code(tmp: Path) -> None:
    (tmp / "a.py").write_text("def foo(x):  # KG: lesson-foo-2026-05-12\n    pass\n")
    (tmp / "b.py").write_text("def bar(y):  # KG: lesson-bar-2026-05-12\n    return y\n")
    (tmp / "c.py").write_text("def baz(): pass\n")  # no KG ref → reverse orphan


class TestE2E:
    def test_clean_audit_zero_drift(self, tmp_path):
        _seed_code(tmp_path)
        kg = MockKgClient(
            refs=[
                KgRefRecord(sourceId="lesson-foo-2026-05-12", sourcePath="a.py:1"),
                KgRefRecord(sourceId="lesson-bar-2026-05-12", sourcePath="b.py:1"),
            ]
        )
        audit = LonginusAudit(kg=kg, code_root=tmp_path)
        report = audit.run_full()
        # Missing/Orphan/SigMismatch/LabelRot 모두 0
        assert report.drifts_by_type.get("Missing", 0) == 0
        assert report.drifts_by_type.get("Orphan", 0) == 0
        # baz()는 reverse orphan
        assert len(report.reverse_orphans) == 1
        assert any("c.py" in p for p in report.reverse_orphans)

    def test_missing_drift_detected(self, tmp_path):
        _seed_code(tmp_path)
        # KG has only foo, not bar → bar 의 ref 는 MISSING
        kg = MockKgClient(
            refs=[
                KgRefRecord(sourceId="lesson-foo-2026-05-12", sourcePath="a.py:1"),
            ]
        )
        audit = LonginusAudit(kg=kg, code_root=tmp_path)
        report = audit.run_full()
        assert report.drifts_by_type.get("Missing", 0) >= 1

    def test_orphan_drift_detected(self, tmp_path):
        _seed_code(tmp_path)
        kg = MockKgClient(
            refs=[
                KgRefRecord(sourceId="lesson-foo-2026-05-12", sourcePath="a.py:1"),
                KgRefRecord(sourceId="lesson-bar-2026-05-12", sourcePath="b.py:1"),
                KgRefRecord(sourceId="lesson-orphan-no-code", sourcePath="??:0"),
            ]
        )
        audit = LonginusAudit(kg=kg, code_root=tmp_path)
        report = audit.run_full()
        assert report.drifts_by_type.get("Orphan", 0) >= 1

    def test_lens_verification_clean(self, tmp_path):
        _seed_code(tmp_path)
        kg = MockKgClient(refs=[])
        audit = LonginusAudit(kg=kg, code_root=tmp_path)
        report = audit.run_full()
        # internal dict lens always satisfies 3 laws
        assert report.lens_verification.get_put is True
        assert report.lens_verification.put_get is True
        assert report.lens_verification.put_put is True

    def test_ged_perfect_when_aligned(self, tmp_path):
        _seed_code(tmp_path)
        # Use fully qualified path to match scanner output exactly
        kg = MockKgClient(
            refs=[
                KgRefRecord(sourceId="lesson-foo-2026-05-12", sourcePath=f"{tmp_path}/a.py:1"),
                KgRefRecord(sourceId="lesson-bar-2026-05-12", sourcePath=f"{tmp_path}/b.py:1"),
            ]
        )
        audit = LonginusAudit(kg=kg, code_root=tmp_path)
        report = audit.run_full()
        assert report.ged_report is not None
        # paths match exactly → 0 insertions/deletions/relabels
        assert report.ged_report.insertions == 0
        assert report.ged_report.deletions == 0
        assert report.ged_report.relabels == 0
