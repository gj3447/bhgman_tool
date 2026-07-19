"""TDD for HALO fix #2 `_arm_reflect`: self-distilled reflect control logic.

Isolates: distill-then-generate, the NOTE is injected while the verbatim failing proof is DROPPED,
K gen + (K-1) distill budget, early-exit. No LLM, no Lean.

# KG: project_ultimate_ai_tool_halo_loop_2026_07_19
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.efficacy.reflect_repair_ab import _arm_reflect

_V = {"AAA": (False, 0.5, "errA"), "BBB": (False, 0.0, "errB"), "WIN": (True, 1.0, "")}


def _fake_evaluate(name, sig, proof, preamble=""):
    proven, graded, err = _V[proof]
    return SimpleNamespace(compiles=proven, proven=proven, sorry_tainted=False,
                           graded_score=graded, error_tail=err)


class _Fake:
    last_usage = (1, 1)

    def __init__(self, gen2):
        self.gen2 = gen2
        self.calls = []  # (kind, seed, out)

    def __call__(self, messages, seed):
        sys = messages[0]["content"]
        user = messages[-1]["content"]
        if "ONE sentence" in sys:  # a distill/reflection call
            self.calls.append(("distill", seed, "USE_INDUCTION"))
            return "USE_INDUCTION"
        if "Expert hint" in user:  # a hint-conditioned generation
            assert "USE_INDUCTION" in user, "the distilled note must be injected"
            assert "AAA" not in user, "the verbatim failing proof must be DROPPED (PROM C6)"
            self.calls.append(("gen2", seed, self.gen2))
            return self.gen2
        self.calls.append(("gen1", seed, "AAA"))  # round-1 fresh draw
        return "AAA"


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    monkeypatch.setattr("engine.efficacy.lean_headroom_run.evaluate", _fake_evaluate)


def _task():
    return SimpleNamespace(name="t", signature="(n:Nat):n=n", preamble="", difficulty="headroom")


def test_distills_then_generates_from_note_dropping_the_proof():
    fake = _Fake(gen2="WIN")
    proven, score = _arm_reflect(_task(), fake, k=4, off=0)
    assert (proven, score) == (True, 1.0)
    kinds = [c[0] for c in fake.calls]
    assert kinds == ["gen1", "distill", "gen2"]  # fresh → distill → hint-gen, early-exit on WIN


def test_budget_is_k_gen_plus_k_minus_1_distill():
    fake = _Fake(gen2="BBB")  # never proves
    proven, score = _arm_reflect(_task(), fake, k=4, off=0)
    assert proven is False
    assert score == 0.5  # keep-best (round-1 AAA=0.5)
    # 1 round-1 gen + 3×(distill + hint-gen) = 1 + 6 = 7 = K gen + (K-1) distill
    assert len(fake.calls) == 7
    assert [c[0] for c in fake.calls].count("distill") == 3


def test_early_exit_round1_no_reflect():
    class F(_Fake):
        def __call__(self, messages, seed):
            if "ONE sentence" in messages[0]["content"]:
                self.calls.append(("distill", seed, "x")); return "x"
            self.calls.append(("gen1", seed, "WIN")); return "WIN"
    fake = F(gen2="WIN")
    proven, score = _arm_reflect(_task(), fake, k=4, off=0)
    assert (proven, score) == (True, 1.0)
    assert len(fake.calls) == 1  # proven on the first fresh draw, no reflect spend
