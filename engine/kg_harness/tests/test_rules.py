"""rule registry TDD — #2 false-negative 차단(apoc/동적라벨/LOAD CSV) + OCP 확장성.

# KG: occam-pass-metahumotonic-20260626
"""

from __future__ import annotations

from engine.kg_harness import RULES, Rule, Severity, Violation, validate_write
from engine.kg_harness.rules import ApocCreateRule, BulkLoadRule, NakedCreateRule


# ── #2: 정규식 우회 false-negative 차단 ──────────────────────────────────────


def test_apoc_create_node_is_error():
    # 정규식 NakedCreate를 우회하던 동적 생성 — 이제 잡힘
    r = validate_write("CALL apoc.create.node(['Apostle'], {name:'x'}) YIELD node RETURN node")
    assert not r.ok
    assert any(v.code == "APOC_CREATE" for v in r.errors)


def test_apoc_create_addlabels_is_error():
    r = validate_write("MATCH (n) CALL apoc.create.addLabels(n, ['Foo']) YIELD node RETURN node")
    assert any(v.code == "APOC_CREATE" for v in r.errors)


def test_apoc_merge_node_is_allowed():
    # 키 기반 MERGE 등가 → 정당, 미플래그
    r = validate_write("CALL apoc.merge.node(['Apostle'], {roman:'IV'}, {}, {}) YIELD node RETURN node")
    assert r.ok
    assert not any(v.code == "APOC_CREATE" for v in r.violations)


def test_load_csv_is_warned():
    r = validate_write("LOAD CSV WITH HEADERS FROM 'file:///x.csv' AS row MERGE (n:Node {id: row.id})")
    assert r.ok  # WARN은 통과
    assert any(v.code == "BULK_LOAD" and v.severity is Severity.WARN for v in r.warnings)


def test_apoc_create_respects_optout_marker():
    from engine.kg_harness import ALLOW_CREATE_MARKER

    r = validate_write(f"CALL apoc.create.node(['Boot'], {{}}) YIELD node RETURN node {ALLOW_CREATE_MARKER}")
    assert not any(v.code == "APOC_CREATE" for v in r.violations)


# ── OCP: 룰 레지스트리 확장성 ────────────────────────────────────────────────


def test_registry_lists_rule_objects():
    codes = {r.code for r in RULES}
    assert {"NAKED_CREATE", "APOC_CREATE", "BULK_LOAD", "VERSIONED_FIELD", "ORPHAN_TOMBSTONE"} <= codes
    assert all(isinstance(r, Rule) for r in RULES)


def test_custom_rule_can_be_injected_without_editing_validate():
    class NoGremlinRule(Rule):
        code = "NO_GREMLIN"

        def check(self, cypher):
            return (
                [Violation(self.code, Severity.ERROR, "gremlin 금지", "gremlin")]
                if "gremlin" in cypher
                else []
            )

    r = validate_write("MERGE (n:X {id:1}) SET n.engine='gremlin'", rules=[NoGremlinRule()])
    assert any(v.code == "NO_GREMLIN" for v in r.errors)


def test_injected_rules_replace_defaults():
    # 커스텀 룰만 주면 기본 룰은 적용 안 됨(naked CREATE인데 NoGremlin만 봄)
    r = validate_write("CREATE (n:X {a:1})", rules=[NakedCreateRule()])
    assert any(v.code == "NAKED_CREATE" for v in r.errors)
    r2 = validate_write("CREATE (n:X {a:1})", rules=[BulkLoadRule()])
    assert r2.ok  # BulkLoad만 봤으니 CREATE 통과(주입 룰만 적용 증명)
