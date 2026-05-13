"""bhgman-tool CLI entry point — stdlib argparse, zero new dependencies.

This module wires four subcommands routed off the top-level `bhgman-tool` console
script registered in the parent `pyproject.toml`:

    bhgman-tool install-skills [--target DIR] [--dry-run] [--force]
    bhgman-tool verify [--scope engine|lean|all]
    bhgman-tool version
    bhgman-tool daemon ...   (delegates to engine.longinus_drift_audit.daemon_cli)

Honest limitations (Goodhart safeguard — no headline metric promotion):
  - install-skills does not check skill content integrity (no sha256 audit yet)
  - verify is *smoke* level — does not enumerate the full theorem set or
    re-derive coverage figures
  - daemon delegation passes through argv; no parameter translation
  - argparse error messages are not internationalized (README is 4-lang, CLI is en-only)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE_VERSION = "0.1.0"


def _repo_root() -> Path:
    """Walk up from this file to locate the bhgman_tool repo root.

    The root is identified by presence of both `skills/` and `pyproject.toml`.
    Returns the first matching ancestor; raises if none found.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "skills").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError(
        f"bhgman_tool repo root not found above {here}. "
        "Expected sibling: skills/ and pyproject.toml."
    )


def cmd_install_skills(args: argparse.Namespace) -> int:
    """Copy skills/* into the user's Claude Code skills directory.

    Mirrors README Quickstart step 4 (`cp -R skills/* ~/.claude/skills/`)
    but in Python so it runs on Windows + reports what changed.
    """
    src = _repo_root() / "skills"
    target = Path(args.target).expanduser().resolve()

    if not src.is_dir():
        print(f"[install-skills] FAIL: source not found: {src}", file=sys.stderr)
        return 2

    skills = sorted(p for p in src.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not skills:
        print(f"[install-skills] FAIL: no skill dirs under {src}", file=sys.stderr)
        return 2

    print(f"[install-skills] source: {src}")
    print(f"[install-skills] target: {target}")
    print(f"[install-skills] {len(skills)} skill dirs detected")

    if args.dry_run:
        for s in skills:
            dst = target / s.name
            verb = "OVERWRITE" if dst.exists() else "INSTALL"
            print(f"  [{verb}] {s.name}")
        print("[install-skills] dry-run: no files written")
        return 0

    target.mkdir(parents=True, exist_ok=True)

    overwrote, installed, skipped = 0, 0, 0
    for s in skills:
        dst = target / s.name
        if dst.exists():
            if not args.force:
                print(f"  [SKIP]      {s.name} (use --force to overwrite)")
                skipped += 1
                continue
            shutil.rmtree(dst)
            shutil.copytree(s, dst)
            print(f"  [OVERWRITE] {s.name}")
            overwrote += 1
        else:
            shutil.copytree(s, dst)
            print(f"  [INSTALL]   {s.name}")
            installed += 1

    print(
        f"[install-skills] done — installed={installed} overwrote={overwrote} skipped={skipped}"
    )
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Smoke-verify the repo: pytest on engine, optional lean.

    Not a coverage report. Reports exit codes of the underlying tools.
    Goodhart safeguard: this prints raw exit codes, not a single
    summary score.
    """
    root = _repo_root()
    failures: list[str] = []

    if args.scope in ("engine", "all"):
        engine = root / "engine"
        print(f"[verify] running pytest in {engine}")
        rc = subprocess.call(
            ["uv", "run", "--with", "pytest", "pytest", str(engine), "-q"],
            cwd=root,
        )
        print(f"[verify] pytest exit={rc}")
        if rc != 0:
            failures.append(f"pytest:{rc}")

    if args.scope in ("lean", "all"):
        lean = root / "lean"
        if not lean.is_dir():
            print(f"[verify] skip lean: {lean} not present")
        else:
            files = sorted(lean.glob("*.lean"))
            print(f"[verify] lean: {len(files)} file(s) found")
            for f in files:
                rc = subprocess.call(["lean", str(f)], cwd=root)
                marker = "OK" if rc == 0 else f"FAIL({rc})"
                print(f"  [{marker}] {f.name}")
                if rc != 0:
                    failures.append(f"lean:{f.name}:{rc}")

    if failures:
        print(f"[verify] FAILURES: {', '.join(failures)}", file=sys.stderr)
        return 1
    print("[verify] all checked components passed (smoke level)")
    return 0


def cmd_version(_args: argparse.Namespace) -> int:
    """Print package version + repo layout summary.

    Honest about source — version is read from this module, not from
    the installed wheel metadata. They can drift if not bumped together.
    """
    root = _repo_root()
    skills = sorted(p.name for p in (root / "skills").iterdir() if p.is_dir())
    engine_subs = sorted(p.name for p in (root / "engine").iterdir() if p.is_dir())
    worked = sorted(p.name for p in (root / "worked").iterdir() if p.is_dir())

    print(f"bhgman-tool {PACKAGE_VERSION}")
    print(f"  repo root: {root}")
    print(f"  skills ({len(skills)}): {', '.join(skills)}")
    print(f"  engine ({len(engine_subs)}): {', '.join(engine_subs)}")
    print(f"  worked ({len(worked)}): {', '.join(worked)}")
    print("  layer: tool (Airplane Man #4 engineering crystallization)")
    print("  essence layer: separate (see docs/07-metahumotonic-trace.md)")
    return 0


def cmd_daemon(args: argparse.Namespace) -> int:
    """Delegate to engine.longinus_drift_audit.daemon_cli."""
    cmd = [sys.executable, "-m", "engine.longinus_drift_audit.daemon_cli", *args.passthrough]
    return subprocess.call(cmd, cwd=_repo_root())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bhgman-tool",
        description=(
            "bhgman_tool umbrella CLI — Airplane Man (#4) Harness toolkit. "
            "Tool layer only; essence/ontology layer in separate repos."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_inst = sub.add_parser(
        "install-skills",
        help="Copy skills/* into ~/.claude/skills/ (replaces README step 4 manual cp).",
    )
    p_inst.add_argument(
        "--target",
        default="~/.claude/skills",
        help="Target dir (default: ~/.claude/skills)",
    )
    p_inst.add_argument("--dry-run", action="store_true", help="Show what would happen, don't write.")
    p_inst.add_argument("--force", action="store_true", help="Overwrite existing skill dirs.")
    p_inst.set_defaults(func=cmd_install_skills)

    p_ver = sub.add_parser("verify", help="Smoke-run pytest (and optionally lean) for the repo.")
    p_ver.add_argument(
        "--scope",
        choices=["engine", "lean", "all"],
        default="engine",
        help="What to verify (default: engine).",
    )
    p_ver.set_defaults(func=cmd_verify)

    p_v = sub.add_parser("version", help="Print version + repo layout summary.")
    p_v.set_defaults(func=cmd_version)

    p_d = sub.add_parser(
        "daemon",
        help="Delegate to engine.longinus_drift_audit.daemon_cli (add / start / stop / status / logs).",
    )
    p_d.add_argument("passthrough", nargs=argparse.REMAINDER, help="Args forwarded to daemon_cli.")
    p_d.set_defaults(func=cmd_daemon)

    return p


def cli(argv: list[str] | None = None) -> int:
    """Entry point registered in parent pyproject.toml [project.scripts]."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(cli())
