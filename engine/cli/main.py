"""bhgman-tool CLI entry point — stdlib argparse, zero new dependencies.

This module wires the top-level `bhgman-tool` console script registered in the
parent `pyproject.toml`. Subcommands span two cohorts:

A. bhgman_tool native (Phase 3 SCW):
    bhgman-tool install-skills [--target DIR] [--dry-run] [--force]
    bhgman-tool verify [--scope engine|lean|all]
    bhgman-tool version
    bhgman-tool daemon ...                    (delegates to engine.longinus_drift_audit.daemon_cli)

B. SYMPOSIUM-absorbed (Wave 7 P2-A 2026-05-14, KG rs-cli-symposium-absorb-2026-05-14):
    bhgman-tool apt <task>                    — APT cycle dispatch (SA → SP → ST → SCW)
    bhgman-tool tpa <path>                    — TPA reverse cycle (TCW → ST → SP → TA)
    bhgman-tool prom <N> <topic>              — Prometheus N-subagent research
    bhgman-tool tlb <target> [--lens NAME]    — Taliban adversarial verification
    bhgman-tool longinus <op>                 — Longinus reference binding (sha256/ged/reverse-scan)
    bhgman-tool harness <action>              — Harness 3-tier scaffolding diagnose
    bhgman-tool status                        — KG audit (ssh dgx → cypher-shell)

C. SYMPOSIUM resolver/gate (Wave 7 P3-H 2026-05-14, KG span-bhgman-resolver-gate-absorption-wave7-2026-05-14):
    bhgman-tool resolver render --input X --output Y    — APT v27 A6 pre-prompt resolver render
    bhgman-tool resolver validate <SKILL.md>            — KG ↔ SKILL drift check
    bhgman-tool gate serve                              — start FastAPI gate endpoint (uvicorn)
    bhgman-tool gate check --gate NAME ...              — POST /gate/check oneshot
    Modules: engine.resolver.resolver (9 pytest absorbed) + engine.gate.gate_endpoint (6 pytest absorbed)
    OPA Rego policies: engine/gate/policies/ (4 bundle dirs preserved from SYMPOSIUM opa_rego_skeleton).

Routing convention for cohort B: each verb resolves a SKILL.md via `skills/<name>/`
and prints the routing intent (stderr) + the SKILL.md path (stdout). Actual phase
logic lives in the SKILL.md (drift prevention).

Honest limitations (Goodhart safeguard — no headline metric promotion):
  - install-skills does not check skill content integrity (no sha256 audit yet)
  - verify is *smoke* level — does not enumerate the full theorem set or
    re-derive coverage figures
  - daemon delegation passes through argv; no parameter translation
  - argparse error messages are not internationalized (README is 4-lang, CLI is en-only)
  - cohort B verbs `apt/tpa/prom/tlb/longinus/harness` only emit the SKILL.md path
    — the parent Claude harness consumes the body. They do NOT execute phase logic.
  - `status` requires `ssh dgx` reachable; degrades to error if absent.
"""
from __future__ import annotations

import argparse
import os
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


def _verify_engine(root: Path) -> str | None:
    engine = root / "engine"
    print(f"[verify] running pytest in {engine}")
    rc = subprocess.call(
        ["uv", "run", "--with", "pytest", "pytest", str(engine), "-q"],
        cwd=root,
    )
    print(f"[verify] pytest exit={rc}")
    return f"pytest:{rc}" if rc != 0 else None


def _verify_lean(root: Path) -> list[str]:
    lean = root / "lean"
    if not lean.is_dir():
        print(f"[verify] skip lean: {lean} not present")
        return []
    files = sorted(lean.glob("*.lean"))
    print(f"[verify] lean: {len(files)} file(s) found")
    failures: list[str] = []
    for f in files:
        rc = subprocess.call(["lean", str(f)], cwd=root)
        marker = "OK" if rc == 0 else f"FAIL({rc})"
        print(f"  [{marker}] {f.name}")
        if rc != 0:
            failures.append(f"lean:{f.name}:{rc}")
    return failures


def cmd_verify(args: argparse.Namespace) -> int:
    """Smoke-verify the repo: pytest on engine, optional lean.

    Not a coverage report. Reports exit codes of the underlying tools.
    Goodhart safeguard: this prints raw exit codes, not a single summary score.
    """
    root = _repo_root()
    failures: list[str] = []

    if args.scope in ("engine", "all"):
        if (failure := _verify_engine(root)) is not None:
            failures.append(failure)

    if args.scope in ("lean", "all"):
        failures.extend(_verify_lean(root))

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


