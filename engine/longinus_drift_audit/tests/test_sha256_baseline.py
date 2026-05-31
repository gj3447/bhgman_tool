"""Tests for sha256 baseline init / verify — Longinus Wave 6 (2026-05-14)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from engine.longinus_drift_audit import sha256_baseline
from engine.longinus_drift_audit.kg_client import MockKgClient
from engine.longinus_drift_audit.models import ReferenceLayer, ReferenceSite, Sha256Status


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Build a tiny repo layout with one watched file."""
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "module.py").write_text("def hello():\n    return 42\n")
    return tmp_path


class TestResolvePath:
    def test_resolve_absolute_file(self, tmp_repo: Path):
        target = tmp_repo / "subdir" / "module.py"
        res = sha256_baseline.resolve_path(str(target))
        assert res.status == "FILE"
        assert res.abs_path is not None
        assert Path(res.abs_path).exists()

    def test_resolve_strips_line_suffix(self, tmp_repo: Path):
        target = tmp_repo / "subdir" / "module.py"
        res = sha256_baseline.resolve_path(f"{target}:1-3")
        assert res.status == "FILE"

    def test_resolve_directory(self, tmp_repo: Path):
        res = sha256_baseline.resolve_path(str(tmp_repo / "subdir"))
        assert res.status == "DIRECTORY"

    def test_resolve_missing(self, tmp_repo: Path):
        res = sha256_baseline.resolve_path(
            str(tmp_repo / "does_not_exist.py"),
            base_chain=(str(tmp_repo),),
        )
        assert res.status == "MISSING"
        assert res.abs_path is None

    def test_resolve_relative_via_chain(self, tmp_repo: Path):
        res = sha256_baseline.resolve_path(
            "subdir/module.py",
            base_chain=(str(tmp_repo),),
        )
        assert res.status == "FILE"


class TestInitBaseline:
    def test_init_populates_baseline_for_file(self, tmp_repo: Path):
        target = tmp_repo / "subdir" / "module.py"
        expected_sha = hashlib.sha256(target.read_bytes()).hexdigest()
        site = ReferenceSite(
            sourceId="rs.test-site",
            sourcePath=f"{target}:1-3",
            kg_anchor="lesson-test-2026-05-14",
            layer=ReferenceLayer.L4_SEMIOTIC,
        )
        kg = MockKgClient()
        result = sha256_baseline.init_baseline(kg=kg, sites=[site])
        assert result.populated == 1
        assert result.directory_skip == 0
        assert result.missing == 0
        # Mock KG should now have the site with sha256 set
        stored = kg.sites[site.sourceId]
        assert stored.sha256 == expected_sha
        assert stored.sha256_baseline == expected_sha
        assert stored.sha256_status == Sha256Status.BASELINE

    def test_init_idempotent_when_baseline_already_set(self, tmp_repo: Path):
        target = tmp_repo / "subdir" / "module.py"
        prior_sha = "deadbeef" * 8
        site = ReferenceSite(
            sourceId="rs.already-set",
            sourcePath=f"{target}:1",
            sha256_baseline=prior_sha,
            sha256_status=Sha256Status.BASELINE,
        )
        kg = MockKgClient()
        result = sha256_baseline.init_baseline(kg=kg, sites=[site])
        # Existing baseline preserved — re-init is no-op for sites with baseline
        assert result.populated == 0

    def test_init_marks_missing(self, tmp_repo: Path):
        site = ReferenceSite(
            sourceId="rs.missing",
            sourcePath=f"{tmp_repo}/never_existed.py:1",
        )
        kg = MockKgClient()
        result = sha256_baseline.init_baseline(
            kg=kg,
            sites=[site],
            base_chain=(str(tmp_repo),),
        )
        assert result.missing == 1
        assert kg.sites[site.sourceId].sha256_status == Sha256Status.FILE_MISSING

    def test_init_marks_directory_skip(self, tmp_repo: Path):
        site = ReferenceSite(
            sourceId="rs.dir",
            sourcePath=f"{tmp_repo}/subdir:1",
        )
        kg = MockKgClient()
        result = sha256_baseline.init_baseline(kg=kg, sites=[site])
        assert result.directory_skip == 1
        assert kg.sites[site.sourceId].sha256_status == Sha256Status.DIRECTORY_SKIP


