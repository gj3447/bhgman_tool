"""Regression tests for Lean headroom raw-log analysis."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

from engine.efficacy import lean_headroom_run
from engine.efficacy.analyze_lean_headroom import (
    _tost_equivalence,
    analyze_paths,
    format_report,
    sign_test_two_sided,
)
from engine.efficacy.lean_oracle import LeanVerdict


def _append_jsonl(path, records):
    with path.open("a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def _run_summary(seed_offset: int, repair: int, bestn: int) -> dict:
    return {
        "record_type": "run_summary",
        "seed_offset": seed_offset,
        "all": {
            "single": 1,
            "repair": repair,
            "bestN": bestn,
            "graded_single": 1.0,
            "graded_repair": float(repair),
            "graded_bestN": float(bestn),
            "of": 2,
        },
        "headroom_only": {
            "single": 0,
            "repair": repair,
            "bestN": bestn,
            "graded_single": 0.0,
            "graded_repair": float(repair),
            "graded_bestN": float(bestn),
            "of": 2,
        },
    }


def _task_summary(seed_offset: int, task: str, repair: bool, bestn: bool) -> dict:
    return {
        "record_type": "task_summary",
        "run_id": f"run-{seed_offset}",
        "seed_offset": seed_offset,
        "task": task,
        "difficulty": "headroom",
        "arms": {
            "single": {"proven": False, "graded_score": 0.0},
            "repair": {"proven": repair, "graded_score": float(repair)},
            "bestN": {"proven": bestn, "graded_score": float(bestn)},
        },
    }


def test_exact_sign_test_matches_run_b_edge_case():
    assert sign_test_two_sided(7, 0) == 0.015625
    assert sign_test_two_sided(0, 7) == 0.015625
    assert sign_test_two_sided(0, 0) == 1.0


def test_analyze_paths_recomputes_sign_test_and_task_counts(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    for i in range(10):
        seed_offset = i * 10
        repair_beats = i < 7
        repair = 2
        bestn = 1 if repair_beats else 2
        path = raw_dir / f"seed_{seed_offset}.jsonl"
        _append_jsonl(
            path,
            [
                {
                    "record_type": "attempt",
                    "seed_offset": seed_offset,
                    "task": "dbl_ge",
                    "arm": "repair",
                    "proven": i < 5,
                },
                _task_summary(seed_offset, "dbl_ge", repair=i < 5, bestn=False),
                _task_summary(seed_offset, "le_sumto", repair=True, bestn=repair_beats),
                _run_summary(seed_offset, repair, bestn),
            ],
        )

    result = analyze_paths([raw_dir])

    assert result["runs"] == 10
    assert result["attempt_records"] == 10
    assert result["repair_vs_bestN_headroom"] == {
        "repair_gt_bestN": 7,
        "ties": 3,
        "bestN_gt_repair": 0,
        "non_ties": 7,
        "p_two_sided": 0.015625,
    }
    assert result["headroom_totals"]["repair"] == 20
    assert result["headroom_totals"]["bestN"] == 13

    by_task = {row["task"]: row for row in result["per_task"]}
    assert by_task["dbl_ge"]["repair"] == 5
    assert by_task["dbl_ge"]["bestN"] == 0
    assert by_task["dbl_ge"]["delta_repair_bestN"] == 5

    report = format_report(result)
    assert "wins=7 ties=3 losses=0" in report
    assert "p_two_sided=0.015625" in report


# ---- 5-arm controls (prereg §4 P2/P3/P4) ----------------------------------------------------


def _run_summary5(seed_offset, *, repair, bestn, decoy, plain) -> dict:
    """A 5-arm run_summary carrying decoy/plain proven counts in headroom_only (new-batch shape)."""
    hr = {
        "single": 0,
        "repair": repair,
        "bestN": bestn,
        "decoy": decoy,
        "plain": plain,
        "graded_single": 0.0,
        "graded_repair": float(repair),
        "graded_bestN": float(bestn),
        "graded_decoy": float(decoy),
        "graded_plain": float(plain),
        "of": 2,
    }
    return {
        "record_type": "run_summary",
        "seed_offset": seed_offset,
        "all": hr,
        "headroom_only": hr,
    }


def _tok(arm, n, in_tok, out_tok) -> list[dict]:
    """n attempt records for `arm`, each with the given per-call token accounting."""
    return [
        {
            "record_type": "attempt",
            "arm": arm,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "model_calls": 1,
        }
        for _ in range(n)
    ]


def test_legacy_batch_marks_new_controls_absent(tmp_path):
    """A 3-arm batch (no decoy/plain, no token fields) → new controls ABSENT, legacy numbers intact."""
    path = tmp_path / "legacy.jsonl"
    _append_jsonl(path, [_run_summary(0, repair=2, bestn=1), _run_summary(10, repair=2, bestn=1)])
    result = analyze_paths([path])
    assert result["repair_vs_bestN_headroom"]["repair_gt_bestN"] == 2  # unchanged
    assert result["repair_vs_decoy_headroom"] is None
    assert result["repair_vs_plain_headroom"] is None
    assert result["decoy_vs_bestN_headroom"] is None
    assert result["token_parity"]["repair_vs_bestN"]["usage_hidden"] is True
    assert result["token_parity"]["repair_vs_bestN"]["tokens_ratio"] is None  # never a fake 1.0
    assert result["token_parity"]["repair_vs_plain"] is None


def test_full_5arm_batch_computes_pairwise_tallies_and_parity(tmp_path):
    """A 5-arm batch → paired sign tests for repair-vs-decoy / repair-vs-plain and token ratios."""
    path = tmp_path / "full.jsonl"
    records: list[dict] = []
    for i in range(6):
        # repair beats decoy and plain on the first 5 runs; decoy tracks bestN (equivalence).
        records.append(_run_summary5(i * 10, repair=3, bestn=1, decoy=1, plain=(1 if i < 5 else 3)))
    # token accounting: repair uses ~the same as bestN (fair), plain a bit less.
    records += _tok("repair", 12, 100, 20) + _tok("bestN", 12, 100, 20) + _tok("plain", 12, 90, 18)
    _append_jsonl(path, records)
    result = analyze_paths([path], tost_margin=1.0)

    rvd = result["repair_vs_decoy_headroom"]
    assert rvd["repair_gt_decoy"] == 6 and rvd["decoy_gt_repair"] == 0  # 3>1 every run
    rvp = result["repair_vs_plain_headroom"]
    assert rvp["repair_gt_plain"] == 5 and rvp["ties"] == 1  # last run 3==3 → tie
    dvb = result["decoy_vs_bestN_headroom"]
    assert dvb["tost"]["equivalent"] is True  # decoy==bestN==1 every run → mean delta 0
    tp = result["token_parity"]["repair_vs_bestN"]
    assert tp["usage_hidden"] is False
    assert tp["calls_ratio"] == 1.0 and tp["tokens_ratio"] == 1.0  # repair == bestN tokens


def test_tost_equivalence_true_and_false():
    """decoy≈bestN (small, tight deltas) → equivalent; a large consistent gap → not equivalent."""
    equal = _tost_equivalence([0, 0, 0, 0, 0, 0], margin=1.0)
    assert equal["equivalent"] is True and equal["mean_delta"] == 0.0
    gap = _tost_equivalence([3, 3, 3, 3, 3, 3], margin=1.0)
    assert gap["equivalent"] is False  # mean 3 >> margin 1
    thin = _tost_equivalence([0, 0], margin=1.0)
    assert thin["equivalent"] is False and thin["reason"] == "runs<3"  # never equiv on <3 runs


def test_runner_writes_attempt_task_and_run_jsonl(monkeypatch):
    task = SimpleNamespace(
        name="toy",
        signature=": True",
        preamble="",
        difficulty="headroom",
    )

    def complete(_messages, seed):
        return f"by exact proof_{seed}"

    def evaluate(_name, _signature, proof, *, preamble=""):
        assert preamble == ""
        return LeanVerdict(
            compiles=True,
            proven=proof.endswith("0"),
            sorry_tainted=False,
            error_tail="",
        )

    monkeypatch.setattr(lean_headroom_run, "TASKS", [task])
    monkeypatch.setattr(lean_headroom_run, "evaluate", evaluate)
    log = io.StringIO()

    summary = lean_headroom_run._run_once(
        complete,
        "fake",
        k=2,
        seed_offset=0,
        log=log,
        run_id="run-0",
    )

    records = [json.loads(line) for line in log.getvalue().splitlines()]
    assert [record["record_type"] for record in records] == [
        "run_start",
        "attempt",  # single
        "attempt",  # repair
        "attempt",  # bestN
        "attempt",  # decoy (prereg P2 placebo arm)
        "attempt",  # plain (prereg P3/K8 baseline arm)
        "task_summary",
        "run_summary",
    ]
    attempt = records[1]
    assert attempt["proof"] == "by exact proof_0"
    assert attempt["proof_sha256"]
    assert attempt["proven"] is True
    assert records[-1]["headroom_only"]["repair"] == 1
    assert records[-1]["headroom_only"]["bestN"] == 1
    assert records[-1]["headroom_only"]["decoy"] == 1  # seed-0 proof proves for every arm here
    assert records[-1]["headroom_only"]["plain"] == 1  # plain (fixed seed 0) proves too
    assert summary["repair_beats_bestN_on_headroom_proven"] is False
    assert summary["repair_beats_decoy_on_headroom_proven"] is False  # 1 == 1
    assert summary["repair_beats_plain_on_headroom_proven"] is False  # 1 == 1