# ─── SYMPOSIUM-absorbed verbs (Wave 7 P2-A, 2026-05-14) ────────────────────────
# KG: rs-cli-symposium-absorb-2026-05-14
# Provenance: bin/symposium (109 lines bash → Python argparse port)


def _resolve_skill_md(skill_name: str) -> Path:
    """Locate `skills/<skill_name>/SKILL.md` honoring SYMPOSIUM_ROOT env override.

    Routing convention: cohort B verbs do not execute phase logic — they print
    the SKILL.md path so the parent Claude harness can consume the body.
    """
    sym = os.environ.get("SYMPOSIUM_ROOT")
    if sym:
        for sub in ("SKILLS", "skills"):
            cand = Path(sym).expanduser() / sub / skill_name / "SKILL.md"
            if cand.is_file():
                return cand
    cand = _repo_root() / "skills" / skill_name / "SKILL.md"
    if not cand.is_file():
        raise FileNotFoundError(
            f"skill not found: {skill_name} (looked in SYMPOSIUM_ROOT and {_repo_root() / 'skills'})"
        )
    return cand


def _route_skill(skill_name: str, args: list[str]) -> int:
    """Print routing intent to stderr, SKILL.md path to stdout. Drift prevention: do NOT execute."""
    try:
        skill_md = _resolve_skill_md(skill_name)
    except FileNotFoundError as e:
        print(f"[bhgman-tool] FAIL: {e}", file=sys.stderr)
        return 2
    print(f"[bhgman-tool] routing → /{skill_name} {' '.join(args)} (SKILL.md: {skill_md})", file=sys.stderr)
    print(str(skill_md))
    return 0


def cmd_apt(args: argparse.Namespace) -> int:
    """APT cycle dispatch (SA → SP → ST → SCW). Routes to skills/apt/SKILL.md."""
    if not args.task:
        print("usage: bhgman-tool apt <task>", file=sys.stderr)
        return 2
    return _route_skill("apt", args.task)


def cmd_tpa(args: argparse.Namespace) -> int:
    """TPA reverse cycle (TCW → ST → SP → TA). Routes to skills/tpa/SKILL.md."""
    if not args.path:
        print("usage: bhgman-tool tpa <path>", file=sys.stderr)
        return 2
    return _route_skill("tpa", args.path)


def cmd_prom(args: argparse.Namespace) -> int:
    """Prometheus N-subagent research. Routes to skills/prometheus/SKILL.md."""
    if not args.topic:
        print("usage: bhgman-tool prom <N> <topic>", file=sys.stderr)
        return 2
    return _route_skill("prometheus", [str(args.N), *args.topic])


def cmd_tlb(args: argparse.Namespace) -> int:
    """Taliban adversarial verification. Routes to skills/taliban/SKILL.md."""
    if not args.target:
        print("usage: bhgman-tool tlb <target> [--lens NAME]", file=sys.stderr)
        return 2
    suffix = [*args.target]
    if args.lens:
        suffix.extend(["--lens", args.lens])
    return _route_skill("taliban", suffix)


def cmd_longinus(args: argparse.Namespace) -> int:
    """Longinus reference binding. Bash dispatcher emulation for sha256/ged/reverse-scan ops."""
    if not args.op:
        print("usage: bhgman-tool longinus <op> [args...]", file=sys.stderr)
        return 2
    op = args.op[0]
    rest = args.op[1:]
    root = _repo_root()
    # Native python scripts: prefer SYMPOSIUM/bin/ if SYMPOSIUM_ROOT is set.
    sym = os.environ.get("SYMPOSIUM_ROOT")
    bin_dirs = [Path(sym).expanduser() / "bin" for sym in [sym] if sym]
    bin_dirs.append(root / "bin")
    script_names = {
        "sha256": "longinus_sha256_daemon.py",
        "ged": "longinus_ged_drift_meter.py",
        "reverse-scan": "longinus_reverse_orphan_scan.py",
    }
    if op in script_names:
        for d in bin_dirs:
            sp = d / script_names[op]
            if sp.is_file():
                cmd = [sys.executable, str(sp), *rest]
                return subprocess.call(cmd)
        # Fall through to skill routing if script not found
        print(f"[bhgman-tool] longinus {op}: script not found in {bin_dirs} — routing to SKILL.md", file=sys.stderr)
    return _route_skill("longinus", args.op)


