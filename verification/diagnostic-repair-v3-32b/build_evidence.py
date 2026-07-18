#!/usr/bin/env python3
"""Build a verdict-free LakatoTree evidence record from frozen harness outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_GATES = ("P1", "P2", "P3", "P4", "P5")
EMPTY_STATUS_SHA256 = hashlib.sha256(b"").hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def relative_source(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def parse_b1(path: Path, expected_commit: str) -> tuple[int, dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    started = re.search(r"^b1_started_at=(.+)$", text, re.MULTILINE)
    finished = re.search(r"^b1_finished_at=(.+)$", text, re.MULTILINE)
    commit = re.search(r"^git_head=([0-9a-f]{40,64})$", text, re.MULTILINE)
    status_hash = re.search(r"^git_status_sha256=([0-9a-f]{64})$", text, re.MULTILINE)
    exit_code = re.search(r"^exit_code=(\d+)$", text, re.MULTILINE)
    observed = (
        started is not None
        and finished is not None
        and commit is not None
        and commit.group(1) == expected_commit
        and status_hash is not None
        and status_hash.group(1) == EMPTY_STATUS_SHA256
        and exit_code is not None
        and exit_code.group(1) == "0"
        and re.search(r"^1 passed in [0-9.]+s$", text, re.MULTILINE) is not None
    )
    return int(observed), {
        "state": "PASS" if observed else "ABSENT",
        "started_at": started.group(1) if started else None,
        "finished_at": finished.group(1) if finished else None,
        "git_head": commit.group(1) if commit else None,
        "git_status_sha256": status_hash.group(1) if status_hash else None,
        "exit_code": int(exit_code.group(1)) if exit_code else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--b1-log", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--prereg-request", type=Path, required=True)
    parser.add_argument("--prereg-response", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--script-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    analysis = load_json(args.analysis)
    prereg_request = load_json(args.prereg_request)
    prereg_response = load_json(args.prereg_response)
    manifest = load_json(args.manifest)

    gates = analysis.get("gates")
    if not isinstance(gates, dict) or tuple(gates) != EXPECTED_GATES:
        raise ValueError("analysis.gates must contain ordered P1-P5 only")
    gate_states: dict[str, str] = {}
    for gate_name in EXPECTED_GATES:
        gate = gates.get(gate_name)
        if not isinstance(gate, dict) or gate.get("status") not in {"PASS", "FAIL", "ABSENT"}:
            raise ValueError(f"analysis.gates.{gate_name}.status is invalid")
        gate_states[gate_name] = str(gate["status"])

    provenance = analysis.get("provenance")
    git = provenance.get("git") if isinstance(provenance, dict) else None
    git_commit = git.get("commit") if isinstance(git, dict) else None
    if not isinstance(git_commit, str):
        raise ValueError("analysis provenance is missing git.commit")
    if analysis.get("runs") != 10:
        raise ValueError("analysis must contain the frozen 10 replications")
    if analysis.get("final_claim_confirm") is not None:
        raise ValueError("analysis.final_claim_confirm must remain null")
    if analysis.get("confirm") is not all(
        gate_states[name] == "PASS" for name in EXPECTED_GATES
    ):
        raise ValueError("analysis.confirm disagrees with P1-P5 states")

    frozen = prereg_request.get("frozen_sources")
    if not isinstance(frozen, dict):
        raise ValueError("preregistration request lacks frozen_sources")
    if sha256(args.manifest) != frozen.get("manifest_sha256"):
        raise ValueError("manifest hash does not match preregistration request")
    if sha256(args.preregistration) != frozen.get("preregistration_sha256"):
        raise ValueError("frozen preregistration hash mismatch")
    if sha256(args.prereg_request) != prereg_response.get("request_sha256"):
        raise ValueError("preregistration response does not bind the request")
    if prereg_response.get("prediction_receipt_sha256") != prereg_response.get(
        "request_sha256"
    ):
        raise ValueError("prediction receipt is not content-addressed to the request")
    if manifest.get("run_design", {}).get("model_id") != analysis.get("model_id"):
        raise ValueError("analysis model does not match the frozen manifest")

    b1_credit, b1_detail = parse_b1(args.b1_log, git_commit)
    statistical_gate_count = sum(
        gate_states[name] == "PASS" for name in EXPECTED_GATES
    )
    confirmed_gate_count = b1_credit + statistical_gate_count

    root = args.repo_root.resolve()
    inputs = [
        ("analysis", args.analysis),
        ("b1_preflight", args.b1_log),
        ("frozen_manifest", args.manifest),
        ("frozen_preregistration", args.preregistration),
        ("lakatotree_preregistration_request", args.prereg_request),
        ("lakatotree_preregistration_response", args.prereg_response),
        ("evidence_builder", args.script_path),
    ]
    record = {
        "schema": "lakato-evidence-record/v1",
        "programme": prereg_request["programme"],
        "branch": prereg_request["branch"],
        "node_tag": "exact-qwen2.5-32b-six-arm-confirmatory",
        "conjecture": prereg_request["conjecture"],
        "preregistration": {
            "registered_before_measurement": True,
            "registered_at": prereg_request["registered_at"],
            "claim": prereg_request["conjecture"],
            "direction": "higher",
            "noise_band": 0.0,
            "predicted": {
                "metric": "confirmed_gate_count",
                "value": 5.5,
                "unit": "gates",
            },
            "kill_condition": prereg_request["kill_condition"],
            "prediction_receipt_sha256": prereg_response[
                "prediction_receipt_sha256"
            ],
        },
        "measurement": {
            "metric": "confirmed_gate_count",
            "value": confirmed_gate_count,
            "unit": "gates",
            "derived": {
                "b1_credit": b1_credit,
                "statistical_gate_count": statistical_gate_count,
                "B1": b1_detail,
                **gate_states,
                "analyzer_confirm_P1_through_P5": analysis["confirm"],
            },
        },
        "provenance": {
            "inputs": [
                {
                    "name": name,
                    "source": relative_source(path, root),
                    "sha256": sha256(path),
                }
                for name, path in inputs
            ],
            "data_manifest": relative_source(args.manifest, root),
            "grounded": True,
        },
        "harness": {
            "script": relative_source(args.script_path, root),
            "git_commit": git_commit,
            "env": (
                f"python={sys.version.split()[0]};"
                f"model={analysis['model_id']};"
                f"endpoint_class={analysis['endpoint_class']};"
                f"lean={analysis['lean_toolchain']}"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
    args.output.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
