"""repo_registry — machine-local repo location store + portable resolution."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from engine.longinus_drift_audit.repo_registry import (
    NotRegistered,
    RepoRegistry,
    locate_site,
    registry_path,
)


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


def _init(tmp_path, remote=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    if remote:
        _git(tmp_path, "remote", "add", "origin", remote)
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


@pytest.fixture
def reg(tmp_path):
    return RepoRegistry(path=tmp_path / "reg" / "repos.toml")


def test_registry_path_honours_longinus_home(monkeypatch, tmp_path):
    monkeypatch.setenv("LONGINUS_HOME", str(tmp_path))
    assert registry_path() == tmp_path / "repos.toml"


def test_registry_path_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv("LONGINUS_HOME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert registry_path() == tmp_path / "longinus" / "repos.toml"


def test_register_resolve_roundtrip(reg, tmp_path):
    repo = _init(tmp_path / "myrepo")
    reg.register("github.com/o/r", str(repo))
    assert reg.resolve("github.com/o/r") == repo
    # survives a fresh instance reading the same file (real persistence)
    assert RepoRegistry(path=reg.path).resolve("github.com/o/r") == repo


def test_resolve_none_when_path_gone(reg, tmp_path):
    reg.register("github.com/o/gone", str(tmp_path / "does-not-exist"))
    assert reg.resolve("github.com/o/gone") is None


def test_discover_auto_registers(reg, tmp_path):
    repo = _init(tmp_path / "proj", remote="https://github.com/o/r.git")
    rid, top = reg.discover(str(repo))
    assert rid == "github.com/o/r" and top == repo
    assert reg.resolve("github.com/o/r") == repo  # persisted by discover


def test_discover_for_finds_under_search_path(reg, tmp_path, monkeypatch):
    # A repo_id that won't collide with the real checkout these tests run inside (else
    # discover_for would correctly match the CWD's own repo first).
    workspace = tmp_path / "ws"
    workspace.mkdir()
    repo = _init(workspace / "proj", remote="git@example.com:acme/widget.git")
    monkeypatch.setenv("LONGINUS_SEARCH_PATHS", str(workspace))
    found = reg.discover_for("example.com/acme/widget")
    assert found == repo
    assert reg.resolve("example.com/acme/widget") == repo


def test_locate_joins_relpath(reg, tmp_path):
    repo = _init(tmp_path / "r")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "b.py").write_text("y = 2\n")
    reg.register("github.com/o/r", str(repo))
    assert reg.locate("github.com/o/r", "pkg/b.py") == repo / "pkg" / "b.py"


def test_locate_raises_not_registered(reg):
    with pytest.raises(NotRegistered) as ei:
        reg.locate("github.com/o/missing", "a.py")
    assert "missing" in str(ei.value) and "register" in str(ei.value)


def test_locate_site_uses_repo_id(reg, tmp_path):
    repo = _init(tmp_path / "r")
    reg.register("github.com/o/r", str(repo))
    site = SimpleNamespace(repo_id="github.com/o/r", repo_relpath="a.py", sourcePath="a.py:1")
    assert locate_site(site, registry=reg) == repo / "a.py"
