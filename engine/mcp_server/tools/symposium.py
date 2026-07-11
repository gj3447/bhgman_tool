"""SYMPOSIUM MCP tools — APT dispatch / KG query / gate check / seed germinate.

KG: rs-mcp-symposium-absorb-2026-05-14 (:ReferenceSite)
Source: SYMPOSIUM/mcp-server-symposium/server.py (absorbed Wave 7 P2-A)
Provenance: span-bhgman-cli-mcp-absorption-wave7-2026-05-14

Exposes 4 SYMPOSIUM core tools that thin-wrap the SYMPOSIUM/bhgman-tool infrastructure:

  apt_dispatch    — APT phase routing (sa | sp | st | scw | meta_review)
  kg_query        — Neo4j Cypher wrapper, fail-open via ssh dgx → data/neo4j-0
  gate_check      — apt-gate-check.sh wrapper (Resilience4j 4-layer chain)
  seed_germinate  — 재배맨 seed planning via the REAL engine (jbm-s2 promotion):
                    validate_seed_invariants fail-closed → plant_seeds dry-run
                    MERGE plans (the former sha256 shim never touched the engine)

Design contract (longinus 7-layer ref binding):
  L1 (Filesystem):  this file
  L2 (Module):      engine.mcp_server.tools.symposium
  L3 (Class):       n/a — registered as `@mcp.tool()` callables
  L4 (Function):    apt_dispatch / kg_query / gate_check / seed_germinate
  L5 (Type):        APTDispatchRequest / KGQueryRequest / GateCheckRequest / SeedGerminateRequest
  L6 (Instance):    registered onto FastMCP via `register(mcp)`
  L7 (Predicate):   fail-open semantics — degraded dict on transport failure, never raise

Honest limitations (Goodhart safeguard):
- The skills directory used for `apt_dispatch` lookup is resolved via env
  `SYMPOSIUM_ROOT` first, then falls back to bhgman_tool's repo-root `skills/`.
  Both contain identical apt-{phase} SKILL.md after Wave 7 P1-C sync, so the
  fallback is sound but not guaranteed across drift events.
- `kg_query` requires `ssh dgx` reachable; absent that, returns degraded dict.
- `gate_check` requires `bin/cypher_validate.sh` on disk; same fallback rules.
- `seed_germinate` is a dry-run planner: it NEVER writes (registry category 'read').
  The parent applies the returned MERGE-only planned_cyphers explicitly (e.g.
  kg_query mutate=true) — the write decision stays at the caller, PROPOSE-style.
  E1 (orphan anchor) is checked ONLY when a KG is provided (kg_path param / store
  seam, jbm-s8) — without it the local 4 invariants (dup/depth/dangling/E3) are
  enforced and the response discloses the E1-unchecked scope honestly.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.jaebaeman.invariants import validate_seed_invariants
from engine.jaebaeman.jaebaeman_models import SeedRecord
from engine.jaebaeman.kg_adapter import plant_seeds

logger = logging.getLogger("bhgman_tool.mcp.symposium")


# ─── repo root resolution ──────────────────────────────────────────────────


def _resolve_skills_dir() -> Path:
    """Locate the skills/ dir. Prefer SYMPOSIUM_ROOT env; fall back to bhgman_tool/skills."""
    sym = os.environ.get("SYMPOSIUM_ROOT")
    if sym:
        candidate = Path(sym).expanduser() / "SKILLS"
        if candidate.is_dir():
            return candidate
        # SYMPOSIUM uses uppercase SKILLS/, bhgman_tool uses lowercase skills/
        lower = Path(sym).expanduser() / "skills"
        if lower.is_dir():
            return lower
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "skills").is_dir() and (parent / "pyproject.toml").is_file():
            return parent / "skills"
    raise RuntimeError(
        "skills directory not found (SYMPOSIUM_ROOT and bhgman_tool fallback both failed)"
    )


def _resolve_repo_root() -> Path:
    """Find SYMPOSIUM root first; else bhgman_tool root."""
    sym = os.environ.get("SYMPOSIUM_ROOT")
    if sym:
        p = Path(sym).expanduser()
        if p.is_dir():
            return p
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("repo root not found")


DGX_HOST = os.environ.get("SYMPOSIUM_DGX_HOST", "dgx")


# ─── DTOs ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class APTDispatchRequest:
    """Phase-routed APT dispatch (SA → SP → ST → SCW).

    `phase` is mandatory: direct user call rejected by APT_GATE_VERSION=v27 dispatch guard.
    Orchestrator (apt/SKILL.md) is the only legitimate caller.
    """

    phase: str  # one of: sa | sp | st | scw | meta_review
    task: str
    cycle_id: str | None = None
    actor: str = "claude-code-harness"


@dataclass(frozen=True, slots=True)
class KGQueryRequest:
    """Neo4j Cypher wrapper. Read-only by default; write requires explicit `mutate=true`."""

    cypher: str
    params: dict[str, Any] = field(default_factory=dict)
    mutate: bool = False
    timeout_s: float = 5.0
    confirm_destructive: bool = False


@dataclass(frozen=True, slots=True)
class GateCheckRequest:
    """apt-gate-check.sh wrapper — Resilience4j 4-layer (timeout / CB / audit / fallback)."""

    gate_name: str  # G3.5 / G6.5 / etc.
    cycle_id: str
    actor: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SeedGerminateRequest:
    """재배맨 SubagentTaskSpec emission (jaebaeman protocol).

    Returns a seed_id that the parent should pre-fetch before dispatching haiku/sonnet subagents.
    """

    spec_name: str
    payload: dict[str, Any]
    parent_cycle_id: str | None = None


# ─── transport (fail-open) ─────────────────────────────────────────────────


def _ssh_cypher(
    cypher: str, params: dict[str, Any] | None = None, timeout_s: float = 5.0
) -> dict[str, Any]:
    """ssh dgx → kubectl exec → cypher-shell. Fail-open: returns degraded dict on error.

    Tests monkeypatch this to inject mocks; do not inline.
    """
    params_json = json.dumps(params or {})
    param_arg = shlex.quote(f"p => {params_json}")
    namespace = os.environ.get("BHGMAN_STATUS_K8S_NAMESPACE") or os.environ.get(
        "BHGMAN_K8S_NAMESPACE", "data"
    )
    pod = os.environ.get("BHGMAN_STATUS_NEO4J_POD") or os.environ.get("BHGMAN_NEO4J_POD", "neo4j-0")
    user = os.environ.get("BHGMAN_STATUS_NEO4J_USER") or os.environ.get("NEO4J_USER", "neo4j")
    password = (
        os.environ.get("BHGMAN_STATUS_NEO4J_PASSWORD")
        or os.environ.get("NEO4J_PASSWORD")
        or os.environ.get("SYMPOSIUM_KG_PASSWORD")
    )
    if not password:
        # No hardcoded fallback (the CLI already dropped its 'neo4jpassword' default):
        # fail closed instead of authenticating with a known constant. bhg-f-secrets-on-argv.
        return {"ok": False, "error": "neo4j_password_not_configured", "degraded": True}
    cmd = [
        "ssh",
        DGX_HOST,
        f"kubectl exec -n {shlex.quote(namespace)} {shlex.quote(pod)} -- "
        f"cypher-shell -u {shlex.quote(user)} -p {shlex.quote(password)} "
        f"--format plain --param {param_arg}",
    ]
    try:
        result = subprocess.run(
            cmd,
            input=cypher,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "degraded": True}
    except FileNotFoundError:
        return {"ok": False, "error": "ssh_not_available", "degraded": True}


# ─── implementations ──────────────────────────────────────────────────────


def _apt_dispatch_impl(req: APTDispatchRequest) -> dict[str, Any]:
    """Phase router. Validates phase + routes to skills/apt-{phase}/SKILL.md."""
    valid = {"sa", "sp", "st", "scw", "meta_review"}
    if req.phase not in valid:
        return {"verdict": "FAIL", "reason": f"invalid phase: {req.phase} (valid: {valid})"}

    skills_dir = _resolve_skills_dir()
    skill_path = skills_dir / f"apt-{req.phase}" / "SKILL.md"
    if not skill_path.is_file():
        return {"verdict": "FAIL", "reason": f"skill not found: {skill_path}", "degraded": True}

    return {
        "verdict": "DISPATCHED",
        "phase": req.phase,
        "skill_md": str(skill_path),
        "task": req.task,
        "cycle_id": req.cycle_id or "unassigned",
        "actor": req.actor,
        "note": "parent orchestrator must consume SKILL.md body and execute phase logic",
    }


# ─── write-clause detection (data-loss guard) ─────────────────────────────
#
# The read-only guard MUST NOT let a `mutate=false` query mutate the KG. The old
# guard only substring-matched CREATE|MERGE|DELETE|REMOVE — so SET / DROP / FOREACH /
# LOAD CSV and apoc/db write procedures slipped through as "reads" (silent data loss),
# while benign reads referencing CREATEDBY / DELETED / MERGED_PR as identifiers were
# wrongly blocked. We detect write *clauses* at word boundaries AFTER stripping string
# literals + comments (so identifiers/literals don't false-positive), plus apoc/db write
# procedures by name (their inner write query is hidden inside a string arg, so a
# literal-stripped keyword scan alone would miss apoc.periodic.* writes).

_CYPHER_WRITE_CLAUSE = re.compile(
    r"\b(CREATE|MERGE|DELETE|REMOVE|SET|DROP|FOREACH|LOAD\s+CSV)\b",
    re.IGNORECASE,
)
# apoc.do.when / apoc.do.case are the WRITE conditional procedures (their read-only
# twins apoc.when / apoc.case carry no "do." and stay allowed) — the inner write query
# hides in a string arg, so the literal-stripped clause scan alone would miss them.
_CYPHER_WRITE_PROC = re.compile(
    r"\bCALL\s+(apoc\.(create|merge|refactor|periodic|trigger|atomic|nodes\.link|"
    r"do\.(when|case)|cypher\.runMany|cypher\.doIt|cypher\.runWrite)|db\.(create|index\.|constraints))",
    re.IGNORECASE,
)
_CYPHER_STRING_LITERAL = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", re.DOTALL)
_CYPHER_LINE_COMMENT = re.compile(r"//[^\n]*")
_CYPHER_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_cypher_noise(cypher: str) -> str:
    """Remove block/line comments and string literals so write-keyword detection
    only sees structural clauses, not identifiers or literal text."""
    s = _CYPHER_BLOCK_COMMENT.sub(" ", cypher)
    s = _CYPHER_LINE_COMMENT.sub(" ", s)
    return _CYPHER_STRING_LITERAL.sub("''", s)


def _cypher_has_write(cypher: str) -> bool:
    """True if the cypher contains any write clause or apoc/db write procedure."""
    stripped = _strip_cypher_noise(cypher)
    return bool(_CYPHER_WRITE_CLAUSE.search(stripped) or _CYPHER_WRITE_PROC.search(stripped))


_CYPHER_DESTRUCTIVE = re.compile(r"\bDETACH\s+DELETE\b|\bDROP\b", re.IGNORECASE)


def _cypher_is_destructive(cypher: str) -> bool:
    """True for irreversible mass ops — DETACH DELETE (nodes+rels) or DROP (schema/db).
    Literal/comment-stripped so 'DROP' inside a string/identifier can't false-positive."""
    return bool(_CYPHER_DESTRUCTIVE.search(_strip_cypher_noise(cypher)))


