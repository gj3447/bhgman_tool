"""bhgman_tool CLI — subcommand handlers (cmd_*). Split out of main.py 2026-06-01."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from pathlib import Path

from engine.cli.runtime import (
    _repo_root,
    _verify_engine,
    _verify_lean,
    _route_skill,
    _agent_runtime,
    _load_occam_runner,
    _resolve_kg_runners,
    make_kg_runners,
    _load_engine_module,
)


try:  # derive from installed dist metadata; no manual sync with pyproject
    PACKAGE_VERSION = _pkg_version("bhgman_tool")
except PackageNotFoundError:  # source checkout (not pip-installed) — no dist metadata
    PACKAGE_VERSION = "0.1.0+source"


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

    Degrades gracefully in a wheel-only install: the PyPI wheel ships ``engine/``
    only, so ``skills/`` + ``worked/`` (and thus ``_repo_root()``) are absent — we
    still print the version and a clear note instead of a RuntimeError traceback.
    """
    print(f"bhgman-tool {PACKAGE_VERSION}")
    try:
        root = _repo_root()
    except RuntimeError:
        print("  layout: wheel-only install (engine/ only — skills/ + lean/ not bundled)")
        print("  for full layout + install-skills/verify, clone the source repo")
        print("  layer: tool (Airplane Man #4 engineering crystallization)")
        return 0

    def _subdirs(name: str) -> list[str]:
        d = root / name
        return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []

    skills, engine_subs, worked = _subdirs("skills"), _subdirs("engine"), _subdirs("worked")
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


def cmd_apt(args: argparse.Namespace) -> int:
    """APT cycle dispatch (SA → SP → ST → SCW). --status nav / --gated runtime / else skill route."""
    if getattr(args, "status", False):
        return _cmd_apt_status(args)
    if getattr(args, "gated", False):
        if args.task:
            return _cmd_apt_task_gated(args)
        return _cmd_apt_gated(args)
    if not args.task:
        print(
            "usage: bhgman-tool apt <task>  |  apt --status --target <SA>  |  "
            "apt --gated [--target <SA>] [--ground-truth CMD]  |  apt <task> --gated [--ground-truth CMD]",
            file=sys.stderr,
        )
        return 2
    return _route_skill("apt", args.task)


def _cmd_apt_task_gated(args: argparse.Namespace) -> int:
    """Gated general-task attempt — produce → adversarially review → G1/G2/G3 (item ⑤ general half).

    OVER-CLAIM GUARD: no cognitive-quality claim. The model's measured advantage is ~0; this only
    certifies the attempt is reproducible (hashed) + audited (reviewed) + oracle-correct (G3).
    """
    from engine.legion.gated_task import run_task_gated  # noqa: PLC0415

    task = " ".join(args.task) if isinstance(args.task, list) else str(args.task)
    agents, reason = _agent_runtime()
    if agents is None:
        print(
            f"[apt <task> --gated] LLM runtime unavailable ({reason}). Set ANTHROPIC_API_KEY or "
            "BHGMAN_LLM_BASE_URL. It would: produce an artifact → adversarially review → gate "
            "G1/G2/G3 (operational verification, NOT a cognitive-quality claim).",
            file=sys.stderr,
        )
        return 2
    client = agents.AgentClient()
    model = os.environ.get("BHGMAN_LLM_MODEL", "claude-sonnet-4-6")

    def produce(t: str) -> str:
        return client.complete(
            system="Attempt the task. Output only the artifact (code or answer), no preamble.",
            user=t,
            model=model,
        ).text

    def adversary(t: str, artifact: str) -> dict:
        try:
            verdict = client.complete(
                system="Adversarial reviewer. Reply 'REJECT: <reason>' if the artifact fails the "
                "task, else 'ACCEPT'.",
                user=f"Task: {t}\n\nArtifact:\n{artifact}",
                model=model,
            ).text
        except Exception as exc:  # noqa: BLE001
            return {"ran": False, "detail": str(exc)[:120]}
        return {
            "ran": True,
            "rejected": verdict.strip().upper().startswith("REJECT"),
            "detail": verdict.strip()[:120],
        }

    res = run_task_gated(
        task, produce, adversary_fn=adversary, ground_truth_cmd=getattr(args, "ground_truth", None)
    )
    print(f"[apt <task> --gated] {task[:60]}")
    marks = {"PASS": "✓", "FAIL": "✗", "SKIPPED": "–"}
    for g in res.gates:
        print(f"  {marks.get(g.status, '?')} {g.name}: {g.status} — {g.detail}")
    print(f"  artifact sha256: {res.artifact_sha256[:16]}…")
    if res.verified:
        print(
            "  VERIFIED ✓ (operational gate — reproducible + audited + oracle-green; NOT a quality claim)"
        )
    else:
        print("  NOT VERIFIED (fail-closed: not all gates PASS)")
    return 0 if res.verified else 1


