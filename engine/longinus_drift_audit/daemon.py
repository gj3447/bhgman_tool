"""Longinus drift detection daemon — multi-repo watch with health check + auto-restart.

Pattern absorbed from code-review-graph (tirth8205) crg-daemon (2026-05-13).
KG: longinus-drift-daemon-pattern-2026-05-13 (:DaemonPattern:Canonical)

Architecture:
    Parent daemon process
      ├── reads TOML config (watch.toml)
      ├── spawns one child WatcherProcess per registered repo
      ├── health-checks children every 30s (configurable)
      ├── auto-restarts dead children
      └── reloads on config file changes

Each child WatcherProcess:
      ├── reads files in its repo
      ├── computes SHA-256 hash (TOCTOU-safe: read-bytes-once → hash → parse)
      ├── compares against an in-memory per-process baseline (NOT the KG-stored baseline —
      │   that comparison + :SourceCodeDriftEvent emission live in
      │   sha256_baseline.verify_baseline; this watcher only detects in-process deltas)
      ├── queues drift deltas on change (parent logs them; KG persistence deferred)
      └── self-exits on signal

Skeleton — KG-backed baseline + drift-event emission, signal handlers, log rotation,
structured logging, metrics export, graceful shutdown deferred to future sprint.
"""
# KG: ATOM_Skill_longinus

from __future__ import annotations

import dataclasses as dc
import hashlib
import logging
import multiprocessing as mp
import queue
import os
import signal
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_HEALTH_CHECK_INTERVAL_SECONDS = 30.0
DEFAULT_CONFIG_RELOAD_INTERVAL_SECONDS = 5.0


# ─── Config schema ───────────────────────────────────────────────────────


@dc.dataclass(frozen=True)
class RepoEntry:
    # KG: ATOM_Skill_longinus
    """One repo in the watch config."""

    path: Path
    alias: Optional[str] = None

    @property
    def display_name(self) -> str:
        return self.alias or self.path.name


@dc.dataclass(frozen=True)
class WatchConfig:
    # KG: ATOM_Skill_longinus
    """Parsed TOML config."""

    repos: tuple[RepoEntry, ...]
    health_check_interval: float = DEFAULT_HEALTH_CHECK_INTERVAL_SECONDS
    config_reload_interval: float = DEFAULT_CONFIG_RELOAD_INTERVAL_SECONDS

    @classmethod
    def parse_toml(cls, toml_text: str) -> WatchConfig:
        """Parse minimal TOML (no external dep). Supports:

        [[repos]]
        path = "/abs/path"
        alias = "proj-a"
        """
        repos: list[RepoEntry] = []
        current: dict[str, str] = {}
        in_repo_section = False

        for raw_line in toml_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line == "[[repos]]":
                if in_repo_section and current.get("path"):
                    repos.append(_entry_from_dict(current))
                current = {}
                in_repo_section = True
                continue
            if in_repo_section and "=" in line:
                key, _, value = line.partition("=")
                current[key.strip()] = value.strip().strip('"').strip("'")
        if in_repo_section and current.get("path"):
            repos.append(_entry_from_dict(current))

        return cls(repos=tuple(repos))

    @classmethod
    def from_registry(cls, registry=None) -> WatchConfig:
        """Build a watch config from the machine-local repo registry (repo_registry).

        Every registered repo whose checkout still exists becomes a watched RepoEntry,
        aliased by its repo_id. This is the watch.toml ⇄ registry fold-in: a machine that
        has registered its repos needs no separate watch.toml — the registry is the single
        source of truth for "which repos live here".
        """
        from engine.longinus_drift_audit.repo_registry import RepoRegistry

        reg = registry or RepoRegistry()
        repos: list[RepoEntry] = []
        for repo_id, entry in sorted(reg.list().items()):
            p = Path(entry.get("path", "")).expanduser()
            if p.is_dir():
                repos.append(RepoEntry(path=p.resolve(), alias=repo_id))
        return cls(repos=tuple(repos))