def _kg_query_impl(req: KGQueryRequest) -> dict[str, Any]:
    """Cypher pass-through with fail-open + word-boundary write-clause guard."""
    has_write_keyword = _cypher_has_write(req.cypher)
    if req.mutate and not has_write_keyword:
        return {"ok": False, "reason": "mutate=true but no write keyword in cypher"}
    if not req.mutate and has_write_keyword:
        return {"ok": False, "reason": "write keyword detected but mutate=false (safety)"}
    # Even under explicit mutate=true, an irreversible mass op (DETACH DELETE / DROP)
    # against prod needs a second opt-in — no silent DROP DATABASE / delete-all.
    if req.mutate and _cypher_is_destructive(req.cypher) and not req.confirm_destructive:
        return {
            "ok": False,
            "reason": "destructive op (DETACH DELETE / DROP) requires confirm_destructive=true",
        }
    return _ssh_cypher(req.cypher, req.params, req.timeout_s)


def _gate_check_impl(req: GateCheckRequest) -> dict[str, Any]:
    """Thin wrapper around the existing apt-gate-check / cypher_validate.sh script."""
    root = _resolve_repo_root()
    # Prefer SYMPOSIUM/bin/cypher_validate.sh; degrade gracefully if absent.
    script = root / "bin" / "cypher_validate.sh"
    if not script.is_file():
        return {"verdict": "WOULD_FAIL", "reason": f"script not found: {script}", "degraded": True}
    try:
        result = subprocess.run(
            [str(script), req.gate_name, req.cycle_id, req.actor],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return {
            "verdict": "PASS" if result.returncode == 0 else "FAIL",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "gate_name": req.gate_name,
            "audit_id": f"audit_{req.cycle_id}_{req.gate_name}",
        }
    except subprocess.TimeoutExpired:
        return {
            "verdict": "WOULD_FAIL",
            "reason": "gate-check timeout (10s exceeded)",
            "degraded": True,
        }
    except OSError as e:
        # non-executable / exec failure must fail-open (degraded dict), never raise out of the
        # MCP tool — the docstring promises graceful degradation but only TimeoutExpired was caught.
        return {"verdict": "WOULD_FAIL", "reason": f"gate-check exec failed: {e}", "degraded": True}


def seeds_from_payload(spec_name: str, payload: dict[str, Any]) -> list[SeedRecord]:
    # KG: 재배맨-v2-subagent-runtime-protocol
    # KG: LakatosTree_BhgmanJaebaeman_20260702/jbm_s2_seed_germinate_engine
    """Parse the tool payload into engine ``SeedRecord``s — the SHARED parser.

    Tests recompute engine plans over the very same records this returns, so the
    MCP==engine parity assertion never depends on a second, drifting parser.

    ``payload["seeds"]`` is a list of seed dicts; a payload without ``"seeds"`` is
    treated as one single-seed spec. A seed without ``anchor``/``source_id`` is
    self-anchored (root). A non-integer ``depth`` coerces to -1 so the invariant
    gate flags it as E4 (fail-closed) instead of raising a transport error.
    """
    raw = payload.get("seeds")
    if raw is None:
        raw = [payload] if payload else [{}]
    seeds: list[SeedRecord] = []
    for i, entry in enumerate(raw):
        name = str(entry.get("name") or f"{spec_name}-seed-{i}")
        anchor = str(entry.get("anchor") or entry.get("source_id") or name)
        try:
            depth = int(entry.get("depth", 0))
        except (TypeError, ValueError):
            depth = -1  # out of [0, MAX_DEPTH] => E4 violation => BLOCKED, never a 500
        parent = entry.get("parent")
        seeds.append(
            SeedRecord(
                name=name,
                skill=str(entry.get("skill") or "jaebaeman"),
                source_id=anchor,
                display_name=str(entry.get("display_name") or name),
                task_type=str(entry.get("task_type") or "research"),
                target_domain=str(entry.get("target_domain") or ""),
                expected_outcome=str(entry.get("expected_outcome") or ""),
                germination_method=str(entry.get("germination_method") or "manual"),
                depth=depth,
                parent=str(parent) if parent is not None else None,
            )
        )
    return seeds


def _seed_germinate_impl(req: SeedGerminateRequest, store: Any | None = None) -> dict[str, Any]:
    # KG: LakatosTree_BhgmanJaebaeman_20260702/jbm_s2_seed_germinate_engine
    # KG: LakatosTree_BhgmanJaebaeman_20260702/jbm_s8_germinate_e1_kg_seam
    # KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01
    # KG: 재배맨-v2-subagent-runtime-protocol
    """Plan 재배맨 seeds via the REAL engine — fail-closed invariant gate, dry-run plans.

    Promotion of the former sha256 shim (7-commander substance audit wf_376c327b-8f3,
    gap G3: the shim hashed inputs and never imported ``engine.jaebaeman``). The
    response now carries engine-derived artifacts only:

      * ``validate_seed_invariants`` gates the batch FIRST — any violation returns
        status 'BLOCKED' with the exact codes and plans NOTHING (fail-closed).
      * a clean batch returns status 'PLANNED' with the MERGE-only cyphers the real
        ``plant_seeds(dry_run=True)`` derived (covenant: seeds are planted, never
        uprooted — the engine asserts DELETE/DETACH/REMOVE absence).
      * this tool itself writes nothing (registry category 'read'); the parent
        applies the plans explicitly, PROPOSE-style, keeping the write decision at
        the caller.

    The shim-era surface (seed_id / spec_name / payload_keys) is preserved.

    jbm-s8 (E1 KG-seam): ``store``(테스트 DIP seam) 또는 MCP ``kg_path`` 로 KG 를 주면
    ``validate_seed_invariants`` 에 run_cypher 가 배선되어 **E1(orphan anchor — 외부
    anchor 의 KG 실존)** 까지 5개 불변식 전종을 MCP 경계에서 fail-closed 로 판별한다.
    KG 미제공이면 현행 로컬-4 유지 — 응답 ``engine.invariants`` 가 어느 쪽인지 공시
    (E1 을 본 척하는 조용한 범위 과장 금지, infra-0 covenant 보존).
    """
    digest = hashlib.sha256(
        json.dumps({"spec": req.spec_name, "payload": req.payload}, sort_keys=True).encode()
    ).hexdigest()[:16]
    seed_id = f"seed_{req.spec_name}_{digest}"
    cycle_id = req.parent_cycle_id or f"seed-germinate-{digest}"

    run_cypher = None
    if store is not None:
        from engine.kg_local.runner import make_local_runner  # noqa: PLC0415

        run_cypher = make_local_runner(store, autosave=False)

    seeds = seeds_from_payload(req.spec_name, req.payload)
    violations = validate_seed_invariants(seeds, run_cypher=run_cypher)
    base: dict[str, Any] = {
        "seed_id": seed_id,
        "spec_name": req.spec_name,
        "payload_keys": list(req.payload.keys()),
        "parent_cycle_id": req.parent_cycle_id,
        "engine": {
            "seeds_planned": len(seeds),
            "seed_names": [s.name for s in seeds],
            "cycle_id": cycle_id,
            "dry_run": True,
            "invariants": "local-4+E1"
            if run_cypher is not None
            else "local-4 (E1 미검 — kg_path 미제공)",
        },
    }
    if violations:
        return {
            **base,
            "status": "BLOCKED",
            "planned_cyphers": [],
            "violations": [
                {"code": v.code.value, "seed_id": v.seed_id, "detail": v.detail} for v in violations
            ],
            "next_action": (
                "fix the invariant violations and re-germinate (fail-closed: nothing was planned)"
            ),
        }
    plan = plant_seeds(seeds, write_cypher=None, cycle_id=cycle_id, dry_run=True)
    return {
        **base,
        "status": "PLANNED",
        "planned_cyphers": [{"cypher": c, "params": p} for c, p in plan.planned_cyphers],
        "violations": [],
        "next_action": (
            "apply the MERGE-only planned_cyphers explicitly (e.g. kg_query mutate=true) "
            "before dispatching subagents (jaebaeman protocol — this tool writes nothing)"
        ),
    }


# ─── registration ─────────────────────────────────────────────────────────


def register(mcp: Any) -> None:
    """Attach 4 SYMPOSIUM tools to the FastMCP instance."""

    @mcp.tool()
    def apt_dispatch(
        phase: str,
        task: str,
        cycle_id: str | None = None,
        actor: str = "claude-code-harness",
    ) -> dict[str, Any]:
        """Dispatch into an APT phase (sa | sp | st | scw | meta_review)."""
        return _apt_dispatch_impl(
            APTDispatchRequest(phase=phase, task=task, cycle_id=cycle_id, actor=actor)
        )

    @mcp.tool()
    def kg_query(
        cypher: str,
        params: dict[str, Any] | None = None,
        mutate: bool = False,
        timeout_s: float = 5.0,
        confirm_destructive: bool = False,
    ) -> dict[str, Any]:
        """Run a Cypher query against the SYMPOSIUM KG (ssh dgx → cypher-shell).

        Writes need `mutate=true`; irreversible mass ops (DETACH DELETE / DROP)
        additionally need `confirm_destructive=true`.
        """
        return _kg_query_impl(
            KGQueryRequest(
                cypher=cypher,
                params=params or {},
                mutate=mutate,
                timeout_s=timeout_s,
                confirm_destructive=confirm_destructive,
            )
        )

    @mcp.tool()
    def gate_check(
        gate_name: str,
        cycle_id: str,
        actor: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run an APT gate check (Resilience4j 4-layer chain)."""
        return _gate_check_impl(
            GateCheckRequest(
                gate_name=gate_name, cycle_id=cycle_id, actor=actor, context=context or {}
            )
        )

    @mcp.tool()
    def seed_germinate(
        spec_name: str,
        payload: dict[str, Any],
        parent_cycle_id: str | None = None,
        kg_path: str = "",
    ) -> dict[str, Any]:
        """Plan 재배맨 seeds via the real engine (fail-closed invariants, dry-run MERGE plans).

        kg_path: optional LocalKgStore JSON — 주면 E1(orphan anchor)까지 5개 불변식 전종을
        MCP 경계에서 판별 (미제공=로컬-4, 응답 engine.invariants 에 공시).
        """
        store = None
        if kg_path:
            from engine.kg_local.store import LocalKgStore  # noqa: PLC0415

            store = LocalKgStore(kg_path)
        return _seed_germinate_impl(
            SeedGerminateRequest(
                spec_name=spec_name, payload=payload, parent_cycle_id=parent_cycle_id
            ),
            store=store,
        )
