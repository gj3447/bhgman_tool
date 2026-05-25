"""E2E LonginusAudit — code root + KG refs → AuditReport."""

from __future__ import annotations

from pathlib import Path

import argparse

import pytest

from audit_runner import LonginusAudit, build_kg
from kg_client import MockKgClient, Neo4jKgClient
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

    def test_anchor_existing_as_non_referencesite_is_not_missing(self, tmp_path):
        # run_full now threads kg.has_node into detect_missing, so a # KG: anchor
        # that exists as a non-ReferenceSite node (here: other_nodes, i.e. a
        # :Lesson/:Span/:ATOM) is NOT false-flagged MISSING — the empirical gap
        # the mock path used to hide (Naesengmoon ensemble finding deeper refinement).
        _seed_code(tmp_path)  # a.py -> lesson-foo, b.py -> lesson-bar
        kg = MockKgClient(refs=[])  # neither is a ReferenceSite
        kg.other_nodes.update({"lesson-foo-2026-05-12", "lesson-bar-2026-05-12"})
        audit = LonginusAudit(kg=kg, code_root=tmp_path)
        report = audit.run_full()
        assert report.drifts_by_type.get("Missing", 0) == 0

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


class TestBuildKg:
    """build_kg backend selection — guards the Goodhart hole where the CLI
    silently defaulted to an empty-ref mock and the neo4j path was an
    unwired stub (Naesengmoon ensemble VR_bhgman_tool_ensemble_2026-05-25
    finding ac-bhgman-5f5a905-goodhart-self-audit-mock-zero-drift).
    """

    def test_mock_backend(self):
        ns = argparse.Namespace(kg="mock", uri=None, user="neo4j", password=None)
        assert isinstance(build_kg(ns), MockKgClient)

    def test_neo4j_without_creds_raises(self):
        ns = argparse.Namespace(kg="neo4j", uri=None, user="neo4j", password=None)
        with pytest.raises(ValueError, match="requires --uri/--password"):
            build_kg(ns)

    def test_neo4j_with_creds_constructs_real_client(self):
        # lazy driver: constructs without connecting
        ns = argparse.Namespace(kg="neo4j", uri="bolt://localhost:7687", user="neo4j", password="x")
        kg = build_kg(ns)
        try:
            assert isinstance(kg, Neo4jKgClient)
        finally:
            kg.close()
