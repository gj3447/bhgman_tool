"""decoy arm — placebo control isolating oracle-SIGNAL from input-context-VOLUME (step 4, prereg P2).

`_arm_decoy` mirrors `_arm_repair` exactly (same K-loop, same varied seed, same prior-proof context
threading) EXCEPT the fed-back error is a well-formed-but-WRONG Lean error from a DIFFERENT task —
constant across rounds, never this task's real oracle error. So repair and decoy have the SAME input-
context volume; only repair carries the true oracle signal. The prereg conclusion (P2) needs
`repair > decoy AND decoy ≈ bestN`; if `decoy ≈ repair`, the win was context-volume, not oracle-content.

Deterministic: a fake `evaluate` (no lean) + a spy `complete`.

# KG: prom16-bhgman-pierce-direction-2026-07-12 (step 4 / P2), PIERCE_PREREGISTRATION.md
"""

from __future__ import annotations

from engine.efficacy import lean_headroom_run as lhr
from engine.efficacy.lean_tasks import TASKS


class _V:
    """minimal lean_oracle verdict double."""

    def __init__(self, *, proven: bool, error_tail: str = "ERR", graded: float = 0.0) -> None:
        self.compiles = proven
        self.proven = proven
        self.graded_score = 1.0 if proven else graded
        self.error_tail = "" if proven else error_tail
        self.sorry_tainted = False


def test_decoy_error_uses_a_different_tasks_reference_proof(monkeypatch):
    """_decoy_error_for(task) evaluates a DIFFERENT task's reference proof against THIS task's
    statement, yielding a real-but-mismatched Lean error."""
    lhr._decoy_error_for.cache_clear()
    seen = {}

    def fake_eval(name, signature, proof, *, preamble=""):  # noqa: ANN001, ARG001
        seen["proof"] = proof
        return _V(proven=False, error_tail="DECOY_ERR")

    monkeypatch.setattr(lhr, "evaluate", fake_eval)
    idx = 3  # gauss
    task = TASKS[idx]
    other = TASKS[(idx + 1) % len(TASKS)]
    err = lhr._decoy_error_for(task.name)
    assert err == "DECOY_ERR"
    assert seen["proof"] == other.reference_proof  # a DIFFERENT task's proof, not this task's


def test_arm_decoy_feeds_fixed_bogus_error_not_the_oracle(monkeypatch):
    """rounds 2+ feed the CONSTANT decoy error (from a different task), never the per-attempt oracle
    error_tail — that is the isolation. round 1 has no feedback (mirrors repair)."""
    lhr._decoy_error_for.cache_clear()
    n = {"i": 0}

    def fake_eval(name, signature, proof, *, preamble=""):  # noqa: ANN001, ARG001
        # decoy-error computation uses a different task's proof → return the fixed DECOY error.
        # the model's own attempts ("by sorry") never prove and return a VARYING oracle error.
        if proof == "by sorry":
            n["i"] += 1
            return _V(proven=False, error_tail=f"ORACLE_ERR_{n['i']}")
        return _V(proven=False, error_tail="DECOY_ERR")

    monkeypatch.setattr(lhr, "evaluate", fake_eval)
    prompts: list[str] = []

    def spy_complete(messages, seed):  # noqa: ANN001, ARG001
        prompts.append(next(m["content"] for m in messages if m["role"] == "user"))
        return "by sorry"  # never proves → loop runs full K

    proven, _best = lhr._arm_decoy(TASKS[3], spy_complete, 3, 0)
    assert proven is False
    assert len(prompts) == 3
    assert "Lean reported" not in prompts[0]  # round 1: no feedback (mirror repair)
    assert "DECOY_ERR" in prompts[1] and "DECOY_ERR" in prompts[2]  # constant bogus error
    assert (
        "ORACLE_ERR" not in prompts[1] and "ORACLE_ERR" not in prompts[2]
    )  # NEVER the real oracle


def test_arm_decoy_records_decoy_arm_and_short_circuits_on_proof(monkeypatch):
    """arm label = 'decoy'; proving short-circuits (returns True, 1.0) like the other arms."""
    lhr._decoy_error_for.cache_clear()
    logged: list[dict] = []

    def fake_eval(name, signature, proof, *, preamble=""):  # noqa: ANN001, ARG001
        if proof == "PROVES":
            return _V(proven=True)
        return _V(proven=False, error_tail="DECOY_ERR")

    monkeypatch.setattr(lhr, "evaluate", fake_eval)
    monkeypatch.setattr(lhr, "_log_record", lambda log, rec: logged.append(rec))

    seq = iter(["by sorry", "PROVES", "unreached"])

    def complete(messages, seed):  # noqa: ANN001, ARG001
        return next(seq)

    proven, best = lhr._arm_decoy(TASKS[3], complete, 4, 0)
    assert proven is True and best == 1.0
    arms = [r["arm"] for r in logged if r.get("record_type") == "attempt"]
    assert arms == ["decoy", "decoy"]  # stopped at the proving attempt (2 of 4)
