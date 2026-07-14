"""Regression tests for Lean headroom raw-log analysis."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

from engine.efficacy import lean_headroom_run
from engine.efficacy.analyze_lean_headroom import (
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
    assert summary["repair_beats_bestN_on_headroom_proven"] is False
    assert summary["repair_beats_decoy_on_headroom_proven"] is False  # 1 == 1
