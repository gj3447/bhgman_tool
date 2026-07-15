"""plain_baseline arm — a FAIR generic agent-with-oracle test-loop (prereg §3 plain_baseline, K8).

`_arm_plain` isolates the bhgman-specific scaffolding of `_arm_repair` from the task-fairness info a
fair generic agent must keep. It differs from repair in EXACTLY three declared ways and nothing else:
  1. conversation ACCUMULATION (full transcript in one user message) vs repair's last-proof/last-error
     structured template;
  2. FIXED seed = off every round vs repair's per-round varied seed;
  3. GENERIC persona vs the "Lean 4 expert" persona.
It keeps the SAME K, oracle, and task info (core Lean 4 / NO Mathlib, statement, output format). If
capable-model `repair <= plain`, the edge is a generic gen-verify-gap ⇒ operational-only (K8).

Deterministic: a fake `evaluate` (no lean) + a spy `complete`.

# KG: LakatosTree_BhgmanCeilingPierce_20260712, PIERCE_PREREGISTRATION §3 plain_baseline (K8)
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


def _spy(seq_default: str = "by sorry"):
    """a spy `complete` recording (user_text, system_text, seed) per call, returning scripted proofs."""
    calls: list[dict] = []

    def complete(messages, seed):  # noqa: ANN001
        sys_text = next(m["content"] for m in messages if m["role"] == "system")
        user_text = next(m["content"] for m in messages if m["role"] == "user")
        calls.append({"seed": seed, "system": sys_text, "user": user_text})
        complete.last_usage = (7, 3)  # per-call token usage surfaced (prereg P4)
        return seq_default

    complete.last_usage = (0, 0)
    return complete, calls


def test_plain_uses_fixed_seed_every_round(monkeypatch):
    """a plain session does not jitter seeds mid-loop — every round uses seed = off (vs repair off+i)."""
    monkeypatch.setattr(lhr, "evaluate", lambda *a, **k: _V(proven=False, error_tail="E"))
    complete, calls = _spy()
    lhr._arm_plain(TASKS[3], complete, 3, off=5)
    assert [c["seed"] for c in calls] == [5, 5, 5]  # FIXED, not 5/6/7


def test_plain_accumulates_full_transcript_in_one_user_message(monkeypatch):
    """round i>1's single user message contains EVERY prior attempt AND every prior raw error, in
    order — the plain agent's growing context lives in the user text (AgentClient flattens to 1+1)."""
    n = {"i": 0}

    def fake_eval(name, signature, proof, *, preamble=""):  # noqa: ANN001, ARG001
        n["i"] += 1
        return _V(proven=False, error_tail=f"ERR{n['i']}")

    monkeypatch.setattr(lhr, "evaluate", fake_eval)
    seq = iter(["ATT1", "ATT2", "ATT3"])
    calls: list[str] = []

    def complete(messages, seed):  # noqa: ANN001, ARG001
        calls.append(next(m["content"] for m in messages if m["role"] == "user"))
        complete.last_usage = (0, 0)
        return next(seq)

    complete.last_usage = (0, 0)
    lhr._arm_plain(TASKS[3], complete, 3, 0)
    assert "ATT1" not in calls[0] and "ERR" not in calls[0]  # round 1: no prior context
    assert "ATT1" in calls[1] and "ERR1" in calls[1]  # round 2: sees attempt 1 + error 1
    # round 3 sees BOTH prior attempts and BOTH prior errors (accumulation, not just the last)
    for token in ("ATT1", "ERR1", "ATT2", "ERR2"):
        assert token in calls[2], f"{token} missing from accumulated round-3 context"


def test_plain_uses_generic_persona_but_keeps_task_fairness_info(monkeypatch):
    """system prompt is a generic coding-agent persona (NOT the Lean-EXPERT template), yet the ask
    still carries no-Mathlib + the exact statement + the output-format instruction (fair, not strawman)."""
    monkeypatch.setattr(lhr, "evaluate", lambda *a, **k: _V(proven=False, error_tail="E"))
    complete, calls = _spy()
    task = TASKS[3]
    lhr._arm_plain(task, complete, 1, 0)
    sys_text = calls[0]["system"].lower()
    user_text = calls[0]["user"]
    assert "expert" not in sys_text  # generic persona, not the "Lean 4 expert" template
    assert "coding assistant" in sys_text
    # task-fairness info preserved (dropping any would strawman the arm — forbidden):
    assert "no mathlib" in user_text.lower()
    assert task.name in user_text and task.signature in user_text  # exact statement
    assert ":=" in user_text  # output-format instruction (proof term after ':=')


def test_plain_records_plain_arm_with_token_fields_and_short_circuits(monkeypatch):
    """arm label = 'plain'; token fields present; proving short-circuits like the other arms."""
    logged: list[dict] = []

    def fake_eval(name, signature, proof, *, preamble=""):  # noqa: ANN001, ARG001
        return _V(proven=(proof == "PROVES"))

    monkeypatch.setattr(lhr, "evaluate", fake_eval)
    monkeypatch.setattr(lhr, "_log_record", lambda log, rec: logged.append(rec))
    seq = iter(["miss", "PROVES", "unreached"])

    def complete(messages, seed):  # noqa: ANN001, ARG001
        complete.last_usage = (11, 4)
        return next(seq)

    complete.last_usage = (0, 0)
    proven, best = lhr._arm_plain(TASKS[3], complete, 4, 0)
    assert proven is True and best == 1.0
    attempts = [r for r in logged if r.get("record_type") == "attempt"]
    assert [r["arm"] for r in attempts] == [
        "plain",
        "plain",
    ]  # stopped at the proving attempt (2/4)
    assert attempts[0]["used_feedback"] is False  # round 1: no prior transcript
    assert attempts[1]["used_feedback"] is True  # round 2: transcript present
    assert attempts[0]["input_tokens"] == 11 and attempts[0]["output_tokens"] == 4


def test_run_summary_carries_plain_contract_fields(monkeypatch):
    """_run_once emits the prereg-P3/K8 run_summary fields for the plain arm."""
    monkeypatch.setattr(lhr, "evaluate", lambda *a, **k: _V(proven=False, error_tail="E"))
    monkeypatch.setattr(lhr, "_log_record", lambda *a, **k: None)

    def complete(messages, seed):  # noqa: ANN001, ARG001
        complete.last_usage = (1, 1)
        return "by sorry"

    complete.last_usage = (0, 0)
    out = lhr._run_once(complete, "test-backend", k=2, seed_offset=0)
    assert "repair_beats_plain_on_headroom_proven" in out
    assert "plain_minus_repair_on_headroom_proven" in out
    assert "plain" in out["headroom_only"] and "graded_plain" in out["headroom_only"]
