from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from engine.efficacy.diagnostic_repair_analysis_errata import (
    ERRATUM_ID,
    ErratumError,
    build_p4_erratum,
    main,
)


def _analysis() -> dict[str, Any]:
    return {
        "schema": "pi-diagnostic-repair-harness/v2",
        "confirm": False,
        "thresholds": {"parity_low": 0.8, "parity_high": 1.25},
        "gates": {
            "P4": {
                "status": "ABSENT",
                "reasons": ["matched-token controls require >=6 non-ties"],
                "raw_ratios": {
                    "bestN": {
                        "model_calls": 0.95,
                        "oracle_calls": 0.95,
                        "total_tokens": 1.486902,
                    },
                    "plain_baseline": {
                        "model_calls": 0.763547,
                        "oracle_calls": 0.763547,
                        "total_tokens": 0.622249,
                    },
                },
            }
        },
    }


def _build(analysis: dict[str, Any]) -> dict[str, Any]:
    return build_p4_erratum(
        analysis,
        source_path="verification/source/analysis.json",
        source_sha256="a" * 64,
        generator_path="engine/efficacy/diagnostic_repair_analysis_errata.py",
        generator_sha256="b" * 64,
    )


def test_known_false_ratio_dominates_underpowered_matched_token_conjunct() -> None:
    erratum = _build(_analysis())

    assert erratum["erratum_id"] == ERRATUM_ID
    assert erratum["observation"]["original_status"] == "ABSENT"
    assert erratum["correction"]["status"] == "FAIL"
    assert erratum["correction"]["corrected_confirm"] is False
    assert erratum["correction"]["final_claim_changed"] is False
    failures = erratum["observation"]["ratio_failures"]
    assert [(row["baseline"], row["metric"]) for row in failures] == [
        ("bestN", "total_tokens"),
        ("plain_baseline", "model_calls"),
        ("plain_baseline", "oracle_calls"),
        ("plain_baseline", "total_tokens"),
    ]


def test_negative_control_refuses_to_invent_failure_when_all_ratios_are_in_bounds() -> None:
    analysis = _analysis()
    p4 = analysis["gates"]["P4"]
    for metrics in p4["raw_ratios"].values():
        for metric in metrics:
            metrics[metric] = 1.0

    with pytest.raises(ErratumError, match="no known raw-ratio violation"):
        _build(analysis)


@pytest.mark.parametrize("status", ["PASS", "FAIL"])
def test_refuses_to_rewrite_non_absent_historical_gate(status: str) -> None:
    analysis = _analysis()
    analysis["gates"]["P4"]["status"] = status

    with pytest.raises(ErratumError, match="requires historical P4=ABSENT"):
        _build(analysis)


def test_cli_binds_source_and_generator_hashes_without_rewriting_source(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    source = root / "verification" / "analysis.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps(_analysis()) + "\n")
    before = source.read_bytes()

    # The real generator lives outside this synthetic root, so use the repository
    # root for the CLI integration test and a temporary source beneath it.
    repo_root = Path(__file__).resolve().parents[3]
    repo_source = repo_root / ".pytest-erratum-source.json"
    repo_output = repo_root / ".pytest-erratum-output.json"
    try:
        repo_source.write_bytes(before)
        assert main([str(repo_source), "--root", str(repo_root), "--output", str(repo_output)]) == 0
        document = json.loads(repo_output.read_text())
        assert document["source"]["sha256"] == hashlib.sha256(before).hexdigest()
        assert (
            document["generator"]["sha256"]
            == hashlib.sha256((repo_root / document["generator"]["path"]).read_bytes()).hexdigest()
        )
        assert repo_source.read_bytes() == before
    finally:
        repo_source.unlink(missing_ok=True)
        repo_output.unlink(missing_ok=True)


def test_input_mutation_does_not_leak_into_output() -> None:
    analysis = _analysis()
    frozen = copy.deepcopy(analysis)
    _build(analysis)
    assert analysis == frozen
