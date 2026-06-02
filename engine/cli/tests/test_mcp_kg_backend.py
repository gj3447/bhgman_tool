"""Tests for the mcp-neo4j-cypher HTTP gateway KG backend (BHGMAN_KG_MCP_URL).

Lets the engine reach a bolt-firewalled KG (e.g. airobotics-1 via Tailscale, bolt
closed but the MCP gateway open on :55013) by POSTing read/write_neo4j_cypher tool
calls and unwrapping the SSE `data:` frame. KG: bhgman-engine-mcp-kg-backend.
"""

from __future__ import annotations

import io
import json

from engine.cli import runtime


class _FakeHTTPResponse(io.BytesIO):
    """urlopen returns a context manager whose .read() yields the SSE body."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _sse(rows: list[dict]) -> bytes:
    text = json.dumps(rows)
    reply = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": text}], "isError": False},
    }
    return f"event: message\ndata: {json.dumps(reply)}\n\n".encode()


def _capture_urlopen(monkeypatch, rows):
    """Patch urlopen to record the posted payload and return an SSE reply."""
    sent: dict = {}

    def fake_urlopen(req, timeout=0):  # noqa: ARG001
        sent["url"] = req.full_url
        sent["payload"] = json.loads(req.data.decode())
        return _FakeHTTPResponse(_sse(rows))

    monkeypatch.setattr(runtime.urllib.request, "urlopen", fake_urlopen)
    return sent


def test_mcp_read_parses_sse_rows(monkeypatch):
    sent = _capture_urlopen(monkeypatch, [{"c": 139587}])
    run, _write, close = runtime._make_mcp_runners("http://kg.example/mcp/")
    rows = run("MATCH (n) RETURN count(n) AS c", {})
    assert rows == [{"c": 139587}]
    assert sent["url"] == "http://kg.example/mcp/"
    assert sent["payload"]["params"]["name"] == "read_neo4j_cypher"
    assert sent["payload"]["params"]["arguments"]["query"].startswith("MATCH")
    close()


def test_mcp_write_routes_to_write_tool(monkeypatch):
    sent = _capture_urlopen(monkeypatch, [])
    _run, write, _close = runtime._make_mcp_runners("http://kg.example/mcp/")
    write("MERGE (t:T {id:$id})", {"id": "x"})
    assert sent["payload"]["params"]["name"] == "write_neo4j_cypher"
    assert sent["payload"]["params"]["arguments"]["params"] == {"id": "x"}


def test_make_kg_runners_prefers_mcp_when_env_set(monkeypatch):
    monkeypatch.setenv("BHGMAN_KG_MCP_URL", "http://kg.example/mcp/")
    _capture_urlopen(monkeypatch, [{"ok": 1}])
    runners = runtime.make_kg_runners()
    assert runners is not None
    run, _write, _close = runners
    assert run("RETURN 1 AS ok", {}) == [{"ok": 1}]


def test_mcp_surfaces_cypher_error(monkeypatch):
    def fake_urlopen(req, timeout=0):  # noqa: ARG001
        reply = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": "boom"}], "isError": True},
        }
        return _FakeHTTPResponse(f"data: {json.dumps(reply)}\n\n".encode())

    monkeypatch.setattr(runtime.urllib.request, "urlopen", fake_urlopen)
    run, _write, _close = runtime._make_mcp_runners("http://kg.example/mcp/")
    try:
        run("BAD CYPHER", {})
        raise AssertionError("expected RuntimeError")
    except RuntimeError as e:
        assert "boom" in str(e)