def cmd_harness(args: argparse.Namespace) -> int:
    """Harness 3-tier scaffolding diagnose. Routes to skills/harness/SKILL.md."""
    if not args.action:
        print("usage: bhgman-tool harness <action>", file=sys.stderr)
        return 2
    return _route_skill("harness", args.action)


_STATUS_CYPHER = """MATCH (n) WITH labels(n) AS l, count(*) AS c
UNWIND l AS lbl
RETURN lbl AS label, sum(c) AS count
ORDER BY count DESC
LIMIT 20;"""


# ─── SYMPOSIUM resolver/gate verbs (Wave 7 P3-H, 2026-05-14) ───────────────────
# KG: span-bhgman-resolver-gate-absorption-wave7-2026-05-14
# Provenance: SYMPOSIUM/THEORY/APT/resolver_prototype + gate_endpoint_prototype


def cmd_resolver(args: argparse.Namespace) -> int:
    """APT v27 A6 pre-prompt resolver dispatch.

    Delegates to engine.resolver.resolver:main() — eager Composition Root
    validation (KG health + 5 core magic fields). Refuses partial render.
    """
    try:
        from engine.resolver.resolver import main as resolver_main
    except ImportError as e:
        print(f"[bhgman-tool] FAIL: engine.resolver not importable — install resolver deps "
              f"(python-frontmatter, Jinja2, neo4j): {e}", file=sys.stderr)
        return 2
    # passthrough — resolver has its own argparse with render/validate subcommands
    return resolver_main(args.passthrough or [])


_GATE_CHECK_FLAGS = {"--gate", "--cycle", "--actor", "--expected", "--actual"}


def _parse_gate_check_args(rest: list[str]) -> dict[str, object] | None:
    """Extract --gate/--cycle/--actor/--expected/--actual from passthrough list.
    Returns dict or None if required keys missing."""
    parsed: dict[str, object] = {}
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok in _GATE_CHECK_FLAGS and i + 1 < len(rest):
            key = tok[2:]  # strip "--"
            val = rest[i + 1]
            parsed[key] = int(val) if key in ("expected", "actual") else val
            i += 2
        else:
            i += 1
    if not all(parsed.get(k) for k in ("gate", "cycle", "actor")):
        return None
    return parsed


def _cmd_gate_serve() -> int:
    try:
        from engine.gate.gate_endpoint import main as gate_main
    except ImportError as e:
        print(f"[bhgman-tool] FAIL: engine.gate not importable — install gate deps "
              f"(fastapi, uvicorn, redis, tenacity): {e}", file=sys.stderr)
        return 2
    gate_main()
    return 0


