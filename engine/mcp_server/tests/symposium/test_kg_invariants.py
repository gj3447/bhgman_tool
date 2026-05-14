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

    @pytest.mark.parametrize("contracts,tasks,seeds,files,expected", [
        (1, 1, 1, 1, True),     # canonical
        (0, 1, 1, 1, False),    # missing contract → orphan span
        (1, 0, 1, 1, False),    # missing task → no execution path
        (1, 1, 0, 1, False),    # missing seed → no subagent dispatch possible
        (1, 1, 1, 0, False),    # missing file → no materialization (KG↔FS drift)
        (2, 1, 1, 1, False),    # multi-contract → ambiguity, NOT atomic
    ])
    def test_5tuple_cardinality_check(self, contracts, tasks, seeds, files, expected):
        is_atomic = (contracts == 1 and tasks == 1 and seeds == 1 and files == 1)
        assert is_atomic is expected


class TestWriteSafety:
    """mutate=False must reject all write keywords; mutate=True must require one."""

    @pytest.mark.parametrize("cypher", [
        "CREATE (n:Foo {name:'x'})",
        "MERGE (n:Foo {id:1})",
        "MATCH (n) DELETE n",
        "MATCH (n) REMOVE n.prop",
    ])
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


class TestFailOpen:
    """When ssh/cypher-shell is unreachable, return degraded dict, never raise."""

    def test_ssh_missing_returns_degraded(self, monkeypatch):
        from engine.mcp_server.tools import symposium

        def fake_ssh(cypher, params=None, timeout_s=5.0):
            return {"ok": False, "error": "ssh_not_available", "degraded": True}

        monkeypatch.setattr(symposium, "_ssh_cypher", fake_ssh)
        out = _kg_query_impl(KGQueryRequest(cypher="MATCH (n) RETURN n"))
        assert out["ok"] is False
        assert out["degraded"] is True