def _cmd_apt_status(args: argparse.Namespace) -> int:
    """Phase navigation — which APT phase a project (or every active SA) is at + what runs next (⑤)."""
    from engine.legion.phase_detect import detect_all, detect_phase  # noqa: PLC0415

    runners = _resolve_kg_runners(args)
    if runners is None:
        print(
            "[apt --status] neo4j unavailable — set NEO4J_*, or run via parent Claude MCP.",
            file=sys.stderr,
        )
        return 2
    run_cypher, _write, close = runners
    target = getattr(args, "target", None)
    try:
        if target:
            status = detect_phase(target, run_cypher)
            print(f"[apt --status] {target}")
            print(f"  phase   : {status.phase}")
            print(f"  next    : {status.next_skill}")
            print(f"  evidence: {status.evidence}")
            if status.phase == "UNKNOWN":
                print(
                    "  (backend could not answer — local KG lacks SA chain; navigation needs neo4j.)"
                )
            return 0 if status.phase != "UNKNOWN" else 1
        # no target → navigate every active SA
        rows = detect_all(run_cypher)
    finally:
        close()
    if not rows:
        print(
            "[apt --status] no active SemanticAnchor reachable (local KG lacks SA chain; needs neo4j)."
        )
        return 1
    print(f"[apt --status] {len(rows)} active SemanticAnchor(s):")
    from collections import Counter  # noqa: PLC0415

    tally: Counter = Counter()
    for name, st in rows:
        tally[st.phase] += 1
        print(f"  {st.phase:20s} {name}  → {st.next_skill}")
    print("  ── phase tally: " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    return 0


def _cmd_apt_gated(args: argparse.Namespace) -> int:
    """`apt run` runtime — closed legion loop + G1/G2/G3 verify-by-default, fail-closed.

    Operational verdict (reproducible / audited / oracle-correct), NOT a cognitive claim (~0).
    # KG: project-apt-ultracode-roadmap-2026-06-02 (item ⑤)
    """
    from engine.legion.commanders import build_default_legion  # noqa: PLC0415
    from engine.legion.gated_run import run_gated  # noqa: PLC0415

    runners = _resolve_kg_runners(args)
    if runners is None:
        print(
            "[apt --gated] neo4j unavailable — use --local for the bundled KG, set NEO4J_*, "
            "or run via parent Claude MCP.",
            file=sys.stderr,
        )
        return 2
    run_cypher, write_cypher, close = runners
    ctx = {"run_cypher": run_cypher, "write_cypher": write_cypher, "apply": False}
    target = getattr(args, "target", None)
    try:
        if target:
            from engine.legion.phase_detect import detect_phase  # noqa: PLC0415

            ph = detect_phase(target, run_cypher)
            print(f"[apt --gated] {target} phase={ph.phase} (next {ph.next_skill}) — {ph.evidence}")
        result = run_gated(
            build_default_legion(), ctx, ground_truth_cmd=getattr(args, "ground_truth", None)
        )
    finally:
        close()

    run = result.legion_run
    print(f"[apt --gated] legion completed={run.completed} ran={run.ran}/6 stages")
    marks = {"PASS": "✓", "FAIL": "✗", "SKIPPED": "–"}
    for g in result.gates:
        print(f"  {marks.get(g.status, '?')} {g.name}: {g.status} — {g.detail}")
    print(f"  artifact sha256: {result.artifact_sha256[:16]}…")
    if result.verified:
        print("  VERIFIED ✓ (G1∧G2∧G3 all PASS) — reproducible + audited + oracle-green artifact.")
    else:
        print(
            "  NOT VERIFIED (fail-closed: not all gates PASS) — operational gate, not a quality claim."
        )
    return 0 if result.verified else 1


def cmd_tpa(args: argparse.Namespace) -> int:
    """TPA reverse cycle (TCW → ST → SP → TA). Routes to skills/tpa/SKILL.md."""
    if not args.path:
        print("usage: bhgman-tool tpa <path>", file=sys.stderr)
        return 2
    return _route_skill("tpa", args.path)


_BACKEND_HINT = (
    "        백엔드 선택:\n"
    "          • 로컬 LLM (key 불필요): export BHGMAN_LLM_BASE_URL=<openai-compat URL> "
    "BHGMAN_LLM_MODEL=<model>\n"
    "          • Anthropic:              export ANTHROPIC_API_KEY=<key>"
)


def _grounding_source(args: argparse.Namespace):
    """LLM 군단장 KG-input 접지원 build → (source | None, close).

    --no-ground → (None, noop). --local 또는 BHGMAN_KG=local → 로컬 store backed.
    그 외 → neo4j run_cypher backed (불가하면 None, graceful 무접지).
    KG: canon-kg-based-coding-essence-2026-05-28, KGFirstCheck_v1.
    """
    noop = lambda: None  # noqa: E731
    if getattr(args, "no_ground", False):
        return None, noop
    import importlib  # noqa: PLC0415

    grounding_mod = importlib.import_module("engine.agents.grounding")
    if getattr(args, "local", False) or os.environ.get("BHGMAN_KG") == "local":
        store_mod = _load_engine_module("kg_local", "store")
        return grounding_mod.LocalGroundingSource(store_mod.LocalKgStore()), noop
    runners = make_kg_runners()
    if runners is None:
        return None, noop
    run_cypher, _write, close = runners
    return grounding_mod.Neo4jGroundingSource(run_cypher), close


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
    source, close = _grounding_source(args)
    if source is None and not getattr(args, "no_ground", False):
        print(
            "[prom] KG 접지원 없음 (neo4j 미가용; --local 또는 BHGMAN_KG=local 권장) → 무접지 실행.",
            file=sys.stderr,
        )
    try:
        report = agents.research(
            topic, args.N, agents.AgentClient(), web_search=not args.no_web, grounding=source
        )
    finally:
        close()
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
    source, close = _grounding_source(args)
    if source is None and not getattr(args, "no_ground", False):
        print(
            "[tlb] KG 접지원 없음 (neo4j 미가용; --local 또는 BHGMAN_KG=local 권장) → 무접지 비평.",
            file=sys.stderr,
        )
    try:
        verdict = agents.critique(
            target, args.claim or target, agents.AgentClient(), lenses=lenses, grounding=source
        )
    finally:
        close()
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
    # `bind` = forward materializer: # KG: comments → ReferenceSite (the missing
    # creation step; sha256/ged/reverse-scan only AUDIT). Reuses audit_runner's
    # tested --materialize path against live neo4j (NEO4J_* env). repo_tag default
    # 'bhgman'; override with `longinus bind <repo_tag>`.
    if op == "bind":
        repo_tag = rest[0] if rest else "bhgman"
        # code-root override: `longinus bind <repo_tag> <code-root>` to materialize
        # another repo's `# KG:` comments (default = this bhgman repo).
        code_root = rest[1] if len(rest) > 1 else str(root)
        # Prefer the MCP gateway when configured (bolt-firewalled KG); else bolt.
        kg = "mcp" if os.environ.get("BHGMAN_KG_MCP_URL") else "neo4j"
        cmd = [
            sys.executable,
            "-m",
            "engine.longinus_drift_audit.audit_runner",
            "--code-root",
            code_root,
            "--kg",
            kg,
            "--materialize",
            "--repo-tag",
            repo_tag,
        ]
        return subprocess.call(cmd)
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


def _resolve_status_creds() -> tuple[str, str, str, float]:
    """Resolve Neo4j connection params for `status` from env (BHGMAN_STATUS_* → NEO4J_* → default)."""
    uri = os.environ.get("BHGMAN_STATUS_NEO4J_URI") or os.environ.get(
        "NEO4J_URI", "bolt://100.64.0.3:7687"
    )
    user = os.environ.get("BHGMAN_STATUS_NEO4J_USER") or os.environ.get("NEO4J_USER", "neo4j")
    password = (
        os.environ.get("BHGMAN_STATUS_NEO4J_PASSWORD")
        or os.environ.get("NEO4J_PASSWORD")
        or os.environ.get("SYMPOSIUM_KG_PASSWORD")
        or "neo4jpassword"
    )
    timeout_s = float(os.environ.get("BHGMAN_STATUS_TIMEOUT", "10"))
    return uri, user, password, timeout_s


def _try_local_cypher_shell(uri: str, user: str, password: str, timeout_s: float) -> int | None:
    """Attempt the KG audit via a local cypher-shell. Return 0 on success, None to fall through."""
    cypher_shell = shutil.which("cypher-shell")
    if not cypher_shell:
        print(
            "[bhgman-tool] WARN: cypher-shell not found; falling back to ssh dgx", file=sys.stderr
        )
        return None
    print(f"[bhgman-tool] cypher-shell {uri} — KG audit", file=sys.stderr)
    cmd = [cypher_shell, "-a", uri, "-u", user, "-p", password, "--format", "plain"]
    try:
        result = subprocess.run(
            cmd,
            input=_STATUS_CYPHER,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(
            f"[bhgman-tool] WARN: direct cypher-shell timeout after {timeout_s}s", file=sys.stderr
        )
        return None
    if result.returncode == 0:
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return 0
    print(
        f"[bhgman-tool] WARN: direct cypher-shell failed rc={result.returncode}; "
        "falling back to ssh dgx",
        file=sys.stderr,
    )
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return None


def cmd_status(_args: argparse.Namespace) -> int:
    """KG audit via local cypher-shell first, then ssh dgx → kubectl fallback."""
    uri, user, password, timeout_s = _resolve_status_creds()
    local_rc = _try_local_cypher_shell(uri, user, password, timeout_s)
    if local_rc is not None:
        return local_rc

    dgx_host = os.environ.get("SYMPOSIUM_DGX_HOST", "dgx")
    namespace = os.environ.get("BHGMAN_STATUS_K8S_NAMESPACE") or os.environ.get(
        "BHGMAN_K8S_NAMESPACE", "data"
    )
    pod = os.environ.get("BHGMAN_STATUS_NEO4J_POD") or os.environ.get("BHGMAN_NEO4J_POD", "neo4j-0")
    print(f"[bhgman-tool] ssh {dgx_host} cypher-shell — KG audit", file=sys.stderr)
    cmd = [
        "ssh",
        dgx_host,
        f"kubectl exec -n {shlex.quote(namespace)} {shlex.quote(pod)} -- "
        f"cypher-shell -u {shlex.quote(user)} -p {shlex.quote(password)} --format plain",
    ]
    try:
        result = subprocess.run(
            cmd, input=_STATUS_CYPHER, text=True, timeout=timeout_s, check=False
        )
        return result.returncode
    except FileNotFoundError:
        print("[bhgman-tool] FAIL: ssh not available — install OpenSSH client", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print(f"[bhgman-tool] FAIL: timeout — ssh {dgx_host} unreachable", file=sys.stderr)
        return 2


# 의미론 dedup 대상 라벨 → (key prop, 텍스트 필드들). cypher 라벨 주입 차단 allowlist.
_SEMANTIC_TARGETS: dict[str, tuple[str, tuple[str, ...]]] = {
    "ResearchFinding": ("findingId", ("oneLineSummary", "name", "finding")),
    "Lesson": ("name", ("name", "description", "wrongAssumption", "truth")),
}


def cmd_naesengmoon_audit(args: argparse.Namespace) -> int:
    """나생문 truth-렌즈 (결정론) — axiom-audit + falsifiability routing.

    "일관성"과 "참"의 간극을 드러낸다: Lean 정리는 *선언된 공리 위 일관성*을 증명하지 공리가
    참임을 증명하지 않는다(공리는 선택). LLM 아님 — grep/import-graph 위상만.
    # KG: 외부 리뷰 tension #1 + #4
    """
    from engine.naesengmoon.axiom_audit import audit_lean_dir, check_claim  # noqa: PLC0415
    from engine.naesengmoon.falsifiability import classify  # noqa: PLC0415

    lean_dir = getattr(args, "lean", None) or str(_repo_root() / "lean")
    report = audit_lean_dir(lean_dir)
    print(report.summary)
    for p in report.profiles:
        if p.axioms or p.sorry_in_proof:
            tag = "AXIOM-RESTING" if p.stem in report.tainted else "free"
            print(f"  {p.stem}: axioms={list(p.axioms)} theorems={p.theorems} [{tag}]")
    claimed = getattr(args, "claimed", None)
    if claimed is not None:
        print(f"  claim-check: {check_claim(report, claimed)}")
    claim = getattr(args, "classify", None)
    if claim:
        c = classify(claim)
        print(f"\nfalsifiability routing for: {c.claim!r}")
        print(f"  class={c.claim_class}  truth_apt={c.truth_apt}")
        print(f"  oracle (NOT the author's LLM): {c.oracle}")
        print(f"  cheapest falsifier: {c.cheapest_falsifier}")
    return 0


def cmd_occam_semantic(args: argparse.Namespace) -> int:
    """오캄 의미론 near-dup — 텍스트 노드 임베딩 cosine ≥ θ 쌍을 supersede 후보로 surface.

    sha256-blind 자리(패러프레이즈 중복)를 임베딩으로 메움. dry-run 기본, --apply로 write.
    θ는 모델 의존 — 번들 all-MiniLM은 paraphrase ≈ 0.6-0.75 (near-identical만 보려면 ↑).
    # KG: rf-semdist-occam-2026-06-01
    """
    runners = _resolve_kg_runners(args)
    if runners is None:
        print(
            "[occam-semantic] neo4j unavailable (set NEO4J_*, --local, or parent Claude MCP). "
            "의미론 dedup은 텍스트 노드를 KG에서 읽어 임베딩한다.",
            file=sys.stderr,
        )
        return 2
    run_cypher, write_cypher, close = runners
    label = getattr(args, "label", None) or "ResearchFinding"
    if label not in _SEMANTIC_TARGETS:
        print(f"[occam-semantic] label must be one of {list(_SEMANTIC_TARGETS)}", file=sys.stderr)
        close()
        return 2
    key, fields = _SEMANTIC_TARGETS[label]
    coalesce = "coalesce(" + ", ".join(f"n.{f}" for f in fields) + ", '')"
    cypher = (
        f"MATCH (n:{label}) WHERE (n.status IS NULL OR n.status <> 'SUPERSEDED') "
        f"AND {coalesce} <> '' "
        f"RETURN n.{key} AS id, {coalesce} AS text ORDER BY id LIMIT $limit"
    )
    try:
        try:
            rows = run_cypher(cypher, {"limit": getattr(args, "limit", 200)})
        except Exception as e:  # noqa: BLE001 — local backend는 임의 MATCH 미지원 → 정직 degrade
            print(
                f"[occam-semantic] backend가 텍스트-노드 스캔 쿼리를 미지원 ({type(e).__name__}). "
                "의미론 dedup은 neo4j(또는 parent Claude MCP)가 필요하다 — local KG는 고정 템플릿만 처리.",
                file=sys.stderr,
            )
            return 2
        items = [(str(r["id"]), str(r["text"])) for r in rows if r.get("id")]
        from engine.memory.embedder import Embedder  # noqa: PLC0415
        from engine.occam.semantic_dedup import run_semantic_dedup  # noqa: PLC0415

        emb = Embedder()
        if (
            getattr(args, "apply", False)
            and not emb.is_real_model
            and not getattr(args, "allow_hash_embed", False)
        ):
            print(
                "[occam-semantic] REFUSING --apply: the sentence-transformers model is "
                "unavailable, so the hash-fallback embedder is active — its cosine "
                "similarities are meaningless and superseding on them would archive nodes "
                "at random. Install the real model (pip install 'bhgman-tool[memory]') or "
                "pass --allow-hash-embed to override (NOT recommended).",
                file=sys.stderr,
            )
            return 1
        report = run_semantic_dedup(
            items,
            embed_fn=lambda texts: [emb.encode(t) for t in texts],
            threshold=getattr(args, "threshold", 0.75),
            key=key,
            write_cypher=write_cypher,
            apply=getattr(args, "apply", False),
        )
    finally:
        close()
    print(report.summary)
    for p in report.pairs[:40]:
        print(f"  {p.similarity:.3f}  keep={p.keep_id}  drop={p.drop_id}")
    if report.dry_run and report.pairs:
        print("  (dry-run — pass --apply to supersede; reversible via status+SUPERSEDED_BY edge)")
    return 0


def cmd_occam(args: argparse.Namespace) -> int:
    """오캄 — KG SourceCodeNode dedup pass. dry-run 기본, --apply로 SUPERSEDED write (reversible)."""
    if getattr(args, "semantic", False):
        return cmd_occam_semantic(args)
    occam_runner = _load_occam_runner()
    runners = _resolve_kg_runners(args)

    if runners is None:
        from engine.occam.kg_adapter import fetch_cypher  # noqa: PLC0415

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


def _oracle_kg_client(args: argparse.Namespace):  # noqa: ANN202
    """drift-recount용 KgClient 구성 (--local=JSON / BHGMAN_KG_MCP_URL=mcp / NEO4J_*=neo4j)."""
    from engine.longinus_drift_audit.audit_runner import build_kg  # noqa: PLC0415

    mode = (
        "local"
        if getattr(args, "local", False)
        else ("mcp" if os.environ.get("BHGMAN_KG_MCP_URL") else "neo4j")
    )
    ns = argparse.Namespace(
        kg=mode,
        kg_path=None,
        mcp_url=os.environ.get("BHGMAN_KG_MCP_URL"),
        uri=os.environ.get("NEO4J_URI"),
        user=os.environ.get("NEO4J_USER"),
        password=os.environ.get("NEO4J_PASSWORD"),
    )
    return build_kg(ns)


def cmd_oracle(args: argparse.Namespace) -> int:
    """결정론 검증 substrate — artifact를 4 oracle 중 하나로 검증 (추론기가 호출하는 표면).

    exit 0 = passed(건전), 1 = failed, 2 = KG 미가용. 루프 아닌 *검증*이 bhgman 정체성 (verdict 2026-06-04).
    """
    from engine.naesengmoon.verify import verify  # noqa: PLC0415

    kind = args.kind
    close = None
    kwargs: dict = {}
    if kind == "lean-goals":
        kwargs = {"lean_dir": args.lean_dir}
    elif kind == "pytest-ratio":
        kwargs = {}
    elif kind == "drift-recount":
        kwargs = {"code_root": args.code_root, "kg": _oracle_kg_client(args)}
    elif kind == "occam-twins":
        runners = _resolve_kg_runners(args)
        if runners is None:
            print(
                "[oracle] occam-twins needs a KG (NEO4J_* / BHGMAN_KG_MCP_URL, or --local).",
                file=sys.stderr,
            )
            return 2
        run_cypher, _w, close = runners
        kwargs = {"run_cypher": run_cypher, "scope": args.scope}

    try:
        v = verify(kind, args.target, **kwargs)
    finally:
        if close is not None:
            close()

    if getattr(args, "json", False):
        print(json.dumps(v.__dict__, ensure_ascii=False))
    else:
        status = "PASS" if v.passed else "FAIL"
        print(f"[{v.kind}] {v.target}: {status} (score={v.score}) - {v.detail}")
    return 0 if v.passed else 1


def cmd_export_prov(args: argparse.Namespace) -> int:
    """W3C PROV-O export — ResearchFinding → prov:Entity Turtle (provenance interchange).

    Delegates to engine.provexport.prov_export:main (own argparse: cycle_id, --format,
    --findings-json, --out). Lets a research cycle's findings leave the KG as a standard
    nanopub/PROV graph instead of a bespoke dump. KG: prov-o-nanopub-export-2026-05-30.
    """
    try:
        from engine.provexport.prov_export import main as prov_main
    except ImportError as e:
        print(
            f"[bhgman-tool] FAIL: engine.provexport not importable — install provexport extra "
            f"(`uv pip install -e '.[provexport]'` → prov, rdflib, lxml): {e}",
            file=sys.stderr,
        )
        return 2
    return prov_main(args.passthrough or [])


def _extract_superclass_candidates(root: Path) -> list[tuple[str, str, list[str], dict[str, str]]]:
    """Scan a dir/file for class pairs sharing a structurally-identical non-dunder
    method (Extract-Superclass candidates). Returns (a, b, shared_methods, {name: src})."""
    import ast  # noqa: PLC0415
    from itertools import combinations  # noqa: PLC0415

    from engine.hades.extract_superclass import common_methods  # noqa: PLC0415

    files = sorted(root.rglob("*.py")) if root.is_dir() else [root]
    classes: dict[str, tuple] = {}
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            continue
        for n in tree.body:
            if isinstance(n, ast.ClassDef):
                classes[n.name] = (n, ast.get_source_segment(text, n) or "")
    out: list[tuple[str, str, list[str], dict[str, str]]] = []
    for a, b in combinations(sorted(classes), 2):
        shared = [
            m for m in common_methods([classes[a][0], classes[b][0]]) if not m.startswith("__")
        ]
        if shared:
            out.append((a, b, shared, {a: classes[a][1], b: classes[b][1]}))
    return out


def _cmd_hades_apply(args: argparse.Namespace) -> int:
    """Gated apply: rewrite the first same-file candidate iff --test-cmd still passes."""
    import shlex  # noqa: PLC0415

    from engine.hades.hades_apply import apply_extract_superclass_gated  # noqa: PLC0415

    root = Path(args.extract_superclass)
    if not root.is_file():
        print("[hades] --apply needs --extract-superclass to be a single file", file=sys.stderr)
        return 2
    if not args.test_cmd:
        print("[hades] --apply needs --test-cmd (the characterization gate)", file=sys.stderr)
        return 2
    candidates = _extract_superclass_candidates(root)
    if not candidates:
        print(f"[hades] no Extract-Superclass candidate in {root}")
        return 0
    a, b, shared, _ = candidates[0]
    res = apply_extract_superclass_gated(
        root, f"{a}{b}Base", [a, b], test_cmd=shlex.split(args.test_cmd)
    )
    print(f"[hades] apply {a}~{b} (lift {shared}) → {res.status}: {res.reason}")
    return 1 if res.status == "REVERTED" else 0


def cmd_hades_extract_superclass(args: argparse.Namespace) -> int:
    """하데스 코드 실현 — 디렉터리에서 구조-동일 공통 메서드 클래스 찾아 Extract-Superclass
    패치 생성. PLAN 기본. --apply + --test-cmd 시 characterization-gate apply. neo4j 불필요."""
    from engine.hades.extract_superclass import (  # noqa: PLC0415
        extract_superclass,
        extract_superclass_cst,
    )

    if args.apply:
        return _cmd_hades_apply(args)

    root = Path(args.extract_superclass)
    if not root.exists():
        print(f"[hades] path not found: {root}", file=sys.stderr)
        return 2
    engine_fn = extract_superclass_cst if args.preserve_format else extract_superclass
    candidates = _extract_superclass_candidates(root)
    print(f"[hades] extract-superclass scan under {root}: {len(candidates)} candidate(s)")
    for a, b, shared, sources in candidates:
        patch = engine_fn(f"{a}{b}Base", sources)
        if patch is None:
            continue
        print(f"  • {a} ~ {b}: lift {list(patch.common_methods)} → new shared base")
        if args.show_patch:
            print("\n".join(f"      {ln}" for ln in patch.unified_diff.splitlines()))
    if not candidates:
        print("  (none — no two classes share a structurally-identical non-dunder method)")
    print("  (PLAN only — covenant: apply 전 characterization test 필수)")
    return 0


def cmd_hades(args: argparse.Namespace) -> int:
    """하데스 — ACCEPTED 추상을 KG에 실현(CANONICAL+INSTANCE_OF). dry-run 기본, --apply로 write."""
    if getattr(args, "extract_superclass", None):
        return cmd_hades_extract_superclass(args)
    hades_runner = _load_engine_module("hades", "hades_runner")
    runners = _resolve_kg_runners(args)
    if runners is None:
        from engine.hades.hades_runner import fetch_accepted_cypher  # noqa: PLC0415

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


def _now_iso() -> str:
    """ISO-8601 UTC timestamp for provenance (researched_at, etc.)."""
    import datetime as _dt  # noqa: PLC0415

    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def cmd_acquire(args: argparse.Namespace) -> int:
    """프로메테우스 결정론 엔진 — 경계축 ingest (gap→query→fetch→parse→ingest).

    LLM 불필요 (그건 `prom`). fetcher 미주입 CLI에선 gap+query surface + PROPOSE cypher.
    실제 fetch ingest는 fetcher 주입(legion --llm 대체 / 프로그램적) 시. dry-run 기본.
    # KG: project-legion-unification-kg-engine-2026-06-01
    """
    from engine.prometheus import run_acquire  # noqa: PLC0415

    runners = _resolve_kg_runners(args)
    if runners is None:
        print(
            "[acquire] neo4j unavailable (set NEO4J_*, --local, or run via parent Claude MCP). "
            "엔진은 KG에서 gap(OpenQuestion/VerdictPending)을 읽어 쿼리를 도출한다.",
            file=sys.stderr,
        )
        return 2
    run_cypher, write_cypher, close = runners
    fetcher = None
    if getattr(args, "web", False):
        from engine.prometheus import WebSearchFetcher  # noqa: PLC0415

        fetcher = WebSearchFetcher()
    if getattr(args, "apply", False) and fetcher is None:
        print(
            "[acquire] --apply ignored: no fetcher wired (nothing to ingest). Pass --web to "
            "fetch real findings, or inject a fetcher programmatically.",
            file=sys.stderr,
        )
    try:
        report = run_acquire(
            run_cypher,
            fetcher=fetcher,
            write_cypher=write_cypher,
            cycle_id=getattr(args, "cycle_id", None) or "acquire-cli",
            apply=getattr(args, "apply", False),
            gap_limit=getattr(args, "gap_limit", 50),
            researched_at=_now_iso(),
        )
    finally:
        close()
    print(report.summary)
    for q in report.queries[:20]:
        print(f"  gap={q.gap_id} → query: {q.text}")
    if report.dry_run and report.planned_cyphers:
        print(
            f"  (PROPOSE: {len(report.planned_cyphers)} planned MERGE — pass --apply + --web to write)"
        )
    return 0


def cmd_legion(args: argparse.Namespace) -> int:
    """레기온 — 6 군단장 통일 닫힌 루프 (획득→연결→창조→정리→검증→실현) 1회 실행.

    결정론 코어가 floor (neo4j/local KG만으로 동작) + LLM은 선택적 enrichment(--llm).
    각 군단장이 동일 CommanderStage 인터페이스로 Contract-bound handoff. dry-run 기본.
    # KG: adr-seven-commander-legion-architecture-2026-05-27, bihaenggiman-legioncommanders-2026-05-26
    """
    runners = _resolve_kg_runners(args)
    if runners is None:
        print(
            "[legion] neo4j unavailable (set NEO4J_*, or --local for the bundled KG, "
            "or run via parent Claude MCP). The closed loop reads KG per stage.",
            file=sys.stderr,
        )
        return 2
    run_cypher, write_cypher, close = runners

    ctx: dict = {
        "run_cypher": run_cypher,
        "write_cypher": write_cypher,
        "apply": getattr(args, "apply", False),
        "scope": getattr(args, "scope", None),
        "concept": getattr(args, "concept", None),
        "topic": " ".join(args.topic) if getattr(args, "topic", None) else None,
        "repo_root": None if getattr(args, "no_disk_scan", False) else str(_repo_root()),
        "researched_at": _now_iso(),
    }
    if getattr(args, "web", False):
        from engine.prometheus import WebSearchFetcher  # noqa: PLC0415

        ctx["fetcher"] = WebSearchFetcher()  # 결정론 획득 코어에 실제 웹 fetcher 주입
    close_g = lambda: None  # noqa: E731
    if getattr(args, "llm", False):
        agents, reason = _agent_runtime()
        if agents is None:
            print(
                f"[legion] --llm 요청했으나 LLM runtime 불가 ({reason}) → 결정론 코어로 진행.",
                file=sys.stderr,
            )
        else:
            source, close_g = _grounding_source(args)
            ctx.update(agents=agents, client=agents.AgentClient(), grounding=source)

    # 재배맨 substrate 경유 (정전: 재배맨=출격=Legion.run 루프). planner+lifecycle+telemetry load-bearing.
    import datetime as _dt  # noqa: PLC0415

    from engine.legion.jaebaeman_substrate import run_legion_via_jaebaeman  # noqa: PLC0415

    run_id = "legion-" + _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
    try:
        result = run_legion_via_jaebaeman(
            ctx, run_id=run_id, write_cypher=write_cypher, apply=getattr(args, "apply", False)
        )
    finally:
        close()
        close_g()
    run, lc, rec = result["legion_run"], result["lifecycle"], result["run_record"]

    if run.contract_violation:
        print(f"[legion] CONTRACT VIOLATION: {run.contract_violation}", file=sys.stderr)
        return 1
    if run.gate_failure:
        print(f"[legion] ORACLE GATE FAIL: {run.gate_failure}", file=sys.stderr)
    for oc in run.outcomes:
        mark = "ok" if oc.ok else "FAIL"
        print(f"  [{mark}] {oc.verb} ({oc.stage}): {oc.detail}")
    print(
        f"[legion] {'completed' if run.completed else 'halted'} — {run.ran}/6 stages, "
        f"keys={list(run.final_context_keys)}"
    )
    print(
        f"[재배맨 substrate] {rec.run_id}: dispatched={len(lc.outcomes)} "
        f"collected={lc.collected} failed={lc.failed} (planner→lifecycle→record)"
    )
    return 0 if run.completed else 1


def _resolve_cycle_id(args: argparse.Namespace) -> str:
    """--cycle-id 있으면 그것, 없으면 per-invocation 유니크 default — cross-run 발아 scope 격리.

    plant + germinate가 *같은* cycle_id를 공유해야 발아가 이번 run의 씨앗만 본다 (footgun 방지).
    """
    explicit = getattr(args, "cycle_id", None)
    if explicit:
        return explicit
    import datetime as _dt  # noqa: PLC0415

    return "jaebaeman-cli-" + _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")


def _maybe_germinate(
    args: argparse.Namespace, run_cypher, write_cypher, cycle_id: str, res
) -> None:
    """--germinate면 발아 단계 실행. 실패 격리 — 발아 오류가 이미 성공한 plant을 죽이지 않는다."""
    if not getattr(args, "germinate", False) or res.violations:
        return
    if run_cypher is None:
        print("[jaebaeman] --germinate는 KG가 필요하다 (--local 또는 NEO4J_*).", file=sys.stderr)
        return
    try:
        _germinate_after_plant(args, run_cypher, write_cypher, cycle_id)
    except Exception as e:  # noqa: BLE001 — 발아 실패 격리 (plant은 이미 성공)
        print(
            f"[jaebaeman] 발아 실패 (격리됨, plant은 성공): {type(e).__name__}: {e}",
            file=sys.stderr,
        )


def _germinate_after_plant(
    args: argparse.Namespace, run_cypher, write_cypher, cycle_id: str
) -> None:
    """발아: 심긴 READY 씨앗을 LLM subagent로 출격(동작)시킨다 — 씨앗→발아→동작 핸드오프.

    --apply 없으면 dispatch 미실행(LLM 비용 0) + 발아 대기 씨앗 수만 보고(true dry-run). --apply면
    실 LLM 출격 + status write. LLM runtime 없으면 graceful skip(계획/씨앗은 이미 성공).
    # KG: finding-jaebaeman-seed-dispatch-handoff-unwired-2026-06-07 (read-back+dispatch 배선)
    """
    from engine.jaebaeman.jaebaeman_runner import germinate_ready_seeds  # noqa: PLC0415
    from engine.jaebaeman.lifecycle import agent_dispatcher  # noqa: PLC0415

    limit = getattr(args, "germinate_limit", None)
    if not getattr(args, "apply", False):  # true dry-run: dispatch 미실행
        lc = germinate_ready_seeds(lambda _s: [], run_cypher, cycle_id=cycle_id, limit=limit)
        print(f"[jaebaeman 발아] {' / '.join(lc.notes)}")
        return
    agents, reason = _agent_runtime()
    if agents is None:
        print(f"[jaebaeman] 발아 skip — LLM runtime 사용 불가 ({reason}).", file=sys.stderr)
        print(_BACKEND_HINT, file=sys.stderr)
        return
    lc = germinate_ready_seeds(
        agent_dispatcher(agents.AgentClient()),
        run_cypher,
        cycle_id=cycle_id,
        write_cypher=write_cypher,
        apply=True,
        limit=limit,
    )
    print(f"[jaebaeman 발아] {lc.summary}")
    for o in lc.outcomes:
        mark = "ok" if o.status.value == "COLLECTED" else "FAIL"
        print(f"    [{mark}] {o.seed_name}: {o.detail[:80]}")


def cmd_jaebaeman(args: argparse.Namespace) -> int:
    """재배맨 — 계획→씨앗 결정화. 목표를 계획 트리로 unfold하고 SubagentTaskSpec 씨앗으로 심는다.

    "씨앗 심기 = 계획 짜기"(사용자 정전 2026-06-01). dry-run 기본(planned만), --apply로 MERGE write.
    --anchor 주면 KG 구조에서 하위 계획을 연쇄 unfold, 없으면 단일 루트 씨앗. neo4j/--local 둘 다.
    # KG: jaebaeman-planfirst-essence-reframe-2026-05-27, 재배맨-v2-subagent-runtime-protocol
    """
    if not args.goal:
        print("usage: bhgman-tool jaebaeman <goal> [--anchor NAME] [--apply]", file=sys.stderr)
        return 2
    from engine.jaebaeman.jaebaeman_models import Goal  # noqa: PLC0415
    from engine.jaebaeman.jaebaeman_runner import run_jaebaeman  # noqa: PLC0415

    goal_text = " ".join(args.goal)
    goal_name = getattr(args, "name", None) or goal_text[:60]
    goal = Goal(
        name=goal_name,
        objective=goal_text,
        task_type=getattr(args, "task_type", None) or "research",
        target_domain=getattr(args, "domain", None) or "",
        anchor=getattr(args, "anchor", None),
    )

    run_cypher = write_cypher = None
    close = lambda: None  # noqa: E731
    runners = _resolve_kg_runners(args)
    if runners is not None:
        run_cypher, write_cypher, close = runners
    elif getattr(args, "apply", False) or getattr(args, "anchor", None):
        print(
            "[jaebaeman] neo4j unavailable (set NEO4J_*, --local, or run via parent Claude MCP). "
            "--apply/--anchor는 KG가 필요하다. 무KG 단일-루트 dry-run은 인자 없이.",
            file=sys.stderr,
        )
        return 2

    cycle_id = _resolve_cycle_id(args)  # plant + germinate가 공유 (per-run scope)
    try:
        res = run_jaebaeman(
            goal,
            run_cypher=run_cypher,
            write_cypher=write_cypher,
            skill=getattr(args, "skill", None) or "jaebaeman",
            cycle_id=cycle_id,
            apply=getattr(args, "apply", False),
            max_depth=getattr(args, "depth", 3),
            coinductive=getattr(args, "coinductive", False),
            fuel=getattr(args, "fuel", None),
        )
        _maybe_germinate(args, run_cypher, write_cypher, cycle_id, res)
    finally:
        close()

    print(res.summary)
    for s in res.seeds:
        indent = "  " * (s.depth + 1)
        print(f"{indent}[d{s.depth}] {s.name}  ({s.germination_method}) ← {s.source_id}")
    if res.violations:
        print(f"  ⚠ invariant gate BLOCKED ({len(res.violations)}) — write 차단 (fail-closed):")
        for v in res.violations:
            print(f"    [{v.code.value}] {v.seed_id}: {v.detail}")
        return 1
    if getattr(args, "record", False):
        _emit_run_record(res, runners=_resolve_kg_runners(args))
    if res.apply_result.dry_run and res.seeds:
        print("  (dry-run — pass --apply to plant seeds; MERGE-only, reversible/idempotent)")
    return 0


def _emit_run_record(res, runners) -> None:
    """production 표면 — 실행을 :JaebaemanRun(KG) + OTel attrs + PROV-O로 기록/출력."""
    import datetime as _dt  # noqa: PLC0415

    from engine.jaebaeman.telemetry import (  # noqa: PLC0415
        from_results,
        record_to_kg,
        to_otel_attributes,
        to_prov,
    )

    now = _dt.datetime.now(_dt.timezone.utc)
    run_id = "jbmrun-" + now.strftime("%Y%m%dT%H%M%S")
    rec = from_results(run_id, res, created_at=now.isoformat())
    print(f"  [record] run={run_id} otel={to_otel_attributes(rec)}")
    if runners is not None:
        _run, write, close = runners
        try:
            record_to_kg(rec, write)
            print(f"  [record] :JaebaemanRun persisted ({run_id})")
        finally:
            close()
    prov = to_prov(rec)
    print(f"  [record] PROV-O: {'turtle emitted' if prov else 'prov extra 미설치 (graceful skip)'}")


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
