"""Small sample module for Longinus drift audit walkthrough.

KG: span-worked-example-longinus-simple-2026-05-13 (:AtomicSpan)
"""

from __future__ import annotations


# KG: lesson-greet-user-2026-05-13
# This reference matches: signature aligns with KG expectation.
def greet(name: str) -> str:
    return f"Hello, {name}"


# KG: lesson-validate-email-2026-05-13
# DELIBERATE DRIFT: KG expects validate(addr: str, strict: bool = False) -> bool
# but actual code has validate(email: str) -> bool.
# Longinus should report SigMismatch (PutGet violation) here.
def validate(email: str) -> bool:
    return "@" in email


# KG: lesson-add-numbers-2026-05-13
# This reference matches.
def add(a: int, b: int) -> int:
    return a + b
