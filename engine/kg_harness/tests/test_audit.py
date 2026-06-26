"""사후 audit TDD — fake runner로 위반 탐지 로직 고정.

# KG: occam-pass-metahumotonic-20260626
"""

from __future__ import annotations

from engine.kg_harness.audit import (
    audit_all,
    dup_id_cypher,
    lint_statements,
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


def test_lint_statements_catches_apoc_and_csv_in_corpus():
    # chokepoint 우회 텍스트(벌크 스크립트)를 사후 그물로 — guard와 동일 룰
    corpus = [
        "MATCH (n) CALL apoc.create.node(['X'], {}) YIELD node RETURN node",
        "LOAD CSV FROM 'f.csv' AS r MERGE (n:N {id:r[0]})",
        "MERGE (n:Apostle {roman:$r}) SET n.role=$x",  # clean
    ]
    findings = lint_statements(corpus)
    codes = {f.code for f in findings}
    assert "LINT:APOC_CREATE" in codes
    assert "LINT:BULK_LOAD" in codes
    # clean 문장(stmt[2])은 위반 없음
    assert not any(f.label == "stmt[2]" for f in findings)


def test_lint_statements_errors_only_mode():
    corpus = ["LOAD CSV FROM 'f.csv' AS r MERGE (n:N {id:r[0]})"]  # WARN만
    assert lint_statements(corpus) != []  # 기본: WARN 포함
    assert lint_statements(corpus, warnings=False) == []  # ERROR-only: 빔


def test_lint_own_artifacts_are_clean():
    # dogfood: 우리 운영자 아티팩트(.cypher)는 룰을 통과해야 한다
    import pathlib

    here = pathlib.Path(__file__).resolve().parents[1]
    stmts = []
    for f in ("constraints.cypher", "rewire_orphan_tombstones.cypher"):
        text = (here / f).read_text(encoding="utf-8")
        stmts += [s for s in text.split(";") if s.strip() and not s.strip().startswith("//")]
    errors = lint_statements(stmts, warnings=False)
    assert errors == [], errors


def test_audit_all_can_skip_versioned_scan():
    calls = []

    def fake_run(cy, p):
        calls.append(cy)
        return [{"dup_groups": 0, "dup_nodes": 0, "orphan_tombstones": 0}]

    audit_all(fake_run, {"Apostle": "roman"}, check_versioned=False)
    assert not any("keys(n)" in c for c in calls)
