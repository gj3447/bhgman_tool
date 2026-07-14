"""ooptdd-loop in_process target — verifies the LIVE Grok KG MCP endpoint
(``mcp-neo4j-grok.metahumotonic.com``, SSE transport, deployed 2026-07-13).

This is NOT a mock. ``run_grok_kg_probe`` drives the real public SSE endpoint exactly
as an SSE client (Grok) would: opens the event stream, reads the ``endpoint`` event to
learn the POST/messages URL, then POSTs initialize -> tools/list -> a real KG write
(CREATE) -> read-back -> DELETE, reading every JSON-RPC response back off the SSE stream.

Each trace event is shipped ONLY when the corresponding real behaviour is observed, so a
broken endpoint makes the bound gate go RED. The event-name string literals below appear
verbatim inside ``run_grok_kg_probe``'s body — they are exactly the events shipped AND the
strings Longinus AST-checks against this symbol (rename one -> gate UNBOUND).

Verified behaviours (one gate each in grok_kg_requirements.yaml):
    grok_https_no_downgrade  : slash-less path returns HTTPS 200, NOT a 307 -> http:// downgrade
    grok_sse_initialized     : SSE handshake + MCP initialize succeed (serverInfo present)
    grok_tools_readwrite     : tools/list exposes read AND write_neo4j_cypher (read+write parity)
    grok_kg_read_ok          : a real read_neo4j_cypher returns a live node count > 0
    grok_kg_write_roundtrip  : CREATE -> read-back(==1) -> DELETE all succeed, no KG residue

# KG: finding-grok-kg-mcp-endpoint-ooptdd-20260713
# KG: reference_grok_kg_mcp_endpoint_2026_07_13
"""
from __future__ import annotations

import json
import subprocess
import time

HOST = "https://mcp-neo4j-grok.metahumotonic.com"
CAP_PATH = "/kg-4ecfe5dca1fc10ff851dc5d9/"
SSE_URL = HOST + CAP_PATH
_KG_ANCHOR = "finding-grok-kg-mcp-endpoint-ooptdd-20260713"
_PROBE_LABEL = "GrokOoptddProbeTemp"


def _ev(cid: str, event: str, **attrs) -> dict:
    return {
        "cid": cid,
        "correlation_id": cid,
        "cycle_id": cid,
        "service": "grok-kg-endpoint",
        "event": event,
        **attrs,
    }


def _curl(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["curl", "-sS", "--max-time", str(timeout), *args],
        capture_output=True, text=True, timeout=timeout + 5,
    )


def _check_no_downgrade() -> tuple[bool, str]:
    """Hit the capability path WITHOUT its trailing slash. A healthy Grok route returns
    HTTP 200 (stream) and never a 307 whose Location downgrades to http:// . We ask curl
    for the code + any redirect target and refuse to follow redirects."""
    r = _curl([
        "-o", "/dev/null", "--no-location",
        "-w", "%{http_code} %{redirect_url}",
        HOST + CAP_PATH.rstrip("/"),
    ], timeout=12)
    code, _, redir = r.stdout.strip().partition(" ")
    downgraded = redir.startswith("http://")
    return (code == "200" and not downgraded), f"code={code} redirect={redir or '-'}"


