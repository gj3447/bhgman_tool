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

    print(f"[install-skills] done — installed={installed} overwrote={overwrote} skipped={skipped}")
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
    print(
        f"[bhgman-tool] routing → /{skill_name} {' '.join(args)} (SKILL.md: {skill_md})",
        file=sys.stderr,
    )
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


# prom/tlb fallback 시 사용자에게 *두 백엔드 옵션 모두* 명시 — ANTHROPIC 강제 인상 제거.
_BACKEND_HINT = (
    "        백엔드 선택:\n"
    "          • 로컬 LLM (key 불필요): export BHGMAN_LLM_BASE_URL=<openai-compat URL> "
    "BHGMAN_LLM_MODEL=<model>\n"
    "          • Anthropic:              export ANTHROPIC_API_KEY=<key>"
)


def _agent_runtime():
    """engine.agents 로드 → (namespace | None, reason). flat-layout: 개별 모듈 import.

    namespace = AgentClient/research/critique/DEFAULT_LENSES. 런타임 불가면 (None, reason).
    """
    import importlib  # noqa: PLC0415
    import types  # noqa: PLC0415

    evict = ("client", "dispatch", "agent_models", "prometheus", "naesengmoon")
    client_mod = _load_engine_module("agents", "client", evict=evict)
    prom = importlib.import_module("prometheus")
    naes = importlib.import_module("naesengmoon")
    ok, reason = client_mod.runtime_status()
    if not ok:
        return None, reason
    ns = types.SimpleNamespace(
        AgentClient=client_mod.AgentClient,
        research=prom.research,
        critique=naes.critique,
        DEFAULT_LENSES=naes.DEFAULT_LENSES,
    )
    return ns, reason


def cmd_prom(args: argparse.Namespace) -> int:
    """프로메테우스 — 지식 선행 리서치. 런타임 있으면 실행, 없으면 skill route(graceful)."""
    if not args.topic:
        print("usage: bhgman-tool prom <N> <topic>", file=sys.stderr)
        return 2
    topic = " ".join(args.topic)
    if getattr(args, "route", False):
        return _route_skill("prometheus", [str(args.N), *args.topic])
    agents, reason = _agent_runtime()
    if agents is None:
        print(f"[prom] LLM runtime 사용 불가 ({reason}) → skill route fallback.", file=sys.stderr)
        print(_BACKEND_HINT, file=sys.stderr)
        return _route_skill("prometheus", [str(args.N), *args.topic])
    report = agents.research(topic, args.N, agents.AgentClient(), web_search=not args.no_web)
    print(report.summary)
    print("\n" + report.synthesis)
    return 0


def cmd_tlb(args: argparse.Namespace) -> int:
    """나생문 — 판단렌즈 ensemble critic. 런타임 있으면 실행, 없으면 skill route(graceful)."""
    if not args.target:
        print("usage: bhgman-tool tlb <target> [--lens NAME] [--claim TEXT]", file=sys.stderr)
        return 2
    target = " ".join(args.target)
    if getattr(args, "route", False):
        suffix = [*args.target] + (["--lens", args.lens] if args.lens else [])
        return _route_skill("taliban", suffix)
    agents, reason = _agent_runtime()
    if agents is None:
        print(f"[tlb] LLM runtime 사용 불가 ({reason}) → skill route fallback.", file=sys.stderr)
        print(_BACKEND_HINT, file=sys.stderr)
        suffix = [*args.target] + (["--lens", args.lens] if args.lens else [])
        return _route_skill("taliban", suffix)
    lenses = (args.lens,) if args.lens else agents.DEFAULT_LENSES
    verdict = agents.critique(target, args.claim or target, agents.AgentClient(), lenses=lenses)
    print(verdict.summary)
    for lv in verdict.lens_verdicts:
        print(f"  [{lv.verdict}] {lv.lens}")
    return 0


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
        print(
            f"[bhgman-tool] longinus {op}: script not found in {bin_dirs} — routing to SKILL.md",
            file=sys.stderr,
        )
    return _route_skill("longinus", args.op)


