"""bhgman_tool CLI — shared runtime helpers (KG runners, skill routing, module loading).

Standalone: no dependency on commands/parser/main. Split out of main.py 2026-06-01
(CCP: CLI monolith → runtime/commands/parser/main)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path


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


def _agent_runtime():
    """engine.agents 로드 → (namespace | None, reason).

    namespace = AgentClient/research/critique/DEFAULT_LENSES. 런타임 불가면 (None, reason).
    """
    import importlib  # noqa: PLC0415
    import types  # noqa: PLC0415

    client_mod = importlib.import_module("engine.agents.client")
    prom = importlib.import_module("engine.agents.prometheus")
    naes = importlib.import_module("engine.agents.naesengmoon")
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


def _load_occam_runner():
    """Lazy-import engine.occam.occam_runner (proper package import)."""
    from engine.occam import occam_runner  # noqa: PLC0415

    return occam_runner


def _mcp_cypher_call(url: str, tool: str, cypher: str, params: dict) -> list[dict]:
    """POST a single cypher to a streamable-HTTP mcp-neo4j-cypher gateway (stateless).

    Routes the engine's KG access through the same MCP endpoint the parent Claude
    harness uses (e.g. http://100.64.0.10:55013/mcp/ — airobotics-1 airo KG), so the
    bolt port need not be exposed over Tailscale. Parses the SSE `data:` frame and
    unwraps result.content[0].text (a JSON array of rows). KG: bhgman-engine-mcp-kg-backend.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": {"query": cypher, "params": params or {}}},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — fixed scheme, op env
        body = resp.read().decode()
    # streamable HTTP returns SSE frames: keep the last `data:` line (the JSON-RPC reply)
    data = body
    for line in body.splitlines():
        if line.startswith("data:"):
            data = line[5:].strip()
    obj = json.loads(data)
    if "error" in obj:
        raise RuntimeError(f"MCP error: {obj['error']}")
    result = obj["result"]
    if result.get("isError"):
        raise RuntimeError(f"cypher error: {result['content'][0]['text']}")
    text = result["content"][0]["text"] if result.get("content") else ""
    parsed = json.loads(text) if text else []
    return parsed if isinstance(parsed, list) else [parsed]  # write tool returns a dict


def _make_mcp_runners(url: str):
    """KG backend over the mcp-neo4j-cypher HTTP gateway → (run, write, close)."""

    def run_cypher(cypher: str, params: dict) -> list[dict]:
        return _mcp_cypher_call(url, "read_neo4j_cypher", cypher, params)

    def write_cypher(cypher: str, params: dict) -> list[dict]:
        return _mcp_cypher_call(url, "write_neo4j_cypher", cypher, params)

    return run_cypher, write_cypher, (lambda: None)


def make_kg_runners():
    """Build (run_cypher, write_cypher, close) backed by neo4j, or None.

    Backend precedence:
      1. BHGMAN_KG_MCP_URL set → route cypher through the mcp-neo4j-cypher HTTP gateway
         (read_neo4j_cypher / write_neo4j_cypher). Lets the engine reach a bolt-firewalled
         KG (e.g. airobotics-1 via Tailscale, bolt closed but MCP open on :55013).
      2. else → neo4j bolt driver. Env: NEO4J_URI (default bolt://localhost:7687),
         NEO4J_USER (neo4j), NEO4J_PASSWORD. Returns None when driver/creds unavailable.
    Monkeypatched in tests to inject fakes.
    """
    mcp_url = os.environ.get("BHGMAN_KG_MCP_URL")
    if mcp_url:
        return _make_mcp_runners(mcp_url)
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


def _load_engine_module(subdir: str, module: str, evict: tuple[str, ...] = ()):
    """Lazy-import an engine submodule as a proper package: engine.<subdir>.<module>.

    `evict` is accepted for backward call-compat but no longer used — subpackages
    are now regular packages with absolute `engine.*` imports, so sibling modules
    sharing a bare name (e.g. occam + eureka both ship `oracle_lens.py`) no longer
    collide in sys.modules.
    """
    import importlib  # noqa: PLC0415

    return importlib.import_module(f"engine.{subdir}.{module}")
