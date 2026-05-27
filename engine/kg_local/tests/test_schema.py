"""KG schema-as-code TDD. # KG: bhgman-local-kg-backend-2026-05-28"""

from __future__ import annotations

from schema import NODE_SCHEMAS, neo4j_ddl, validate_node


def test_sourcecodenode_missing_required_flagged():
    v = validate_node("SourceCodeNode", {"sourcePath": "x.py"})  # sha256/lineCount 결손
    assert v is not None
    assert "sha256" in v.missing and "lineCount" in v.missing


def test_sourcecodenode_complete_ok():
    v = validate_node("SourceCodeNode", {"sourcePath": "x.py", "sha256": "a", "lineCount": 5})
    assert v is None


def test_unknown_label_passes():
    # 스키마 미정의 라벨 = 자유(검증 안 함).
    assert validate_node("RandomThing", {}) is None


def test_neo4j_ddl_emits_constraints():
    ddl = "\n".join(neo4j_ddl())
    assert "CREATE CONSTRAINT" in ddl
    assert "SourceCodeNode" in ddl and "AbstractClass" in ddl
    # required 표기 주석 포함
    assert "sha256" in ddl


def test_schema_covers_engine_node_types():
    assert {"SourceCodeNode", "AbstractClass"} <= set(NODE_SCHEMAS)
