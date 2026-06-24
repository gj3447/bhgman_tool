"""Machine-local repo location registry — the "where on this box" half of Longinus.

A binding addresses code portably by ``repo_id`` (see :mod:`repo_identity`); this registry
answers the hardware-specific question *"where is repo_id checked out on THIS machine?"*.
It is deliberately **not** stored inside any git repo — it is per-hardware state, so it
lives at (first that applies):

  1. ``$LONGINUS_HOME/repos.toml``
  2. ``$XDG_CONFIG_HOME/longinus/repos.toml``
  3. ``~/.config/longinus/repos.toml``

File schema (minimal array-of-tables; no external TOML dep, matching daemon.py)::

    [[repo]]
    id     = "github.com/gj3447/bhgman_tool"
    path   = "/data/kjra/PROJECT/PI/bhgman_tool"
    remote = "https://github.com/gj3447/bhgman_tool.git"

Resolution: ``locate(repo_id, repo_relpath)`` = ``resolve(repo_id) / repo_relpath``. On a
miss it tries auto-discovery (CWD + search paths), registering what it finds (with a log
line); only if that also fails does it raise :class:`NotRegistered` — an actionable error,
never a silently-wrong file.

# KG: ATOM_Skill_longinus
"""

from __future__ import annotations

import builtins
import logging
import os
from pathlib import Path
from typing import Optional

from engine.longinus_drift_audit.repo_identity import (
    git_toplevel,
    repo_id_for,
    _git,
)

logger = logging.getLogger(__name__)


class NotRegistered(Exception):
    """``repo_id`` has no location on this machine and could not be discovered."""

    def __init__(self, repo_id: str):
        super().__init__(
            f"repo {repo_id!r} is not registered on this machine and was not found by "
            f"discovery — register it with:  python -m engine.longinus_drift_audit.repo_cli "
            f"register {repo_id!r} <local_path>"
        )
        self.repo_id = repo_id


def registry_path() -> Path:
    """Location of the per-machine registry file (env-overridable; never inside a repo)."""
    home = os.environ.get("LONGINUS_HOME")
    if home:
        return Path(home).expanduser() / "repos.toml"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "longinus" / "repos.toml"


# ── minimal TOML array-of-tables read/write (no external dep) ───────────────


def _parse_repos_toml(text: str) -> dict[str, dict]:
    """Parse ``[[repo]]`` tables into ``{id: {path, remote}}``. Tolerant of comments/blanks."""
    out: dict[str, dict] = {}
    cur: dict[str, str] = {}
    in_section = False

    def _flush():
        if in_section and cur.get("id"):
            out[cur["id"]] = {"path": cur.get("path", ""), "remote": cur.get("remote")}

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[[repo]]":
            _flush()
            cur = {}
            in_section = True
            continue
        if in_section and "=" in line:
            key, _, val = line.partition("=")
            cur[key.strip()] = val.strip().strip('"').strip("'")
    _flush()
    return out


def _dump_repos_toml(entries: dict[str, dict]) -> str:
    lines = [
        "# Longinus machine-local repo registry — per-hardware, do NOT commit.",
        "# Maps a portable repo_id to where that repo is checked out on THIS machine.",
        "",
    ]
    for repo_id, e in sorted(entries.items()):
        lines.append("[[repo]]")
        lines.append(f'id   = "{repo_id}"')
        lines.append(f'path = "{e.get("path", "")}"')
        if e.get("remote"):
            lines.append(f'remote = "{e["remote"]}"')
        lines.append("")
    return "\n".join(lines)


