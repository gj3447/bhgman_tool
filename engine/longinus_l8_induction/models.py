"""AbstractClass + GeneralizesEdge Pydantic v2 schemas.

Mirrors CONTRACT_AbstractClass_v1 (SYMPOSIUM/THEORY/LONGINUS/CONTRACT_AbstractClass_v1_2026-05-20.md).
Direction: (AbstractClass)-[:GENERALIZES]->(member) — option A (empirical 2026-05-20).

P3 (Naesengmoon SOLID HIGH): inductionMethod is `str` with registry validation,
not a closed enum, enabling OCP-compliant plugin registration of new operators.
The InductionMethod enum is preserved as a convenience for the 5 default names.

P4 (Naesengmoon SOLID MEDIUM): @model_validator enforces induced→{extent, intent,
stabilityScore} required when inductionMethod is an automated inducer.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from induction_operators.registry import is_automated, is_registered, known_methods


class InductionMethod(str, Enum):
    FCA = "fca"
    AMIE3 = "amie3"
    LEIDEN_LLM = "leiden-llm"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class AbstractClassStatus(str, Enum):
    PROPOSED = "PROPOSED"
    VERDICT_PENDING = "VerdictPending"
    CANONICAL = "CANONICAL"
    CANONICAL_DELEGATED = "CANONICAL_DELEGATED"
    REJECTED = "REJECTED"


class AbstractClass(BaseModel):
    """L8-induced abstract category over L1-L7 ReferenceSite member nodes."""

    name: str = Field(..., min_length=1, max_length=128)
    summary: str = Field(..., min_length=1, max_length=240)
    inductionMethod: str = Field(..., min_length=1)
    cycleId: str = Field(..., min_length=1)
    createdAt: dt.datetime
    status: AbstractClassStatus = AbstractClassStatus.PROPOSED

    extent: Optional[list[str]] = None
    intent: Optional[list[str]] = None
    stabilityScore: Optional[float] = Field(None, ge=0.0, le=1.0)
    silhouette: Optional[float] = Field(None, ge=-1.0, le=1.0)
    modularity: Optional[float] = Field(None, ge=-0.5, le=1.0)
    gamma: Optional[float] = Field(None, gt=0.0)
    provenance: Optional[dict] = None

    @field_validator("name")
    @classmethod
    def name_format(cls, v: str) -> str:
        if not (
            v.startswith("ac_")
            or v.startswith("AC_")
            or v.replace("-", "").replace("_", "").isalnum()
        ):
            raise ValueError(
                f"AbstractClass name must be kebab-case slug or ac_<elementId>_<size>_<rev>, got: {v}"
            )
        return v

    @field_validator("inductionMethod", mode="before")
    @classmethod
    def normalize_method(cls, v):
        if isinstance(v, InductionMethod):
            v = v.value
        v = str(v)
        if not is_registered(v):
            raise ValueError(
                f"unknown inductionMethod {v!r}; known: {sorted(known_methods())}. "
                "Register via induction_operators.registry.register_method() first."
            )
        return v

    @model_validator(mode="after")
    def induced_requires_extent_intent_stability(self):
        if is_automated(self.inductionMethod):
            missing = [
                f
                for f, v in (
                    ("extent", self.extent),
                    ("intent", self.intent),
                    ("stabilityScore", self.stabilityScore),
                )
                if v is None
            ]
            if missing:
                raise ValueError(
                    f"inductionMethod={self.inductionMethod!r} is an automated inducer; "
                    f"requires non-null: {missing}"
                )
        return self


class GeneralizesEdge(BaseModel):
    """(AbstractClass)-[:GENERALIZES]->(member) edge properties.

    Direction = option A: src=AbstractClass (general), tgt=member (specific).
    Confirmed empirically 2026-05-20 via 181 sample edges.
    """

    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    method: str = Field(..., min_length=1)
    communityId: Optional[str] = None
    cycleId: str = Field(..., min_length=1)
    createdAt: dt.datetime
    induced: bool

    @field_validator("method", mode="before")
    @classmethod
    def normalize_method(cls, v):
        if isinstance(v, InductionMethod):
            v = v.value
        v = str(v)
        if not is_registered(v):
            raise ValueError(f"unknown method {v!r}; known: {sorted(known_methods())}")
        return v

    @model_validator(mode="after")
    def confidence_required_when_induced(self):
        if self.induced is True and self.confidence is None:
            raise ValueError("confidence required when induced=true")
        return self


__all__ = [
    "AbstractClass",
    "AbstractClassStatus",
    "GeneralizesEdge",
    "InductionMethod",
]