def cmd_harness(args: argparse.Namespace) -> int:
    """하네스 — 3계층/4축 진단 엔진(결정론, 인프라 0). --route로 skill 라우팅."""
    if not args.action:
        print("usage: bhgman-tool harness <subject>", file=sys.stderr)
        return 2
    if getattr(args, "route", False):
        return _route_skill("harness", args.action)
    harness = _load_engine_module("harness", "harness", evict=("harness", "harness_models"))
    diag = harness.diagnose(" ".join(args.action))
    print(diag.summary)
    print(f"  tier: {diag.tier.value} ({diag.tier_confidence.value}) — {diag.tier_reason}")
    for f in diag.axes:
        print(f"  [{f.presence.value:8s}] {f.axis.value:10s} ({f.signal})")
    if diag.mcp_adapter:
        print("  MCP: cross-tier adapter detected")
    # 코어 진단은 인프라 0. --apply 시에만 KG persist (occam/hades 패턴, --local 가능).
    if getattr(args, "apply", False):
        runners = _resolve_kg_runners(args)
        if runners is None:
            print(
                "  [harness] KG 사용 불가 (NEO4J_* 또는 --local 필요) — persist 생략.",
                file=sys.stderr,
            )
            return 2
        _run, write, close = runners
        cypher, params = harness.build_diagnosis_cypher(diag)
        try:
            write(cypher, params)
        finally:
            close()
        print(f"  persisted → :HarnessDiagnosis {{name:'{diag.subject}'}}")
    return 0


_STATUS_CYPHER = """MATCH (n) WITH labels(n) AS l, count(*) AS c
UNWIND l AS lbl
RETURN lbl AS label, sum(c) AS count
ORDER BY count DESC
LIMIT 20;"""


def cmd_longinus_floating(args: argparse.Namespace) -> int:
    """Floating concept-node scan — concept nodes with no Longinus binding to source.

    Operationalizes lesson-concept-nodes-created-without-longinus-binding-float-2026-05-29:
    a concept node created without a binding to a SourceCodeNode "floats" (unreachable by
    legion synthesis / TPA recovery). Local KG only; reports, never writes.
    """
    store_mod = _load_engine_module("kg_local", "store")
    scan_mod = _load_engine_module("kg_local", "floating_scan")
    store = store_mod.LocalKgStore()
    floating = scan_mod.find_floating_concepts(store.nodes, store.edges)
    total = sum(
        1 for n in store.nodes if any(lbl in scan_mod.CONCEPT_LABELS for lbl in n.get("labels", []))
    )
    ratio = scan_mod.floating_ratio(total_concepts=total, floating_count=len(floating))
    status = "CLEAN" if not floating else "UNBOUND"
    print(
        f"longinus-floating: concepts={total} floating={len(floating)} ratio={ratio:.2f} → {status}"
    )
    for name in floating:
        print(f"  [floating] {name} — no edge to a SourceCodeNode (bind via longinus)")
    return 0 if not floating else 1


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
        print(
            f"[bhgman-tool] FAIL: engine.resolver not importable — install resolver deps "
            f"(python-frontmatter, Jinja2, neo4j): {e}",
            file=sys.stderr,
        )
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
        print(
            f"[bhgman-tool] FAIL: engine.gate not importable — install gate deps "
            f"(fastapi, uvicorn, redis, tenacity): {e}",
            file=sys.stderr,
        )
        return 2
    gate_main()
    return 0


