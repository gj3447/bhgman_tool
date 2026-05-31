"""InductionMethod registry — OCP fix for L8 induction operator extensibility.

Replaces hardcoded `InductionMethod(str, Enum)` dispatch with a runtime-extensible
registry. New operators self-register on import, so adding a 6th operator does not
require modifying models.py.

Default registered set mirrors the previous enum:
- fca, amie3, leiden-llm, manual, unknown
"""
# KG: eureka-canonical-2026-05-26

from __future__ import annotations

import threading


_REGISTERED: set[str] = {"fca", "amie3", "leiden-llm", "manual", "unknown"}
_LOCK = threading.Lock()
_INDUCED_AUTOMATED = {"fca", "amie3", "leiden-llm"}


def register_method(name: str, *, automated: bool = False) -> None:
    """Register a new induction method name. Idempotent."""
    with _LOCK:
        _REGISTERED.add(name)
        if automated:
            _INDUCED_AUTOMATED.add(name)


def is_registered(name: str) -> bool:
    return name in _REGISTERED


def is_automated(name: str) -> bool:
    """True if the method is an automated inducer (FCA/AMIE3/Leiden-LLM family).

    Used by AbstractClass model_validator to enforce induced→{extent,intent,
    stabilityScore} required fields.
    """
    return name in _INDUCED_AUTOMATED


def known_methods() -> frozenset[str]:
    return frozenset(_REGISTERED)


__all__ = [
    "is_automated",
    "is_registered",
    "known_methods",
    "register_method",
]