def _open_sse_stream(cid: str):
    """Open the real SSE stream with curl -N and return (Popen, post_url)."""
    proc = subprocess.Popen(
        ["curl", "-sS", "-N", "--max-time", "40", SSE_URL, "-H", "Accept: text/event-stream"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    post_url = None
    deadline = time.time() + 15
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()
        if line.startswith("data:") and "/messages/" in line:
            post_url = HOST + line.split(":", 1)[1].strip()
            break
    return proc, post_url


def _post(post_url: str, obj: dict) -> None:
    _curl([post_url, "-H", "Content-Type: application/json", "-d", json.dumps(obj)], timeout=12)


def _drain(proc, want_ids: set[int], timeout: int = 18) -> dict:
    """Read JSON-RPC responses off the SSE stream until every id in want_ids is seen."""
    out: dict = {}
    deadline = time.time() + timeout
    while want_ids - set(out) and time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line.split(":", 1)[1].strip()
        if not payload.startswith("{"):
            continue
        try:
            o = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(o.get("id"), int):
            out[o["id"]] = o
    return out


def _text_result(resp: dict) -> str:
    try:
        return resp["result"]["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return ""


def run_grok_kg_probe(backend, cid: str) -> dict:
    """Loop entry point. Drives the LIVE Grok SSE endpoint and ships one trace event per
    real, observed behaviour. Event literals here are Longinus-bound (see module docstring).
    """
    summary: dict = {"endpoint": SSE_URL}

    # 1) HTTPS integrity: slash-less path must not 307 -> http:// (the bug that killed the
    #    streamable-HTTP gpt route in Grok). Only ship if genuinely clean.
    ok, detail = _check_no_downgrade()
    summary["https_check"] = detail
    if ok:
        backend.ship([_ev(cid, "grok_https_no_downgrade", detail=detail)])

    # 2) Real SSE handshake + MCP session
    proc, post_url = _open_sse_stream(cid)
    summary["post_url"] = post_url
    try:
        if not post_url:
            summary["error"] = "no endpoint event from SSE stream"
            return summary

        _post(post_url, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "ooptdd-grok-probe", "version": "1"}}})
        _post(post_url, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        _post(post_url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        _post(post_url, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                         "params": {"name": "read_neo4j_cypher",
                                    "arguments": {"query": "MATCH (n) RETURN count(n) AS nodes"}}})
        _post(post_url, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                         "params": {"name": "write_neo4j_cypher",
                                    "arguments": {"query": f"CREATE (x:{_PROBE_LABEL} {{cid:'{cid}'}}) RETURN x"}}})
        _post(post_url, {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                         "params": {"name": "read_neo4j_cypher",
                                    "arguments": {"query": f"MATCH (x:{_PROBE_LABEL} {{cid:'{cid}'}}) RETURN count(x) AS c"}}})
        _post(post_url, {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                         "params": {"name": "write_neo4j_cypher",
                                    "arguments": {"query": f"MATCH (x:{_PROBE_LABEL} {{cid:'{cid}'}}) DELETE x"}}})

        resp = _drain(proc, {1, 2, 3, 4, 5, 6})
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

    # 3) initialize
    init = resp.get(1, {})
    server = (init.get("result") or {}).get("serverInfo") or {}
    summary["serverInfo"] = server
    if server.get("name"):
        backend.ship([_ev(cid, "grok_sse_initialized", server_name=server.get("name"),
                          server_version=server.get("version"))])

    # 4) tools/list must carry read AND write
    tools = [t.get("name") for t in ((resp.get(2, {}).get("result") or {}).get("tools") or [])]
    summary["tools"] = tools
    if "read_neo4j_cypher" in tools and "write_neo4j_cypher" in tools:
        backend.ship([_ev(cid, "grok_tools_readwrite", tools=tools)])

    # 5) live read returns a positive node count
    read_txt = _text_result(resp.get(3, {}))
    node_count = None
    try:
        node_count = json.loads(read_txt)[0]["nodes"]
    except (json.JSONDecodeError, IndexError, KeyError, TypeError):
        pass
    summary["node_count"] = node_count
    if isinstance(node_count, int) and node_count > 0:
        backend.ship([_ev(cid, "grok_kg_read_ok", node_count=node_count)])

    # 6) write round-trip: created 1 -> read-back 1 -> deleted 1, no residue
    created = "nodes_created" in _text_result(resp.get(4, {}))
    try:
        readback = json.loads(_text_result(resp.get(5, {})))[0]["c"]
    except (json.JSONDecodeError, IndexError, KeyError, TypeError):
        readback = None
    deleted = "nodes_deleted" in _text_result(resp.get(6, {}))
    summary["write_roundtrip"] = {"created": created, "readback": readback, "deleted": deleted}
    if created and readback == 1 and deleted:
        backend.ship([_ev(cid, "grok_kg_write_roundtrip", created=created,
                          readback=readback, deleted=deleted)])

    return summary