def _cmd_gate_check(rest: list[str]) -> int:
    import json
    import urllib.request

    parsed = _parse_gate_check_args(rest)
    if parsed is None:
        print(
            "usage: bhgman-tool gate check --gate NAME --cycle ID --actor NAME "
            "[--expected N --actual N]",
            file=sys.stderr,
        )
        return 2
    host = os.environ.get("APT_GATE_HOST", "127.0.0.1")
    port = os.environ.get("APT_GATE_PORT", "8765")
    body = {
        "gate_name": parsed["gate"],
        "cycle_id": parsed["cycle"],
        "actor": parsed["actor"],
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
        "ssh",
        dgx_host,
        "kubectl exec -n neo4j neo4j-0 -- cypher-shell -u neo4j "
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


# ─── occam verb (engine-executing, like longinus — not SKILL-routing) ─────────
# KG: occam-kam-canonical-2026-05-26, occam-pass-kg-wide-2026-05-27
# occam은 실제 엔진(occam_pass)을 KG에 대해 돌린다. covenant: archive-only, dry-run 기본.


def _load_occam_runner():
    """Lazy-import engine.occam.occam_runner with the occam dir on sys.path.

    occam modules use bare imports (`from occam import ...`); the test conftest
    injects the path. The CLI mirrors that bridge at call time.
    KG: ap-bhgman-longinus-import-drift-fix-2026-05-15 (Option A precedent).
    """
    occam_dir = _repo_root() / "engine" / "occam"
    if str(occam_dir) not in sys.path:
        sys.path.insert(0, str(occam_dir))
    import occam_runner  # noqa: E402,PLC0415

    return occam_runner


def make_kg_runners():
    """Build (run_cypher, write_cypher, close) backed by the neo4j driver, or None.

    Env: NEO4J_URI (default bolt://localhost:7687), NEO4J_USER (neo4j), NEO4J_PASSWORD.
    Returns None when the driver or credentials are unavailable — the caller then
    degrades to printing the fetch cypher for the parent Claude harness (MCP) to run.
    Monkeypatched in tests to inject fakes.
    """
    try:
        from neo4j import GraphDatabase  # noqa: PLC0415
    except ImportError:
        return None
    pw = os.environ.get("NEO4J_PASSWORD")
    if not pw:
        return None
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, pw))
    except Exception as e:  # noqa: BLE001 — any driver init failure → graceful degrade
        print(f"[occam] neo4j driver init failed: {e}", file=sys.stderr)
        return None

    def run_cypher(cypher: str, params: dict) -> list[dict]:
        with driver.session() as s:
            return [dict(r) for r in s.run(cypher, **params)]

    return run_cypher, run_cypher, driver.close


def _make_local_runners():
    """무의존 로컬 KG backend (engine/kg_local) → (run, write, close). neo4j 불필요.

    occam/hades/eureka가 외부 neo4j 없이 로컬 JSON KG(~/.bhgman/kg.json) 위에서 돈다.
    KG: bhgman-local-kg-backend-2026-05-28.
    """
    store_mod = _load_engine_module("kg_local", "store")
    runner_mod = _load_engine_module("kg_local", "runner")
    store = store_mod.LocalKgStore()
    run = runner_mod.make_local_runner(store)
    return run, run, (lambda: None)


def _resolve_kg_runners(args: argparse.Namespace):
    """--local 또는 BHGMAN_KG=local 이면 로컬 backend, 아니면 neo4j. (run, write, close) | None."""
    if getattr(args, "local", False) or os.environ.get("BHGMAN_KG") == "local":
        return _make_local_runners()
    return make_kg_runners()


