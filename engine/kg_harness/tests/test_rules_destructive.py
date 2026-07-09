"""DestructiveWriteRule — kg_harness delete-blind 봉합 (RED-first).

2026-07-08 8차원 감사 confirmed-high: DETACH DELETE / DELETE / DROP / 파괴적 apoc 가
validate_write 를 ALLOWED 로 통과했다 — 가드의 위협모델이 dedup/god-object/orphan 뿐이라
공유 KG 의 최상위 위협(비가역 삭제)이 chokepoint 에서 무검출. 부수 발견: 정규식 룰이
주석 삽입(`CREATE /* x */ (n:Foo)`)으로 우회되고, 반대로 주석 *텍스트* 의 단어에는
오탐한다(문자열/주석 비구분). 이 테스트들이 그 부재를 핀하고(RED),
DestructiveWriteRule + string-aware 주석 스트립 전처리가 GREEN 으로 만든다.

# KG: LakatosTree_BhgmanSeamIntegrity_20260708/kgh_destructive_rule
"""

from __future__ import annotations

from engine.kg_harness.write_guard import (
    ALLOW_DESTRUCTIVE_MARKER,
    strip_cypher_comments,
    supersede_node,
    upsert_node,
    validate_write,
)


# ── 파괴 연산 = ERROR (archive-only covenant 의 chokepoint 승격) ────────────────


def test_detach_delete_refused():
    report = validate_write("MATCH (n:Concept {name:'x'}) DETACH DELETE n")
    assert not report.ok
    assert "DESTRUCTIVE_WRITE" in {v.code for v in report.errors}


def test_plain_delete_refused():
    assert not validate_write("MATCH (n:Concept {name:'x'}) DELETE n").ok


def test_drop_constraint_refused():
    assert not validate_write("DROP CONSTRAINT kgh_Concept_name_unique IF EXISTS").ok


def test_remove_refused():
    # REMOVE n.prop = 무이력 데이터 소실(archive-only covenant 위반), REMOVE n:Label = 라벨 파괴.
    # (:Superseded 제거는 오늘도 OrphanTombstoneRule 에 *우연히* 걸리므로, 진짜 blind 지점인
    # 속성 REMOVE 로 핀한다.)
    assert not validate_write("MATCH (n:Concept {name:'x'}) REMOVE n.summary").ok


def test_apoc_merge_nodes_refused():
    cy = "MATCH (a:Concept),(b:Concept) CALL apoc.refactor.mergeNodes([a,b],{}) YIELD node RETURN node"
    assert not validate_write(cy).ok


def test_apoc_nodes_delete_refused():
    assert not validate_write("MATCH (n:Concept {status:'dead'}) CALL apoc.nodes.delete(n, 100)").ok


def test_apoc_periodic_iterate_with_destructive_inner_refused():
    # 내부 쿼리는 문자열 인자지만 전체 텍스트 lint 에 그대로 노출된다 — DELETE 가 잡혀야 한다.
    cy = (
        'CALL apoc.periodic.iterate("MATCH (n:Concept) RETURN n", '
        '"DETACH DELETE n", {batchSize:100})'
    )
    assert not validate_write(cy).ok


# ── 주석 우회/오탐 (string-aware 전처리) ──────────────────────────────────────


def test_comment_evasion_on_create_refused():
    # 기존 NakedCreateRule 정규식은 CREATE 와 ( 사이 블록주석으로 우회됐다.
    report = validate_write("CREATE /* sneaky */ (n:Concept {name:'evil'})")
    assert not report.ok
    assert "NAKED_CREATE" in {v.code for v in report.errors}


def test_comment_evasion_on_destructive_refused():
    assert not validate_write("MATCH (n:Concept) DETACH /* c */ DELETE n").ok


def test_comment_text_does_not_false_positive():
    # 주석 *텍스트* 속 단어는 위반이 아니다 — raw 정규식은 여기 오탐했다.
    cy = "MATCH (n:Concept {id:$i}) // note: never DETACH DELETE here\nSET n.y = $y"
    assert validate_write(cy).ok


def test_url_in_string_literal_is_not_a_comment():
    # 'http://...' 의 // 는 주석 시작이 아니다 — 문자열 무시하고 자르면 뒤의 DELETE 를 놓친다.
    bad = "MERGE (n:Ref {id:$id}) SET n.url = 'http://e.test/x' DETACH DELETE n"
    assert not validate_write(bad).ok
    good = "MERGE (n:Ref {id:$id}) SET n.url = 'http://e.test/x'"
    assert validate_write(good).ok


def test_strip_preserves_kgh_directives():
    stripped = strip_cypher_comments("// kgh:allow-create\nCREATE (n:Boot {id:$i})")
    assert "kgh:allow-create" in stripped


# ── opt-out 마커 + 정상 경로 counter-test (revert-proof 양방향) ────────────────


def test_allow_destructive_marker_opts_out():
    cy = f"{ALLOW_DESTRUCTIVE_MARKER}\nMATCH (n:TmpFixture {{run: $run}}) DETACH DELETE n"
    assert validate_write(cy).ok


def test_builders_still_pass():
    up, _ = upsert_node("Concept", "name", "x", {"summary": "s"})
    assert validate_write(up).ok
    sup, _ = supersede_node("Concept", "name", "old", "new", "dup")
    assert validate_write(sup).ok


def test_benign_merge_set_still_passes():
    assert validate_write("MERGE (n:Concept {name:$name}) SET n += $props").ok
