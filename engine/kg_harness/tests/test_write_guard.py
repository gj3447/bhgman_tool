"""kg_harness write-guard TDD — 3대 불변식 + 빌더 by-construction + chokepoint 강제.

적대적: 통과해야 할 정당 cypher(관계 CREATE, CONSTRAINT, SUPERSEDED_BY 동반)와
막아야 할 위반(naked CREATE, _vN 누적, 묘비-without-edge)을 양쪽 다 고정.

# KG: occam-pass-metahumotonic-20260626
"""

from __future__ import annotations

import pytest

from engine.kg_harness.write_guard import (
    ALLOW_CREATE_MARKER,
    GuardReport,
    Severity,
    WriteGuardError,
    constraint_cypher,
    guarded_run,
    supersede_node,
    upsert_node,
    validate_write,
)


# ── INV1: anti-dup (naked CREATE) ────────────────────────────────────────────


def test_naked_create_of_labeled_node_is_error():
    r = validate_write("CREATE (n:Apostle {name: 'X'})")
    assert not r.ok
    assert any(v.code == "NAKED_CREATE" for v in r.errors)


def test_merge_with_stable_key_is_clean():
    r = validate_write("MERGE (n:Apostle {roman: $id}) SET n.role = $role")
    assert r.ok
    assert r.violations == ()


def test_relationship_create_is_not_flagged():
    # 라벨 없는 관계전용 CREATE는 정당 — 노드 dup이 아님.
    r = validate_write("MATCH (a:Foo {id:1}),(b:Foo {id:2}) CREATE (a)-[:REL]->(b)")
    assert r.ok, [v.code for v in r.errors]


def test_create_constraint_is_not_flagged():
    r = validate_write(constraint_cypher("Apostle", "roman"))
    assert r.ok, [v.code for v in r.errors]


def test_allow_create_marker_opts_out():
    cy = f"CREATE (n:BootstrapRoot {{k:1}}) {ALLOW_CREATE_MARKER}"
    r = validate_write(cy)
    assert r.ok
    assert not any(v.code == "NAKED_CREATE" for v in r.violations)


def test_merge_without_key_is_warn_not_error():
    r = validate_write("MERGE (n:Apostle)")
    assert r.ok  # WARN은 통과
    assert any(v.code == "MERGE_WITHOUT_KEY" and v.severity is Severity.WARN for v in r.warnings)


# ── INV2: anti-god-object (versioned fields) ─────────────────────────────────


def test_versioned_field_dot_access_is_error():
    r = validate_write("MATCH (n:Apostle) SET n.essence_v4 = $e")
    assert not r.ok
    assert any(v.code == "VERSIONED_FIELD" and v.evidence == "essence_v4" for v in r.errors)


def test_versioned_field_in_inline_map_is_error():
    r = validate_write("MERGE (n:Apostle {roman:$r}) SET n += {canonicalSources_v5: $c}")
    assert any(
        v.code == "VERSIONED_FIELD" and v.evidence == "canonicalSources_v5" for v in r.errors
    )


def test_string_literal_with_v_digit_is_not_flagged():
    # 'config_v2'는 *값* 리터럴 — 속성 키가 아니므로 FP 금지.
    r = validate_write("MERGE (n:Cfg {id:$i}) SET n.profile = 'config_v2'")
    assert not any(v.code == "VERSIONED_FIELD" for v in r.violations), r.violations


def test_stale_suffix_is_warn():
    r = validate_write("MATCH (n:Apostle) SET n.epithet_old = $x")
    assert r.ok
    assert any(v.code == "STALE_FIELD" and v.severity is Severity.WARN for v in r.warnings)


# ── INV3: anti-orphan (tombstone must carry edge) ────────────────────────────


def test_superseded_label_without_edge_is_error():
    r = validate_write("MATCH (n:Node {id:$i}) SET n:Superseded")
    assert not r.ok
    assert any(v.code == "ORPHAN_TOMBSTONE" for v in r.errors)