def cmd_occam(args: argparse.Namespace) -> int:
    """오캄 — KG SourceCodeNode dedup pass. dry-run 기본, --apply로 SUPERSEDED write (reversible)."""
    occam_runner = _load_occam_runner()
    runners = _resolve_kg_runners(args)

    if runners is None:
        from kg_adapter import fetch_cypher  # noqa: PLC0415

        cypher, _ = fetch_cypher(args.scope)
        print(
            "[occam] neo4j unavailable (set NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD, or run via "
            "parent Claude MCP). fetch cypher below → occam_pass → supersede:",
            file=sys.stderr,
        )
        print(cypher)
        return 2

    run_cypher, write_cypher, close = runners
    # 디스크-aware 기본 ON (sha-이동/orphan 탐지). --no-disk-scan으로 끔(KG-only).
    repo_root = None if getattr(args, "no_disk_scan", False) else str(_repo_root())
    try:
        res = occam_runner.run_occam(
            run_cypher,
            write_cypher=write_cypher,
            scope=args.scope,
            apply=args.apply,
            repo_root=repo_root,
        )
    finally:
        close()

    print(res.summary)
    if res.apply_result.dry_run:
        for i, (_cy, pa) in enumerate(res.apply_result.planned_cyphers, 1):
            print(f"  [plan {i}] supersede {pa['stale_name']} → {pa['current_name']}")
        if res.report.superseded_count:
            print("  (dry-run — pass --apply to write SUPERSEDED; reversible via status+edge)")
    elif res.apply_result.superseded:
        print(f"  applied: {', '.join(res.apply_result.superseded)}")
    if res.report.orphan_count:
        print(
            f"  disk-orphans (flag-only, machloket 보존 — supersede 안 함, Longinus/사용자 판단): "
            f"{res.report.orphan_count}"
        )
        for o in res.report.orphans:
            print(f"    [orphan] {o.name} @ {o.source_path}")
    return 0


def _load_engine_module(subdir: str, module: str, evict: tuple[str, ...] = ()):
    """Lazy-import a flat-layout engine module with its dir on sys.path[0].

    Sibling subsystems share bare module names (e.g. occam + eureka both ship
    `oracle_lens.py`). `evict` drops stale cached names from sys.modules so the
    bare import re-resolves to *this* subdir. CLI runtime is one-command-per-process
    (no collision), but the same-process pytest session needs the eviction.
    KG: ap-bhgman-longinus-import-drift-fix-2026-05-15 (flat-layout bridge).
    """
    import importlib  # noqa: PLC0415

    engine_dir = _repo_root() / "engine" / subdir
    sys.path.insert(0, str(engine_dir))
    for name in evict:
        cached = sys.modules.get(name)
        if (
            cached is not None
            and getattr(cached, "__file__", "")
            and str(engine_dir) not in cached.__file__
        ):
            del sys.modules[name]
    return importlib.import_module(module)


def cmd_hades(args: argparse.Namespace) -> int:
    """하데스 — ACCEPTED 추상을 KG에 실현(CANONICAL+INSTANCE_OF). dry-run 기본, --apply로 write."""
    hades_runner = _load_engine_module("hades", "hades_runner")
    runners = _resolve_kg_runners(args)
    if runners is None:
        from hades_runner import fetch_accepted_cypher  # noqa: PLC0415

        cypher, _ = fetch_accepted_cypher(args.concept)
        print(
            "[hades] neo4j unavailable (set NEO4J_*, or run via parent Claude MCP). "
            "ACCEPTED 추상 fetch cypher below → realize:",
            file=sys.stderr,
        )
        print(cypher)
        return 2

    run_cypher, write_cypher, close = runners
    try:
        res = hades_runner.run_hades(
            run_cypher, apply_cypher=write_cypher, concept=args.concept, apply=args.apply
        )
    finally:
        close()

    print(res.summary)
    for v in res.verdicts:
        print(f"  [{v.status.value}] {v.concept}: {v.reason}")
    if res.dry_run and res.verdicts:
        print("  (dry-run — pass --apply to materialize; reversible via undo ops)")
    return 0


