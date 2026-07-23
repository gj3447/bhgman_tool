"""TDD for HALO fix #1 `_arm_hybrid`: explore-then-repair-BEST control logic.

No LLM, no Lean — a scripted `complete` + a monkeypatched `evaluate` isolate the control flow:
anchor on the BEST-so-far (not the last attempt), keep-best monotone, equal-K budget, early exit.

# KG: project_ultimate_ai_tool_halo_loop_2026_07_19
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.efficacy import hybrid_repair_ab
from engine.efficacy.hybrid_repair_ab import _arm_hybrid

# graded verdicts for the scripted proof tokens.
_VERDICTS = {
    "AAA": (False, 0.5, "errA"),   # good partial (best explore candidate)
    "BBB": (False, 0.0, "errB"),   # weak explore candidate
    "WIN": (True, 1.0, ""),        # a proof that compiles
    "LOSE": (False, 0.0, "errL"),  # a repair that fails
    "WORSE": (False, 0.0, "errW"), # a repair strictly worse than the best-so-far
}


def _fake_evaluate(name, sig, proof, preamble=""):
    proven, graded, err = _VERDICTS[proof]
    return SimpleNamespace(
        compiles=proven, proven=proven, sorry_tainted=False,
        graded_score=graded, error_tail=err,
    )


class _Fake:
    """Scripted (messages, seed) -> proof token, recording each call + the prior it saw."""

    def __init__(self, script):
        self.script = script
        self.calls: list[tuple[int, str | None, str]] = []
        self.last_usage = (1, 1)

    def __call__(self, messages, seed):
        user = messages[-1]["content"]
        prior = None
        if "Your previous proof:" in user:
            prior = user.split("Your previous proof:\n", 1)[1].split("\n\nLean reported", 1)[0]
        out = self.script(seed, prior)
        self.calls.append((seed, prior, out))
        return out


@pytest.fixture(autouse=True)
def _patch_eval(monkeypatch):
    # _eval_attempt (in lean_headroom_run) calls the module-global `evaluate`.
    monkeypatch.setattr("engine.efficacy.lean_headroom_run.evaluate", _fake_evaluate)


def _task():
    return SimpleNamespace(name="t", signature="(n:Nat):n=n", preamble="", difficulty="headroom")


def test_repair_anchors_on_best_not_last():
    """Explore yields AAA(0.5) then BBB(0.0); the best is AAA. Repair must condition on AAA (which
    scripts a WIN). If it wrongly anchored on the LAST attempt (BBB) it would get LOSE and never prove."""
    def script(seed, prior):
        if prior is None:
            return {0: "AAA", 1: "BBB"}[seed]      # seeds 0,1 = the two explore draws
        return "WIN" if "AAA" in prior else "LOSE"
    fake = _Fake(script)
    proven, score = _arm_hybrid(_task(), fake, k=4, off=0)
    assert (proven, score) == (True, 1.0)
    assert len(fake.calls) == 3          # 2 explore + 1 repair, early-exit on the WIN
    assert fake.calls[2][1] == "AAA"     # the repair anchored on the BEST, not the last (BBB)


def test_equal_k_budget_when_nothing_proves():
    def script(seed, prior):
        if prior is None:
            return {0: "AAA", 1: "BBB"}[seed]
        return "LOSE"
    fake = _Fake(script)
    proven, score = _arm_hybrid(_task(), fake, k=4, off=0)
    assert proven is False
    assert score == 0.5                  # best-so-far (AAA) preserved
    assert len(fake.calls) == 4          # exactly K oracle-calls (2 explore + 2 repair)


def test_early_exit_in_explore_phase():
    def script(seed, prior):
        return "WIN"                     # first explore draw already proves
    fake = _Fake(script)
    proven, score = _arm_hybrid(_task(), fake, k=4, off=0)
    assert (proven, score) == (True, 1.0)
    assert len(fake.calls) == 1          # no wasted budget once proven


def test_keep_best_is_monotone_a_regression_does_not_lower_score():
    """k=2 -> 1 explore (AAA=0.5) + 1 repair. The repair returns WORSE(0.0); keep-best must NOT drop
    the reported score below the explore best (0.5)."""
    def script(seed, prior):
        return "AAA" if prior is None else "WORSE"
    fake = _Fake(script)
    proven, score = _arm_hybrid(_task(), fake, k=2, off=0)
    assert proven is False
    assert score == 0.5                  # not lowered to WORSE's 0.0
    assert len(fake.calls) == 2
