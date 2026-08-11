"""Executable evaluator seam: exact binding, fail-closed downgrade, real JSON process."""

from __future__ import annotations

import hashlib
import subprocess
import sys

import pytest
from pydantic import ValidationError

from engine.eureka.evaluation import (
    CheckResult,
    CommandEvaluator,
    EvaluationRequest,
    EvaluationResult,
    EvaluationVerdict,
    EvaluatorReceipt,
    execute_evaluation,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _request(*checks: str) -> EvaluationRequest:
    return EvaluationRequest(
        candidate_digest=_sha("candidate"),
        input_snapshot_hash=_sha("input"),
        baseline_snapshot_hash=_sha("baseline"),
        critic_receipt_digest=_sha("critic"),
        requested_checks=checks or ("compile", "unit"),
    )


def _check(name: str, passed: bool = True) -> CheckResult:
    return CheckResult(
        check_id=name,
        passed=passed,
        evidence_digest=_sha(f"evidence:{name}:{passed}"),
        summary=f"{name} {'passed' if passed else 'failed'}",
    )


class _StaticEvaluator:
    evaluator_type = "test-oracle"
    evaluator_version = "1.0.0"
    environment_digest = _sha("test-environment")

    def __init__(self, result: EvaluationResult) -> None:
        self.result = result

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        return self.result


def test_receipt_exactly_binds_request_and_has_stable_content_digest():
    request = _request("compile", "unit")
    result = EvaluationResult(
        verdict=EvaluationVerdict.PASS,
        checks=(_check("compile"), _check("unit")),
        objective_vector={"fidelity": 1.0, "coverage": 1.0},
        artifact_digests=(_sha("test-report"),),
    )

    first = execute_evaluation(request, _StaticEvaluator(result))
    second = execute_evaluation(request, _StaticEvaluator(result))

    assert first.verdict is EvaluationVerdict.PASS
    assert first.passed is True
    assert first.request_digest == request.request_digest
    assert first.candidate_digest == request.candidate_digest
    assert first.input_snapshot_hash == request.input_snapshot_hash
    assert first.baseline_snapshot_hash == request.baseline_snapshot_hash
    assert first.critic_receipt_digest == request.critic_receipt_digest
    assert first.requested_checks == ("compile", "unit")
    assert first.executed_checks == ("compile", "unit")
    assert first.receipt_digest == second.receipt_digest

    tampered = first.model_dump(mode="json") | {"candidate_digest": _sha("other")}
    with pytest.raises(ValidationError, match="request_digest"):
        EvaluatorReceipt.model_validate(tampered)


def test_reported_pass_with_missing_requested_check_downgrades_to_inconclusive():
    receipt = execute_evaluation(
        _request("compile", "unit"),
        _StaticEvaluator(
            EvaluationResult(
                verdict=EvaluationVerdict.PASS,
                checks=(_check("compile"),),
            )
        ),
    )

    assert receipt.verdict is EvaluationVerdict.INCONCLUSIVE
    assert receipt.passed is False
    assert receipt.executed_checks == ("compile",)
    assert receipt.missing_checks == ("unit",)


def test_reported_pass_with_failed_requested_check_downgrades_to_fail():
    receipt = execute_evaluation(
        _request("compile", "unit"),
        _StaticEvaluator(
            EvaluationResult(
                verdict=EvaluationVerdict.PASS,
                checks=(_check("compile"), _check("unit", passed=False)),
            )
        ),
    )

    assert receipt.verdict is EvaluationVerdict.FAIL
    assert receipt.passed is False


def test_exception_and_subprocess_timeout_become_error_receipts():
    class _BrokenEvaluator:
        evaluator_type = "broken"
        evaluator_version = "1"
        environment_digest = _sha("broken-env")

        def evaluate(self, request):
            raise RuntimeError("boom")

    exception_receipt = execute_evaluation(_request("compile"), _BrokenEvaluator())
    assert exception_receipt.verdict is EvaluationVerdict.ERROR
    assert exception_receipt.error_type == "RuntimeError"
    assert exception_receipt.error_digest

    timeout_evaluator = CommandEvaluator(
        command=(sys.executable, "-c", "import time; time.sleep(1)"),
        evaluator_version="1",
        environment_digest=_sha("timeout-env"),
        timeout_seconds=0.02,
    )
    timeout_receipt = execute_evaluation(_request("compile"), timeout_evaluator)
    assert timeout_receipt.verdict is EvaluationVerdict.ERROR
    assert timeout_receipt.error_type == subprocess.TimeoutExpired.__name__
    assert timeout_receipt.executed_checks == ()


def test_command_evaluator_round_trips_json_over_stdin_stdout_without_shell():
    script = r"""
import hashlib
import json
import sys

request = json.load(sys.stdin)
checks = []
for check_id in request["requested_checks"]:
    checks.append({
        "check_id": check_id,
        "passed": True,
        "evidence_digest": hashlib.sha256(("subprocess:" + check_id).encode()).hexdigest(),
        "summary": "executed in child process",
        "details": {"candidate_digest": request["candidate_digest"]},
    })
json.dump({
    "verdict": "PASS",
    "checks": checks,
    "objective_vector": {"executed_fraction": 1.0},
    "counterexamples": [],
    "artifact_digests": [hashlib.sha256(b"child-report").hexdigest()],
    "cost": {"tool_calls": 1},
    "contamination": {"network_accessed": False},
    "nondeterminism": {"deterministic": True, "replayable": True},
}, sys.stdout)
"""
    evaluator = CommandEvaluator(
        command=(sys.executable, "-c", script),
        evaluator_version="1.2.3",
        environment_digest=_sha("json-child-environment"),
        timeout_seconds=2.0,
    )

    receipt = execute_evaluation(_request("compile", "unit"), evaluator)

    assert receipt.verdict is EvaluationVerdict.PASS
    assert receipt.evaluator_type == "command"
    assert receipt.evaluator_version == "1.2.3"
    assert receipt.executed_checks == ("compile", "unit")
    assert receipt.objective_vector == {"executed_fraction": 1.0}
    assert receipt.cost.tool_calls == 1
    assert receipt.checks[0].details["candidate_digest"] == receipt.candidate_digest


def test_command_evaluator_rejects_shell_string():
    with pytest.raises(ValueError, match="not a shell string"):
        CommandEvaluator(
            command="echo unsafe",  # type: ignore[arg-type]
            evaluator_version="1",
            environment_digest=_sha("environment"),
        )