def _cmd_gate_check(rest: list[str]) -> int:
    import json
    import urllib.request
    parsed = _parse_gate_check_args(rest)
    if parsed is None:
        print("usage: bhgman-tool gate check --gate NAME --cycle ID --actor NAME "
              "[--expected N --actual N]", file=sys.stderr)
        return 2
    host = os.environ.get("APT_GATE_HOST", "127.0.0.1")
    port = os.environ.get("APT_GATE_PORT", "8765")
    body = {
        "gate_name": parsed["gate"], "cycle_id": parsed["cycle"], "actor": parsed["actor"],
        "context": {"expected_count": parsed.get("expected"), "actual_count": parsed.get("actual")},
    }
    req = urllib.request.Request(
        f"http://{host}:{port}/gate/check",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            print(resp.read().decode("utf-8"))
            return 0 if resp.status == 200 else 1
    except Exception as e:
        print(f"[bhgman-tool] gate check FAIL: {e}", file=sys.stderr)
        return 2


def cmd_gate(args: argparse.Namespace) -> int:
    """APT v27 A7 gate hook dispatch.

    Subcommands:
      serve  → uvicorn-run engine.gate.gate_endpoint:app
      check  → oneshot POST /gate/check (requires server running)
    """
    if not args.passthrough:
        print("usage: bhgman-tool gate {serve,check} [options]", file=sys.stderr)
        return 2
    sub = args.passthrough[0]
    rest = args.passthrough[1:]
    if sub == "serve":
        return _cmd_gate_serve()
    if sub == "check":
        return _cmd_gate_check(rest)
    print(f"[bhgman-tool] unknown gate subcommand: {sub} (expected serve|check)", file=sys.stderr)
    return 2


def cmd_status(_args: argparse.Namespace) -> int:
    """KG audit via ssh dgx → cypher-shell. Degrades gracefully if dgx unreachable."""
    dgx_host = os.environ.get("SYMPOSIUM_DGX_HOST", "dgx")
    print(f"[bhgman-tool] ssh {dgx_host} cypher-shell — KG audit", file=sys.stderr)
    cmd = [
        "ssh", dgx_host,
        'kubectl exec -n neo4j neo4j-0 -- cypher-shell -u neo4j '
        '-p "${NEO4J_PASSWORD:-neo4j}" --format plain',
    ]
    try:
        result = subprocess.run(cmd, input=_STATUS_CYPHER, text=True, timeout=10, check=False)
        return result.returncode
    except FileNotFoundError:
        print("[bhgman-tool] FAIL: ssh not available — install OpenSSH client", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print(f"[bhgman-tool] FAIL: timeout — ssh {dgx_host} unreachable", file=sys.stderr)
        return 2


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

    # ─── SYMPOSIUM-absorbed verbs (Wave 7 P2-A, 2026-05-14) ────────────────
    p_apt = sub.add_parser("apt", help="APT cycle dispatch (SA → SP → ST → SCW).")
    p_apt.add_argument("task", nargs="+", help="Task description forwarded to /apt.")
    p_apt.set_defaults(func=cmd_apt)

    p_tpa = sub.add_parser("tpa", help="TPA reverse cycle (TCW → ST → SP → TA).")
    p_tpa.add_argument("path", nargs="+", help="Codebase path to reverse-engineer.")
    p_tpa.set_defaults(func=cmd_tpa)

    p_prom = sub.add_parser("prom", help="Prometheus N-subagent research.")
    p_prom.add_argument("N", type=int, help="Subagent count (16 / 32 / 64 / 100).")
    p_prom.add_argument("topic", nargs="+", help="Research topic.")
    p_prom.set_defaults(func=cmd_prom)

    p_tlb = sub.add_parser("tlb", help="Taliban adversarial verification.")
    p_tlb.add_argument("target", nargs="+", help="Verification target (SPAN/CONTRACT/etc.).")
    p_tlb.add_argument("--lens", help="Lens set (constitutional / mathematical / solid).")
    p_tlb.set_defaults(func=cmd_tlb)

    p_long = sub.add_parser("longinus", help="Longinus reference binding (sha256/ged/reverse-scan).")
    p_long.add_argument("op", nargs="+", help="Operation: sha256 / ged / reverse-scan / <freeform>.")
    p_long.set_defaults(func=cmd_longinus)

    p_hns = sub.add_parser("harness", help="Harness 3-tier scaffolding diagnose.")
    p_hns.add_argument("action", nargs="+", help="Action forwarded to /harness.")
    p_hns.set_defaults(func=cmd_harness)

    p_st = sub.add_parser("status", help="KG audit (ssh dgx → cypher-shell).")
    p_st.set_defaults(func=cmd_status)

    # ─── SYMPOSIUM resolver/gate verbs (Wave 7 P3-H, 2026-05-14) ──────────
    p_rs = sub.add_parser(
        "resolver",
        help="APT v27 A6 pre-prompt resolver (render | validate). 9 pytest absorbed.",
    )
    p_rs.add_argument(
        "passthrough", nargs=argparse.REMAINDER,
        help="Args forwarded to engine.resolver.resolver (render --input X --output Y | validate <path>).",
    )
    p_rs.set_defaults(func=cmd_resolver)

    p_gt = sub.add_parser(
        "gate",
        help="APT v27 A7 fail-closed gate endpoint (serve | check). 6 pytest absorbed.",
    )
    p_gt.add_argument(
        "passthrough", nargs=argparse.REMAINDER,
        help="serve | check --gate NAME --cycle ID --actor NAME [--expected N --actual N]",
    )
    p_gt.set_defaults(func=cmd_gate)

    return p


def cli(argv: list[str] | None = None) -> int:
    """Entry point registered in parent pyproject.toml [project.scripts]."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(cli())
