"""make_local_runner TDD — 엔진 cypher 템플릿 → 로컬 store dispatch (neo4j 없이).

각 핸들러를 *엔진이 실제로 emit하는* cypher 문자열로 호출해 검증 (dispatch feature 회귀 방지).

# KG: bhgman-local-kg-backend-2026-05-28
"""

from __future__ import annotations

import pytest
from runner import UnsupportedLocalQuery, make_local_runner
from store import LocalKgStore


def _store(tmp_path):
    return LocalKgStore(tmp_path / "kg.json")


# occam이 실제 emit하는 fetch (kg_adapter._FETCH_ALL 형태)
_OCCAM_FETCH = (
    "MATCH (s:SourceCodeNode) WHERE s.sha256 IS NOT NULL AND s.lineCount IS NOT NULL "
    "AND s.sourcePath IS NOT NULL AND (s.status IS NULL OR s.status <> 'SUPERSEDED') "
    "RETURN s.name AS name, s.sourcePath AS source_path, s.sha256 AS sha256, s.lineCount AS line_count"
)
_OCCAM_SUPERSEDE = (
    "MATCH (stale:SourceCodeNode {name: $stale_name}) MATCH (current:SourceCodeNode {name: $current_name}) "
    "WHERE stale <> current SET stale.status = 'SUPERSEDED', stale.supersededBy = $current_name "
    "MERGE (stale)-[:SUPERSEDED_BY]->(current) RETURN stale.name AS superseded"
)
_HADES_FETCH = (
    "MATCH (a:AbstractClass) WHERE a.verdictStatus = 'ACCEPTED' AND (a.status IS NULL OR a.status <> 'CANONICAL') "
    "RETURN a.name AS concept, a.verdictStatus AS verdict, coalesce(a.extent, []) AS members"
)
_HADES_MERGE = (
    "MERGE (a:AbstractClass {name:$concept}) SET a.status='CANONICAL', a.realizedBy='hades'"
)
_HADES_LINK = "UNWIND $members AS m MATCH (a:AbstractClass {name:$concept}) MATCH (o {name:m}) MERGE (o)-[:INSTANCE_OF]->(a)"
_EUREKA_READ = (
    "MATCH (o)-[r]->(v) WHERE type(r) IN $facet_rels WITH o, count(DISTINCT v) AS facet_deg, "
    "collect(DISTINCT type(r) + ':' + v.name) AS attrs RETURN o.name AS object, attrs AS attributes"
)


def test_occam_fetch_excludes_superseded(tmp_path):
    s = _store(tmp_path)
    s.merge_node(
        "SourceCodeNode", "sourcePath", "a.py", {"name": "a", "sha256": "h", "lineCount": 1}
    )
    s.merge_node(
        "SourceCodeNode",
        "sourcePath",
        "b.py",
        {"name": "b", "sha256": "h", "lineCount": 1, "status": "SUPERSEDED"},
    )
    run = make_local_runner(s)
    rows = run(_OCCAM_FETCH, {})
    assert {r["name"] for r in rows} == {"a"}  # superseded 제외


def test_occam_supersede_sets_status_and_edge(tmp_path):
    s = _store(tmp_path)
    s.merge_node(
        "SourceCodeNode", "sourcePath", "old.py", {"name": "old", "sha256": "h1", "lineCount": 1}
    )
    s.merge_node(
        "SourceCodeNode", "sourcePath", "new.py", {"name": "new", "sha256": "h2", "lineCount": 9}
    )
    run = make_local_runner(s)
    out = run(_OCCAM_SUPERSEDE, {"stale_name": "old", "current_name": "new", "reason": "r"})
    assert out == [{"superseded": "old", "current": "new"}]
    old = s.find_one("name", "old")
    assert old["props"]["status"] == "SUPERSEDED"
    assert any(e["type"] == "SUPERSEDED_BY" for e in s.edges)


def test_hades_fetch_then_materialize(tmp_path):
    s = _store(tmp_path)
    s.merge_node(
        "AbstractClass", "name", "ac", {"verdictStatus": "ACCEPTED", "extent": ["m1", "m2"]}
    )
    run = make_local_runner(s)
    fetched = run(_HADES_FETCH, {})
    assert fetched == [{"concept": "ac", "verdict": "ACCEPTED", "members": ["m1", "m2"]}]
    run(_HADES_MERGE, {"concept": "ac"})
    run(_HADES_LINK, {"concept": "ac", "members": ["m1", "m2"]})
    ac = s.find_one("name", "ac", "AbstractClass")
    assert ac["props"]["status"] == "CANONICAL" and ac["props"]["realizedBy"] == "hades"
    assert sum(1 for e in s.edges if e["type"] == "INSTANCE_OF") == 2
    # 실현된 ac는 다음 fetch에서 제외 (status=CANONICAL)
    assert run(_HADES_FETCH, {}) == []


def test_eureka_facet_read_builds_context(tmp_path):
    s = _store(tmp_path)
    o = s.merge_node("Topic", "name", "Topology", {})
    ax = s.merge_node("Axis", "name", "Math", {})
    dom = s.merge_node("Domain", "name", "Algebra", {})
    s.add_edge(o, "ALIGNS_WITH_AXIS", ax)
    s.add_edge(o, "USES_ABSTRACT_DOMAIN", dom)
    run = make_local_runner(s)
    rows = run(
        _EUREKA_READ,
        {
            "facet_rels": ["ALIGNS_WITH_AXIS", "USES_ABSTRACT_DOMAIN"],
            "bulk_labels": [],
            "hub_cap": 4,
            "min_facets": 2,
        },
    )
    assert rows == [
        {
            "object": "Topology",
            "attributes": ["ALIGNS_WITH_AXIS:Math", "USES_ABSTRACT_DOMAIN:Algebra"],
        }
    ]


def test_eureka_excludes_bulk_label(tmp_path):
    s = _store(tmp_path)
    o = s.merge_node("Comment", "name", "noise", {})  # bulk label
    ax = s.merge_node("Axis", "name", "Math", {})
    s.add_edge(o, "ALIGNS_WITH_AXIS", ax)
    run = make_local_runner(s)
    rows = run(
        _EUREKA_READ,
        {
            "facet_rels": ["ALIGNS_WITH_AXIS"],
            "bulk_labels": ["Comment"],
            "hub_cap": 4,
            "min_facets": 1,
        },
    )
    assert rows == []


def test_unsupported_query_raises_not_silent(tmp_path):
    run = make_local_runner(_store(tmp_path))
    with pytest.raises(UnsupportedLocalQuery):
        run("MATCH (n:Mystery) RETURN n", {})
