#!/usr/bin/env python3
"""Build integrity and machine-judgment receipts for the frozen v3 experiment."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from lakatos.programme import evidence as evidence_contract
from lakatos.programme.record_judge import judge_record


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SYMPOSIUM_ROOT = REPO_ROOT.parents[1]
ANALYZER = REPO_ROOT / "engine/efficacy/analyze_diagnostic_repair_harness.py"
CONTRACT = REPO_ROOT / "engine/efficacy/diagnostic_repair_harness_contract.json"
JUDGE_SOURCE = (
    SYMPOSIUM_ROOT / "PI/lakatotree/lakatos/programme/record_judge.py"
)
JUDGE_RUNNER = HERE / "run_pure_judge.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def git_head(path: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def contains_authored_verdict(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key.casefold() in {
                "verdict",
                "manual_verdict",
                "metric_verdict",
                "human_verdict",
                "verdict_source",
            }
            or contains_authored_verdict(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(contains_authored_verdict(child) for child in value)
    return False


def verify_evidence_inputs(evidence: dict[str, Any]) -> None:
    for item in evidence["provenance"]["inputs"]:
        source = (REPO_ROOT / item["source"]).resolve()
        require(
            source.is_relative_to(REPO_ROOT),
            f"evidence input escapes repo: {source}",
        )
        require(source.is_file(), f"evidence input does not exist: {source}")
        require(
            sha256(source) == item["sha256"],
            f"evidence input hash mismatch: {source}",
        )


def main() -> int:
    analysis_path = HERE / "analysis.json"
    restored_path = HERE / "analysis-restored.json"
    negative_start_path = HERE / "negative-run-start.json"
    negative_stderr_path = HERE / "negative-analyzer.stderr.json"
    negative_rc_path = HERE / "negative-analyzer.rc"
    prereg_request_path = HERE / "lakatotree-preregistration-request.json"
    prereg_response_path = HERE / "lakatotree-preregistration-response.json"
    evidence_path = HERE / "lakato-evidence.json"
    judge_response_path = HERE / "judge-response.json"
    judge_rc_path = HERE / "judge.rc"
    analysis_rc_path = HERE / "analysis.rc"
    restored_rc_path = HERE / "analysis-restored.rc"

    analysis = load_json(analysis_path)
    restored = load_json(restored_path)
    negative_error = load_json(negative_stderr_path)
    prereg_request = load_json(prereg_request_path)
    prereg_response = load_json(prereg_response_path)
    evidence = load_json(evidence_path)
    judge_response = load_json(judge_response_path)

    analysis_sha = sha256(analysis_path)
    restored_sha = sha256(restored_path)
    raw_inputs = analysis["provenance"]["raw_jsonl_sha256"]
    original_jsonl_path = Path(raw_inputs[0]["path"])
    original_run_start_line = original_jsonl_path.read_bytes().splitlines(
        keepends=True
    )[0]
    original_run_start = json.loads(original_run_start_line)
    require(
        sha256(original_jsonl_path) == raw_inputs[0]["sha256"],
        "original JSONL no longer matches the positive analysis",
    )
    require(analysis_sha == restored_sha, "restored analysis does not match original")
    require(analysis == restored, "restored analysis JSON differs from original")
    require(negative_rc_path.read_text(encoding="utf-8").strip() == "2", "negative analyzer rc must be 2")
    require(negative_error.get("error") == "ContractError", "negative analyzer must fail with ContractError")
    require(negative_error.get("ok") is False, "negative analyzer must report ok=false")
    require(analysis.get("runs") == 10, "positive analysis must contain 10 runs")
    require(
        analysis.get("provenance", {}).get("oracle_replay", {}).get("status")
        == "PASS",
        "positive analysis must pass oracle replay",
    )
    require(
        analysis.get("provenance", {}).get("oracle_replay", {}).get(
            "mismatch_count"
        )
        == 0,
        "positive analysis must have zero replay mismatches",
    )
    require(
        prereg_response.get("prediction_receipt_sha256")
        == prereg_response.get("request_sha256")
        == sha256(prereg_request_path),
        "preregistration response does not bind its request",
    )
    require(
        prereg_request.get("registered_before_measurement") is True,
        "preregistration must precede measurement",
    )
    require(
        not evidence_contract.validate_record(evidence),
        "evidence record is invalid",
    )
    require(
        evidence_contract.is_grounded(evidence),
        "evidence record is not grounded",
    )
    require(not contains_authored_verdict(evidence), "evidence contains a verdict key")
    require(
        evidence.get("programme") == prereg_request["programme"],
        "evidence programme does not match preregistration",
    )
    require(
        evidence.get("branch") == prereg_request["branch"],
        "evidence branch does not match preregistration",
    )
    require(
        evidence.get("conjecture") == prereg_request["conjecture"],
        "evidence conjecture does not match preregistration",
    )
    evidence_prereg = evidence["preregistration"]
    require(
        evidence_prereg.get("claim") == prereg_request["conjecture"],
        "evidence claim does not match preregistration",
    )
    require(
        evidence_prereg.get("kill_condition")
        == prereg_request["kill_condition"],
        "evidence kill condition does not match preregistration",
    )
    require(
        evidence_prereg.get("prediction_receipt_sha256")
        == prereg_response["prediction_receipt_sha256"],
        "evidence does not bind the prediction receipt",
    )
    require(
        evidence_prereg.get("registered_at") == prereg_request["registered_at"],
        "evidence registration timestamp does not match preregistration",
    )
    require(
        evidence["harness"].get("git_commit")
        == prereg_request["frozen_sources"]["git_head"],
        "evidence git commit does not match the frozen source",
    )
    b1_started_at = evidence["measurement"]["derived"]["B1"]["started_at"]
    live_started_at = analysis["timestamps_utc"][0]
    measurement_started_at = min(
        parse_timestamp(b1_started_at),
        parse_timestamp(live_started_at),
    )
    require(
        parse_timestamp(prereg_request["registered_at"])
        < measurement_started_at,
        "a credited measurement predates preregistration",
    )
    verify_evidence_inputs(evidence)
    require(
        analysis_rc_path.read_text(encoding="utf-8").strip() == "0",
        "positive analyzer rc must be 0",
    )
    require(
        restored_rc_path.read_text(encoding="utf-8").strip() == "0",
        "restored analyzer rc must be 0",
    )
    require(
        judge_rc_path.read_text(encoding="utf-8").strip() == "0",
        "pure judge rc must be 0",
    )

    rederived_response = judge_record(evidence_path)
    require(
        rederived_response == judge_response,
        "stored judge response does not match a fresh pure-judge derivation",
    )
    require(
        judge_response.get("status") == "judged",
        "pure judge did not produce a machine judgment",
    )

    negative_receipt_path = HERE / "negative-oracle.json"
    negative_receipt = {
        "schema": "pi-diagnostic-repair-negative-oracle/v1",
        "technique": "fault_injection",
        "injection": (
            "On an isolated copy only, replace the first run_start.model_id "
            "with fault-injected-model-id."
        ),
        "expected_result": {
            "analyzer_exit_code": 2,
            "error": "ContractError",
            "claim_bearing_analysis_emitted": False,
        },
        "observed_result": {
            "analyzer_exit_code": 2,
            "error": negative_error["error"],
            "ok": negative_error["ok"],
            "detail": negative_error["detail"],
            "original_jsonl_path": relative(original_jsonl_path, REPO_ROOT),
            "original_jsonl_sha256": sha256(original_jsonl_path),
            "original_run_start_model_id": original_run_start["model_id"],
            "original_run_start_sha256": hashlib.sha256(
                original_run_start_line
            ).hexdigest(),
            "modified_run_start_path": relative(negative_start_path, REPO_ROOT),
            "modified_run_start_sha256": sha256(negative_start_path),
            "stderr_path": relative(negative_stderr_path, REPO_ROOT),
            "stderr_sha256": sha256(negative_stderr_path),
        },
        "restore_check": {
            "restored": True,
            "original_analysis_path": relative(analysis_path, REPO_ROOT),
            "original_analysis_sha256": analysis_sha,
            "restored_analysis_path": relative(restored_path, REPO_ROOT),
            "restored_analysis_sha256": restored_sha,
            "hashes_equal": True,
            "restored_analyzer_exit_code": int(
                restored_rc_path.read_text(encoding="utf-8").strip()
            ),
        },
    }
    write_json(negative_receipt_path, negative_receipt)

    ooptdd_path = HERE / "ooptdd-receipt.json"
    analyzer_sha = sha256(ANALYZER)
    contract_sha = sha256(CONTRACT)
    replay = analysis["provenance"]["oracle_replay"]
    ooptdd_receipt = {
        "schema_version": "symposium-ooptdd-receipt/v1",
        "template_only": False,
        "receipt_id": "bhgman-diagnostic-repair-v3-integrity",
        "cycle_id": "pi-diagnostic-repair-live-20260716",
        "requirement_group": "DIAGNOSTIC-REPAIR-V3-INTEGRITY",
        "spec": {
            "path": relative(CONTRACT, REPO_ROOT),
            "sha256": contract_sha,
            "locked_before_positive_run": True,
        },
        "producer": {
            "command": (
                "uv run python -m "
                "engine.efficacy.analyze_diagnostic_repair_harness "
                "--json verification/diagnostic-repair-v3-32b "
                "> verification/diagnostic-repair-v3-32b/analysis.json "
                "2> /tmp/pi-diagnostic-repair-v3-analysis-20260717.stderr"
            ),
            "cwd": str(REPO_ROOT),
            "git_head": analysis["provenance"]["git"]["commit"],
            "entrypoint": (
                "engine.efficacy.analyze_diagnostic_repair_harness:analyze_paths"
            ),
            "source_path": relative(ANALYZER, REPO_ROOT),
            "source_symbol": "analyze_paths",
            "real_code_path": True,
            "exit_code": int(
                analysis_rc_path.read_text(encoding="utf-8").strip()
            ),
        },
        "correlation": {
            "cid": "pi-diagnostic-repair-v3-32b-20260716",
        },
        "requirements": [
            {
                "id": "DR-V3-CONTRACT-DRIFT",
                "role": "guard_defect",
                "event": "fault_injected_model_id_rejected_with_contract_error",
            },
            {
                "id": "DR-V3-RESTORE-REPLAY",
                "role": "guard_mechanism",
                "event": "untouched_analysis_reproduces_original_sha256",
            },
        ],
        "positive": {
            "observed_verdict": "green",
            "receipt_path": relative(analysis_path, REPO_ROOT),
            "receipt_sha256": analysis_sha,
            "evidence_tier": "arrived",
            "charge_ratio": 1.0,
            "forbidden_events_passed": (
                replay["mismatch_count"] == 0 and not replay["errors"]
            ),
            "loop": {
                "complete": True,
                "methodology_ok": True,
                "done": analysis["runs"],
                "total": 10,
            },
        },
        "negative_oracle": {
            "spec_sha256": contract_sha,
            "technique": "fault_injection",
            "injection": negative_receipt["injection"],
            "observed_verdict": "rejected",
            "receipt_path": relative(negative_receipt_path, REPO_ROOT),
            "receipt_sha256": sha256(negative_receipt_path),
            "restored": True,
        },
        "oracle": {
            "separate_source": False,
            "corroborated": False,
            "emit_identity": f"file://{relative(analysis_path, REPO_ROOT)}",
            "read_identity": f"file://{relative(analysis_path, REPO_ROOT)}",
        },
        "source_binding": {
            "path": relative(ANALYZER, REPO_ROOT),
            "symbol": "analyze_paths",
            "sha256": analyzer_sha,
        },
    }
    write_json(ooptdd_path, ooptdd_receipt)

    judge_response_sha = sha256(judge_response_path)
    prediction_receipt_sha = prereg_response["prediction_receipt_sha256"]
    chain_path = HERE / "judge-chain.json"
    chain = {
        "schema": "local-pure-judge-chain/v1",
        "head": judge_response_sha,
        "receipts": [
            {
                "receipt_sha": judge_response_sha,
                "prev_receipt_sha": prediction_receipt_sha,
                "receipt_kind": "machine_judgment",
                "judge_entrypoint": "lakatos.programme.record_judge:judge_record",
                "response": judge_response,
            },
            {
                "receipt_sha": prediction_receipt_sha,
                "prev_receipt_sha": None,
                "receipt_kind": "prediction",
                "request_sha256": sha256(prereg_request_path),
                "registered_at": prereg_request["registered_at"],
            },
        ],
    }
    write_json(chain_path, chain)

    verify_path = HERE / "judge-verify.json"
    judge_source_sha = sha256(JUDGE_SOURCE)
    scripted_source_confirmed = (
        judge_source_sha
        == prereg_request["frozen_sources"]["judge_script_sha256"]
    )
    verify = {
        "schema": "local-pure-judge-verification/v1",
        "ok": True,
        "from_receipt": True,
        "head_receipt_sha256": judge_response_sha,
        "prev_receipt_sha256": prediction_receipt_sha,
        "response_matches_fresh_derivation": True,
        "scripted_source_confirmed": scripted_source_confirmed,
        "judge_script_sha256": judge_source_sha,
        "judge_runner_sha256": sha256(JUDGE_RUNNER),
        "evidence_sha256": sha256(evidence_path),
    }
    require(scripted_source_confirmed, "judge source hash does not match preregistration")
    write_json(verify_path, verify)

    packet_path = HERE / "judgment-packet.json"
    packet = {
        "schema_version": "symposium-lakatotree-judgment/v1",
        "template_only": False,
        "programme": prereg_request["programme"],
        "branch": prereg_request["branch"],
        "conjecture": prereg_request["conjecture"],
        "roles": {
            "implementer": "codex-pi-diagnostic-repair-live-20260716",
            "judge": "lakatotree-local-pure-judge",
        },
        "preregistration": {
            "request_path": relative(prereg_request_path, SYMPOSIUM_ROOT),
            "request_sha256": sha256(prereg_request_path),
            "response_path": relative(prereg_response_path, SYMPOSIUM_ROOT),
            "response_sha256": sha256(prereg_response_path),
            "prediction_receipt_sha256": prediction_receipt_sha,
            "registered_at": prereg_request["registered_at"],
            "registered_before_measurement": True,
            "prediction": {
                "metric": prereg_request["prediction"]["metric"],
                "direction": prereg_request["prediction"]["direction"],
                "baseline": prereg_request["prediction"]["baseline"],
                "noise_band": prereg_request["prediction"]["noise_band"],
                "scale_type": prereg_request["prediction"]["scale_type"],
            },
            "kill_condition": prereg_request["kill_condition"],
            "judge_script_path": relative(JUDGE_SOURCE, SYMPOSIUM_ROOT),
            "judge_script_sha256": judge_source_sha,
        },
        "measurement": {
            "started_at": measurement_started_at.isoformat(),
            "evidence_records": [
                {
                    "path": relative(evidence_path, SYMPOSIUM_ROOT),
                    "sha256": sha256(evidence_path),
                    "schema": "lakato-evidence-record/v1",
                    "grounded": True,
                    "contains_verdict": False,
                }
            ],
        },
        "judge": {
            "command": (
                "PYTHONPATH=PI/lakatotree PI/lakatotree/.venv/bin/python "
                "GIT/bhgman_tool-wt-pi-runtime-20260716/verification/"
                "diagnostic-repair-v3-32b/run_pure_judge.py "
                "--evidence GIT/bhgman_tool-wt-pi-runtime-20260716/"
                "verification/diagnostic-repair-v3-32b/lakato-evidence.json "
                "--output GIT/bhgman_tool-wt-pi-runtime-20260716/"
                "verification/diagnostic-repair-v3-32b/judge-response.json "
                "--rc-output GIT/bhgman_tool-wt-pi-runtime-20260716/"
                "verification/diagnostic-repair-v3-32b/judge.rc "
                "> GIT/bhgman_tool-wt-pi-runtime-20260716/verification/"
                "diagnostic-repair-v3-32b/judge.stdout.log "
                "2> GIT/bhgman_tool-wt-pi-runtime-20260716/verification/"
                "diagnostic-repair-v3-32b/judge.stderr.log"
            ),
            "cwd": str(SYMPOSIUM_ROOT),
            "git_head": git_head(SYMPOSIUM_ROOT / "PI/lakatotree"),
            "entrypoint": "lakatos.programme.record_judge:judge_record",
            "exit_code": int(
                judge_rc_path.read_text(encoding="utf-8").strip()
            ),
            "response_path": relative(judge_response_path, SYMPOSIUM_ROOT),
            "response_sha256": judge_response_sha,
            "verdict_receipt_sha256": judge_response_sha,
            "prev_receipt_sha256": prediction_receipt_sha,
        },
        "verification": {
            "receipt_chain_path": relative(chain_path, SYMPOSIUM_ROOT),
            "receipt_chain_sha256": sha256(chain_path),
            "verify_output_path": relative(verify_path, SYMPOSIUM_ROOT),
            "verify_output_sha256": sha256(verify_path),
            "head_receipt_sha256": judge_response_sha,
            "ok": True,
            "from_receipt": True,
            "scripted_source_confirmed": scripted_source_confirmed,
        },
    }
    require(
        not contains_authored_verdict(packet),
        "judgment packet contains a forbidden verdict key",
    )
    write_json(packet_path, packet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
