"""migrate-repo-ids — backfill git anchoring onto pre-anchoring ReferenceSites."""
from __future__ import annotations

import subprocess

import pytest

from engine.longinus_drift_audit.kg_client import MockKgClient
from engine.longinus_drift_audit.migrate_repo_ids import migrate
from engine.longinus_drift_audit.models import ReferenceSite, Sha256Status
from engine.longinus_drift_audit.repo_registry import RepoRegistry


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


def _repo(path, remote="git@example.com:acme/widget.git"):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "Test")
    _git(path, "remote", "add", "origin", remote)
    _git(path, "commit", "-q", "--allow-empty", "-m", "init")  # HEAD exists -> commit resolvable
    return path


@pytest.fixture
def reg(tmp_path):
    return RepoRegistry(path=tmp_path / "reg.toml")


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("LONGINUS_HOME", str(tmp_path / "lh"))
    monkeypatch.delenv("CD_ROOT", raising=False)
    monkeypatch.delenv("LONGINUS_SEARCH_PATHS", raising=False)
    monkeypatch.chdir(home)


def test_migrates_legacy_site_to_full_anchor(reg, tmp_path):
    repo = _repo(tmp_path / "r")
    (repo / "a.py").write_text("def f():\n    log('x')\n")
    kg = MockKgClient()
    # legacy site: repo-relative sourcePath, no repo_id / repo_relpath / blob baseline
    kg.merge_reference_site_state(ReferenceSite(
        sourceId="X.f", sourcePath="a.py:1", repo_tag="widget",
        sha256_baseline="oldsha", sha256_status=Sha256Status.BASELINE))

    res = migrate(kg, registry=reg, base_chain=(str(repo),))
    assert res.migrated == 1 and res.already == 0 and res.unresolved == 0

    site = kg.sites["X.f"]
    assert site.repo_id == "example.com/acme/widget"
    assert site.repo_relpath == "a.py"
    assert site.blob_oid and site.blob_oid_baseline == site.blob_oid  # baseline recomputed
    assert site.commit
    # repo auto-registered for future direct resolution
    assert reg.resolve("example.com/acme/widget") == repo


def test_idempotent_skips_already_anchored(reg, tmp_path):
    repo = _repo(tmp_path / "r")
    (repo / "a.py").write_text("x = 1\n")
    kg = MockKgClient()
    kg.merge_reference_site_state(ReferenceSite(
        sourceId="X.f", sourcePath="a.py:1",
        repo_id="example.com/acme/widget", repo_relpath="a.py",
        blob_oid="abc", blob_oid_baseline="abc"))
    res = migrate(kg, registry=reg, base_chain=(str(repo),))
    assert res.already == 1 and res.migrated == 0


def test_dry_run_does_not_mutate(reg, tmp_path):
    repo = _repo(tmp_path / "r")
    (repo / "a.py").write_text("x = 1\n")
    kg = MockKgClient()
    kg.merge_reference_site_state(ReferenceSite(
        sourceId="X.f", sourcePath="a.py:1", repo_tag="widget"))
    res = migrate(kg, registry=reg, base_chain=(str(repo),), dry_run=True)
    assert res.migrated == 1                       # would migrate
    assert kg.sites["X.f"].repo_id is None         # but nothing written
    assert reg.resolve("example.com/acme/widget") is None


def test_unresolvable_site_tagged_from_learned_map(reg, tmp_path):
    repo = _repo(tmp_path / "r")
    (repo / "a.py").write_text("x = 1\n")
    kg = MockKgClient()
    # one resolvable site teaches widget -> example.com/acme/widget
    kg.merge_reference_site_state(ReferenceSite(
        sourceId="X.f", sourcePath="a.py:1", repo_tag="widget"))
    # one site whose file is NOT on disk, same repo_tag
    kg.merge_reference_site_state(ReferenceSite(
        sourceId="X.g", sourcePath="missing.py:9", repo_tag="widget"))

    res = migrate(kg, registry=reg, base_chain=(str(repo),))
    assert res.migrated == 1 and res.tagged_only == 1 and res.unresolved == 0
    g = kg.sites["X.g"]
    assert g.repo_id == "example.com/acme/widget"   # scoped via tag map
    assert g.repo_relpath == "missing.py"           # best-effort from sourcePath
    assert g.blob_oid_baseline is None              # no disk file here -> no baseline


def test_unresolvable_no_tag_left_untouched(reg, tmp_path):
    kg = MockKgClient()
    kg.merge_reference_site_state(ReferenceSite(
        sourceId="X.h", sourcePath="nowhere.py:1"))  # not on disk, no repo_tag
    res = migrate(kg, registry=reg, base_chain=(str(tmp_path / "empty"),))
    assert res.unresolved == 1 and res.migrated == 0 and res.tagged_only == 0
    assert kg.sites["X.h"].repo_id is None
