"""Locks the honest per-TASK re-analysis of the committed 32b headroom A/B.

Pins the numbers so a future regrade cannot silently restore the naive
'8W/10run p=0.0078 = measured capability' reading: the signal is concentrated in
4/10 tasks with ~46% carried by sumto_mono alone.

# KG: project_ultimate_ai_tool_halo_loop_2026_07_19
"""
from __future__ import annotations

from engine.efficacy.analyze_headroom_pertask_paired import analyze


def test_per_seed_sign_test_reproduces_committed_p():
    r = analyze()
    st = r["per_seed_sign_test"]
    assert (st["W"], st["T"], st["L"]) == (8, 2, 0)
    assert abs(st["p"] - 0.007812) < 1e-5  # matches headroom_32b VERDICT.md


def test_signal_is_concentrated_not_general():
    r = analyze()
    # only 4 of 10 headroom tasks carry positive net signal
    assert r["n_positive_tasks"] == 4
    assert r["headroom_tasks"] == 10
    # sumto_mono carries the single largest share, ~46% of the net delta
    assert r["top_task"] == "sumto_mono"
    assert 0.40 <= r["top_task_concentration"] <= 0.55
    # honest label must NOT read as a broad measured capability
    assert "PLAUSIBLE-uncontrolled" in r["verdict"]


def test_carrying_tasks_are_the_prereg_four():
    r = analyze()
    assert set(r["positive_tasks"]) == {"sumto_mono", "dbl_ge", "le_sumto", "sumlist_app"}
