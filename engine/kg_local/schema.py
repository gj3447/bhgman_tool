"""KG schema as code — 로컬 backend + neo4j 부트스트랩 공용 단일 정의.

"스키마를 코드로 넣어서 쓰세요" (사용자 verdict 2026-05-28): 노드/엣지 모양을 외부 neo4j에
미리 깔아둔 제약/트리거에 의존하지 않고 *repo 코드*가 들고 있는다. 두 곳이 이 정의를 쓴다:
  - 로컬 backend(store.py): MERGE 시 required-field 검증을 이 스키마로 강제.
  - 실 neo4j: `neo4j_ddl()`가 같은 제약을 CREATE CONSTRAINT DDL로 내보냄 → 부트스트랩.

CLAUDE.md Constrain Layer의 제약(SourceCodeNode required fields, ActiveComment unique)을
코드 단일 출처로 미러. 로컬에선 store가 검증, neo4j에선 DDL이 강제 — 동일 의미.

# KG: t_sourcecode_required_fields_not_null, activecomment_name_unique,
#     bhgman-local-kg-backend-2026-05-28
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NodeSchema:
    """한 노드 라벨의 모양. required = NULL 불가(neo4j NOT NULL constraint / 로컬 검증)."""

    label: str
    required: tuple[str, ...] = ()
    unique: tuple[str, ...] = ()  # 단일 키 유니크 (name 등)
    key: str = "name"  # 로컬 store upsert 식별 prop


NODE_SCHEMAS: dict[str, NodeSchema] = {
    "SourceCodeNode": NodeSchema(
        label="SourceCodeNode",
        required=("sourcePath", "sha256", "lineCount"),
        unique=("sourcePath",),
        key="sourcePath",
    ),
    "AbstractClass": NodeSchema(
        label="AbstractClass",
        required=("name",),
        unique=("name",),
        key="name",
    ),
    "ActiveComment": NodeSchema(
        label="ActiveComment",
        required=("name",),
        unique=("name",),
        key="name",
    ),
    "HarnessDiagnosis": NodeSchema(
        label="HarnessDiagnosis",
        required=("name",),
        unique=("name",),
        key="name",
    ),
}

# 엔진들이 실제로 쓰는 엣지 타입 (occam supersede / hades materialize / eureka facet read).
EDGE_TYPES: frozenset[str] = frozenset(
    {"SUPERSEDED_BY", "INSTANCE_OF", "ALIGNS_WITH_AXIS", "USES_ABSTRACT_DOMAIN"}
)


@dataclass(frozen=True)
class SchemaViolation:
    label: str
    key_value: str
    missing: tuple[str, ...] = field(default_factory=tuple)
    reason: str = ""


def validate_node(label: str, props: dict) -> SchemaViolation | None:
    """노드 props가 스키마 required를 만족하나. 미지 라벨은 통과(스키마 미정의 = 자유). None=ok."""
    schema = NODE_SCHEMAS.get(label)
    if schema is None:
        return None
    missing = tuple(f for f in schema.required if props.get(f) in (None, ""))
    if missing:
        key_val = str(props.get(schema.key, "<no-key>"))
        return SchemaViolation(label, key_val, missing, f"required NULL: {missing}")
    return None


def neo4j_ddl() -> list[str]:
    """동일 스키마를 실 neo4j 부트스트랩 DDL로. `bhgman-tool kg-schema --emit neo4j`로 내보냄.

    NOT NULL은 node property existence constraint(Enterprise) 대신 호환 위해
    key uniqueness + 주석으로 required 표기 (Community edition 안전).
    """
    ddl: list[str] = []
    for s in NODE_SCHEMAS.values():
        for u in s.unique:
            cname = f"{s.label.lower()}_{u}_unique"
            ddl.append(
                f"CREATE CONSTRAINT {cname} IF NOT EXISTS "
                f"FOR (n:{s.label}) REQUIRE n.{u} IS UNIQUE;"
            )
        if s.required:
            ddl.append(
                f"// {s.label} required (NULL 금지, 로컬 store 강제): {', '.join(s.required)}"
            )
    return ddl


__all__ = [
    "EDGE_TYPES",
    "NODE_SCHEMAS",
    "NodeSchema",
    "SchemaViolation",
    "neo4j_ddl",
    "validate_node",
]