def _entry_from_dict(d: dict[str, str]) -> RepoEntry:
    return RepoEntry(path=Path(d["path"]).expanduser().resolve(), alias=d.get("alias"))


# ─── TOCTOU-safe read-hash-parse ─────────────────────────────────────────


def safe_read_hash(file_path: Path) -> tuple[bytes, str]:
    # KG: ATOM_Skill_longinus
    """Read file bytes once, compute SHA-256, return both.

    Guarantees no time-of-check / time-of-use race — the same bytes are
    used for hash and downstream parse. Caller passes `bytes_data` to parser,
    not the file path.
    """
    bytes_data = file_path.read_bytes()
    sha256 = hashlib.sha256(bytes_data).hexdigest()
    return bytes_data, sha256


# ─── Watcher child process ───────────────────────────────────────────────


def _watcher_main(
    repo: RepoEntry,
    stop_event: mp.synchronize.Event,
    drift_queue: mp.Queue,
) -> None:
    """Child process entry point.

    Polls files in `repo.path`, computes sha256 baselines, emits drift events
    when a file changes (compared to last seen hash).
    Exit on `stop_event.set()` from parent.
    """
    pid = os.getpid()
    logger.info(f"[watcher pid={pid} alias={repo.display_name}] started")

    seen_hashes: dict[Path, str] = {}

    try:
        while not stop_event.is_set():
            try:
                for path in _iter_repo_files(repo.path):
                    bytes_data, sha = safe_read_hash(path)
                    prior = seen_hashes.get(path)
                    if prior is None:
                        seen_hashes[path] = sha
                    elif prior != sha:
                        drift_queue.put(
                            {
                                "repo_alias": repo.display_name,
                                "path": str(path),
                                "old_hash": prior,
                                "new_hash": sha,
                                "bytes_len": len(bytes_data),
                                "detected_at": time.time(),
                            }
                        )
                        seen_hashes[path] = sha
            except OSError as e:
                logger.warning(f"[watcher pid={pid}] OSError during scan: {e}")
            stop_event.wait(timeout=2.0)
    finally:
        logger.info(f"[watcher pid={pid} alias={repo.display_name}] exiting")


def _iter_repo_files(repo_root: Path) -> list[Path]:
    """Yield files in repo, skipping common ignore patterns.

    Skeleton — production should consume .longinusignore + .gitignore.
    """
    skip_dirs = {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
        ".mypy_cache",
        ".ruff_cache",
    }
    out: list[Path] = []
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in files:
            if name.endswith((".pyc", ".pyo")):
                continue
            out.append(Path(root) / name)
    return out


# ─── Parent daemon ───────────────────────────────────────────────────────


