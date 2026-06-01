"""bhgman_tool CLI — subcommand handlers (cmd_*). Split out of main.py 2026-06-01."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
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


PACKAGE_VERSION = "0.1.0"


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
        cmd = [
            sys.executable,
            "-m",
            "engine.longinus_drift_audit.audit_runner",
            "--code-root",
            str(root),
            "--kg",
            "neo4j",
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


def cmd_occam(args: argparse.Namespace) -> int:
    """오캄 — KG SourceCodeNode dedup pass. dry-run 기본, --apply로 SUPERSEDED write (reversible)."""
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


def cmd_legion(args: argparse.Namespace) -> int:
    """레기온 — 6 군단장 통일 닫힌 루프 (획득→연결→창조→정리→검증→실현) 1회 실행.

    결정론 코어가 floor (neo4j/local KG만으로 동작) + LLM은 선택적 enrichment(--llm).
    각 군단장이 동일 CommanderStage 인터페이스로 Contract-bound handoff. dry-run 기본.
    # KG: adr-seven-commander-legion-architecture-2026-05-27, bihaenggiman-legioncommanders-2026-05-26
    """
    from engine.legion.commanders import build_default_legion  # noqa: PLC0415

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
    }
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

    try:
        run = build_default_legion().run(context=ctx)
    finally:
        close()
        close_g()

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
    return 0 if run.completed else 1


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
