"""Adversarial contract and false-pass tests for the six-arm v2 analyzer."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from engine.efficacy import analyze_diagnostic_repair_harness as analyzer

ARMS = analyzer.ARMS
SCHEMA = analyzer.SCHEMA
ContractError = analyzer.ContractError
analyze_paths = analyzer.analyze_paths
main = analyzer.main
sign_test_two_sided = analyzer.sign_test_two_sided
tost_equivalence = analyzer.tost_equivalence
REAL_GIT_VERIFY = analyzer._verify_git_provenance
REAL_ORACLE_REPLAY = analyzer._replay_oracle_integrity


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _task_band(task_count: int = 6) -> list[dict[str, str]]:
    return [
        {
            "name": f"task-{index}",
            "difficulty": "headroom",
            "task_sha256": _sha(f"task:{index}"),
        }
        for index in range(task_count)
    ]


def _synthetic_manifest(task_count: int = 6) -> dict[str, Any]:
    artifact_hashes = {name: _sha(f"artifact:{name}") for name in analyzer.MANIFEST_ARTIFACT_KEYS}
    artifact_paths = {name: f"engine/efficacy/{name}.synthetic" for name in artifact_hashes}
    return {
        "path": "/synthetic/repo/engine/efficacy/diagnostic_repair_harness_manifest.v3.json",
        "sha256": _sha("manifest"),
        "harness_version": "2.0.1",
        "thresholds": dict(analyzer._FROZEN_THRESHOLDS),
        "run_design": {
            **copy.deepcopy(analyzer._FROZEN_RUN_DESIGN),
            "task_band": _task_band(task_count),
        },
        "repo_root": "/synthetic/repo",
        "artifact_hashes": artifact_hashes,
        "artifact_paths": artifact_paths,
        "artifact_relative_paths": artifact_paths,
        "manifest_relative_path": ("engine/efficacy/diagnostic_repair_harness_manifest.v3.json"),
        "preregistration_v3_path": (
            "/synthetic/repo/engine/efficacy/DIAGNOSTIC_REPAIR_PREREGISTRATION_V3.md"
        ),
        "preregistration_v3_relative_path": (
            "engine/efficacy/DIAGNOSTIC_REPAIR_PREREGISTRATION_V3.md"
        ),
        "preregistration_v3_sha256": _sha("preregistration"),
        "bridge_conformance": {
            "path": "/synthetic/repo/engine/efficacy/tests/test_diagnostic_repair_harness.py",
            "relative_path": ("engine/efficacy/tests/test_diagnostic_repair_harness.py"),
            "sha256": _sha("bridge"),
            "pytest_nodeid": (
                "engine/efficacy/tests/test_diagnostic_repair_harness.py::"
                "test_legacy_and_pi_repair_have_equivalent_generation_and_oracle_traces"
            ),
        },
    }


def _envelope(manifest: dict[str, Any]) -> dict[str, str]:
    return {
        **manifest["artifact_hashes"],
        "manifest": manifest["sha256"],
        "preregistration_v3": manifest["preregistration_v3_sha256"],
    }


@pytest.fixture(autouse=True)
def _frozen_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = _synthetic_manifest()
    monkeypatch.setattr(analyzer, "_load_manifest", lambda _path: copy.deepcopy(manifest))

    def synthetic_decoy_source(task_name: str, start: analyzer.RunStart) -> dict[str, str]:
        index = start.task_order.index(task_name)
        source_task = start.task_order[(index + 1) % len(start.task_order)]
        return {
            "source_task": source_task,
            "source_task_sha256": start.task_hashes[source_task],
            "source_reference_proof_sha256": _sha(f"reference:{source_task}"),
        }

    monkeypatch.setattr(analyzer, "_decoy_source_binding", synthetic_decoy_source)

    def synthetic_git_verify(**kwargs: Any) -> dict[str, Any]:
        errors, checked = analyzer._temporal_provenance_checks(
            commit_timestamp_epoch=1_577_836_800,
            run_timestamps=kwargs["run_timestamps"],
            jsonl_paths=kwargs["jsonl_paths"],
        )
        checked["synthetic"] = "ok"
        return {"ok": not errors, "errors": errors, "checked": checked}

    monkeypatch.setattr(
        analyzer,
        "_verify_git_provenance",
        synthetic_git_verify,
    )

    def synthetic_oracle_replay(
        *, runs: list[analyzer.Run], manifest: dict[str, Any]
    ) -> dict[str, Any]:
        attempts = [
            attempt
            for run in runs
            for arm_attempts in run.attempts.values()
            for attempt in arm_attempts
        ]
        count = len(attempts)
        setup_count = sum(len(run.decoy_setups) for run in runs)
        full = all(attempt.raw_payload_complete for attempt in attempts)
        return {
            "status": "PASS" if full else "ABSENT",
            "attempt_count": count,
            "replayed_count": count if full else 0,
            "setup_count": setup_count,
            "setup_replayed_count": setup_count if full else 0,
            "receipt_sha256": _sha(f"synthetic-replay:{count}") if full else None,
            "mismatch_count": 0,
            "mismatches": [],
            "errors": [] if full else ["full attempt payloads are required"],
            "identity": {
                "expected": manifest["run_design"]["lean_binary_sha256"],
                "observed": manifest["run_design"]["lean_binary_sha256"],
            },
        }

    monkeypatch.setattr(analyzer, "_replay_oracle_integrity", synthetic_oracle_replay)


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True) + "\n")


def _decoy(real_diagnostic: str) -> str:
    if not real_diagnostic:
        return ""
    marker = "DECOY"
    repeats = (len(real_diagnostic) + len(marker) - 1) // len(marker)
    value = (marker * repeats)[: len(real_diagnostic)]
    return ("X" if value[0] != "X" else "Y") + value[1:] if value == real_diagnostic else value


def _final_proven(run_index: int, arm: str, task: str, non_live: set[str]) -> bool:
    if task in non_live:
        return False
    if arm == "pi_repair":
        return run_index < 9
    return run_index == 0


def _pi_lifecycle(
    *,
    common: dict[str, Any],
    task: str,
    arm: str,
    attempts: list[dict[str, Any]],
    final_proven: bool,
) -> list[dict[str, Any]]:
    def event_feedback(attempt: dict[str, Any]) -> Any:
        return analyzer.feedback_from_value(
            lens="lean-ungameable",
            kind="lean-proof",
            passed=bool(attempt["proven"]),
            score=float(attempt["graded_score"]),
            diagnostic=str(attempt["diagnostic"]),
        )

    pi_run_id = f"{common['run_id']}:{task}:{arm}"
    records: list[dict[str, Any]] = []
    event_sequence = 0
    for index, attempt in enumerate(attempts):
        if index:
            records.append(
                {
                    "record_type": "pi_event",
                    **common,
                    "task": task,
                    "difficulty": "headroom",
                    "arm": arm,
                    "pi_run_id": pi_run_id,
                    "sequence": event_sequence,
                    "kind": "repair_requested",
                    "attempt": index,
                    "elapsed_ms": event_sequence,
                    "candidate_fingerprint": analyzer.candidate_fingerprint(
                        attempts[index - 1]["proof"]
                    ),
                    "diagnostic_fingerprint": event_feedback(attempts[index - 1]).fingerprint,
                    "status": "failed",
                    "score": 0.0,
                    "detail_sha256": _sha("bounded diagnostic supplied to repair generator"),
                }
            )
            event_sequence += 1
        records.append(
            {
                "record_type": "pi_event",
                **common,
                "task": task,
                "difficulty": "headroom",
                "arm": arm,
                "pi_run_id": pi_run_id,
                "sequence": event_sequence,
                "kind": "oracle_evaluated",
                "attempt": index,
                "elapsed_ms": event_sequence,
                "candidate_fingerprint": analyzer.candidate_fingerprint(attempt["proof"]),
                "diagnostic_fingerprint": event_feedback(attempt).fingerprint,
                "status": "passed" if attempt["proven"] else "failed",
                "score": float(attempt["proven"]),
                "detail_sha256": _sha(""),
            }
        )
        event_sequence += 1
    records.append(
        {
            "record_type": "pi_event",
            **common,
            "task": task,
            "difficulty": "headroom",
            "arm": arm,
            "pi_run_id": pi_run_id,
            "sequence": event_sequence,
            "kind": "stopped",
            "attempt": len(attempts) - 1,
            "elapsed_ms": event_sequence,
            "candidate_fingerprint": analyzer.candidate_fingerprint(attempts[-1]["proof"]),
            "diagnostic_fingerprint": "",
            "status": "",
            "score": None,
            "detail_sha256": _sha("complete" if final_proven else "capped"),
        }
    )
    event_sequence += 1
    records.append(
        {
            "record_type": "pi_stop",
            **common,
            "task": task,
            "difficulty": "headroom",
            "arm": arm,
            "pi_run_id": pi_run_id,
            "stop": "complete" if final_proven else "capped",
            "verified": final_proven,
            "improved": final_proven,
            "evaluations": len(attempts),
            "repairs": len(attempts) - 1,
            "elapsed_ms": event_sequence,
            "reported_input_tokens": sum(int(attempt["input_tokens"]) for attempt in attempts[1:]),
            "reported_output_tokens": sum(
                int(attempt["output_tokens"]) for attempt in attempts[1:]
            ),
            "best_attempt": len(attempts) - 1 if final_proven else 0,
            "current_attempt": len(attempts) - 1,
            "event_count": event_sequence,
            "stop_detail_sha256": _sha("complete" if final_proven else "capped"),
        }
    )
    return records


def _batch(
    *,
    manifest: dict[str, Any] | None = None,
    non_live: set[str] | None = None,
    payload_mode: str = "full",
    missing_arm: str | None = None,
    omit_usage: bool = False,
    zero_usage: tuple[str, str, str, int] | None = None,
) -> list[dict[str, Any]]:
    frozen = _synthetic_manifest() if manifest is None else manifest
    task_band = frozen["run_design"]["task_band"]
    non_live = set() if non_live is None else non_live
    records: list[dict[str, Any]] = []
    for run_index, seed_offset in enumerate(frozen["run_design"]["seed_offsets"]):
        run_id = f"run-{run_index}"
        common = {
            "schema": SCHEMA,
            "harness_version": "2.0.1",
            "run_id": run_id,
            "backend": frozen["run_design"]["backend"],
            "model_id": frozen["run_design"]["model_id"],
            "endpoint_class": frozen["run_design"]["endpoint_class"],
            "endpoint_fingerprint": _sha("endpoint"),
            "temperature": frozen["run_design"]["temperature"],
            "max_tokens_per_attempt": frozen["run_design"]["max_tokens_per_attempt"],
            "oracle_isolation": frozen["run_design"]["oracle_isolation"],
            "sandbox_runner_sha256": frozen["artifact_hashes"]["lean_sandbox_runner_macos"],
            "lean_toolchain": frozen["run_design"]["lean_toolchain"],
            "lean_version": frozen["run_design"]["lean_version"],
            "lean_binary_sha256": frozen["run_design"]["lean_binary_sha256"],
            "K": frozen["run_design"]["k"],
            "seed_offset": seed_offset,
            "timestamp_utc": f"2026-07-16T{run_index:02d}:00:00+00:00",
            "payload_mode": payload_mode,
        }
        records.append(
            {
                "record_type": "run_start",
                **common,
                "n_tasks": len(task_band),
                "arms": list(ARMS),
                "arm_order_policy": analyzer.ARM_ORDER_POLICY,
                "tasks": copy.deepcopy(task_band),
                "artifact_hashes": _envelope(frozen),
                "git_commit": "f" * 40,
                "git_dirty": False,
                "git_status_sha256": analyzer._EMPTY_SHA256,
            }
        )
        task_summaries: list[dict[str, Any]] = []
        for task_index, task_spec in enumerate(task_band):
            task = task_spec["name"]
            rotation = (seed_offset + task_index) % len(ARMS)
            arm_order = ARMS[rotation:] + ARMS[:rotation]
            arm_summaries: dict[str, dict[str, Any]] = {}
            for arm in arm_order:
                if arm == missing_arm:
                    continue
                decoy_seed_diagnostic: str | None = None
                if arm == "pi_decoy":
                    source_spec = task_band[(task_index + 1) % len(task_band)]
                    source_reference_proof = f"reference:{source_spec['name']}"
                    oracle_diagnostic = f"setup-error:{task}:from:{source_spec['name']}"
                    decoy_seed_diagnostic = oracle_diagnostic or "unsolved goals\n"
                    records.append(
                        {
                            "record_type": "pi_decoy_setup",
                            **common,
                            "task": task,
                            "difficulty": task_spec["difficulty"],
                            "arm": "pi_decoy",
                            "source_task": source_spec["name"],
                            "source_task_sha256": source_spec["task_sha256"],
                            "source_reference_proof_sha256": _sha(source_reference_proof),
                            "compiles": False,
                            "proven": False,
                            "sorry_tainted": False,
                            "graded_score": 0.0,
                            "oracle_diagnostic": oracle_diagnostic,
                            "oracle_diagnostic_sha256": _sha(oracle_diagnostic),
                            "decoy_seed_diagnostic": decoy_seed_diagnostic,
                            "decoy_seed_diagnostic_sha256": _sha(decoy_seed_diagnostic),
                            "setup_oracle_calls": 1,
                        }
                    )
                success = _final_proven(run_index, arm, task, non_live)
                attempt_count = 1 if arm == "single" else frozen["run_design"]["k"]
                attempts: list[dict[str, Any]] = []
                previous_proof = ""
                previous_diagnostic = ""
                for attempt_index in range(1, attempt_count + 1):
                    attempt_proven = success and attempt_index == attempt_count
                    proof = f"proof:{run_id}:{task}:{arm}:{attempt_index}"
                    diagnostic = "" if attempt_proven else f"error:{task}:{arm}:{attempt_index}"
                    chained = arm in {
                        "legacy_repair",
                        "pi_repair",
                        "pi_decoy",
                        "plain_baseline",
                    }
                    if attempt_index == 1 or not chained:
                        supplied_feedback = ""
                        feedback_source = "none"
                        prior_proof_sha256 = ""
                        used_feedback = False
                    else:
                        supplied_feedback = (
                            analyzer._fit_decoy(
                                decoy_seed_diagnostic or "",
                                previous_diagnostic,
                            )
                            if arm == "pi_decoy"
                            else previous_diagnostic
                        )
                        feedback_source = "decoy" if arm == "pi_decoy" else "real"
                        prior_proof_sha256 = _sha(previous_proof)
                        used_feedback = True
                    input_tokens, output_tokens = 40, 10
                    if zero_usage == (run_id, task, arm, attempt_index):
                        input_tokens = output_tokens = 0
                    attempt = {
                        "record_type": "attempt",
                        **common,
                        "task": task,
                        "task_sha256": task_spec["task_sha256"],
                        "difficulty": task_spec["difficulty"],
                        "arm": arm,
                        "attempt": attempt_index,
                        "seed": seed_offset + attempt_index - 1,
                        "used_feedback": used_feedback,
                        "feedback_source": feedback_source,
                        "proven": attempt_proven,
                        "compiles": attempt_proven,
                        "sorry_tainted": False,
                        "graded_score": float(attempt_proven),
                        "response_model_id": frozen["run_design"]["model_id"],
                        "response_model_observed": True,
                        "proof": proof,
                        "diagnostic": diagnostic,
                        "supplied_feedback": supplied_feedback,
                        "proof_sha256": _sha(proof),
                        "diagnostic_sha256": _sha(diagnostic),
                        "supplied_feedback_sha256": _sha(supplied_feedback),
                        "prior_proof_sha256": prior_proof_sha256,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "model_calls": 1,
                        "oracle_calls": 1,
                        "pi_run_id": (
                            f"{run_id}:{task}:{arm}" if arm in {"pi_repair", "pi_decoy"} else ""
                        ),
                        "pi_stop_reason": None,
                        "pi_event_count": None,
                    }
                    if payload_mode == "redacted":
                        for key in ("proof", "diagnostic", "supplied_feedback"):
                            del attempt[key]
                    if (
                        omit_usage
                        and run_index == 0
                        and task_index == 0
                        and arm == "bestN"
                        and attempt_index == 1
                    ):
                        del attempt["input_tokens"]
                    attempts.append(attempt)
                    records.append(attempt)
                    previous_proof = proof
                    previous_diagnostic = diagnostic
                pi_stop = None
                if arm in {"pi_repair", "pi_decoy"}:
                    lifecycle_attempts = [
                        {
                            **attempt,
                            "proof": f"proof:{run_id}:{task}:{arm}:{index}",
                            "diagnostic": (
                                ""
                                if success and index == attempt_count
                                else f"error:{task}:{arm}:{index}"
                            ),
                        }
                        for index, attempt in enumerate(attempts, start=1)
                    ]
                    records.extend(
                        _pi_lifecycle(
                            common=common,
                            task=task,
                            arm=arm,
                            attempts=lifecycle_attempts,
                            final_proven=success,
                        )
                    )
                    pi_stop = "complete" if success else "capped"
                arm_summaries[arm] = {
                    "proven": success,
                    "graded_score": float(success),
                    "attempts": len(attempts),
                    "model_calls": len(attempts),
                    "oracle_calls": len(attempts),
                    "setup_oracle_calls": int(arm == "pi_decoy"),
                    "input_tokens": sum(
                        int(attempt.get("input_tokens", 0)) for attempt in attempts
                    ),
                    "output_tokens": sum(int(attempt["output_tokens"]) for attempt in attempts),
                    "pi_stop": pi_stop,
                }
            task_summary = {
                "record_type": "task_summary",
                **common,
                "task": task,
                "task_sha256": task_spec["task_sha256"],
                "difficulty": task_spec["difficulty"],
                "arm_order": list(arm_order),
                "arms": arm_summaries,
            }
            records.append(task_summary)
            task_summaries.append(task_summary)
        all_summary: dict[str, Any] = {"of": len(task_summaries)}
        for arm in ARMS:
            summaries = [task["arms"][arm] for task in task_summaries if arm in task["arms"]]
            all_summary[arm] = sum(int(summary["proven"]) for summary in summaries)
            all_summary[f"graded_{arm}"] = float(all_summary[arm])
            for field in (
                "model_calls",
                "oracle_calls",
                "setup_oracle_calls",
                "input_tokens",
                "output_tokens",
            ):
                all_summary[f"{field}_{arm}"] = sum(int(summary[field]) for summary in summaries)
        records.append(
            {
                "record_type": "run_summary",
                **common,
                "n_tasks": len(task_summaries),
                "n_headroom": len(task_summaries),
                "all": copy.deepcopy(all_summary),
                "headroom_only": copy.deepcopy(all_summary),
            }
        )
    _resequence(records)
    return records


def _resequence(records: list[dict[str, Any]]) -> None:
    counters: dict[str, int] = defaultdict(int)
    for record in records:
        record["record_sequence"] = counters[record["run_id"]]
        counters[record["run_id"]] += 1


def _rebuild_accounting(records: list[dict[str, Any]]) -> None:
    attempts: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    summaries: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        if record["record_type"] == "attempt":
            attempts[(record["run_id"], record["task"], record["arm"])].append(record)
        elif record["record_type"] == "task_summary":
            summaries[(record["run_id"], record["task"])] = record
    for (run_id, task, arm), arm_attempts in attempts.items():
        summary = summaries[(run_id, task)]["arms"][arm]
        summary.update(
            {
                "proven": any(bool(item["proven"]) for item in arm_attempts),
                "graded_score": max(float(item["graded_score"]) for item in arm_attempts),
                "attempts": len(arm_attempts),
                "model_calls": sum(int(item["model_calls"]) for item in arm_attempts),
                "oracle_calls": sum(int(item["oracle_calls"]) for item in arm_attempts),
                "input_tokens": sum(int(item["input_tokens"]) for item in arm_attempts),
                "output_tokens": sum(int(item["output_tokens"]) for item in arm_attempts),
            }
        )
    for record in records:
        if record["record_type"] == "pi_stop":
            arm_attempts = attempts[(record["run_id"], record["task"], record["arm"])]
            record["evaluations"] = len(arm_attempts)
            record["repairs"] = len(arm_attempts) - 1
            record["reported_input_tokens"] = sum(
                int(item["input_tokens"]) for item in arm_attempts[1:]
            )
            record["reported_output_tokens"] = sum(
                int(item["output_tokens"]) for item in arm_attempts[1:]
            )
    for record in records:
        if record["record_type"] != "run_summary":
            continue
        run_summaries = [
            value for (run_id, _task), value in summaries.items() if run_id == record["run_id"]
        ]
        for arm in ARMS:
            arm_rows = [task["arms"][arm] for task in run_summaries]
            for subset in ("all", "headroom_only"):
                record[subset][arm] = sum(int(row["proven"]) for row in arm_rows)
                record[subset][f"graded_{arm}"] = sum(
                    float(row["graded_score"]) for row in arm_rows
                )
                for field in (
                    "model_calls",
                    "oracle_calls",
                    "setup_oracle_calls",
                    "input_tokens",
                    "output_tokens",
                ):
                    record[subset][f"{field}_{arm}"] = sum(int(row[field]) for row in arm_rows)


def _analyze(tmp_path: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    path = tmp_path / "batch.jsonl"
    _write_jsonl(path, records)
    return analyze_paths([path])


def test_exact_sign_test_and_student_t_tost_counterexample() -> None:
    assert sign_test_two_sided(6, 0) == 0.03125
    assert analyzer._student_t_cdf(1.0, 1) == pytest.approx(0.75, abs=1e-10)
    # A normal approximation accepts this small-n case (one-sided p≈.033), but Student-t df=4
    # correctly rejects equivalence.
    result = tost_equivalence([0.0, 0.0, 1.0, 1.0, 1.0], margin=1.05)
    assert result["method"] == "paired-student-t-tost"
    assert result["p_upper"] > 0.05
    assert result["equivalent"] is False


def test_full_synthetic_batch_confirms_p1_to_p5(tmp_path: Path) -> None:
    result = _analyze(tmp_path, _batch())

    assert result["runs"] == 10
    assert result["live_discriminating_task_count"] == 6
    assert result["confirm"] is True
    assert {key: value["status"] for key, value in result["gates"].items()} == {
        "P1": "PASS",
        "P2": "PASS",
        "P3": "PASS",
        "P4": "PASS",
        "P5": "PASS",
    }
    primary = result["comparisons"]["pi_repair_vs_bestN"]["live_discriminating"]
    assert primary["per_run"]["wins"] == 8
    assert primary["per_task"]["wins"] == 6
    assert result["usage"]["pi_repair_ratios"]["bestN"]["total_tokens"] == 1.0
    assert result["usage"]["setup_oracle_calls_excluded"]["all_tasks"]["pi_decoy"] == 60
    assert result["provenance"]["oracle_replay"]["status"] == "PASS"
    assert result["provenance"]["oracle_replay"]["replayed_count"] > 0


def test_real_replay_helper_hashes_receipt_and_detects_exact_diagnostic_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _synthetic_manifest(task_count=1)
    manifest["run_design"]["replications"] = 1
    manifest["run_design"]["seed_offsets"] = [0]
    manifest["run_design"]["task_band"] = [
        {
            "name": "gauss",
            "difficulty": "headroom",
            "task_sha256": _sha("task:gauss"),
        }
    ]
    path = tmp_path / "replay-helper.jsonl"
    _write_jsonl(path, _batch(manifest=manifest))
    runs = analyzer._validated_runs(analyzer._read_records([path]))
    manifest["run_design"]["task_band"] = analyzer._frozen_lean_task_band()
    verdicts = {
        attempt.proof: analyzer.lean_oracle.LeanVerdict(
            compiles=attempt.compiles,
            proven=attempt.proven,
            sorry_tainted=attempt.sorry_tainted,
            error_tail=attempt.diagnostic or "",
        )
        for attempts in runs[0].attempts.values()
        for attempt in attempts
    }
    setup_diagnostic_override: list[str | None] = [None]

    class FakeSandboxEvaluator:
        def __init__(self, *, runner: Path) -> None:
            self.runner = runner
            self.lean_toolchain = manifest["run_design"]["lean_toolchain"]
            self.lean_version = manifest["run_design"]["lean_version"]
            self.lean_binary_sha256 = manifest["run_design"]["lean_binary_sha256"]

        @property
        def runner_sha256(self) -> str:
            return manifest["artifact_hashes"]["lean_sandbox_runner_macos"]

        def __call__(
            self,
            name: str,
            signature: str,
            proof: str,
            *,
            preamble: str = "",
        ) -> Any:
            task = next(task for task in analyzer.lean_tasks.TASKS if task.name == name)
            assert signature == task.signature
            assert preamble == task.preamble
            if proof in verdicts:
                return verdicts[proof]
            setup = runs[0].decoy_setups[name]
            return analyzer.lean_oracle.LeanVerdict(
                compiles=setup.compiles,
                proven=setup.proven,
                sorry_tainted=setup.sorry_tainted,
                error_tail=(
                    setup_diagnostic_override[0]
                    if setup_diagnostic_override[0] is not None
                    else setup.oracle_diagnostic
                ),
            )

    monkeypatch.setattr(
        analyzer.lean_oracle,
        "ExternalSandboxLeanEvaluator",
        FakeSandboxEvaluator,
    )
    replayed_candidates: list[str] = []
    real_candidate_adapter = analyzer.lean_oracle.evaluate_untrusted_candidate

    def recording_candidate_adapter(
        evaluator: Any,
        name: str,
        signature: str,
        proof: str,
        *,
        preamble: str = "",
    ) -> Any:
        replayed_candidates.append(proof)
        return real_candidate_adapter(
            evaluator,
            name,
            signature,
            proof,
            preamble=preamble,
        )

    monkeypatch.setattr(
        analyzer.lean_oracle,
        "evaluate_untrusted_candidate",
        recording_candidate_adapter,
    )
    passed = REAL_ORACLE_REPLAY(runs=runs, manifest=manifest)
    assert passed["status"] == "PASS"
    assert passed["replayed_count"] == passed["attempt_count"] == 21
    assert passed["setup_replayed_count"] == passed["setup_count"] == 1
    assert len(passed["receipt_sha256"]) == 64
    assert len(replayed_candidates) == passed["attempt_count"]

    first_proof = next(iter(verdicts))
    first_key = next(
        key
        for key, attempts in runs[0].attempts.items()
        if any(attempt.proof == first_proof for attempt in attempts)
    )
    first_index = next(
        index
        for index, attempt in enumerate(runs[0].attempts[first_key])
        if attempt.proof == first_proof
    )
    original_attempt = runs[0].attempts[first_key][first_index]
    unsafe_proof = "by\n  trivial\n#check Nat"
    runs[0].attempts[first_key][first_index] = replace(
        original_attempt,
        proof=unsafe_proof,
        proof_sha256=_sha(unsafe_proof),
        compiles=False,
        proven=False,
        sorry_tainted=False,
        graded_score=0.0,
        diagnostic=analyzer.lean_oracle.UNSAFE_PAYLOAD_DIAGNOSTIC,
        diagnostic_sha256=_sha(analyzer.lean_oracle.UNSAFE_PAYLOAD_DIAGNOSTIC),
    )
    unsafe_replay = REAL_ORACLE_REPLAY(runs=runs, manifest=manifest)
    assert unsafe_replay["status"] == "PASS"
    assert unsafe_replay["replayed_count"] == unsafe_replay["attempt_count"]
    runs[0].attempts[first_key][first_index] = original_attempt

    original = verdicts[first_proof]
    verdicts[first_proof] = analyzer.lean_oracle.LeanVerdict(
        compiles=original.compiles,
        proven=original.proven,
        sorry_tainted=original.sorry_tainted,
        error_tail="normalized but forged replay diagnostic",
    )
    failed = REAL_ORACLE_REPLAY(runs=runs, manifest=manifest)
    assert failed["status"] == "FAIL"
    assert failed["mismatch_count"] == 1
    assert failed["mismatches"][0]["diagnostic_exact"] is False

    verdicts[first_proof] = original
    setup_diagnostic_override[0] = "forged setup diagnostic"
    failed_setup = REAL_ORACLE_REPLAY(runs=runs, manifest=manifest)
    assert failed_setup["status"] == "FAIL"
    assert failed_setup["setup_replayed_count"] == failed_setup["setup_count"] == 1
    assert failed_setup["mismatches"][0]["kind"] == "pi_decoy_setup"

    relabeled = copy.deepcopy(manifest)
    relabeled["run_design"]["task_band"][0]["difficulty"] = "forged"
    rejected_band = REAL_ORACLE_REPLAY(runs=runs, manifest=relabeled)
    assert rejected_band["status"] == "FAIL"
    assert "not bound to frozen" in rejected_band["errors"][0]


def test_fewer_than_six_live_tasks_is_absent_not_negative(tmp_path: Path) -> None:
    result = _analyze(tmp_path, _batch(non_live={"task-5"}))

    assert result["live_discriminating_task_count"] == 5
    for gate in ("P1", "P2", "P3", "P4"):
        assert result["gates"][gate]["status"] == "ABSENT"
    assert result["gates"]["P5"]["status"] == "PASS"
    assert result["confirm"] is False


def test_exact_sign_gate_requires_six_non_ties(tmp_path: Path) -> None:
    records = _batch()
    for record in records:
        if record.get("task") != "task-5" or record["record_type"] != "attempt":
            continue
        if record["arm"] == "bestN":
            record["proven"] = record["run_id"] != "run-9" and record["attempt"] == 4
            record["compiles"] = record["proven"]
            record["sorry_tainted"] = False
            record["graded_score"] = float(record["proven"])
    _rebuild_accounting(records)
    result = _analyze(tmp_path, records)

    per_task = result["comparisons"]["pi_repair_vs_bestN"]["live_discriminating"]["per_task"]
    assert per_task["non_ties"] == 5
    assert result["gates"]["P1"]["status"] == "ABSENT"


def test_missing_arm_and_usage_fields_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(
        ContractError,
        match="pi_decoy_setup|contiguous attempt block|arms must contain exactly",
    ):
        _analyze(tmp_path, _batch(missing_arm="pi_decoy"))
    with pytest.raises(ContractError, match="input_tokens"):
        _analyze(tmp_path, _batch(omit_usage=True))


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("seed", "seed="),
        ("index", "integer >= 1"),
        ("real_feedback", "does not chain"),
        ("independent_feedback", "must not carry feedback"),
    ],
)
def test_attempt_chain_tampering_fails_closed(tmp_path: Path, mutation: str, match: str) -> None:
    records = _batch()
    attempts = [record for record in records if record["record_type"] == "attempt"]
    if mutation == "seed":
        attempts[0]["seed"] += 99
    elif mutation == "index":
        attempts[0]["attempt"] = 0
    elif mutation == "real_feedback":
        target = next(
            item for item in attempts if item["arm"] == "legacy_repair" and item["attempt"] == 2
        )
        target["supplied_feedback"] = "wrong"
        target["supplied_feedback_sha256"] = _sha("wrong")
    else:
        target = next(item for item in attempts if item["arm"] == "bestN" and item["attempt"] == 2)
        target["used_feedback"] = True
        target["feedback_source"] = "real"
    with pytest.raises(ContractError, match=match):
        _analyze(tmp_path, records)


def test_attempt_requires_exact_model_and_lean_verdict_semantics(tmp_path: Path) -> None:
    wrong_model = _batch()
    attempt = next(record for record in wrong_model if record["record_type"] == "attempt")
    attempt["response_model_id"] = "substituted-model"
    with pytest.raises(ContractError, match="response_model_id"):
        _analyze(tmp_path, wrong_model)

    unobserved_model = _batch()
    attempt = next(record for record in unobserved_model if record["record_type"] == "attempt")
    attempt["response_model_observed"] = False
    with pytest.raises(ContractError, match="response_model_observed"):
        _analyze(tmp_path, unobserved_model)

    forged_invariant = _batch()
    attempt = next(record for record in forged_invariant if record["record_type"] == "attempt")
    attempt["compiles"] = True
    attempt["sorry_tainted"] = False
    attempt["proven"] = False
    attempt["graded_score"] = 0.0
    with pytest.raises(ContractError, match="proven must equal"):
        _analyze(tmp_path, forged_invariant)

    wrong_grade = _batch()
    attempt = next(record for record in wrong_grade if record["record_type"] == "attempt")
    attempt["compiles"] = True
    attempt["sorry_tainted"] = True
    attempt["proven"] = False
    attempt["graded_score"] = 0.0
    with pytest.raises(ContractError, match="LeanVerdict semantics"):
        _analyze(tmp_path, wrong_grade)


def test_reversed_attempt_records_fail_file_order_contract(tmp_path: Path) -> None:
    records = _batch()
    indexes = [
        index
        for index, record in enumerate(records)
        if record["record_type"] == "attempt"
        and record["run_id"] == "run-1"
        and record["task"] == "task-0"
        and record["arm"] == "bestN"
    ]
    records[indexes[0]], records[indexes[1]] = records[indexes[1]], records[indexes[0]]
    _resequence(records)

    with pytest.raises(ContractError, match="file order 1..N"):
        _analyze(tmp_path, records)


def test_swapped_task_groups_fail_counterbalanced_layout(tmp_path: Path) -> None:
    records = _batch()
    first_start = next(
        index
        for index, record in enumerate(records)
        if record["run_id"] == "run-0"
        and record.get("task") == "task-0"
        and record["record_type"] == "attempt"
    )
    first_end = next(
        index
        for index, record in enumerate(records)
        if record["run_id"] == "run-0"
        and record.get("task") == "task-0"
        and record["record_type"] == "task_summary"
    )
    second_end = next(
        index
        for index, record in enumerate(records)
        if record["run_id"] == "run-0"
        and record.get("task") == "task-1"
        and record["record_type"] == "task_summary"
    )
    first_group = records[first_start : first_end + 1]
    second_group = records[first_end + 1 : second_end + 1]
    records[first_start : second_end + 1] = second_group + first_group
    _resequence(records)

    with pytest.raises(ContractError, match="contiguous attempt block|task group order"):
        _analyze(tmp_path, records)


def test_unsuccessful_baseline_must_exhaust_k(tmp_path: Path) -> None:
    records = _batch()
    records[:] = [
        record
        for record in records
        if not (
            record["record_type"] == "attempt"
            and record["run_id"] == "run-9"
            and record.get("task") == "task-0"
            and record.get("arm") == "bestN"
            and record.get("attempt") == 4
        )
    ]
    _rebuild_accounting(records)
    _resequence(records)

    with pytest.raises(ContractError, match="must exhaust K"):
        _analyze(tmp_path, records)


def test_pi_lifecycle_is_required_and_conserved(tmp_path: Path) -> None:
    missing = [
        record
        for record in _batch()
        if not (
            record["run_id"] == "run-0"
            and record.get("task") == "task-0"
            and record.get("arm") == "pi_repair"
            and record["record_type"] in {"pi_event", "pi_stop"}
        )
    ]
    _resequence(missing)
    with pytest.raises(ContractError, match="PI event block|pi_stop|lifecycle"):
        _analyze(tmp_path, missing)

    corrupt = _batch()
    stop = next(
        record
        for record in corrupt
        if record["record_type"] == "pi_stop"
        and record["run_id"] == "run-0"
        and record["task"] == "task-0"
        and record["arm"] == "pi_repair"
    )
    stop["evaluations"] -= 1
    with pytest.raises(ContractError, match="do not conserve"):
        _analyze(tmp_path, corrupt)


def test_deleted_repair_requested_event_fails_exact_lifecycle(tmp_path: Path) -> None:
    records = _batch()
    target = next(
        index
        for index, record in enumerate(records)
        if record["record_type"] == "pi_event"
        and record["run_id"] == "run-0"
        and record["task"] == "task-0"
        and record["arm"] == "pi_repair"
        and record["kind"] == "repair_requested"
    )
    del records[target]
    _resequence(records)

    with pytest.raises(
        ContractError,
        match="PI event sequence|lifecycle event pattern|pattern expected",
    ):
        _analyze(tmp_path, records)


def test_decoy_setup_source_and_exact_transform_are_mandatory(tmp_path: Path) -> None:
    missing = [
        record
        for record in _batch()
        if not (
            record["record_type"] == "pi_decoy_setup"
            and record["run_id"] == "run-0"
            and record["task"] == "task-0"
        )
    ]
    _resequence(missing)
    with pytest.raises(ContractError, match="pi_decoy_setup"):
        _analyze(tmp_path, missing)

    corrupt_source = _batch()
    setup = next(
        record
        for record in corrupt_source
        if record["record_type"] == "pi_decoy_setup"
        and record["run_id"] == "run-0"
        and record["task"] == "task-0"
    )
    setup["source_task"] = "forged-source"
    with pytest.raises(ContractError, match="source_task"):
        _analyze(tmp_path, corrupt_source)

    wrong_transform = _batch()
    target = next(
        record
        for record in wrong_transform
        if record["record_type"] == "attempt"
        and record["run_id"] == "run-0"
        and record["task"] == "task-0"
        and record["arm"] == "pi_decoy"
        and record["attempt"] == 2
    )
    previous = next(
        record
        for record in wrong_transform
        if record["record_type"] == "attempt"
        and record["run_id"] == "run-0"
        and record["task"] == "task-0"
        and record["arm"] == "pi_decoy"
        and record["attempt"] == 1
    )
    target["supplied_feedback"] = "Z" * len(previous["diagnostic"])
    target["supplied_feedback_sha256"] = _sha(target["supplied_feedback"])
    with pytest.raises(ContractError, match="frozen setup transform"):
        _analyze(tmp_path, wrong_transform)


@pytest.mark.parametrize("field", ["candidate_fingerprint", "diagnostic_fingerprint"])
def test_corrupt_pi_event_fingerprint_fails_payload_binding(tmp_path: Path, field: str) -> None:
    records = _batch()
    event = next(
        record
        for record in records
        if record["record_type"] == "pi_event"
        and record["run_id"] == "run-0"
        and record["task"] == "task-0"
        and record["arm"] == "pi_repair"
        and record["kind"] == "oracle_evaluated"
        and record["attempt"] == 0
    )
    event[field] = _sha(f"corrupt:{field}")

    with pytest.raises(ContractError, match=f"{field} does not bind"):
        _analyze(tmp_path, records)


def test_every_attempt_requires_positive_visible_telemetry(tmp_path: Path) -> None:
    with pytest.raises(ContractError, match="input_tokens.*integer >= 1"):
        _analyze(
            tmp_path,
            _batch(zero_usage=("run-0", "task-0", "single", 1)),
        )


def test_output_tokens_cannot_exceed_frozen_attempt_cap(tmp_path: Path) -> None:
    records = _batch()
    attempt = next(
        record
        for record in records
        if record["record_type"] == "attempt"
        and record["run_id"] == "run-1"
        and record["task"] == "task-0"
        and record["arm"] == "single"
    )
    attempt["output_tokens"] = 9999

    with pytest.raises(ContractError, match="exceeds frozen max_tokens_per_attempt"):
        _analyze(tmp_path, records)


def test_raw_parity_uses_live_tasks_not_non_live_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _synthetic_manifest(task_count=7)
    monkeypatch.setattr(analyzer, "_load_manifest", lambda _path: copy.deepcopy(manifest))
    records = _batch(manifest=manifest, non_live={"task-6"})
    for record in records:
        if (
            record["record_type"] == "attempt"
            and record["task"] == "task-6"
            and record["arm"] == "pi_repair"
        ):
            record["input_tokens"] *= 100
    _rebuild_accounting(records)
    result = _analyze(tmp_path, records)

    assert result["live_discriminating_task_count"] == 6
    assert (
        result["usage"]["all_tasks"]["pi_repair"]["total_tokens"]
        > result["usage"]["all_tasks"]["bestN"]["total_tokens"]
    )
    assert result["usage"]["pi_repair_ratios"]["bestN"]["total_tokens"] == 1.0
    assert result["gates"]["P4"]["status"] == "PASS"


def test_p4_requires_matched_survival_against_decoy_and_plain(tmp_path: Path) -> None:
    records = _batch()
    for record in records:
        if record["record_type"] == "attempt" and record["arm"] == "pi_decoy":
            record["input_tokens"] = 35
            record["output_tokens"] = 10
            if record["run_id"] != "run-9" and record["attempt"] == 4:
                record["proven"] = True
                record["compiles"] = True
                record["sorry_tainted"] = False
                record["graded_score"] = 1.0
                record["diagnostic"] = ""
                record["diagnostic_sha256"] = analyzer._EMPTY_SHA256
        if (
            record["record_type"] == "pi_event"
            and record["arm"] == "pi_decoy"
            and record["run_id"] != "run-9"
            and record["kind"] == "oracle_evaluated"
            and record["attempt"] == 3
        ):
            record["status"] = "passed"
            record["score"] = 1.0
            record["diagnostic_fingerprint"] = analyzer.feedback_from_value(
                lens="lean-ungameable",
                kind="lean-proof",
                passed=True,
                score=1.0,
                diagnostic="",
            ).fingerprint
        if (
            record["record_type"] == "pi_stop"
            and record["arm"] == "pi_decoy"
            and record["run_id"] != "run-9"
        ):
            record["stop"] = "complete"
            record["verified"] = True
            record["improved"] = True
            record["best_attempt"] = 3
        if record["record_type"] == "task_summary" and record["run_id"] != "run-9":
            record["arms"]["pi_decoy"]["pi_stop"] = "complete"
    _rebuild_accounting(records)
    result = _analyze(tmp_path, records)

    assert result["usage"]["pi_repair_ratios"]["pi_decoy"]["total_tokens"] == pytest.approx(
        200 / 180
    )
    matched = result["gates"]["P4"]["matched_cumulative_tokens"]["pi_decoy"]
    assert matched["per_run"]["wins"] == 0
    assert result["gates"]["P4"]["status"] == "FAIL"


def test_run_design_timestamp_and_endpoint_evidence_fail_closed(tmp_path: Path) -> None:
    wrong_design = _batch()
    for record in wrong_design:
        record["backend"] = "frontier:not-the-frozen-model"
    result = _analyze(tmp_path, wrong_design)
    assert result["gates"]["P5"]["status"] == "FAIL"
    assert "backend" in result["gates"]["P5"]["run_design_mismatches"]

    bad_timestamp = _batch()
    for record in bad_timestamp:
        if record["run_id"] == "run-0":
            record["timestamp_utc"] = "2026-07-16T00:00:00"
    with pytest.raises(ContractError, match="timezone"):
        _analyze(tmp_path, bad_timestamp)

    inconsistent_endpoint = _batch()
    for record in inconsistent_endpoint:
        if record["run_id"] == "run-1":
            record["endpoint_fingerprint"] = _sha("other-endpoint")
    with pytest.raises(ContractError, match="endpoint"):
        _analyze(tmp_path, inconsistent_endpoint)


def test_git_commit_must_predate_every_run_timestamp(tmp_path: Path) -> None:
    records = _batch()
    for record in records:
        if record["run_id"] == "run-0":
            record["timestamp_utc"] = "2000-01-01T00:00:00+00:00"
    result = _analyze(tmp_path, records)

    assert result["gates"]["P5"]["status"] == "FAIL"
    assert any(
        "must predate run timestamp" in error
        for error in result["gates"]["P5"]["git"]["verification"]["errors"]
    )


def test_git_commit_must_predate_each_jsonl_mtime(tmp_path: Path) -> None:
    path = tmp_path / "old-evidence.jsonl"
    _write_jsonl(path, _batch())
    os.utime(path, (946_684_800, 946_684_800))
    result = analyze_paths([path])

    assert result["gates"]["P5"]["status"] == "FAIL"
    assert any(
        "must predate JSONL mtime" in error
        for error in result["gates"]["P5"]["git"]["verification"]["errors"]
    )


def test_task_hash_and_cross_run_task_order_are_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_hash = _batch()
    summary = next(record for record in bad_hash if record["record_type"] == "task_summary")
    summary["task_sha256"] = _sha("other-task")
    with pytest.raises(ContractError, match="task_sha256"):
        _analyze(tmp_path, bad_hash)

    path = tmp_path / "ordered.jsonl"
    _write_jsonl(path, _batch())
    parsed = analyzer._read_records([path])
    original_build = analyzer._build_run

    def reordered(run_id: str, rows: list[dict[str, Any]]) -> analyzer.Run:
        run = original_build(run_id, rows)
        if run_id == "run-1":
            run.task_order = list(reversed(run.task_order))
        return run

    monkeypatch.setattr(analyzer, "_build_run", reordered)
    with pytest.raises(ContractError, match="ordered task band"):
        analyzer._validated_runs(parsed)


def test_manifest_and_sandbox_hash_mismatch_fail_p5(tmp_path: Path) -> None:
    records = _batch()
    for record in records:
        if record["record_type"] == "run_start":
            record["artifact_hashes"]["runner"] = "0" * 64
        record["sandbox_runner_sha256"] = _sha("wrong-sandbox")
    result = _analyze(tmp_path, records)

    assert result["gates"]["P5"]["status"] == "FAIL"
    assert "runner" in result["gates"]["P5"]["provenance_mismatches"]
    assert "sandbox_runner_sha256" in result["gates"]["P5"]["run_design_mismatches"]


def test_git_verification_failure_blocks_p5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        analyzer,
        "_verify_git_provenance",
        lambda **_kwargs: {
            "ok": False,
            "errors": ["commit blob mismatch"],
            "checked": {},
        },
    )
    result = _analyze(tmp_path, _batch())

    assert result["gates"]["P5"]["status"] == "FAIL"
    assert "commit blob mismatch" in result["gates"]["P5"]["git"]["verification"]["errors"]


def test_self_consistent_forged_oracle_booleans_fail_replay_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    records = _batch()
    target = next(
        record
        for record in records
        if record["record_type"] == "attempt"
        and record["run_id"] == "run-1"
        and record["task"] == "task-0"
        and record["arm"] == "single"
    )
    target.update(
        {
            "compiles": True,
            "proven": True,
            "sorry_tainted": False,
            "graded_score": 1.0,
            "diagnostic": "",
            "diagnostic_sha256": analyzer._EMPTY_SHA256,
        }
    )
    _rebuild_accounting(records)

    def replay_mismatch(**kwargs: Any) -> dict[str, Any]:
        attempts = [
            attempt
            for run in kwargs["runs"]
            for arm_attempts in run.attempts.values()
            for attempt in arm_attempts
        ]
        forged = next(
            attempt
            for attempt in attempts
            if attempt.run_id == "run-1" and attempt.task == "task-0" and attempt.arm == "single"
        )
        assert forged.compiles and forged.proven and not forged.sorry_tainted
        return {
            "status": "FAIL",
            "attempt_count": len(attempts),
            "replayed_count": len(attempts),
            "receipt_sha256": _sha("forged-verdict-replay"),
            "mismatch_count": 1,
            "mismatches": [{"differences": ["compiles", "proven", "graded_score"]}],
            "errors": ["one or more replayed oracle verdicts differ"],
            "identity": {"expected": "frozen", "observed": "frozen"},
        }

    monkeypatch.setattr(analyzer, "_replay_oracle_integrity", replay_mismatch)
    result = _analyze(tmp_path, records)

    assert result["gates"]["P5"]["status"] == "FAIL"
    assert result["gates"]["P5"]["oracle_replay"]["mismatch_count"] == 1


def test_forged_failed_diagnostic_fails_replay_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    records = _batch()
    target = next(
        record
        for record in records
        if record["record_type"] == "attempt"
        and record["run_id"] == "run-1"
        and record["task"] == "task-0"
        and record["arm"] == "single"
    )
    target["diagnostic"] = "forged deterministic failure"
    target["diagnostic_sha256"] = _sha(target["diagnostic"])
    monkeypatch.setattr(
        analyzer,
        "_replay_oracle_integrity",
        lambda **_kwargs: {
            "status": "FAIL",
            "attempt_count": 1,
            "replayed_count": 1,
            "receipt_sha256": _sha("forged-diagnostic-replay"),
            "mismatch_count": 1,
            "mismatches": [{"differences": ["diagnostic_sha256", "diagnostic_exact"]}],
            "errors": ["one or more replayed oracle verdicts differ"],
            "identity": {"expected": "frozen", "observed": "frozen"},
        },
    )
    result = _analyze(tmp_path, records)

    assert result["gates"]["P5"]["status"] == "FAIL"
    assert (
        "diagnostic_sha256"
        in result["gates"]["P5"]["oracle_replay"]["mismatches"][0]["differences"]
    )


def test_sandbox_unavailable_fails_mandatory_replay_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        analyzer,
        "_replay_oracle_integrity",
        lambda **_kwargs: {
            "status": "FAIL",
            "attempt_count": 1440,
            "replayed_count": 0,
            "receipt_sha256": None,
            "mismatch_count": 0,
            "mismatches": [],
            "errors": ["sandbox unavailable: SandboxUnavailable"],
            "identity": None,
        },
    )
    result = _analyze(tmp_path, _batch())

    assert all(result["gates"][gate]["status"] == "ABSENT" for gate in ("P1", "P2", "P3", "P4"))
    assert result["gates"]["P5"]["status"] == "FAIL"
    assert "sandbox unavailable" in result["gates"]["P5"]["oracle_replay"]["errors"][0]


def test_git_helper_rejects_dirty_digest_and_missing_commit() -> None:
    manifest = _synthetic_manifest()
    manifest["repo_root"] = str(Path.cwd())
    result = REAL_GIT_VERIFY(
        commit="f" * 40,
        dirty=True,
        status_sha256=_sha("dirty"),
        manifest=manifest,
    )

    assert result["ok"] is False
    assert any("git_dirty" in error for error in result["errors"])
    assert any("sha256(empty)" in error for error in result["errors"])
    assert any("does not exist" in error for error in result["errors"])


def test_threshold_override_and_redaction_cannot_confirm(
    tmp_path: Path,
) -> None:
    path = tmp_path / "override.jsonl"
    _write_jsonl(path, _batch(payload_mode="redacted"))
    result = analyze_paths([path], parity_high=2.0)

    assert result["threshold_override"] is True
    assert result["gates"]["P5"]["status"] == "FAIL"
    assert result["confirm"] is False


def test_cli_is_json_and_contract_errors_are_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good = tmp_path / "good.jsonl"
    _write_jsonl(good, _batch())
    assert main([str(good), "--json", "--compact"]) == 0
    assert json.loads(capsys.readouterr().out)["confirm"] is True

    bad = tmp_path / "bad.jsonl"
    _write_jsonl(bad, _batch(missing_arm="single"))
    assert main([str(bad), "--compact"]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "ContractError"