class TestVerifyBaseline:
    def _seed(self, tmp_repo: Path, kg: MockKgClient):
        target = tmp_repo / "subdir" / "module.py"
        site = ReferenceSite(
            sourceId="rs.verify",
            sourcePath=f"{target}:1-3",
        )
        sha256_baseline.init_baseline(kg=kg, sites=[site])
        return target, kg.sites[site.sourceId]

    def test_verify_clean(self, tmp_repo: Path):
        kg = MockKgClient()
        target, site = self._seed(tmp_repo, kg)
        # Re-fetch the freshly baselined site
        sites = kg.list_reference_site_states()
        result = sha256_baseline.verify_baseline(kg=kg, sites=sites)
        assert result.ok == 1
        assert result.drift == 0
        assert kg.sites[site.sourceId].sha256_status == Sha256Status.VERIFIED

    def test_verify_detects_drift(self, tmp_repo: Path):
        kg = MockKgClient()
        target, site = self._seed(tmp_repo, kg)
        # Mutate the file → drift
        target.write_text("def hello():\n    return 99  # changed\n")
        sites = kg.list_reference_site_states()
        result = sha256_baseline.verify_baseline(kg=kg, sites=sites)
        assert result.drift == 1
        assert result.ok == 0
        assert len(result.drift_events) == 1
        assert result.drift_events[0].kind == "SHA256_MISMATCH"
        assert kg.sites[site.sourceId].sha256_status == Sha256Status.DRIFT
        # Drift event was emitted into KG
        assert len(kg.drift_events) == 1

    def test_verify_detects_file_deletion(self, tmp_repo: Path):
        kg = MockKgClient()
        target, site = self._seed(tmp_repo, kg)
        target.unlink()
        sites = kg.list_reference_site_states()
        result = sha256_baseline.verify_baseline(kg=kg, sites=sites)
        assert result.missing == 1
        assert result.drift_events[0].kind == "FILE_MISSING"
        assert kg.sites[site.sourceId].sha256_status == Sha256Status.FILE_MISSING

    def test_verify_skips_when_no_baseline(self, tmp_repo: Path):
        kg = MockKgClient()
        site = ReferenceSite(
            sourceId="rs.no-baseline",
            sourcePath=f"{tmp_repo}/subdir/module.py:1",
        )
        kg.merge_reference_site_state(site)
        result = sha256_baseline.verify_baseline(
            kg=kg,
            sites=kg.list_reference_site_states(),
        )
        assert result.skipped_baseline == 1

    def test_verify_skips_directory(self, tmp_repo: Path):
        kg = MockKgClient()
        site = ReferenceSite(
            sourceId="rs.dir-skip",
            sourcePath=f"{tmp_repo}/subdir:1",
            sha256_status=Sha256Status.DIRECTORY_SKIP,
        )
        kg.merge_reference_site_state(site)
        result = sha256_baseline.verify_baseline(
            kg=kg,
            sites=kg.list_reference_site_states(),
        )
        assert result.skipped_dir == 1


class TestMakeReferenceSite7Tuple:
    def test_factory_builds_baseline_state(self):
        site = sha256_baseline.make_reference_site_7tuple(
            sourceId="rs.factory",
            sourcePath="x.py:1-3",
            sha256_baseline="abc" * 21 + "x",  # 64 chars (mock)
            kg_anchor="lesson-foo-2026-05-14",
            layer=ReferenceLayer.L7_AESTHETIC,
        )
        assert site.sha256_status == Sha256Status.BASELINE
        assert site.sha256 == site.sha256_baseline
        assert site.layer == ReferenceLayer.L7_AESTHETIC
        assert site.kg_anchor == "lesson-foo-2026-05-14"
        assert site.last_validated is not None