def cmd_eureka(args: argparse.Namespace) -> int:
    """유레카 — KG 패턴→추상 개념 induce (PROPOSE only). covenant: auto-commit 금지, 실현은 하데스."""
    import datetime as _dt  # noqa: PLC0415

    pipeline = _load_engine_module("eureka", "pipeline", evict=("oracle_lens",))
    runners = _resolve_kg_runners(args)
    if runners is None:
        print(
            "[eureka] neo4j unavailable (set NEO4J_*, or run via parent Claude MCP). "
            "eureka reads KG to build a formal context — no live connection to scan.",
            file=sys.stderr,
        )
        return 2

    run_cypher, _write, close = runners
    eureka_stages = _load_engine_module("eureka", "stages")
    cycle_id = "cli-" + _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
    cfg = pipeline.PipelineConfig(
        cycle_id=cycle_id, **eureka_stages.wire_default_stages(run_cypher)
    )
    try:
        pr = pipeline.run_from_kg(run_cypher, cfg)
    finally:
        close()

    for s in pr.stages:
        status = "ok" if s.ok else "FAIL"
        print(f"  [{status}] {s.stage}")
    print(
        "[eureka] PROPOSE only — candidates surfaced; materialize via 하데스 + 나생문 gate (no auto-commit)."
    )
    return 0


