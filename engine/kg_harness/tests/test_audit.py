"""사후 audit TDD — fake runner로 위반 탐지 로직 고정.

# KG: occam-pass-metahumotonic-20260626
"""

from __future__ import annotations

from engine.kg_harness.audit import (
    audit_all,
    dup_id_cypher,
    orphan_tombstone_cypher,
    versioned_field_cypher,
)


def test_dup_id_cypher_shape():
    cy, p = dup_id_cypher("ReferenceSite", "sourceId")
    assert "MATCH (n:`ReferenceSite`)" in cy and "n.`sourceId`" in cy
    assert "c > 1" in cy and p == {}


def test_orphan_tombstone_cypher_requires_missing_edge():
    cy, _ = orphan_tombstone_cypher()
    assert "n:Superseded" in cy and "NOT (n)-[:SUPERSEDED_BY]->()" in cy


def test_versioned_field_cypher_matches_vN_keys():
    cy, _ = versioned_field_cypher("Apostle")
    assert "_v" in cy and "keys(n)" in cy


def test_audit_all_collects_violations_from_fake_kg():
    def fake_run(cy, p):
        if "Superseded" in cy:
            return [{"orphan_tombstones": 7}]
        if "versioned_nodes" in cy or "_v" in cy:
            return [{"versioned_nodes": 2}] if "Apostle" in cy else [{"versioned_nodes": 0}]
        # dup_id: ReferenceSite dirty, 나머지 clean
        return (
            [{"dup_groups": 5, "dup_nodes": 12}]
            if "ReferenceSite" in cy
            else [{"dup_groups": 0, "dup_nodes": 0}]
        )

    findings = audit_all(fake_run, {"ReferenceSite": "sourceId", "Apostle": "roman"})
    codes = {(f.code, f.label) for f in findings}
    assert ("DUP_ID", "ReferenceSite") in codes
    assert ("VERSIONED_FIELD", "Apostle") in codes
    assert ("ORPHAN_TOMBSTONE", "*") in codes


def test_audit_all_clean_kg_returns_empty():
    findings = audit_all(
        lambda cy, p: [
            {"dup_groups": 0, "dup_nodes": 0, "versioned_nodes": 0, "orphan_tombstones": 0}
        ],
        {"Apostle": "roman"},
    )
    assert findings == []


def test_audit_all_can_skip_versioned_scan():
    calls = []

    def fake_run(cy, p):
        calls.append(cy)
        return [{"dup_groups": 0, "dup_nodes": 0, "orphan_tombstones": 0}]

    audit_all(fake_run, {"Apostle": "roman"}, check_versioned=False)
    assert not any("keys(n)" in c for c in calls)
