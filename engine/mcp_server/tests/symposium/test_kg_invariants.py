"""Validates the 5-tuple identity invariant:

    AtomicSpan  ≡  Contract  ≡  Task  ≡  Seed  ≡  File
    cardinality 1 : 1 : 1 : 1 : 1

Reference:
  - APT v27 ST phase — Crystallization Frontier (all leaves = AtomicSpan)
  - Longinus v3 — 7-Layer Reference Model
  - 재배맨 v2.1 — SubagentTaskSpec (Seed) as the FK linking KG ↔ filesystem

KG: rs-test-kg-invariants-5tuple-2026-05-14
Provenance: SYMPOSIUM/tests/test_kg_invariants.py (absorbed Wave 7 P2-A)
"""

from __future__ import annotations

import subprocess
import shlex

import pytest

from engine.mcp_server.tools.symposium import (
    KGQueryRequest,
    _kg_query_impl,
)


INVARIANT_CYPHER = """
MATCH (s:AtomicSpan)
OPTIONAL MATCH (s)-[:HAS_CONTRACT]->(c:Contract)
OPTIONAL MATCH (s)-[:HAS_TASK]->(t:Task)
OPTIONAL MATCH (s)-[:HAS_SEED]->(seed:SubagentTaskSpec)
OPTIONAL MATCH (s)-[:MATERIALIZES]->(f:File)
RETURN s.id AS span_id,
       count(DISTINCT c) AS contracts,
       count(DISTINCT t) AS tasks,
       count(DISTINCT seed) AS seeds,
       count(DISTINCT f) AS files
"""


class TestFiveTupleIdentity:
    """The atomic-span shipping principle: 1 span = 1 contract = 1 task = 1 seed = 1 file."""

    def test_invariant_cypher_well_formed(self):
        # No write keywords, valid for mutate=False
        assert "CREATE" not in INVARIANT_CYPHER.upper()
        assert "MERGE" not in INVARIANT_CYPHER.upper()
        assert "DELETE" not in INVARIANT_CYPHER.upper()

    def test_invariant_passes_mock_kg(self, mock_kg):
        req = KGQueryRequest(cypher=INVARIANT_CYPHER, mutate=False, timeout_s=2.0)
        out = _kg_query_impl(req)
        assert out["ok"] is True
        assert len(mock_kg) == 1

    @pytest.mark.parametrize(
        "contracts,tasks,seeds,files,expected",
        [
            (1, 1, 1, 1, True),  # canonical
            (0, 1, 1, 1, False),  # missing contract → orphan span
            (1, 0, 1, 1, False),  # missing task → no execution path
            (1, 1, 0, 1, False),  # missing seed → no subagent dispatch possible
            (1, 1, 1, 0, False),  # missing file → no materialization (KG↔FS drift)
            (2, 1, 1, 1, False),  # multi-contract → ambiguity, NOT atomic
        ],
    )
    def test_5tuple_cardinality_check(self, contracts, tasks, seeds, files, expected):
        is_atomic = contracts == 1 and tasks == 1 and seeds == 1 and files == 1
        assert is_atomic is expected


