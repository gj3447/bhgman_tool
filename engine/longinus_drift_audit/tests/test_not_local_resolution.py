"""NOT_LOCAL — repo-registry-anchored resolution + shared-KG multi-repo correctness.

A ReferenceSite whose repo is not checked out on THIS machine must resolve to NOT_LOCAL
(skipped), never FILE_MISSING/DRIFT — so a single-repo audit over a shared KG does not
false-flag another repo's sites. When the repo IS present but the file is gone, that is a
real MISSING (drift). Legacy sites (no repo anchor) keep using the heuristic resolver.
"""

from __future__ import annotations

import subprocess

import pytest

from engine.longinus_drift_audit.daemon import WatchConfig
from engine.longinus_drift_audit.kg_client import MockKgClient
from engine.longinus_drift_audit.models import ReferenceSite, Sha256Status
from engine.longinus_drift_audit.repo_registry import RepoRegistry
from engine.longinus_drift_audit.sha256_baseline import (
    init_baseline,
    resolve_site,
    verify_baseline,
)

UNREG = "example.com/acme/widget"  # an id that won't collide with the real checkout


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


def _repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "Test")
    return path


@pytest.fixture
def reg(tmp_path):
    return RepoRegistry(path=tmp_path / "reg.toml")


@pytest.fixture(autouse=True)
def _isolate_discovery(tmp_path, monkeypatch):
    """Confine registry auto-discovery to empty tmp dirs so an unregistered repo_id stays
    NOT_LOCAL (fast + deterministic; no scanning the real home/workspace)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("LONGINUS_HOME", str(tmp_path / "lh"))
    monkeypatch.delenv("CD_ROOT", raising=False)
    monkeypatch.delenv("LONGINUS_SEARCH_PATHS", raising=False)
    monkeypatch.chdir(home)


def _site(**kw):
    base = dict(sourceId="X.y", sourcePath="a.py:1")
    base.update(kw)
    return ReferenceSite(**base)


# ── resolve_site ──


def test_resolve_site_not_local_when_repo_unregistered(reg):
    res = resolve_site(_site(repo_id=UNREG, repo_relpath="a.py"), registry=reg)
    assert res.status == "NOT_LOCAL" and res.abs_path is None


def test_resolve_site_file_when_registered(reg, tmp_path):
    repo = _repo(tmp_path / "r")
    (repo / "a.py").write_text("x = 1\n")
    reg.register(UNREG, str(repo))
    res = resolve_site(_site(repo_id=UNREG, repo_relpath="a.py"), registry=reg)
    assert res.status == "FILE" and res.abs_path == str(repo / "a.py")


def test_resolve_site_missing_when_repo_present_but_file_gone(reg, tmp_path):
    repo = _repo(tmp_path / "r")
    reg.register(UNREG, str(repo))  # repo IS here, file is not -> real drift, not NOT_LOCAL
    res = resolve_site(_site(repo_id=UNREG, repo_relpath="gone.py"), registry=reg)
    assert res.status == "MISSING"


def test_resolve_site_legacy_fallback_without_repo_anchor(reg, tmp_path):
    f = tmp_path / "leg.py"
    f.write_text("x = 1\n")
    res = resolve_site(_site(sourcePath=f"{f}:1"), registry=reg)  # no repo_id -> heuristic
    assert res.status == "FILE" and res.abs_path == str(f)


# ── verify_baseline ──


def test_verify_baseline_not_local_is_not_drift(reg):
    kg = MockKgClient()
    site = _site(
        repo_id=UNREG,
        repo_relpath="a.py",
        sha256_baseline="deadbeef",
        sha256_status=Sha256Status.BASELINE,
    )
    res = verify_baseline(kg=kg, sites=[site], registry=reg)
    assert res.not_local == 1
    assert res.drift == 0 and res.missing == 0 and res.drift_events == []
    assert kg.sites[site.sourceId].sha256_status == Sha256Status.NOT_LOCAL


def test_verify_baseline_real_missing_still_drifts(reg, tmp_path):
    repo = _repo(tmp_path / "r")
    reg.register(UNREG, str(repo))
    kg = MockKgClient()
    site = _site(
        repo_id=UNREG,
        repo_relpath="gone.py",
        sha256_baseline="deadbeef",
        sha256_status=Sha256Status.BASELINE,
    )
    res = verify_baseline(kg=kg, sites=[site], registry=reg)
    assert res.missing == 1 and res.not_local == 0 and len(res.drift_events) == 1
    assert res.drift_events[0].kind == "FILE_MISSING"


# ── init_baseline ──


def test_init_baseline_not_local_is_skipped(reg):
    kg = MockKgClient()
    site = _site(repo_id=UNREG, repo_relpath="a.py")  # no baseline yet
    res = init_baseline(kg=kg, sites=[site], registry=reg)
    assert res.not_local == 1 and res.populated == 0
    assert kg.sites[site.sourceId].sha256_status == Sha256Status.NOT_LOCAL


# ── daemon watch.toml <-> registry fold-in ──


def test_daemon_watchconfig_from_registry(reg, tmp_path):
    repo = _repo(tmp_path / "d")
    reg.register(UNREG, str(repo))
    cfg = WatchConfig.from_registry(registry=reg)
    assert len(cfg.repos) == 1
    assert cfg.repos[0].alias == UNREG
    assert cfg.repos[0].path == repo.resolve()


def test_daemon_from_registry_skips_vanished_checkouts(reg, tmp_path):
    reg.register(UNREG, str(tmp_path / "not-there"))
    assert WatchConfig.from_registry(registry=reg).repos == ()
