"""repo_identity — portable, machine-independent repo anchoring."""

from __future__ import annotations

import subprocess

import pytest

from engine.longinus_drift_audit.repo_identity import (
    git_identity,
    normalize_remote,
    repo_id_for,
    root_commit,
)


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


def _init(tmp_path, remote=None):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    if remote:
        _git(tmp_path, "remote", "add", "origin", remote)
    (tmp_path / "a.py").write_text('def f():\n    log("x")\n')
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/gj3447/bhgman_tool.git", "github.com/gj3447/bhgman_tool"),
        ("http://github.com/gj3447/bhgman_tool", "github.com/gj3447/bhgman_tool"),
        ("git@github.com:gj3447/bhgman_tool.git", "github.com/gj3447/bhgman_tool"),
        ("ssh://git@github.com:2222/gj3447/bhgman_tool.git", "github.com/gj3447/bhgman_tool"),
        ("https://GitHub.com/O/R.git", "github.com/O/R"),
        ("not a url", None),
        (None, None),
    ],
)
def test_normalize_remote(url, expected):
    assert normalize_remote(url) == expected


def test_repo_id_prefers_explicit_repo_toml(tmp_path):
    repo = _init(tmp_path, remote="https://github.com/o/r.git")
    (repo / ".longinus").mkdir()
    (repo / ".longinus" / "repo.toml").write_text('id = "canonical/explicit-id"\n')
    assert repo_id_for(str(repo / "a.py")) == "canonical/explicit-id"


def test_repo_id_falls_back_to_remote(tmp_path):
    repo = _init(tmp_path, remote="git@github.com:o/r.git")
    assert repo_id_for(str(repo)) == "github.com/o/r"


def test_repo_id_falls_back_to_root_commit_when_no_remote(tmp_path):
    repo = _init(tmp_path)  # no remote
    rid = repo_id_for(str(repo))
    assert rid == f"rootcommit:{root_commit(str(repo))}"
    assert rid.startswith("rootcommit:") and len(rid) > len("rootcommit:")


def test_repo_id_none_outside_git(tmp_path):
    assert repo_id_for(str(tmp_path)) is None


def test_git_identity_full(tmp_path):
    repo = _init(tmp_path, remote="https://github.com/o/r.git")
    ident = git_identity(str(repo / "a.py"))
    assert ident["repo_id"] == "github.com/o/r"
    assert ident["repo_relpath"] == "a.py"
    assert ident["commit"] and len(ident["commit"]) == 40
    assert ident["blob_oid"] and len(ident["blob_oid"]) == 40
    assert ident["toplevel"]


def test_git_identity_repo_relpath_is_posix(tmp_path):
    repo = _init(tmp_path)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "b.py").write_text("x = 1\n")
    ident = git_identity(str(repo / "pkg" / "b.py"))
    assert ident["repo_relpath"] == "pkg/b.py"  # forward slash regardless of OS


def test_git_identity_all_none_outside_git(tmp_path):
    ident = git_identity(str(tmp_path / "nope.py"))
    assert all(v is None for v in ident.values())