class TestWriteSafety:
    """mutate=False must reject all write keywords; mutate=True must require one."""

    @pytest.mark.parametrize(
        "cypher",
        [
            "CREATE (n:Foo {name:'x'})",
            "MERGE (n:Foo {id:1})",
            "MATCH (n) DELETE n",
            "MATCH (n) REMOVE n.prop",
        ],
    )
    def test_write_in_read_mode_rejected(self, cypher):
        req = KGQueryRequest(cypher=cypher, mutate=False)
        out = _kg_query_impl(req)
        assert out["ok"] is False
        assert "write keyword detected" in out["reason"]

    def test_read_in_mutate_mode_rejected(self):
        req = KGQueryRequest(cypher="MATCH (n) RETURN n", mutate=True)
        out = _kg_query_impl(req)
        assert out["ok"] is False
        assert "no write keyword" in out["reason"]

    def test_read_in_read_mode_accepted(self, mock_kg):
        req = KGQueryRequest(cypher="MATCH (n:AtomicSpan) RETURN count(n)", mutate=False)
        out = _kg_query_impl(req)
        assert out["ok"] is True

    @pytest.mark.parametrize(
        "cypher",
        [
            "MATCH (n) SET n.x = 1",
            "DROP CONSTRAINT foo IF EXISTS",
            "MATCH (n) DETACH DELETE n",
            "LOAD CSV FROM 'file:///x.csv' AS row CREATE (n)",
            "CALL apoc.periodic.iterate('MATCH (n) RETURN n', 'DELETE n', {})",
            "CALL apoc.refactor.mergeNodes([n])",
            "CALL apoc.do.when(true, 'CREATE (:N)', '', {})",
            "CALL apoc.do.case([true, 'DELETE n'], '', {})",
            "FOREACH (x IN [1,2] | CREATE (:N {v:x}))",
        ],
    )
    def test_extended_write_clauses_blocked_in_read_mode(self, cypher):
        """SET / DROP / DETACH DELETE / LOAD CSV / FOREACH / apoc write procs must
        NOT slip through the read-only guard (the old substring guard missed them all)."""
        out = _kg_query_impl(KGQueryRequest(cypher=cypher, mutate=False))
        assert out["ok"] is False
        assert "write keyword detected" in out["reason"]

    @pytest.mark.parametrize(
        "cypher",
        [
            "MATCH (n) WHERE n.createdBy = 'CREATE' RETURN n",
            "MATCH (n {status:'DELETED'}) RETURN n.mergedAt",
            "MATCH (n)-[:MERGED_PR]->(m) RETURN n, m",
            "MATCH (n) RETURN n.preset, n.asset, n.subset",
            "// CREATE is only mentioned in this comment\nMATCH (n) RETURN n",
            "MATCH (n) WHERE n.note = 'please DELETE the ticket' RETURN n",
            "CALL apoc.when(true, 'RETURN 1', 'RETURN 2') YIELD value RETURN value",
        ],
    )
    def test_benign_reads_with_write_words_as_literals_allowed(self, cypher, mock_kg):
        """Reads referencing write keywords as identifiers / props / literals / comments
        (CREATEDBY, DELETED, MERGED_PR, preset, …) must be allowed in read mode."""
        out = _kg_query_impl(KGQueryRequest(cypher=cypher, mutate=False))
        assert out["ok"] is True


