"""Protocols for L8 induction pipeline — DIP + SAP + half-finished fix.

Per Naesengmoon SOLID lens HIGH-3 (pipeline.py stage_2/3/6/7 stub stability paradox):
- DIP: pipeline.run() depended on concrete induce_fca / validate / gate. Now injects
  via Stage and InductionOperator protocols.
- SAP: most-depended-on pipeline.py had concrete stub stages mixed with stable
  orchestrator. Now stable abstractions (Stage protocol) + explicit NotImplementedStage
  classes for missing implementations.
- half-finished: stub stages now explicitly raise NotImplementedStageError on call,
  not silently return placeholder dicts.
"""
# KG: eureka-canonical-2026-05-26

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable


class NotImplementedStageError(NotImplementedError):
    # KG: eureka-canonical-2026-05-26
    """Stage explicitly declared not-yet-implemented. Caller must accept this."""


@dataclass(frozen=True)
class StageResult:
    # KG: eureka-canonical-2026-05-26
    stage: str
    ok: bool
    payload: Any = None
    error: Optional[str] = None


@runtime_checkable
class Stage(Protocol):
    # KG: eureka-canonical-2026-05-26
    """A single pipeline stage. Stateless. Returns a StageResult."""

    name: str

    def run(self, context: dict[str, Any]) -> StageResult: ...


@runtime_checkable
class InductionOperator(Protocol):
    # KG: eureka-canonical-2026-05-26
    """Pluggable induction operator (FCA / AMIE3 / Leiden-LLM / future).

    Implementations live in induction_operators/ and self-register via
    induction_operators.registry.register_method().
    """

    method_name: str

    def induce(self, context: dict[str, Any]) -> Any:
        """Run induction. Returns an operator-specific result.

        The pipeline post-processes the result into AbstractClass + GeneralizesEdge
        instances. Operators don't need to know about the KG schema.
        """
        ...


@runtime_checkable
class QualityGate(Protocol):
    # KG: eureka-canonical-2026-05-26
    """Pluggable quality gate. Returns ok + diagnostic."""

    def check(self, abstract_classes: list[Any]) -> StageResult: ...


class NotImplementedStage:
    # KG: eureka-canonical-2026-05-26
    """Explicit stand-in for a pipeline stage that is not yet implemented.

    Calling run() raises NotImplementedStageError with the reason. This makes the
    half-finished status legible to callers instead of returning silent placeholder
    payloads.
    """

    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self.reason = reason

    def run(self, context: dict[str, Any]) -> StageResult:
        raise NotImplementedStageError(f"stage {self.name!r}: {self.reason}")


__all__ = [
    "InductionOperator",
    "NotImplementedStage",
    "NotImplementedStageError",
    "QualityGate",
    "Stage",
    "StageResult",
]
