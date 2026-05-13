"""CLI for the Longinus drift daemon — `bhgman-daemon` entry point.

Skeleton — minimal commands (add / start / stop / status / logs).
Production hardening (proper TOML serialization, log rotation, lock files
to prevent double-start, IPC for live status) deferred.
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from pathlib import Path

from daemon import LonginusDaemon, WatchConfig

DEFAULT_CONFIG_DIR = Path.home() / ".bhgman-tool"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "watch.toml"
DEFAULT_PID_PATH = DEFAULT_CONFIG_DIR / "daemon.pid"
DEFAULT_LOG_PATH = DEFAULT_CONFIG_DIR / "daemon.log"

logger = logging.getLogger(__name__)


def _ensure_config_dir() -> None:
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def cmd_add(args: argparse.Namespace) -> int:
    """Add a repo to the watch config."""
    _ensure_config_dir()
    if DEFAULT_CONFIG_PATH.exists():
        existing = DEFAULT_CONFIG_PATH.read_text()
    else:
        existing = ""

    new_entry = '\n[[repos]]\npath = "' + str(Path(args.path).expanduser().resolve()) + '"\n'
    if args.alias:
        new_entry += f'alias = "{args.alias}"\n'

    DEFAULT_CONFIG_PATH.write_text(existing + new_entry)
    print(f"✓ added {args.path}" + (f" (alias={args.alias})" if args.alias else ""))
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    """Start the daemon (foreground in skeleton; production should daemonize)."""
    _ensure_config_dir()
    if DEFAULT_PID_PATH.exists():
        pid = DEFAULT_PID_PATH.read_text().strip()
        try:
            os.kill(int(pid), 0)
            print(f"daemon already running (pid={pid})", file=sys.stderr)
            return 1
        except (ProcessLookupError, ValueError):
            DEFAULT_PID_PATH.unlink()

    DEFAULT_PID_PATH.write_text(str(os.getpid()))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(DEFAULT_LOG_PATH),
            logging.StreamHandler(sys.stderr),
        ],
    )
    print(f"daemon starting (pid={os.getpid()}, config={DEFAULT_CONFIG_PATH})")

    try:
        daemon = LonginusDaemon(config_path=DEFAULT_CONFIG_PATH)
        daemon.start()
    finally:
        if DEFAULT_PID_PATH.exists():
            DEFAULT_PID_PATH.unlink()
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    """Stop the running daemon (SIGTERM)."""
    if not DEFAULT_PID_PATH.exists():
        print("daemon not running", file=sys.stderr)
        return 1
    pid = int(DEFAULT_PID_PATH.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"sent SIGTERM to pid={pid}")
    except ProcessLookupError:
        DEFAULT_PID_PATH.unlink()
        print(f"daemon (pid={pid}) was not running; cleared stale PID file")
        return 1
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show daemon + per-repo status."""
    if DEFAULT_PID_PATH.exists():
        pid = DEFAULT_PID_PATH.read_text().strip()
        try:
            os.kill(int(pid), 0)
            print(f"daemon: running (pid={pid})")
        except (ProcessLookupError, ValueError):
            print(f"daemon: stale PID file (pid={pid} not alive)")
            return 1
    else:
        print("daemon: not running")

    if DEFAULT_CONFIG_PATH.exists():
        config = WatchConfig.parse_toml(DEFAULT_CONFIG_PATH.read_text())
        print(f"config: {DEFAULT_CONFIG_PATH}")
        for repo in config.repos:
            print(f"  - {repo.display_name}: {repo.path}")
    else:
        print(f"config: (none at {DEFAULT_CONFIG_PATH})")
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    """Tail the daemon log."""
    if not DEFAULT_LOG_PATH.exists():
        print("no log file yet", file=sys.stderr)
        return 1
    if args.follow:
        # naive tail -f
        with DEFAULT_LOG_PATH.open() as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    print(line, end="")
                else:
                    time.sleep(0.5)
    else:
        print(DEFAULT_LOG_PATH.read_text())
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bhgman-daemon",
        description="Longinus multi-repo drift detection daemon",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="add a repo to the watch config")
    p_add.add_argument("path", help="path to the repo (absolute or ~/...)")
    p_add.add_argument("--alias", help="optional alias for this repo")
    p_add.set_defaults(func=cmd_add)

    p_start = sub.add_parser("start", help="start the daemon (foreground)")
    p_start.set_defaults(func=cmd_start)

    p_stop = sub.add_parser("stop", help="stop the running daemon")
    p_stop.set_defaults(func=cmd_stop)

    p_status = sub.add_parser("status", help="show daemon + repo status")
    p_status.set_defaults(func=cmd_status)

    p_logs = sub.add_parser("logs", help="tail the daemon log")
    p_logs.add_argument("-f", "--follow", action="store_true", help="follow log output")
    p_logs.set_defaults(func=cmd_logs)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
