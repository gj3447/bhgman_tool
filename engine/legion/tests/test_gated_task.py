"""Tests for the gated general-task attempt (item ⑤ general half). Fakes — no LLM needed.

KG: project-apt-ultracode-roadmap-2026-06-02
"""

from engine.legion.gated_task import (
    TaskGatedResult,
    eval_g1_task,
    eval_g2_task,
    run_task_gated,
)


def test_g1_empty_artifact_fails():
    assert eval_g1_task("").status == "FAIL"
    assert eval_g1_task("   \n ").status == "FAIL"


def test_g1_nonempty_passes():
    assert eval_g1_task("def f(): return 1").status == "PASS"


def test_g2_no_review_fails():
    assert eval_g2_task(None).status == "FAIL"
    assert eval_g2_task({"ran": False}).status == "FAIL"


def test_g2_rejected_fails():
    assert eval_g2_task({"ran": True, "rejected": True, "detail": "wrong"}).status == "FAIL"


def test_g2_passes_when_ran_and_not_rejected():
    assert eval_g2_task({"ran": True, "rejected": False}).status == "PASS"


def _produce(_task):
    return "the artifact"


def _ok_review(_task, _artifact):
    return {"ran": True, "rejected": False, "detail": "looks fine"}


def test_run_task_gated_verified_when_all_pass():
    res = run_task_gated("do X", _produce, adversary_fn=_ok_review, ground_truth_cmd="true")
    assert isinstance(res, TaskGatedResult)
    assert res.verified is True
    assert len(res.artifact_sha256) == 64


def test_run_task_gated_fail_closed_no_adversary():
    res = run_task_gated("do X", _produce, ground_truth_cmd="true")
    assert res.verified is False  # G2 fails (no review ran)
    assert res.gate("G2_ADVERSARY_RAN").status == "FAIL"


def test_run_task_gated_fail_closed_no_oracle():
    res = run_task_gated("do X", _produce, adversary_fn=_ok_review)
    assert res.verified is False  # G3 SKIPPED
    assert res.gate("G3_GROUND_TRUTH_GREEN").status == "SKIPPED"


def test_run_task_gated_fail_closed_empty_artifact():
    res = run_task_gated("do X", lambda _t: "", adversary_fn=_ok_review, ground_truth_cmd="true")
    assert res.verified is False
    assert res.gate("G1_ARTIFACT_EXISTS").status == "FAIL"