class LonginusDaemon:
    # KG: ATOM_Skill_longinus
    """Multi-repo drift watch daemon."""

    def __init__(self, config_path: Path, occam_dirty_db: Path | None = None) -> None:
        self.config_path = config_path
        self.workers: dict[str, _Worker] = {}
        self.drift_queue: mp.Queue = mp.Queue()
        # occam dirty-set 큐 DB (None = dirty_queue 기본 ~/.bhgman/occam_dirty.db)
        self.occam_dirty_db = occam_dirty_db
        self._stop = False

    def start(self) -> None:
        config = self._load_config()
        signal.signal(signal.SIGTERM, self._signal_stop)
        signal.signal(signal.SIGINT, self._signal_stop)

        for repo in config.repos:
            self._spawn_worker(repo)

        last_health = time.time()
        last_reload = time.time()

        while not self._stop:
            now = time.time()

            # health check (Cherns Principle 3: variance at origin — child reports)
            if now - last_health >= config.health_check_interval:
                self._health_check()
                last_health = now

            # config hot-reload
            if now - last_reload >= config.config_reload_interval:
                new_config = self._load_config()
                self._reconcile(new_config.repos)
                last_reload = now

            # drain drift events
            self._drain_drift_queue()

            time.sleep(0.5)

        self._shutdown_all()

    def _load_config(self) -> WatchConfig:
        if not self.config_path.exists():
            # No explicit watch.toml — fall back to the shared machine-local repo registry
            # so a registered machine watches its repos with zero extra config.
            cfg = WatchConfig.from_registry()
            if cfg.repos:
                logger.info(
                    "config not found: %s; watching %d repo(s) from the repo registry",
                    self.config_path,
                    len(cfg.repos),
                )
            else:
                logger.warning(
                    "config not found: %s and repo registry is empty; using empty config",
                    self.config_path,
                )
            return cfg
        return WatchConfig.parse_toml(self.config_path.read_text())

    def _spawn_worker(self, repo: RepoEntry) -> None:
        stop_event = mp.Event()
        proc = mp.Process(
            target=_watcher_main,
            args=(repo, stop_event, self.drift_queue),
            name=f"longinus-watcher-{repo.display_name}",
            daemon=True,
        )
        proc.start()
        self.workers[repo.display_name] = _Worker(repo=repo, process=proc, stop_event=stop_event)
        logger.info(f"spawned watcher for {repo.display_name} pid={proc.pid}")

    def _health_check(self) -> None:
        """Auto-restart dead children (CRG pattern)."""
        for alias, worker in list(self.workers.items()):
            if not worker.process.is_alive():
                logger.warning(f"watcher {alias} died; restarting")
                self.workers.pop(alias, None)
                self._spawn_worker(worker.repo)

    def _reconcile(self, new_repos: tuple[RepoEntry, ...]) -> None:
        """Add new repos, remove disappeared repos."""
        new_aliases = {r.display_name for r in new_repos}
        current_aliases = set(self.workers.keys())

        # remove disappeared
        for alias in current_aliases - new_aliases:
            logger.info(f"repo {alias} removed from config; stopping watcher")
            self.workers[alias].stop_event.set()
            self.workers[alias].process.join(timeout=5.0)
            self.workers.pop(alias, None)

        # add new
        for repo in new_repos:
            if repo.display_name not in self.workers:
                self._spawn_worker(repo)

    def _drain_drift_queue(self) -> list[dict]:
        events: list[dict] = []
        while True:
            try:
                events.append(self.drift_queue.get_nowait())
            except queue.Empty:
                break
        for ev in events:
            logger.info(f"drift detected: {ev}")
        if events:
            self._enqueue_occam_dirty(events)
        return events

    def _enqueue_occam_dirty(self, events: list[dict]) -> None:
        """drift 이벤트 → occam dirty-set 큐 (PROM 6 C7/A2 배선, 2026-07-19).

        sha 드리프트가 감지된 경로를 occam 증분 재감사 대상으로 영속 enqueue —
        occam 소비 흐름: pending(now_ms) → run_incremental(scope) → ack().
        lazy import + fail-open: occam 측 오류가 daemon 을 죽이지 않는다.
        # KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A2-2026-07-19
        """
        try:
            from engine.occam.dirty_queue import DirtyQueue, enqueue_from_drift  # noqa: PLC0415

            q = DirtyQueue(self.occam_dirty_db) if self.occam_dirty_db else DirtyQueue()
            for ev in events:
                at_ms = int(float(ev.get("detected_at", 0)) * 1000)
                enqueue_from_drift(q, [str(ev.get("path", ""))], at_ms=at_ms)
        except Exception as e:  # noqa: BLE001 — daemon liveness > queue delivery
            logger.warning(f"occam dirty enqueue failed (daemon continues): {e}")

    def _signal_stop(self, signum: int, frame: object) -> None:
        logger.info(f"received signal {signum}; initiating shutdown")
        self._stop = True

    def _shutdown_all(self) -> None:
        for worker in self.workers.values():
            worker.stop_event.set()
        for worker in self.workers.values():
            worker.process.join(timeout=5.0)
            if worker.process.is_alive():
                worker.process.terminate()
        logger.info("daemon shutdown complete")


@dc.dataclass
class _Worker:
    """Internal: parent's handle to one watcher child."""

    repo: RepoEntry
    process: mp.Process
    stop_event: mp.synchronize.Event
