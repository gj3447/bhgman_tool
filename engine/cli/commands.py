"""bhgman_tool CLI — subcommand handlers (cmd_*). Split out of main.py 2026-06-01."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from pathlib import Path
from typing import Any

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
    try:
        src = _repo_root() / "skills"
    except RuntimeError:
        print(
            "[install-skills] FAIL: no source checkout (pip-installed wheel ships no skills/). "
            "Set SYMPOSIUM_ROOT to a checkout, or run from a git clone.",
            file=sys.stderr,
        )
        return 2
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
    try:
        root = _repo_root()
    except RuntimeError:
        print(
            "[verify] FAIL: no source checkout (pip-installed wheel ships no engine/ tests). "
            "Set SYMPOSIUM_ROOT to a checkout, or run from a git clone.",
            file=sys.stderr,
        )
        return 2
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
    # KG: ATOM_Skill_apt_orchestrator
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
            status = detect_phase(target, run_cypher, with_blockers=True)
            print(f"[apt --status] {target}")
            print(f"  phase   : {status.phase}")
            print(f"  next    : {status.next_skill}")
            print(f"  evidence: {status.evidence}")
            if status.blockers:
                print(f"  blockers: {len(status.blockers)} node(s) blocking {status.next_skill}")
                for b in status.blockers:
                    print(f"    - {b.node}: {b.reason}")
                if len(status.blockers) == 20:  # _BLOCKER_LIMIT; there may be more
                    print("    … (first 20 shown; close these to reveal the rest)")
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
    # KG: ATOM_Skill_tpa_orchestrator_v10
    """TPA reverse cycle. --status nav / --gated engine runtime / else skill route."""
    if getattr(args, "status", False):
        return _cmd_tpa_status(args)
    if getattr(args, "gated", False):
        return _cmd_tpa_gated(args)
    if not args.path:
        print(
            "usage: bhgman-tool tpa <path>  |  tpa <path> --gated  |  "
            "tpa --status --target <recovery-cycle>",
            file=sys.stderr,
        )
        return 2
    return _route_skill("tpa", args.path)


def _cmd_tpa_gated(args: argparse.Namespace) -> int:
    """Run the engine/tpa reverse legion loop over a path: TCW→ST→SP→TA (deterministic substrate).

    OVER-CLAIM GUARD: no cognitive-quality claim. This composes existing engines (code_to_kg
    extraction + longinus 5-drift) into the reversed Contract-bound loop; value is operational
    (reproducible extraction + audited handoff), per adr-apt-tpa-engine-substrate-scope-2026-06-14.
    """
    from engine.tpa import build_tpa_legion  # noqa: PLC0415

    if not args.path:
        print("[tpa --gated] need a <path> to reverse-engineer.", file=sys.stderr)
        return 2
    root = args.path[0] if isinstance(args.path, list) else args.path
    captured: dict = {}

    def _capture(ctx: dict) -> tuple[bool, str]:
        captured.update(ctx)
        return True, "ok"

    run = build_tpa_legion().run({"code_root": str(root)}, gate=_capture)
    print(f"[tpa --gated] reverse loop over {root}")
    for o in run.outcomes:
        if o.verb == "검증":
            continue  # the capture-gate's own bookkeeping row
        print(f"  {'✓' if o.ok else '✗'} {o.stage} ({o.verb}): {o.detail}")
    if run.contract_violation:
        print(f"  CONTRACT VIOLATION: {run.contract_violation}", file=sys.stderr)
        return 1
    for key in ("tcw_result", "contracts", "patterns", "drift_report"):
        node = captured.get(key) or {}
        if node.get("summary"):
            print(f"  · {node['summary']}")
    print(
        "  (deterministic substrate — reproducible extraction + audited handoff, NOT a quality claim)"
    )
    return 0 if run.completed else 1


def _cmd_tpa_status(args: argparse.Namespace) -> int:
    """Reverse phase navigation — which TPA phase a recovery target is at + what runs next."""
    from engine.tpa import detect_reverse_phase  # noqa: PLC0415

    target = getattr(args, "target", None)
    if not target:
        print("[tpa --status] need --target <recovery-cycle name>.", file=sys.stderr)
        return 2
    runners = _resolve_kg_runners(args)
    if runners is None:
        print(
            "[tpa --status] neo4j unavailable — set NEO4J_*, or run via parent Claude MCP.",
            file=sys.stderr,
        )
        return 2
    run_cypher, _write, close = runners
    try:
        status = detect_reverse_phase(target, run_cypher)
    finally:
        close()
    print(f"[tpa --status] {target}")
    print(f"  phase   : {status.phase}")
    print(f"  next    : {status.next_skill}")
    print(f"  evidence: {status.evidence}")
    return 0 if status.phase != "UNKNOWN" else 1


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
    # KG: ATOM_Skill_prometheus
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
        from engine.agents.client import _local_base_url  # noqa: PLC0415

        # 로컬 DGX/vLLM 백엔드면 web_search 강제 OFF: Anthropic server-side tool 부재 /
        # SearXNG ReAct 직렬 round-trip 세금 → K-샘플링 전 하드 전제(hygiene).
        web = (not args.no_web) and not _local_base_url()
        kwargs: dict = {"web_search": web, "grounding": source}
        k = getattr(args, "k", None)
        if k is not None:
            kwargs["k"] = k
        # L4/L5/L6 노브 — None(미지정)이면 env 기본을 research() 가 그대로 쓴다.
        depth = getattr(args, "depth", None)
        if depth is not None:
            kwargs["depth"] = depth
        hard_axes = getattr(args, "hard_axes", None)
        if hard_axes is not None:
            kwargs["hard_axes"] = hard_axes
        if getattr(args, "verify", False):
            kwargs["verify"] = True
        report = agents.research(topic, args.N, agents.AgentClient(), **kwargs)
    finally:
        close()
    print(report.summary)
    print("\n" + report.synthesis)
    return 0


def cmd_tlb(args: argparse.Namespace) -> int:
    # KG: naesengmoon-canonical-2026-05-19
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
    # KG: ATOM_Skill_longinus
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
    # KG: ATOM_Skill_harness
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
    # KG: ATOM_Skill_longinus
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
    # No hard-coded default password (W4): shipping `neo4jpassword` is a weak default + it
    # ended up on the cypher-shell argv (visible in `ps`). Empty → cypher-shell fails auth
    # clearly; the password is passed via env (NEO4J_PASSWORD), never argv.
    password = (
        os.environ.get("BHGMAN_STATUS_NEO4J_PASSWORD")
        or os.environ.get("NEO4J_PASSWORD")
        or os.environ.get("SYMPOSIUM_KG_PASSWORD")
        or ""
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
    # password via env (NEO4J_PASSWORD), NOT `-p` on argv → not visible in `ps` (W4).
    cmd = [cypher_shell, "-a", uri, "-u", user, "--format", "plain"]
    env = {**os.environ, "NEO4J_PASSWORD": password}
    try:
        result = subprocess.run(
            cmd,
            input=_STATUS_CYPHER,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            env=env,
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
    # bhg-f-secrets-on-argv: 비밀번호는 argv 금지 — stdin 첫 줄로 전달해 pod 안 sh 가
    # NEO4J_PASSWORD 로 export (cypher-shell 이 그 env 를 인식). mcp_server _ssh_cypher 와
    # 동일 패턴 — 적대검증 2026-07-15 이 두 자매 호출부 중 여기가 미수복임을 지적.
    # `kubectl exec -i` 필수: -i 없이는 stdin 이 pod 에 도달하지 않는다.
    inner = (
        "IFS= read -r NEO4J_PASSWORD; export NEO4J_PASSWORD; "
        f"exec cypher-shell -u {shlex.quote(user)} --format plain"
    )
    cmd = [
        "ssh",
        dgx_host,
        f"kubectl exec -i -n {shlex.quote(namespace)} {shlex.quote(pod)} -- "
        f"sh -c {shlex.quote(inner)}",
    ]
    try:
        result = subprocess.run(
            cmd,
            input=f"{password}\n{_STATUS_CYPHER}",
            text=True,
            timeout=timeout_s,
            check=False,
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
    # KG: naesengmoon-canonical-2026-05-19
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
    # KG: occam-kam-canonical-2026-05-26
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
            label=label,  # H5: supersede MATCH 를 스캔한 노드 라벨로 스코핑 (bare-name over-supersede 차단)
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
    # covenant: byte-identity 없는 의미론 중복은 단독 supersede 금지 → 항상 나생문 검증으로 escalate.
    # (build_escalation_plan(semantic_pairs=)이 라우팅을 이미 구현 — CLI만 호출 안 하던 dead seam.)
    if report.pairs:
        from engine.occam.escalation import build_escalation_plan  # noqa: PLC0415
        from engine.occam.occam_models import OccamReport  # noqa: PLC0415

        plan = build_escalation_plan(OccamReport(), semantic_pairs=report.pairs)
        if plan.count:
            print(f"  {plan.summary}")
            for it in plan.items:
                print(f"    [escalate→{it.target}] {it.subject}: {it.command}")
    return 0


def cmd_occam(args: argparse.Namespace) -> int:
    # KG: occam-kam-canonical-2026-05-26
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
    # surface the continuous σ + per-candidate verdict occam computes (was invisible on every
    # surface — only the writer read candidate.score). σ is the archive-safety value (높을수록 안전).
    for c in res.report.candidates:
        if c.score is not None:
            ident = c.stale.name or c.stale.source_path
            print(f"  σ={c.score:.2f} verdict={c.verdict} conf={c.confidence.value}  {ident}")
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
    # σ-gate deferred (auto-apply 안 한 불확실 후보) + escalation routing — CLI/MCP/legion
    # parity: MCP·legion은 summarize_occam_result로 이미 노출, CLI도 같은 plan을 띄운다.
    deferred = res.apply_result.deferred
    if deferred:
        print(f"  deferred (σ-gate 미확신 → escalation, auto-apply 안 함): {len(deferred)}")
        for d in deferred:
            print(f"    [defer] {d}")
    from engine.occam.escalation import build_escalation_plan  # noqa: PLC0415

    plan = build_escalation_plan(res.report)
    if plan.count:
        print(f"  {plan.summary}")
        for it in plan.items:
            print(f"    [escalate→{it.target}] {it.subject}: {it.command}")
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
        user=os.environ.get("NEO4J_USERNAME") or os.environ.get("NEO4J_USER"),
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
        # repo_root enables disk-aware (mode-2/3) twin detection (W3-F); default to the
        # repo unless --no-disk-scan.
        repo_root = None if getattr(args, "no_disk_scan", False) else str(_repo_root())
        kwargs = {"run_cypher": run_cypher, "scope": args.scope, "repo_root": repo_root}
    elif kind == "kg-corroborate":
        # separate-source corroboration of --target (the claim) against canonical KG facts.
        if getattr(args, "local", False):
            store_mod = _load_engine_module("kg_local", "store")
            kwargs = {"kg": store_mod.LocalKgStore()}
        else:
            runners = _resolve_kg_runners(args)
            if runners is None:
                print(
                    "[oracle] kg-corroborate needs a KG (NEO4J_* / BHGMAN_KG_MCP_URL, or --local).",
                    file=sys.stderr,
                )
                return 2
            run_cypher, _w, close = runners
            kwargs = {"run_cypher": run_cypher}

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
    # KG: hades-canonical-2026-05-27
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
    # KG: hades-canonical-2026-05-27
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
    # KG: ATOM_Skill_prometheus
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


def _consume_pathkey_selftest() -> bool:
    """R2′ 속성 게이트의 술어: 이 체크아웃의 파일 경로가 occam KG 키로 정규화되는가.

    normalize_path 가 repo 세그먼트(bhgman_tool[-wt-*])를 못 찾는 체크아웃(무규약 클론)에서
    apply-모드 janitor 를 공유 KG 에 물리면, occam 이 KG 키와 다른 세계를 보고 재실행된다 —
    그 조합만 거부한다 (블랭킷 --local 강제의 정직한 후속, seam-integrity 2026-07-10)."""
    from engine.occam.occam import normalize_path  # noqa: PLC0415

    probe = str(_repo_root() / "engine" / "__probe__.py")
    return normalize_path(probe) == "engine/__probe__.py"


def cmd_legion(args: argparse.Namespace) -> int:
    # KG: adr-seven-commander-legion-architecture-2026-05-27
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
    # T0-3 정방향 패리티: cycle_id 스탬프 → :DispatchEvent.cycle_id 가 null 이 되지 않는다.
    # verdict_gate leg 는 store-backed ledger 필요 — neo4j/MCP runner 는 store 를 노출하지 않으므로
    # (make_kg_runners 는 (run,write,close)만 반환) 여기선 cycle_id 패리티만. store-less ledger =
    # 별개 follow-up(q-legion-cli-verdict-ledger). MCP legion 툴과 동일 헬퍼.
    from engine.legion.verdict_gate import prepare_forward_ctx  # noqa: PLC0415

    prepare_forward_ctx(ctx)
    if getattr(args, "web", False):
        from engine.prometheus.web import make_web_fetcher  # noqa: PLC0415

        # SearXNG self-host(BHGMAN_SEARXNG_URL) 있으면 그것, 없으면 DDG fallback
        ctx["fetcher"] = make_web_fetcher()
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
    consume = getattr(args, "consume_dispatch", False)
    # R2′ 속성 게이트 (seam-integrity 2026-07-10): 옛 블랭킷 금지("--local 에서만")의 명시
    # 전제였던 normalize_path 워크트리 결함이 착지로 소멸 — fail-closed 정신은 *능력 속성*
    # 체크로 보존한다: 이 체크아웃의 경로가 KG 키로 정규화되지 않으면(무규약 클론 등) 공유 KG
    # apply-모드 소비를 여전히 거부. 미래에 체크아웃 규약이 깨지면 자동으로 다시 닫힌다.
    if consume and getattr(args, "apply", False) and not getattr(args, "local", False):
        if not _consume_pathkey_selftest():
            print(
                "[legion] 이 체크아웃 경로는 KG 키로 정규화 불가 — 공유 KG apply 소비 거부 "
                "(R2′ 속성 게이트: bhgman_tool[-wt-*] 규약 체크아웃에서 실행하라).",
                file=sys.stderr,
            )
            return 2
    consume_report = None
    try:
        result = run_legion_via_jaebaeman(
            ctx, run_id=run_id, write_cypher=write_cypher, apply=getattr(args, "apply", False)
        )
        if consume:
            # G5-C5 post-run 소비 — runner 가 닫히기 전(try 안)에 실행해야 한다.
            from engine.legion.dispatch_consumer import consume_dispatch  # noqa: PLC0415

            consume_report = consume_dispatch(result["legion_run"].dispatch_decisions, ctx)
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
    # T1-2 dispatch_errors 소비 (적대검증 2026-07-15): 실명화해 놓고 아무도 안 읽으면
    # 이 시리즈가 닫겠다던 emit-without-consume 을 그대로 재생산한다.
    for err in run.dispatch_errors:
        print(f"  [dispatch-error] {err}", file=sys.stderr)
    print(
        f"[legion] {'completed' if run.completed else 'halted'} — {run.ran}/6 stages, "
        f"keys={list(run.final_context_keys)}"
    )
    print(
        f"[재배맨 substrate] {rec.run_id}: dispatched={len(lc.outcomes)} "
        f"collected={lc.collected} failed={lc.failed} (planner→lifecycle→record)"
    )
    if consume_report is not None:
        for r in consume_report.all_records:
            print(
                f"  [consume:{r.status}] {r.decision.source_commander}→"
                f"{r.decision.target_commander} {r.decision.metric_name} "
                f"depth={r.decision.depth} children={r.child_decision_count}"
                + (f" outcome={r.outcome}" if r.outcome is not None else "")
            )
        print(
            f"[dispatch consume] executed={len(consume_report.executed)} "
            f"skipped={len(consume_report.skipped)} "
            f"depth_capped={len(consume_report.depth_capped)} "
            f"failed={len(consume_report.failed)} (G5-C5 post-run, allowlist·depth-capped)"
        )
    return 0 if run.completed else 1


def cmd_bot(args: argparse.Namespace) -> int:
    # KG: bhgman-bot-daemon-2026-06-16
    """bhgman 봇 — legion 닫힌루프 백그라운드 자율 데몬 (vLLM 추론 + KG + SearXNG + 하네스).

    moltbot 류 self-hosted 자율 에이전트의 bhgman 판. 각 tick = topic 선택 → legion run
    (획득→연결→창조→정리→검증→실현) → KG read/write. 하네스 = legion Contract+oracle gate.
    --once 검증 / --interval N 주기 / --max-ticks N / --topics rot / --llm vLLM / --web SearXNG.
    # KG: bhgman-bot-daemon-2026-06-16
    """
    from engine.legion.daemon import BotConfig, run_bot  # noqa: PLC0415

    runners = _resolve_kg_runners(args)
    if runners is None:
        print(
            "[bot] neo4j unavailable (set NEO4J_*, or --local). 봇은 KG 기반이라 KG 필수.",
            file=sys.stderr,
        )
        return 2
    run_cypher, write_cypher, close = runners

    fetcher = None
    agents = client = grounding = None
    close_g = lambda: None  # noqa: E731
    if getattr(args, "web", False):
        from engine.prometheus.web import make_web_fetcher  # noqa: PLC0415

        fetcher = make_web_fetcher()  # SearXNG(self-host) 우선, 없으면 DDG
    if getattr(args, "llm", False):
        agents, reason = _agent_runtime()
        if agents is None:
            print(
                f"[bot] --llm 요청했으나 LLM runtime 불가 ({reason}) → 결정론 코어로 진행.",
                file=sys.stderr,
            )
        else:
            grounding, close_g = _grounding_source(args)
            client = agents.AgentClient()

    import datetime as _dt  # noqa: PLC0415

    from engine.legion.jaebaeman_substrate import run_legion_via_jaebaeman  # noqa: PLC0415
    from engine.legion.verdict_gate import prepare_forward_ctx  # noqa: PLC0415

    apply = getattr(args, "apply", False)

    def build_ctx(topic: str) -> dict:
        ctx: dict = {
            "run_cypher": run_cypher,
            "write_cypher": write_cypher,
            "apply": apply,
            "scope": getattr(args, "scope", None),
            "concept": None,
            "topic": topic,
            "repo_root": None if getattr(args, "no_disk_scan", False) else str(_repo_root()),
            "researched_at": _now_iso(),
        }
        if fetcher is not None:
            ctx["fetcher"] = fetcher
        if agents is not None and client is not None:
            ctx.update(agents=agents, client=client, grounding=grounding)
        # T0-3 정방향 패리티: bot 도 CLI/MCP 와 동일 헬퍼 경유. build_ctx 는 tick 마다 호출되고
        # 매 tick = 별개 사이클이므로 여기서 mint 하면 tick 별 고유 cycle_id 가 된다 (ledger
        # false-collision 방지 — MCP 의 서버-mint 와 같은 이유). 상시 데몬의 :DispatchEvent 가
        # 전부 cycle_id=null 로 쌓이던 결손 봉합.
        prepare_forward_ctx(ctx)
        return ctx

    def run_tick(ctx: dict, _topic: str) -> dict:
        run_id = "bot-" + _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
        return run_legion_via_jaebaeman(ctx, run_id=run_id, write_cypher=write_cypher, apply=apply)

    def pick_work() -> str | None:
        try:
            rows = run_cypher(
                "MATCH (n) WHERE n.name IS NOT NULL "
                "AND (n:OpenQuestion OR n:Concept OR n:OntologyClass) "
                "RETURN n.name AS topic ORDER BY coalesce(n.created_at,'') DESC LIMIT 1",
                {},
            )
        except Exception:  # noqa: BLE001 — pick 실패 → idle
            return None
        if rows and isinstance(rows, list) and isinstance(rows[0], dict):
            return rows[0].get("topic")
        return None

    cfg = BotConfig(
        interval=float(getattr(args, "interval", 300)),
        max_ticks=1 if getattr(args, "once", False) else getattr(args, "max_ticks", None),
        topics=tuple(getattr(args, "topics", None) or ()),
        apply=apply,
    )
    try:
        results = run_bot(build_ctx=build_ctx, run_tick=run_tick, cfg=cfg, pick_work=pick_work)
    finally:
        close()
        close_g()
    completed = sum(1 for r in results if r.completed)
    print(f"[bot] done — {completed}/{len(results)} ticks completed")
    return 0


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


def _jaebaeman_decompose(
    method: str | None,
    run_cypher,
    *,
    llm_complete=None,
    task_type: str = "research",
):
    # KG: LakatosTree_BhgmanJaebaeman_20260702/jbm_s6_orphan_wire_or_prune
    # KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01
    """--method → (DecomposeFn|None, 사용자 표시용 note|None). None = run_jaebaeman auto 규칙 위임.

    jbm-s6 G6 배선: kg-htn = htn.kg_method_decompose (HAS_METHOD/DECOMPOSES_TO method 계층),
    llm = llm_decompose (LLM=untrusted generator + 결정론 gate, C5 정전). llm runtime 부재 시
    결정론 fallback(kg_decompose|leaf)으로 *정직 강등* — 사유를 note로 반환 (무음 극장 금지).
    ``llm_complete`` 는 테스트/판정용 주입 seam (기본 = 실 AgentClient 어댑터).
    """
    if method in (None, "", "auto"):
        return None, None
    if method in ("kg", "kg-htn") and run_cypher is None:
        return None, (
            f"[jaebaeman] --method {method}는 KG가 필요 (NEO4J_* 또는 --local) → auto로 진행."
        )
    if method == "kg":
        from engine.jaebaeman.kg_adapter import kg_decompose  # noqa: PLC0415

        return kg_decompose(run_cypher, task_type=task_type), None
    if method == "kg-htn":
        from engine.jaebaeman.htn import kg_method_decompose  # noqa: PLC0415

        return kg_method_decompose(run_cypher, task_type=task_type), None
    if method == "llm":
        from engine.jaebaeman.llm_decompose import from_agent_client, llm_decompose  # noqa: PLC0415

        fallback = None
        if run_cypher is not None:
            from engine.jaebaeman.kg_adapter import kg_decompose  # noqa: PLC0415

            fallback = kg_decompose(run_cypher, task_type=task_type)
        complete = llm_complete
        if complete is None:
            agents, reason = _agent_runtime()
            if agents is None:
                return fallback, (
                    f"[jaebaeman] --method llm 요청했으나 LLM runtime 불가 ({reason}) → "
                    "결정론 fallback으로 정직 강등."
                )
            complete = from_agent_client(agents.AgentClient())
        return llm_decompose(complete, fallback=fallback, task_type=task_type), None
    return None, f"[jaebaeman] unknown --method {method!r} → auto로 진행."


def cmd_jaebaeman(args: argparse.Namespace) -> int:
    # KG: 재배맨-v2-subagent-runtime-protocol
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

    # jbm-s6 G6 배선: --method가 htn/llm_decompose를 production 경로로 라우팅.
    decompose, method_note = _jaebaeman_decompose(
        getattr(args, "method", "auto"),
        run_cypher,
        task_type=getattr(args, "task_type", None) or "research",
    )
    if method_note:
        print(method_note, file=sys.stderr)

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
            decompose=decompose,
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


def _eureka_code_snippets(args: argparse.Namespace) -> list[str]:
    snippets = list(getattr(args, "snippet", None) or [])
    code_file = getattr(args, "code_file", None)
    if not code_file:
        return snippets
    text = Path(code_file).read_text(encoding="utf-8")
    chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
    snippets.extend(
        chunks if len(chunks) > 1 else [line for line in text.splitlines() if line.strip()]
    )
    return snippets


def _print_eureka_code_result(result: dict[str, Any]) -> None:
    print(f"[eureka --code] status={result['status']} (PROPOSE only — 실현은 하데스)")
    if result.get("template"):
        print(f"  template: {result['template']}")
    for key in ("holes", "hole_ratio", "instances", "reason", "note"):
        if key in result:
            print(f"  {key}: {result[key]}")


def _cmd_eureka_code(args: argparse.Namespace) -> int:
    """eureka code-template path (Plotkin LGG anti-unification) — neo4j-free, PROPOSE-only.

    Lifts a shared template from ≥min-instances near-identical snippets (Rule of Three). Disjoint
    from the KG-induction path (which still needs neo4j); Extract-Superclass materialize는 하데스 소관.
    """
    from engine.eureka.anti_unify import propose_template  # noqa: PLC0415

    snippets = _eureka_code_snippets(args)
    if not snippets:
        print(
            "[eureka --code] no snippets — pass --snippet ... (repeat) or --code-file FILE",
            file=sys.stderr,
        )
        return 2
    result = propose_template(snippets, min_instances=getattr(args, "min_instances", 3))
    _print_eureka_code_result(result)
    return 0


def _eureka_preflight(args: argparse.Namespace) -> int | None:
    if getattr(args, "accept", False):
        print(
            "[eureka] --accept refused: external human/Naesengmoon verdict ingress not "
            "implemented; use --creative --apply for VERDICT_PENDING",
            file=sys.stderr,
        )
        return 2
    code_mode = bool(getattr(args, "code", False))
    if code_mode and getattr(args, "creative", False):
        print("[eureka] --code cannot be combined with --creative", file=sys.stderr)
        return 2
    if not code_mode and (
        getattr(args, "creative_rounds", 2) < 1 or getattr(args, "creative_limit", 3) < 1
    ):
        print("[eureka] creative budgets must be positive", file=sys.stderr)
        return 2
    return None


def _eureka_cycle_id() -> str:
    import datetime as _dt  # noqa: PLC0415

    return "cli-" + _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S")


def _eureka_creative_enricher(
    args: argparse.Namespace,
    cycle_id: str,
    close: Callable[[], None],
) -> tuple[Any | None, int | None]:
    if not getattr(args, "creative", False):
        return None, None

    agents, reason = _agent_runtime()
    if agents is None:
        close()
        print(f"[eureka --creative] agent runtime unavailable: {reason}", file=sys.stderr)
        return None, 2
    from engine.eureka.creative import (  # noqa: PLC0415
        AgentCreativeProposer,
        AgentProposalCritic,
        CreativeEnricher,
        CreativeLoopConfig,
    )

    try:
        client = agents.AgentClient()
    except Exception as error:  # noqa: BLE001 — optional runtime boundary, fail closed
        close()
        print(
            f"[eureka --creative] agent client initialization failed: {error}",
            file=sys.stderr,
        )
        return None, 2
    creative_rounds = int(getattr(args, "creative_rounds", 2))
    enricher = CreativeEnricher(
        AgentCreativeProposer(client, session=f"{cycle_id}:proposer"),
        AgentProposalCritic(client, session=f"{cycle_id}:critic"),
        config=CreativeLoopConfig(
            max_rounds=creative_rounds,
            max_model_calls=max(2, 2 * creative_rounds),
        ),
        limit=getattr(args, "creative_limit", 3),
    )
    return enricher, None


def _eureka_stage_count(stages: list[Any], prefix: str, key: str) -> int:
    for stage in stages:
        if stage.stage.startswith(prefix) and isinstance(stage.payload, dict):
            return int(stage.payload.get(key, 0) or 0)
    return 0


def _eureka_stage(stages: list[Any], name: str) -> Any | None:
    return next((stage for stage in stages if stage.stage == name), None)


def _eureka_creative_stage_failed(stage: Any | None) -> bool:
    if stage is None:
        return False
    if isinstance(stage.payload, dict):
        outcomes = stage.payload.get("outcomes", [])
        return bool(isinstance(outcomes, (list, tuple, set)) and "FAILED" in outcomes)
    return bool(not stage.ok and stage.error)


def _eureka_execution_failed(pr: Any, *, persist: bool, creative: bool) -> bool:
    persist_stage = _eureka_stage(pr.stages, "6-persist")
    if persist and (persist_stage is None or not persist_stage.ok):
        return True
    validator_stage = _eureka_stage(pr.stages, "5.5-pre-merge-validator")
    if validator_stage is not None and not validator_stage.ok:
        return True
    return creative and _eureka_creative_stage_failed(
        _eureka_stage(pr.stages, "4.9-semantic-creative-loop")
    )


def _eureka_run_summary(pr: Any, *, persist: bool, creative: bool) -> dict[str, Any]:
    induced = _eureka_stage_count(pr.stages, "4-induce", "abstract_classes")
    proposed = len(getattr(pr, "proposals", []))
    if _eureka_execution_failed(pr, persist=persist, creative=creative):
        outcome, rc = "EXECUTION_FAILED", 3
    elif proposed == 0:
        outcome, rc = ("GATE_REJECTED" if induced else "NO_CANDIDATE"), 1
    else:
        outcome, rc = "PROPOSED", 0
    return {
        "induced": induced,
        "survived": _eureka_stage_count(pr.stages, "4.5-quality-gate", "survived"),
        "proposed": proposed,
        "persisted": _eureka_stage_count(pr.stages, "6-persist", "persisted"),
        "outcome": outcome,
        "rc": rc,
    }


def _eureka_candidate_payload(ac: Any, artifact: Any | None) -> dict[str, Any]:
    return {
        "candidate_id": ac.candidateDigest or ac.name,
        "candidate_digest": ac.candidateDigest,
        "concept_name": ac.semanticName or ac.name,
        "definition": ac.summary,
        "mechanism": ac.mechanism,
        "scope": ac.scope,
        "falsifier": ac.falsifier,
        "extent": ac.extent or [],
        "intent": ac.intent or [],
        "stability_score": ac.stabilityScore,
        "novelty_score": ac.noveltyScore,
        "validation_receipt_digest": ac.validationReceiptDigest,
        "status": ac.status.value,
        "source_layer": "SECONDARY_AI" if artifact else "STRUCTURAL_INDUCTION",
        "artifact": artifact,
    }


def _eureka_candidates(pr: Any) -> list[dict[str, Any]]:
    artifacts = {item["candidate_digest"]: item for item in getattr(pr, "creative_artifacts", [])}
    return [
        _eureka_candidate_payload(ac, artifacts.get(ac.candidateDigest or ""))
        for ac in getattr(pr, "proposals", [])
    ]


def _eureka_envelope(
    pr: Any,
    cfg: Any,
    *,
    cycle_id: str,
    creative: bool,
    persist: bool,
    summary: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": "bhgman.eureka.run.v1",
        "cycle_id": cycle_id,
        "outcome": summary["outcome"],
        "mode": "creative" if creative else "structural",
        "method": cfg.method,
        "earned": {key: summary[key] for key in ("induced", "survived", "proposed", "persisted")},
        "candidates": candidates,
        "validation_receipts": list(getattr(pr, "creative_receipts", [])),
        "stages": [
            {"name": stage.stage, "ok": bool(stage.ok), "error": stage.error} for stage in pr.stages
        ],
        "persistence": {
            "requested": persist,
            "verdict": "VERDICT_PENDING" if persist else None,
            "receipt_required": False,
        },
        "errors": [stage.error for stage in pr.stages if stage.error],
    }


def _print_eureka_details(pr: Any, candidates: list[dict[str, Any]]) -> None:
    for stage in pr.stages:
        status = "ok" if stage.ok else "FAIL"
        print(f"  [{status}] {stage.stage}")
    for candidate in candidates:
        print(f"  [proposal] {candidate['concept_name']}: {candidate['definition']}")
        if candidate["candidate_digest"]:
            print(f"    digest={candidate['candidate_digest']}")


def _print_eureka_terminal(summary: dict[str, Any], *, persist: bool) -> None:
    outcome = summary["outcome"]
    if persist:
        verdict = "VERDICT_PENDING (visible, not yet realizable)"
        print(f"[eureka] {outcome}: persisted {summary['persisted']} concept(s) as {verdict}.")
        return
    if summary["rc"] == 0:
        print(
            f"[eureka] {outcome}: {summary['proposed']} proposal(s), PROPOSE only (dry-run). "
            "Use --apply for VERDICT_PENDING; Hades remains the materializer."
        )
        return
    print(f"[eureka] {outcome}: no proposal survived.")


def cmd_eureka(args: argparse.Namespace) -> int:
    # KG: eureka-canonical-2026-05-26
    """유레카 — structural induction + optional bounded semantic insight loop."""
    preflight_rc = _eureka_preflight(args)
    if preflight_rc is not None:
        return preflight_rc
    if getattr(args, "code", False):
        return _cmd_eureka_code(args)

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
    cycle_id = _eureka_cycle_id()
    # CLI persistence is PROPOSE-only: it can expose candidates as VERDICT_PENDING,
    # while an external human/Naesengmoon verdict ingress must own ACCEPTED transitions.
    persist = bool(getattr(args, "apply", False))
    creative = bool(getattr(args, "creative", False))
    creative_enricher, setup_rc = _eureka_creative_enricher(args, cycle_id, close)
    if setup_rc is not None:
        return setup_rc
    cfg = pipeline.PipelineConfig(
        cycle_id=cycle_id,
        method=getattr(args, "method", "fca"),
        fidelity_runner=run_cypher,
        creative_enricher=creative_enricher,
        persist_cypher=_write if persist else None,
        persist_accept=False,
        require_acceptance_receipt=False,
        **eureka_stages.wire_default_stages(run_cypher),
    )
    try:
        pr = pipeline.run_from_kg(run_cypher, cfg)
    finally:
        close()

    summary = _eureka_run_summary(pr, persist=persist, creative=creative)
    candidates = _eureka_candidates(pr)
    envelope = _eureka_envelope(
        pr,
        cfg,
        cycle_id=cycle_id,
        creative=creative,
        persist=persist,
        summary=summary,
        candidates=candidates,
    )
    if getattr(args, "json", False):
        print(json.dumps(envelope, ensure_ascii=False, sort_keys=True))
        return int(summary["rc"])

    _print_eureka_details(pr, candidates)
    _print_eureka_terminal(summary, persist=persist)
    return int(summary["rc"])


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