class RepoRegistry:
    """Read/write view over the machine-local registry file."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else registry_path()

    # ── persistence ──
    def _load(self) -> dict[str, dict]:
        try:
            return _parse_repos_toml(self.path.read_text(encoding="utf-8"))
        except OSError:
            return {}

    def _save(self, entries: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(_dump_repos_toml(entries), encoding="utf-8")

    # ── queries / mutations ──
    def list(self) -> dict[str, dict]:
        return self._load()

    def resolve(self, repo_id: str) -> Optional[Path]:
        """Local checkout path for ``repo_id`` if registered AND still on disk, else ``None``."""
        e = self._load().get(repo_id)
        if not e or not e.get("path"):
            return None
        p = Path(e["path"]).expanduser()
        return p if p.is_dir() else None

    def register(
        self, repo_id: str, path: str, remote: Optional[str] = None, *, log: bool = True
    ) -> None:
        entries = self._load()
        entries[repo_id] = {"path": str(Path(path).expanduser().resolve()), "remote": remote}
        self._save(entries)
        if log:
            logger.info("longinus: registered repo %s -> %s", repo_id, entries[repo_id]["path"])

    def discover(self, start: str) -> Optional[tuple[str, Path]]:
        """If ``start`` is inside a git repo, derive its repo_id, auto-register it, and return
        ``(repo_id, toplevel)``. ``None`` if ``start`` is not in a work tree."""
        top = git_toplevel(start)
        if top is None:
            return None
        rid = repo_id_for(start)
        if rid is None:
            return None
        remote = _git(["config", "--get", "remote.origin.url"], top)  # raw URL, for reference
        self.register(rid, top, remote=remote)
        return rid, Path(top)

    def discover_for(
        self, repo_id: str, search_paths: Optional[builtins.list[str]] = None
    ) -> Optional[Path]:
        """Hunt for ``repo_id`` without it being pre-registered: check the CWD's repo, then
        the immediate children of each search root ($LONGINUS_SEARCH_PATHS, $CD_ROOT, ~,
        CWD and its parent). Registers + returns the first match."""
        # 1) CWD's own repo
        hit = self.discover(os.getcwd())
        if hit and hit[0] == repo_id:
            return hit[1]
        # 2) one level under candidate roots
        roots: list[str] = []
        env = os.environ.get("LONGINUS_SEARCH_PATHS")
        if env:
            roots += [p for p in env.split(os.pathsep) if p]
        if os.environ.get("CD_ROOT"):
            roots.append(os.environ["CD_ROOT"])
        roots += [os.getcwd(), os.path.dirname(os.getcwd()), os.path.expanduser("~")]
        if search_paths:
            roots = list(search_paths) + roots
        seen: set[str] = set()
        for root in roots:
            ar = os.path.abspath(os.path.expanduser(root))
            if ar in seen or not os.path.isdir(ar):
                continue
            seen.add(ar)
            try:
                children = sorted(os.scandir(ar), key=lambda d: d.name)
            except OSError:
                continue
            for child in children:
                if not child.is_dir():
                    continue
                if repo_id_for(child.path) == repo_id:
                    remote = _git(["config", "--get", "remote.origin.url"], child.path)
                    top = git_toplevel(child.path) or child.path
                    self.register(repo_id, top, remote=remote)
                    return Path(top)
        return None

    def locate(self, repo_id: str, repo_relpath: str) -> Path:
        """Absolute path of ``repo_relpath`` within ``repo_id`` on this machine.

        ``resolve`` -> ``discover_for`` -> :class:`NotRegistered`. Never guesses a wrong file.
        """
        root = self.resolve(repo_id) or self.discover_for(repo_id)
        if root is None:
            raise NotRegistered(repo_id)
        return root / repo_relpath


_DEFAULT: Optional[RepoRegistry] = None


def default_registry() -> RepoRegistry:
    """Process-wide registry at the env-resolved path. (Recomputed if the env changes by
    constructing :class:`RepoRegistry` directly.)"""
    global _DEFAULT
    if _DEFAULT is None or _DEFAULT.path != registry_path():
        _DEFAULT = RepoRegistry()
    return _DEFAULT


def locate_site(site, *, registry: Optional[RepoRegistry] = None) -> Path:
    """Resolve a :class:`ReferenceSite` (or any object with ``repo_id``/``repo_relpath``,
    falling back to ``sourcePath``) to an absolute path on this machine.

    Registry-first (the new portable path); legacy base-chain fallback for sites recorded
    before repo anchoring so old data keeps resolving.
    """
    reg = registry or default_registry()
    repo_id = getattr(site, "repo_id", None)
    repo_relpath = getattr(site, "repo_relpath", None)
    if repo_id and repo_relpath:
        return reg.locate(repo_id, repo_relpath)
    # Legacy: no repo anchor — fall back to the heuristic resolver over sourcePath's file.
    from engine.longinus_drift_audit.sha256_baseline import resolve_path

    bare = getattr(site, "file", None) or str(getattr(site, "sourcePath", "")).split(":", 1)[0]
    res = resolve_path(bare)
    if res.abs_path:
        return Path(res.abs_path)
    raise NotRegistered(repo_id or f"<legacy:{bare}>")
