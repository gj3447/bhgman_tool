"""Repo identity — the portable, machine-independent key a Longinus binding is anchored to.

A binding must address code without an absolute path so the *same* anchor resolves on any
clone, on any machine. The "what" lives here (repo identity + repo-relative path + git
content hash); the "where on this box" lives in :mod:`repo_registry`.

repo_id resolution is layered, first hit wins — so identity survives forks/renames yet
still works for remote-less local repos:

  1. ``.longinus/repo.toml`` at the git toplevel  ->  its ``id = "..."``  (explicit, canonical)
  2. the ``origin`` remote URL, normalized        ->  ``github.com/<owner>/<repo>``
  3. the root-commit SHA                           ->  ``rootcommit:<sha>``  (no remote needed)

All git calls are best-effort: outside a work tree, or with git absent, the functions
return ``None`` and callers fall back to the legacy path resolver (offline invariant).

# KG: ATOM_Skill_longinus
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Optional


def _git(args: list[str], cwd: str) -> Optional[str]:
    """Run ``git <args>`` in ``cwd``; stripped stdout or ``None`` on any failure."""
    try:
        out = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def git_toplevel(start: str) -> Optional[str]:
    """Repo root containing ``start`` (``git rev-parse --show-toplevel``)."""
    d = start if os.path.isdir(start) else (os.path.dirname(start) or ".")
    return _git(["rev-parse", "--show-toplevel"], d)


def normalize_remote(url: Optional[str]) -> Optional[str]:
    """Normalize a git remote URL to ``host/owner/repo`` (scheme, user, port, ``.git`` stripped).

    Handles https/http/ssh URLs and scp-like ``git@host:owner/repo.git`` forms so the same
    repo gets one identity regardless of how it was cloned.
    """
    if not url:
        return None
    u = url.strip()
    # scp-like: git@host:owner/repo(.git)
    m = re.match(r"^[\w.+-]+@([^:/]+):(.+)$", u)
    if m:
        host, path = m.group(1), m.group(2)
    else:
        # scheme://[user@]host[:port]/owner/repo(.git)
        m = re.match(r"^[a-zA-Z][\w+.-]*://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$", u)
        if not m:
            return None
        host, path = m.group(1), m.group(2)
    path = re.sub(r"\.git$", "", path).strip("/")
    if not path:
        return None
    return f"{host.lower()}/{path}"


_REPO_TOML_ID = re.compile(r"""^\s*id\s*=\s*["']([^"']+)["']""", re.MULTILINE)


def _read_repo_toml_id(toplevel: str) -> Optional[str]:
    """Explicit ``id = "..."`` from ``<toplevel>/.longinus/repo.toml`` if present."""
    p = Path(toplevel) / ".longinus" / "repo.toml"
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _REPO_TOML_ID.search(text)
    return m.group(1).strip() if m else None


def root_commit(toplevel: str) -> Optional[str]:
    """The repository's root commit SHA — stable across clones, no remote required."""
    out = _git(["rev-list", "--max-parents=0", "HEAD"], toplevel)
    if not out:
        return None
    # A repo can have multiple root commits (merged histories); take the last (oldest line)
    # for determinism.
    return out.splitlines()[-1].strip()


def repo_id_for(path: str) -> Optional[str]:
    """The portable repo identity for the repo containing ``path`` (layered resolution).

    Returns ``None`` if ``path`` is not inside a git work tree (git absent or no repo).
    """
    top = git_toplevel(path)
    if top is None:
        return None
    explicit = _read_repo_toml_id(top)
    if explicit:
        return explicit
    remote = normalize_remote(_git(["config", "--get", "remote.origin.url"], top))
    if remote:
        return remote
    rc = root_commit(top)
    return f"rootcommit:{rc}" if rc else None


def git_identity(abs_path: str) -> dict:
    """Best-effort git anchoring for ``abs_path``.

    Returns ``{toplevel, repo_id, commit, blob_oid, remote, repo_relpath}`` — each ``None``
    when the file is not inside a git work tree. ``repo_relpath`` is POSIX (forward slashes)
    so it is identical across operating systems. ``blob_oid`` is the working-tree content
    hash (``git hash-object``) — the content-addressed, machine-independent drift signal.
    """
    out: dict[str, str | None] = {
        "toplevel": None,
        "repo_id": None,
        "commit": None,
        "blob_oid": None,
        "remote": None,
        "repo_relpath": None,
    }
    top = git_toplevel(abs_path)
    if top is None:
        return out
    out["toplevel"] = top
    out["repo_id"] = repo_id_for(abs_path)
    out["commit"] = _git(["rev-parse", "HEAD"], top)
    out["blob_oid"] = _git(["hash-object", abs_path], top)
    out["remote"] = _git(["config", "--get", "remote.origin.url"], top)
    try:
        out["repo_relpath"] = Path(os.path.relpath(abs_path, top)).as_posix()
    except ValueError:  # different drive on Windows
        out["repo_relpath"] = None
    return out
