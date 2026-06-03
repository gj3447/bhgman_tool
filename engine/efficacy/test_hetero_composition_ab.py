"""Offline-falsifiable proof that the heterogeneous-composition gate FIRES BOTH WAYS.

Injects deterministic fake generators (no LLM): the artifact is a quality integer, public = quality,
hidden = quality >= threshold. Planting "heterogeneous roles improve quality" yields realized=True;
planting "roles useless" yields realized=False; planting "the verify gate alone suffices" yields
realized=False (ARM2 not > ARM3). This is the same discipline as test_composition_ab.py.

KG: project-apt-ultracode-roadmap-2026-06-02
"""

from engine.efficacy.hetero_composition_ab import evaluate_realized, run_arms

THRESHOLD = 4
BUDGET = 80  # 8 gens @ 10 tokens — enough for ARM2 to cycle the 6 roles


def _make_gen(role_gain: dict):
    """fake generate: 'solve'->quality 1; each role adds role_gain[role] to the running quality."""

    def gen(role, context, _seed):
        if role == "solve":
            return "1", 10
        q = int(context) if context else 1
        return str(q + role_gain.get(role, 0)), 10

    return gen


def _public(a: str) -> float:
    return float(a or 0)


def _hidden(a: str) -> bool:
    return float(a or 0) >= THRESHOLD


def _runs(gen, n=5):
    return [run_arms(gen, _public, _hidden, budget=BUDGET, seed0=i) for i in range(n)]


# heterogeneous roles improve, verify is pure-check (+0) — the genuine-composition world
_HELPFUL = {"gather": 1, "connect": 1, "abstract": 1, "prune": 1, "realize": 1, "verify": 0}
_USELESS: dict = {}
_GATE_ALONE = {"verify": 1}  # only the gate improves → ARM3 also reaches threshold


def test_realized_true_when_heterogeneous_handoff_helps():
    v = evaluate_realized(_runs(_make_gen(_HELPFUL)))
    assert v.realized is True
    assert v.delta_21_ci_lo > 0 and v.delta_23_ci_lo > 0


def test_realized_false_when_roles_useless():
    v = evaluate_realized(_runs(_make_gen(_USELESS)))
    assert v.realized is False  # ARM2 ≈ ARM1 (compounding cost, no cognition)


def test_realized_false_when_gate_alone_suffices():
    # verify-only reaches threshold too → ARM2 not strictly > ARM3 → "pipeline is décor"
    v = evaluate_realized(_runs(_make_gen(_GATE_ALONE)))
    assert v.realized is False
    assert v.delta_23_ci_lo <= 0


def test_arm_outcomes_in_helpful_world():
    one = _runs(_make_gen(_HELPFUL), n=1)[0]
    assert one["ARM2_hetero"].hidden_ok is True  # 5 improving roles climb past threshold
    assert one["ARM1_monolith"].hidden_ok is False  # independent solves stay at quality 1
    assert one["ARM3_gate_only"].hidden_ok is False  # verify-only does not improve
    # equal-compute honesty: every arm spent within one budget
    for arm in one.values():
        assert arm.tokens <= BUDGET
