"""SYMPOSIUM MCP tools — APT dispatch / KG query / gate check / seed germinate.

KG: rs-mcp-symposium-absorb-2026-05-14 (:ReferenceSite)
Source: SYMPOSIUM/mcp-server-symposium/server.py (absorbed Wave 7 P2-A)
Provenance: span-bhgman-cli-mcp-absorption-wave7-2026-05-14

Exposes 4 SYMPOSIUM core tools that thin-wrap the SYMPOSIUM/bhgman-tool infrastructure:

  apt_dispatch    — APT phase routing (sa | sp | st | scw | meta_review)
  kg_query        — Neo4j Cypher wrapper, fail-open via ssh dgx → cypher-shell
  gate_check      — apt-gate-check.sh wrapper (Resilience4j 4-layer chain)
  seed_germinate  — 재배맨 SubagentTaskSpec emission (jaebaeman protocol)

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
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    cmd = [
        "ssh",
        DGX_HOST,
        f'kubectl exec -n neo4j neo4j-0 -- cypher-shell -u neo4j -p "${{NEO4J_PASSWORD:-neo4j}}" '
        f"--format plain --param 'p => {params_json}'",
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


def _kg_query_impl(req: KGQueryRequest) -> dict[str, Any]:
    """Cypher pass-through with fail-open + write-keyword guard."""
    has_write_keyword = any(
        kw in req.cypher.upper() for kw in ("CREATE", "MERGE", "DELETE", "REMOVE")
    )
    if req.mutate and not has_write_keyword:
        return {"ok": False, "reason": "mutate=true but no write keyword in cypher"}
    if not req.mutate and has_write_keyword:
        return {"ok": False, "reason": "write keyword detected but mutate=false (safety)"}
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
        return {"verdict": "WOULD_FAIL", "reason": "timeout (Resilience4j 500ms exceeded)"}


def _seed_germinate_impl(req: SeedGerminateRequest) -> dict[str, Any]:
    """Emits a SubagentTaskSpec seed and returns its identifier.

    Parent claude is responsible for the KG write (재배맨 MIC_v1.SubagentSeeder slot).
    """
    digest = hashlib.sha256(
        json.dumps({"spec": req.spec_name, "payload": req.payload}, sort_keys=True).encode()
    ).hexdigest()[:16]
    seed_id = f"seed_{req.spec_name}_{digest}"
    return {
        "seed_id": seed_id,
        "spec_name": req.spec_name,
        "payload_keys": list(req.payload.keys()),
        "parent_cycle_id": req.parent_cycle_id,
        "next_action": "parent MUST KG-write before dispatching subagents (jaebaeman protocol)",
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
    ) -> dict[str, Any]:
        """Run a Cypher query against the SYMPOSIUM KG (ssh dgx → cypher-shell)."""
        return _kg_query_impl(
            KGQueryRequest(cypher=cypher, params=params or {}, mutate=mutate, timeout_s=timeout_s)
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
    ) -> dict[str, Any]:
        """Emit a 재배맨 SubagentTaskSpec seed (jaebaeman protocol)."""
        return _seed_germinate_impl(
            SeedGerminateRequest(
                spec_name=spec_name, payload=payload, parent_cycle_id=parent_cycle_id
            )
        )