class TestFailOpen:
    """When ssh/cypher-shell is unreachable, return degraded dict, never raise."""

    def test_ssh_cypher_uses_canonical_data01_container(self, monkeypatch):
        from engine.mcp_server.tools import symposium

        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

        monkeypatch.setattr(symposium.subprocess, "run", fake_run)
        out = symposium._ssh_cypher("MATCH (n) RETURN count(n)", {"x": "y"})
        assert out["ok"] is True
        command = calls[0][0]
        assert command[:5] == ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5"]
        assert command[5] == "metahumotonic27@192.168.0.25"
        assert "docker exec -i canonical-neo4j" in command[6]
        assert 'CANONICAL_NEO4J_PASSWORD' in command[6]
        assert "pw" not in command[6]
        remote = shlex.split(command[6])
        assert remote[-1] == '{`x`: "y"}'
        assert "p =>" not in command[6]
        assert calls[0][1]["input"] == "MATCH (n) RETURN count(n)"

    def test_ssh_cypher_encodes_nested_params_as_one_argument(self, monkeypatch):
        from engine.mcp_server.tools import symposium

        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

        monkeypatch.setattr(symposium.subprocess, "run", fake_run)
        out = symposium._ssh_cypher(
            "RETURN $message",
            {
                "message": 'quote " newline\n한글; $(touch /tmp/nope)',
                "nested": {"enabled": True, "items": [1, None, "x"]},
            },
        )

        assert out["ok"] is True
        remote = shlex.split(calls[0][0][6])
        assert remote[-1].startswith('{`message`: "quote \\" newline\\n')
        assert r"\ud55c\uae00" in remote[-1]
        assert remote[-1].endswith(', `nested`: {`enabled`: true, `items`: [1, null, "x"]}}')
        assert len(remote) == 10
        assert calls[0][1]["input"] == "RETURN $message"

    @pytest.mark.parametrize(
        "invalid",
        [
            {1: "value"},
            {"x": float("nan")},
            {"x": {1, 2}},
            {"x": chr(0xD800)},
            {chr(0xD800): "value"},
            {chr(0): "value"},
        ],
    )
    def test_ssh_cypher_rejects_non_json_params_without_spawning(self, monkeypatch, invalid):
        from engine.mcp_server.tools import symposium

        calls = []
        monkeypatch.setattr(symposium.subprocess, "run", lambda *a, **k: calls.append((a, k)))

        out = symposium._ssh_cypher("RETURN 1", invalid)

        assert out["ok"] is False
        assert out["error"] == "invalid_params"
        assert calls == []

    def test_ssh_cypher_needs_no_local_password(self, monkeypatch):
        """Container expands its protected password; MCP env/argv carries no secret."""
        from engine.mcp_server.tools import symposium

        for var in ("BHGMAN_STATUS_NEO4J_PASSWORD", "NEO4J_PASSWORD", "SYMPOSIUM_KG_PASSWORD"):
            monkeypatch.delenv(var, raising=False)
        called = []
        monkeypatch.setattr(
            symposium.subprocess,
            "run",
            lambda *a, **k: called.append((a, k))
            or subprocess.CompletedProcess(a[0], 0, stdout="1", stderr=""),
        )
        out = symposium._ssh_cypher("MATCH (n) RETURN 1")
        assert out["ok"] is True
        assert len(called) == 1
        assert "neo4jpassword" not in " ".join(called[0][0][0])

    def test_ssh_missing_returns_degraded(self, monkeypatch):
        from engine.mcp_server.tools import symposium

        def fake_ssh(cypher, params=None, timeout_s=5.0):
            return {"ok": False, "error": "ssh_not_available", "degraded": True}

        monkeypatch.setattr(symposium, "_ssh_cypher", fake_ssh)
        out = _kg_query_impl(KGQueryRequest(cypher="MATCH (n) RETURN n"))
        assert out["ok"] is False
        assert out["degraded"] is True


class TestDestructiveConfirm:
    """DETACH DELETE / DROP need confirm_destructive=true even under mutate=true.
    bhg-f-kgquery-destructive-path."""

    @pytest.mark.parametrize(
        "cypher",
        [
            "MATCH (n) DETACH DELETE n",
            "MATCH (n:Foo) DETACH  DELETE n",
            "DROP CONSTRAINT foo IF EXISTS",
            "DROP DATABASE neo4j",
            "DROP INDEX idx",
        ],
    )
    def test_destructive_blocked_without_confirm(self, cypher):
        out = _kg_query_impl(KGQueryRequest(cypher=cypher, mutate=True))
        assert out["ok"] is False
        assert "confirm_destructive" in out["reason"]

    @pytest.mark.parametrize(
        "cypher",
        ["MATCH (n:Tmp) DETACH DELETE n", "DROP CONSTRAINT foo IF EXISTS"],
    )
    def test_destructive_allowed_with_confirm(self, cypher, mock_kg):
        out = _kg_query_impl(KGQueryRequest(cypher=cypher, mutate=True, confirm_destructive=True))
        assert out["ok"] is True

    @pytest.mark.parametrize(
        "cypher",
        ["CREATE (:N {v:1})", "MATCH (n) SET n.x = 1", "MERGE (n:N {id:'a'})"],
    )
    def test_nondestructive_write_not_gated_by_confirm(self, cypher, mock_kg):
        # ordinary writes still go through with mutate=true, no confirm needed
        out = _kg_query_impl(KGQueryRequest(cypher=cypher, mutate=True))
        assert out["ok"] is True

    def test_destructive_word_in_literal_not_gated(self, mock_kg):
        # 'DROP' as a string literal must not trip the destructive gate
        out = _kg_query_impl(
            KGQueryRequest(cypher="MATCH (n) SET n.note = 'please DROP this' RETURN n", mutate=True)
        )
        assert out["ok"] is True