def cmd_kg_schema(args: argparse.Namespace) -> int:
    """KG 스키마(코드) 출력 / Neo4j 부트스트랩 DDL emit. neo4j 없이도 schema 코드가 정본."""
    schema = _load_engine_module("kg_local", "schema")
    if args.emit == "neo4j":
        for line in schema.neo4j_ddl():
            print(line)
        return 0
    print("# bhgman_tool KG schema (in-code — local backend + Neo4j 공용 단일 정의)")
    for name, s in schema.NODE_SCHEMAS.items():
        print(f"  ({name})  key={s.key}  required={list(s.required)}  unique={list(s.unique)}")
    print(f"  edges: {sorted(schema.EDGE_TYPES)}")
    print("\n  → neo4j 부트스트랩: bhgman-tool kg-schema --emit neo4j | cypher-shell")
    print("  → neo4j 없이 실행:  bhgman-tool <occam|hades|eureka> --local")
    return 0


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
    p_inst.add_argument(
        "--dry-run", action="store_true", help="Show what would happen, don't write."
    )
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

    p_prom = sub.add_parser("prom", help="프로메테우스 리서치 (런타임 실행 / 없으면 skill route).")
    p_prom.add_argument("N", type=int, help="Sub-question 수 (병렬 서브에이전트).")
    p_prom.add_argument("topic", nargs="+", help="Research topic.")
    p_prom.add_argument("--no-web", action="store_true", help="web_search 끄기 (LLM 지식만).")
    p_prom.add_argument("--route", action="store_true", help="실행 대신 SKILL.md 경로만 출력.")
    p_prom.set_defaults(func=cmd_prom)

    p_tlb = sub.add_parser("tlb", help="나생문 ensemble critic (런타임 실행 / 없으면 skill route).")
    p_tlb.add_argument("target", nargs="+", help="검증 대상 식별자 (SPAN/CONTRACT/claim 이름).")
    p_tlb.add_argument(
        "--lens", help="단일 lens (constitutional / mathematical / solid). 생략=3중."
    )
    p_tlb.add_argument("--claim", help="검증할 주장/산출물 텍스트 (생략 시 target을 사용).")
    p_tlb.add_argument("--route", action="store_true", help="실행 대신 SKILL.md 경로만 출력.")
    p_tlb.set_defaults(func=cmd_tlb)

    p_long = sub.add_parser(
        "longinus", help="Longinus reference binding (sha256/ged/reverse-scan)."
    )
    p_long.add_argument(
        "op", nargs="+", help="Operation: sha256 / ged / reverse-scan / <freeform>."
    )
    p_long.set_defaults(func=cmd_longinus)

    p_lfloat = sub.add_parser(
        "longinus-floating",
        help="Floating concept-node scan — concept nodes with no binding to source (local KG).",
    )
    p_lfloat.set_defaults(func=cmd_longinus_floating)

    p_hns = sub.add_parser("harness", help="하네스 3계층/4축 진단 (결정론 엔진). --route=skill.")
    p_hns.add_argument("action", nargs="+", help="진단 대상 (프레임워크명 또는 설명 텍스트).")
    p_hns.add_argument("--route", action="store_true", help="진단 대신 SKILL.md 경로만 출력.")
    p_hns.add_argument(
        "--apply", action="store_true", help="진단을 KG(:HarnessDiagnosis)에 persist."
    )
    p_hns.add_argument("--no-disk-scan", action="store_true", help=argparse.SUPPRESS)
    p_hns.add_argument(
        "--local", action="store_true", help="KG persist에 로컬 KG 사용 (--apply과 함께)."
    )
    p_hns.set_defaults(func=cmd_harness)

    p_st = sub.add_parser("status", help="KG audit (ssh dgx → cypher-shell).")
    p_st.set_defaults(func=cmd_status)

    p_oc = sub.add_parser(
        "occam",
        help="오캄 KG dedup — superseded/dup SourceCodeNode archive (dry-run default, --apply to write).",
    )
    p_oc.add_argument(
        "--scope", help="Restrict to nodes whose sourcePath CONTAINS this (label/path)."
    )
    p_oc.add_argument(
        "--apply",
        action="store_true",
        help="Write SUPERSEDED (reversible). Omit = dry-run (covenant: archive-only).",
    )
    p_oc.add_argument(
        "--no-disk-scan",
        action="store_true",
        help="KG-only (mode-1 same-path dedup). Default scans disk for moved-node/orphan detection.",
    )
    p_oc.add_argument(
        "--local",
        action="store_true",
        help="Use the bundled neo4j-free local KG (~/.bhgman/kg.json) instead of Neo4j.",
    )
    p_oc.set_defaults(func=cmd_occam)

    p_hd = sub.add_parser(
        "hades",
        help="하데스 — ACCEPTED 추상을 KG에 실현 (CANONICAL+INSTANCE_OF). dry-run default, --apply to write.",
    )
    p_hd.add_argument(
        "--concept", help="Realize only this AbstractClass name (default: all ACCEPTED)."
    )
    p_hd.add_argument(
        "--apply",
        action="store_true",
        help="Materialize (reversible via undo). Omit = dry-run (c6 danger guard).",
    )
    p_hd.add_argument(
        "--local",
        action="store_true",
        help="Use the bundled neo4j-free local KG (~/.bhgman/kg.json) instead of Neo4j.",
    )
    p_hd.set_defaults(func=cmd_hades)

    p_eu = sub.add_parser(
        "eureka",
        help="유레카 — KG 패턴→추상 개념 induce (PROPOSE only, no write; materialize via hades).",
    )
    p_eu.add_argument(
        "--local",
        action="store_true",
        help="Use the bundled neo4j-free local KG (~/.bhgman/kg.json) instead of Neo4j.",
    )
    p_eu.set_defaults(func=cmd_eureka)

    p_ks = sub.add_parser(
        "kg-schema",
        help="Print the in-code KG schema (node/edge defs) or emit Neo4j bootstrap DDL.",
    )
    p_ks.add_argument(
        "--emit",
        choices=["summary", "neo4j"],
        default="summary",
        help="summary = human view; neo4j = CREATE CONSTRAINT DDL to bootstrap a fresh Neo4j.",
    )
    p_ks.set_defaults(func=cmd_kg_schema)

    # ─── SYMPOSIUM resolver/gate verbs (Wave 7 P3-H, 2026-05-14) ──────────
    p_rs = sub.add_parser(
        "resolver",
        help="APT v27 A6 pre-prompt resolver (render | validate). 9 pytest absorbed.",
    )
    p_rs.add_argument(
        "passthrough",
        nargs=argparse.REMAINDER,
        help="Args forwarded to engine.resolver.resolver (render --input X --output Y | validate <path>).",
    )
    p_rs.set_defaults(func=cmd_resolver)

    p_gt = sub.add_parser(
        "gate",
        help="APT v27 A7 fail-closed gate endpoint (serve | check). 6 pytest absorbed.",
    )
    p_gt.add_argument(
        "passthrough",
        nargs=argparse.REMAINDER,
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
