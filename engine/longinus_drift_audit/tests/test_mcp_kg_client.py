"""Tests for McpKgClient — KgClient over the mcp-neo4j-cypher HTTP gateway.

Lets the longinus audit/materialize reach a bolt-firewalled KG (e.g. airobotics-1
over Tailscale; bolt 7687 closed, MCP open on :55013) by POSTing read/write
cypher tool calls. KG: bhgman-engine-mcp-kg-backend.
"""

from __future__ import annotations

import io
import json

from engine.longinus_drift_audit import kg_client
from engine.longinus_drift_audit.kg_client import McpKgClient, _mcp_exec
from engine.longinus_drift_audit.models import KgRefRecord


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _sse(rows):
    reply = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": json.dumps(rows)}], "isError": False},
    }
    return f"event: message\ndata: {json.dumps(reply)}\n\n".encode()


def _patch(monkeypatch, rows):
    sent = {}

    def fake_urlopen(req, timeout=0):  # noqa: ARG001
        sent["payload"] = json.loads(req.data.decode())
        return _Resp(_sse(rows))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return sent


def test_mcp_exec_classifies_read_vs_write(monkeypatch):
    sent = _patch(monkeypatch, [{"c": 1}])
    _mcp_exec("http://kg/mcp/", "MATCH (n) RETURN count(n) AS c", {})
    assert sent["payload"]["params"]["name"] == "read_neo4j_cypher"
    _mcp_exec("http://kg/mcp/", "MERGE (n:X {id:1})", {})
    assert sent["payload"]["params"]["name"] == "write_neo4j_cypher"


def test_run_and_list_reference_sites(monkeypatch):
    _patch(
        monkeypatch,
        [{"sourceId": "S1", "sourcePath": "a.py", "label": None, "signature_baseline": None}],
    )
    c = McpKgClient("http://kg/mcp/")
    assert c.run("MATCH (n) RETURN n")[0]["sourceId"] == "S1"
    refs = c.list_reference_sites()
    assert len(refs) == 1 and isinstance(refs[0], KgRefRecord) and refs[0].sourceId == "S1"


def test_merge_forward_binding_skips_when_anchor_absent(monkeypatch):
    # has_node → count 0 ⇒ anchor absent ⇒ skip (no dangling binding), return False
    _patch(monkeypatch, [{"c": 0}])
    c = McpKgClient("http://kg/mcp/")
    site = kg_client.ReferenceSite(sourceId="S1", sourcePath="pkg/m.py", kg_anchor="GHOST_ANCHOR")
    assert c.merge_forward_binding(site, line_count=10) is False


def test_merge_forward_binding_writes_when_anchor_present(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=0):  # noqa: ARG001
        payload = json.loads(req.data.decode())
        calls.append(payload["params"]["arguments"]["query"])
        # first call = has_node read (count 1 = present); rest = the MERGE write
        rows = [{"c": 1}] if "count(n)" in payload["params"]["arguments"]["query"] else []
        return _Resp(_sse(rows))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    c = McpKgClient("http://kg/mcp/")
    site = kg_client.ReferenceSite(sourceId="S1", sourcePath="pkg/m.py", kg_anchor="REAL_ANCHOR")
    assert c.merge_forward_binding(site, line_count=10) is True
    assert any("BINDS_TO" in q for q in calls)  # the binding MERGE ran
