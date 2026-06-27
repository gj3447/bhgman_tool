"""Tests for the apt-run gated runtime (G1/G2/G3 fail-closed verification).

Hermetic: synthetic LegionRun / StageOutcome + trivially true/false oracle commands.
KG: project-apt-ultracode-roadmap-2026-06-02
"""

from engine.legion.gated_run import (
    GatedRunResult,
    artifact_hash,
    eval_g1_artifact_exists,
    eval_g2_adversary_ran,
    eval_g3_ground_truth,
    run_gated,
)
from engine.legion.legion_models import LegionRun, StageOutcome


def _outcome(stage, verb, ok=True):
    return StageOutcome(stage, verb, ok, f"{stage} {verb}")


def _good_run():
    return LegionRun(
        outcomes=(
            _outcome("prometheus", "획득"),
            _outcome("longinus", "연결"),
            _outcome("eureka", "창조"),
            _outcome("occam", "정리"),
            _outcome("naesengmoon", "검증"),
            _outcome("hades", "실현"),
        ),
        completed=True,
        final_context_keys=(
            "run_cypher",
            "acquired",
            "bindings",
            "abstractions",
            "hygiene",
            "verdict",
            "realized",
        ),
    )


class _FakeLegion:
    def __init__(self, run):
        self._run = run

    def run(self, context=None, gate=None):  # noqa: ARG002 — duck-types Legion
        return self._run


# ---- G1 ARTIFACT_EXISTS ----
def test_g1_pass_on_completed_run_with_artifacts():
    assert eval_g1_artifact_exists(_good_run()).status == "PASS"


def test_g1_fail_on_contract_violation():
    run = LegionRun(outcomes=(), completed=False, contract_violation="hades requires ['verdict']")
    v = eval_g1_artifact_exists(run)
    assert v.status == "FAIL" and "verdict" in v.detail


def test_g1_fail_on_completed_but_empty():
    assert eval_g1_artifact_exists(LegionRun(outcomes=(), completed=True)).status == "FAIL"


# ---- G2 ADVERSARY_RAN ----
def test_g2_pass_when_verify_stage_ran_ok():
    assert eval_g2_adversary_ran(_good_run()).status == "PASS"


def test_g2_fail_when_no_verify_stage():
    run = LegionRun(outcomes=(_outcome("prometheus", "획득"),), completed=True)
    assert eval_g2_adversary_ran(run).status == "FAIL"


def test_g2_fail_when_verify_failed():
    run = LegionRun(outcomes=(_outcome("naesengmoon", "검증", ok=False),), completed=True)
    assert eval_g2_adversary_ran(run).status == "FAIL"


def test_g2_fail_when_ensemble_rejects_despite_ok_stage():
    """W1-D: a stage that ran ok=True but carries ensemble=REJECT must NOT pass G2."""
    run = LegionRun(
        outcomes=(_outcome("naesengmoon", "검증"),),
        completed=True,
        final_verdict={"oracle": "PASS", "ensemble": "REJECT"},
    )
    v = eval_g2_adversary_ran(run)
    assert v.status == "FAIL" and "ensemble=REJECT" in v.detail


def test_g2_fail_when_oracle_fail_despite_ok_stage():
    run = LegionRun(
        outcomes=(_outcome("naesengmoon", "검증"),),
        completed=True,
        final_verdict={"oracle": "FAIL", "ensemble": "PASS"},
    )
    assert eval_g2_adversary_ran(run).status == "FAIL"


def test_g2_pass_when_verdict_clean():
    run = LegionRun(
        outcomes=(_outcome("naesengmoon", "검증"),),
        completed=True,
        final_verdict={"oracle": "PASS", "ensemble": "PASS"},
    )
    assert eval_g2_adversary_ran(run).status == "PASS"


# ---- G3 GROUND_TRUTH_GREEN ----
def test_g3_pass_on_zero_exit():
    assert eval_g3_ground_truth("true").status == "PASS"


def test_g3_fail_on_nonzero_exit():
    assert eval_g3_ground_truth("false").status == "FAIL"


def test_g3_skipped_when_no_oracle():
    assert eval_g3_ground_truth(None).status == "SKIPPED"


# ---- run_gated fail-closed ----
def test_run_gated_verified_only_when_all_three_pass():
    res = run_gated(_FakeLegion(_good_run()), {}, ground_truth_cmd="true")
    assert isinstance(res, GatedRunResult)
    assert res.verified is True
    assert {g.name for g in res.gates} == {
        "G1_ARTIFACT_EXISTS",
        "G2_ADVERSARY_RAN",
        "G3_GROUND_TRUTH_GREEN",
    }


def test_run_gated_fail_closed_when_oracle_skipped():
    # G1+G2 pass but no oracle -> G3 SKIPPED -> NOT verified (fail-closed honesty)
    res = run_gated(_FakeLegion(_good_run()), {}, ground_truth_cmd=None)
    assert res.verified is False
    assert res.gate("G3_GROUND_TRUTH_GREEN").status == "SKIPPED"


def test_run_gated_fail_closed_when_oracle_red():
    res = run_gated(_FakeLegion(_good_run()), {}, ground_truth_cmd="false")
    assert res.verified is False


def test_run_gated_fail_closed_on_incomplete_loop():
    bad = LegionRun(outcomes=(), completed=False, contract_violation="x")
    res = run_gated(_FakeLegion(bad), {}, ground_truth_cmd="true")
    assert res.verified is False
    assert res.gate("G1_ARTIFACT_EXISTS").status == "FAIL"


# ---- artifact hash ----
def test_artifact_hash_deterministic_and_sensitive():
    h1 = artifact_hash(_good_run())
    h2 = artifact_hash(_good_run())
    assert h1 == h2 and len(h1) == 64
    different = LegionRun(
        outcomes=(_outcome("prometheus", "획득"),), completed=True, final_context_keys=("acquired",)
    )
    assert artifact_hash(different) != h1


def test_g2_gate_requires_valid_verdict_signature():
    # R7/OQ1c: 게이트 주입 시 위조 final_verdict(clean content + bad sig) 를 G2 가 거부.
    from engine.legion.verdict_gate import VerdictGate, VerdictLedger

    g = VerdictGate(b"k" * 40, ledger=VerdictLedger())
    signed = g.sign({"oracle": "PASS", "ensemble": "PASS"}, "c", "a")
    run_ok = LegionRun(outcomes=(_outcome("naesengmoon", "검증"),), final_verdict=signed)
    assert eval_g2_adversary_ran(run_ok, gate=g).passed

    forged = {
        "oracle": "PASS",
        "ensemble": "PASS",
        "verdict_source": "naesengmoon-verify",
        "cycle_id": "c",
        "artifact_id": "a",
        "hmac_signature": "deadbeef",
    }
    run_forged = LegionRun(outcomes=(_outcome("naesengmoon", "검증"),), final_verdict=forged)
    v = eval_g2_adversary_ran(run_forged, gate=g)
    assert not v.passed and "signature" in v.detail
    # no gate → 후방 호환 (content-only 통과)
    assert eval_g2_adversary_ran(run_forged).passed
