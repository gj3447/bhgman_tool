"""W3-L: MCP read/write tool routing must use word-boundary write detection — substring
matching misrouted legitimate READS (n.createdAt, :MergedPR, literals) to the write tool."""

from __future__ import annotations

from engine.longinus_drift_audit.kg_client import _is_write_cypher


def test_real_writes_routed_to_write():
    assert _is_write_cypher("MERGE (n:X {id:1}) RETURN n")
    assert _is_write_cypher("MATCH (n) SET n.x = 1")
    assert _is_write_cypher("MATCH (n) DETACH DELETE n")


def test_reads_with_write_words_as_identifiers_or_literals_routed_to_read():
    assert not _is_write_cypher("MATCH (n) RETURN n.createdAt, n.preset, n.assetId")
    assert not _is_write_cypher("MATCH (n)-[:MERGED_PR]->(m) RETURN n, m")
    assert not _is_write_cypher("MATCH (n) WHERE n.note = 'please CREATE a ticket' RETURN n")