def test_superseded_status_without_edge_is_error():
    r = validate_write("MATCH (n:Node {id:$i}) SET n.status = 'SUPERSEDED'")
    assert any(v.code == "ORPHAN_TOMBSTONE" for v in r.errors)


def test_supersede_with_edge_is_clean():
    cy = (
        "MATCH (s:Node {id:$s}) MATCH (c:Node {id:$c}) "
        "SET s:Superseded, s.status='SUPERSEDED' "
        "MERGE (s)-[:SUPERSEDED_BY]->(c)"
    )
    r = validate_write(cy)
    assert r.ok, [v.code for v in r.errors]


# ── 빌더: by construction 불변식 만족 ────────────────────────────────────────


def test_upsert_node_builds_clean_merge():
    cy, params = upsert_node("Apostle", "roman", "III", {"role": "사회 축", "is_speaker": True})
    assert validate_write(cy).ok
    assert "MERGE (n:Apostle {roman: $id})" in cy
    assert "_kgh_updated_at = datetime()" in cy
    assert params == {"id": "III", "props": {"role": "사회 축", "is_speaker": True}}


def test_upsert_node_rejects_versioned_props():
    with pytest.raises(WriteGuardError) as ei:
        upsert_node("Apostle", "roman", "IX", {"essence_v4": "..."})
    assert any(v.code == "VERSIONED_FIELD" for v in ei.value.report.errors)


def test_upsert_node_rejects_injection_in_label():
    with pytest.raises(ValueError):
        upsert_node("Apostle) DETACH DELETE n //", "roman", "X", {})


def test_supersede_node_passes_its_own_guard_and_has_edge():
    cy, params = supersede_node("Node", "id", "old1", "new1", "dup")
    r = validate_write(cy)
    assert r.ok, [v.code for v in r.errors]
    assert "SUPERSEDED_BY" in cy
    assert "stale <> current" in cy  # self-supersede 차단
    assert params == {"stale": "old1", "current": "new1", "reason": "dup"}


def test_constraint_cypher_shape():
    cy = constraint_cypher("Apostle", "roman")
    assert cy == (
        "CREATE CONSTRAINT kgh_Apostle_roman_unique IF NOT EXISTS "
        "FOR (n:Apostle) REQUIRE n.roman IS UNIQUE"
    )


# ── chokepoint: guarded_run 강제 ─────────────────────────────────────────────


def test_guarded_run_executes_clean_write():
    seen = []

    def fake_run(cy, p):
        seen.append((cy, p))
        return [{"id": "III"}]

    cy, params = upsert_node("Apostle", "roman", "III", {"role": "x"})
    out = guarded_run(fake_run, cy, params)
    assert out == [{"id": "III"}]
    assert len(seen) == 1


def test_guarded_run_refuses_dirty_write_without_executing():
    seen = []

    def fake_run(cy, p):  # pragma: no cover — 호출되면 테스트 실패
        seen.append(cy)
        return []

    with pytest.raises(WriteGuardError):
        guarded_run(fake_run, "CREATE (n:Apostle {name:'x'})")
    assert seen == []  # ERROR면 runner 절대 호출 안 됨


def test_upsert_node_with_run_executes_via_guard():
    seen = []
    upsert_node(
        "Apostle", "roman", "I", {"role": "공간"}, run=lambda c, p: seen.append((c, p)) or []
    )
    assert len(seen) == 1


# ── GuardReport 동작 ─────────────────────────────────────────────────────────


def test_guard_report_partitions_errors_and_warnings():
    r = validate_write("CREATE (n:X {a:1}) SET n.b_old = 2")  # ERROR + WARN 혼합
    assert not r.ok
    assert {v.code for v in r.errors} == {"NAKED_CREATE"}
    assert {v.code for v in r.warnings} == {"STALE_FIELD"}


def test_empty_violations_report_is_ok():
    r = GuardReport(cypher="RETURN 1")
    assert r.ok and r.violations == ()
