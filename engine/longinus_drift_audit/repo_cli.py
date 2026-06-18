"""Longinus repo registry CLI — manage the per-machine repo_id -> local-path map.

    python -m engine.longinus_drift_audit.repo_cli list
    python -m engine.longinus_drift_audit.repo_cli register <repo_id> <local_path>
    python -m engine.longinus_drift_audit.repo_cli discover [dir]      # auto-register dir's repo
    python -m engine.longinus_drift_audit.repo_cli id [dir]           # print the dir's repo_id
    python -m engine.longinus_drift_audit.repo_cli locate <repo_id> <repo_relpath>

The registry is machine-local (see repo_registry.registry_path) and must not be committed.

# KG: ATOM_Skill_longinus
"""
from __future__ import annotations

import argparse
import logging
import sys

from engine.longinus_drift_audit.repo_identity import repo_id_for
from engine.longinus_drift_audit.repo_registry import (
    NotRegistered,
    RepoRegistry,
    registry_path,
)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(prog="longinus-repo", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="show all registered repos")
    p_reg = sub.add_parser("register", help="register repo_id -> local path")
    p_reg.add_argument("repo_id")
    p_reg.add_argument("path")
    p_disc = sub.add_parser("discover", help="auto-register the repo containing a directory")
    p_disc.add_argument("dir", nargs="?", default=".")
    p_id = sub.add_parser("id", help="print the portable repo_id of a directory")
    p_id.add_argument("dir", nargs="?", default=".")
    p_loc = sub.add_parser("locate", help="resolve repo_id + repo_relpath to an abs path")
    p_loc.add_argument("repo_id")
    p_loc.add_argument("repo_relpath")
    args = ap.parse_args(argv)

    reg = RepoRegistry()

    if args.cmd == "list":
        entries = reg.list()
        print(f"# registry: {registry_path()}")
        if not entries:
            print("(empty)")
        for rid, e in sorted(entries.items()):
            print(f"{rid}\t{e.get('path', '')}")
        return 0

    if args.cmd == "register":
        reg.register(args.repo_id, args.path)
        return 0

    if args.cmd == "discover":
        hit = reg.discover(args.dir)
        if hit is None:
            print(f"not a git repo: {args.dir}", file=sys.stderr)
            return 1
        rid, top = hit
        print(f"{rid}\t{top}")
        return 0

    if args.cmd == "id":
        rid = repo_id_for(args.dir)
        if rid is None:
            print(f"not a git repo: {args.dir}", file=sys.stderr)
            return 1
        print(rid)
        return 0

    if args.cmd == "locate":
        try:
            print(reg.locate(args.repo_id, args.repo_relpath))
        except NotRegistered as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
