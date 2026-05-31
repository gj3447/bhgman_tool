"""Application-side schema enforcement for AbstractClass + GeneralizesEdge.

Why application-side: APOC trigger t_abstractclass_required_fields BLOCKED on Community Edition
without admin role (seed-hookinstall-t_abstractclass_required_fields-2026-05-20).
This validator runs BEFORE any MERGE/CREATE Cypher and rejects malformed nodes/edges.
"""

from __future__ import annotations

from typing import Any

from engine.eureka.induction_models import AbstractClass, GeneralizesEdge


class SchemaViolation(ValueError):
    """Raised when an AbstractClass or GeneralizesEdge fails schema validation."""


def validate_abstract_class(payload: dict[str, Any]) -> AbstractClass:
    try:
        return AbstractClass.model_validate(payload)
    except Exception as e:
        raise SchemaViolation(f"AbstractClass schema violation: {e}\nPayload: {payload}") from e


def validate_generalizes_edge(payload: dict[str, Any]) -> GeneralizesEdge:
    try:
        return GeneralizesEdge.model_validate(payload)
    except Exception as e:
        raise SchemaViolation(f"GeneralizesEdge schema violation: {e}\nPayload: {payload}") from e


def gate_before_merge(
    abstract_classes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> tuple[list[AbstractClass], list[GeneralizesEdge]]:
    """Run validation gate for a batch about to be MERGEd into Neo4j.

    Raises SchemaViolation on first failure (fail-fast). Caller catches and
    decides whether to skip the offending item or abort the batch.
    """
    validated_acs = [validate_abstract_class(p) for p in abstract_classes]
    validated_edges = [validate_generalizes_edge(p) for p in edges]
    return validated_acs, validated_edges


__all__ = [
    "SchemaViolation",
    "gate_before_merge",
    "validate_abstract_class",
    "validate_generalizes_edge",
]
