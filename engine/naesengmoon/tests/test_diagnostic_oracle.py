from __future__ import annotations

import os
import sys
import time
from dataclasses import replace

import pytest

from engine.naesengmoon.diagnostic_oracle import (
    CommandDiagnosticOracle,
    feedback_from_value,
)


def test_command_oracle_returns_typed_pass_and_failure() -> None:
    passing = CommandDiagnosticOracle(
        name="python",
        kind="test",
        command=(sys.executable, "-c", "print('green')"),
        allow_host_execution=True,
    ).evaluate(None)
    assert passing.passed is True
    assert passing.status == "passed"
    assert passing.valid is True
    assert passing.exit_code == 0
    assert passing.score == 1.0
    assert passing.command[0] == sys.executable

    oracle = CommandDiagnosticOracle(
        name="python",
        kind="test",
        command=(sys.executable, "-c", "import sys; print('expected 42'); sys.exit(3)"),
        allow_host_execution=True,
    )
    failed = oracle.evaluate(None)
    repeated = oracle.evaluate(None)
    assert failed.passed is False
    assert failed.status == "failed"
    assert failed.valid is True
    assert failed.exit_code == 3
    assert "expected 42" in failed.missing
    assert failed.fingerprint == repeated.fingerprint


def test_host_execution_is_fail_closed_by_default(tmp_path) -> None:
    marker = tmp_path / "must-not-run"
    oracle = CommandDiagnosticOracle(
        name="disabled",
        kind="test",
        command=(sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"),
    )
    feedback = oracle.evaluate(None)
    assert feedback.status == "error"
    assert "host execution disabled" in feedback.diagnostic
    assert not marker.exists()


@pytest.mark.parametrize("field", ["allow_host_execution", "inherit_env"])
def test_security_switches_require_exact_booleans(field: str) -> None:
    kwargs = {field: "false"}
    with pytest.raises(TypeError, match=field):
        CommandDiagnosticOracle(  # type: ignore[arg-type]
            name="invalid-bool",
            kind="test",
            command=(sys.executable, "-c", "pass"),
            **kwargs,
        )


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), -float("inf")])
def test_timeout_must_be_finite(timeout: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        CommandDiagnosticOracle(
            name="invalid-timeout",
            kind="test",
            command=(sys.executable, "-c", "pass"),
            timeout_s=timeout,
        )


def test_default_environment_does_not_inherit_secrets(monkeypatch) -> None:
    monkeypatch.setenv("PI_TEST_SECRET", "must-not-cross")
    feedback = CommandDiagnosticOracle(
        name="scrubbed-env",
        kind="test",
        command=(
            sys.executable,
            "-c",
            "import os; print(os.environ.get('PI_TEST_SECRET', 'ABSENT'))",
        ),
        allow_host_execution=True,
    ).evaluate(None)
    assert feedback.status == "passed"
    assert feedback.diagnostic.strip() == "ABSENT"


def test_candidate_aware_cwd_and_score_parser(tmp_path) -> None:
    (tmp_path / "value.txt").write_text("3 passed, 1 failed\n")

    def score(_code: int, output: str) -> float:
        return 0.75 if "3 passed" in output else 0.0

    oracle = CommandDiagnosticOracle(
        name="ratio",
        kind="pytest-ratio",
        command=(
            sys.executable,
            "-c",
            "from pathlib import Path; print(Path('value.txt').read_text())",
        ),
        cwd=lambda candidate: candidate,
        score_fn=score,
        allow_host_execution=True,
    )
    feedback = oracle.evaluate(tmp_path)
    assert feedback.passed is True
    assert feedback.score == 0.75
    assert "3 passed" in feedback.diagnostic


def test_candidate_can_be_verified_through_stdin_without_workspace_mutation() -> None:
    oracle = CommandDiagnosticOracle(
        name="py-compile",
        kind="compiler",
        command=(
            sys.executable,
            "-c",
            "import sys; compile(sys.stdin.read(), '<candidate>', 'exec')",
        ),
        stdin=lambda candidate: candidate,
        allow_host_execution=True,
    )
    failed = oracle.evaluate("answer = (")
    passed = oracle.evaluate("answer = 42")
    assert failed.status == "failed"
    assert "SyntaxError" in failed.diagnostic
    assert passed.passed is True


def test_timeout_is_bounded_repairable_feedback() -> None:
    oracle = CommandDiagnosticOracle(
        name="slow",
        kind="test",
        command=(sys.executable, "-c", "import time; print('started', flush=True); time.sleep(1)"),
        timeout_s=0.02,
        allow_host_execution=True,
    )
    feedback = oracle.evaluate(None)
    assert feedback.status == "timeout"
    assert feedback.timed_out is True
    assert feedback.passed is False
    assert feedback.terminal_error is False
    assert "timeout" in feedback.diagnostic


@pytest.mark.skipif(os.name != "posix", reason="process-group timeout contract is POSIX-specific")
def test_timeout_kills_verifier_child_process_group(tmp_path) -> None:
    marker = tmp_path / "orphan-wrote.txt"
    child = (
        "import time; from pathlib import Path; "
        f"time.sleep(0.25); Path({str(marker)!r}).write_text('orphan')"
    )
    parent = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(10)"
    )
    feedback = CommandDiagnosticOracle(
        name="process-tree",
        kind="test",
        command=(sys.executable, "-c", parent),
        timeout_s=0.03,
        allow_host_execution=True,
    ).evaluate(None)
    time.sleep(0.35)
    assert feedback.status == "timeout"
    assert not marker.exists(), "timed-out verifier left a child process running"


def test_unavailable_command_is_terminal_oracle_error() -> None:
    feedback = CommandDiagnosticOracle(
        name="missing",
        kind="compiler",
        command=("definitely-no-such-pi-command-20260716",),
        allow_host_execution=True,
    ).evaluate(None)
    assert feedback.status == "unavailable"
    assert feedback.terminal_error is True
    assert feedback.passed is False


def test_output_is_head_tail_capped() -> None:
    oracle = CommandDiagnosticOracle(
        name="chatty",
        kind="test",
        command=(sys.executable, "-c", "print('A' * 1000 + 'Z' * 1000)"),
        output_limit=256,
        allow_host_execution=True,
    )
    feedback = oracle.evaluate(None)
    assert feedback.status == "output_limit"
    assert len(feedback.diagnostic) <= 256
    assert "\nA" in feedback.diagnostic
    assert feedback.diagnostic.rstrip().endswith("Z")
    assert "truncated" in feedback.diagnostic


def test_shell_string_is_rejected() -> None:
    with pytest.raises(TypeError, match="argv"):
        CommandDiagnosticOracle(name="unsafe", kind="test", command="pytest -q")  # type: ignore[arg-type]

    oracle = CommandDiagnosticOracle(
        name="unsafe-factory",
        kind="test",
        command=lambda _candidate: "pytest -q",  # type: ignore[return-value]
        allow_host_execution=True,
    )
    assert oracle.evaluate(None).status == "error"


def test_non_subprocess_feedback_exposes_missing() -> None:
    feedback = feedback_from_value(
        lens="lean",
        kind="proof",
        passed=False,
        score=0.5,
        diagnostic="unsolved goal: P",
    )
    assert feedback.status == "failed"
    assert feedback.missing == "unsolved goal: P"
    assert feedback.as_dict()["fingerprint"] == feedback.fingerprint


def test_non_finite_scores_fail_closed() -> None:
    oracle = CommandDiagnosticOracle(
        name="nan-score",
        kind="test",
        command=(sys.executable, "-c", "pass"),
        score_fn=lambda _code, _output: float("nan"),
        allow_host_execution=True,
    )
    assert oracle.evaluate(None).status == "error"
    with pytest.raises(ValueError, match="finite"):
        feedback_from_value(
            lens="nan",
            kind="test",
            passed=False,
            score=float("inf"),
            diagnostic="bad score",
        )


@pytest.mark.parametrize("status", ["failed", "timeout", "error", "nonsense"])
def test_passed_status_invariant_blocks_false_success(status: str) -> None:
    with pytest.raises(ValueError, match="passed|status"):
        feedback_from_value(
            lens="inconsistent",
            kind="test",
            passed=True,
            score=1.0,
            diagnostic="not actually green",
            status=status,
        )


def test_direct_feedback_constructor_rechecks_finite_score() -> None:
    valid = feedback_from_value(
        lens="valid",
        kind="test",
        passed=False,
        score=0.0,
        diagnostic="red",
    )
    with pytest.raises(ValueError, match="finite"):
        replace(valid, score=float("nan"))


def test_stdin_adapter_failure_happens_before_process_spawn(tmp_path) -> None:
    marker = tmp_path / "must-not-outlive-adapter"

    def broken_stdin(_candidate):
        raise RuntimeError("stdin adapter failed")

    oracle = CommandDiagnosticOracle(
        name="stdin-error",
        kind="test",
        command=(
            sys.executable,
            "-c",
            f"import time; from pathlib import Path; time.sleep(.1); Path({str(marker)!r}).touch()",
        ),
        stdin=broken_stdin,
        allow_host_execution=True,
    )
    assert oracle.evaluate("candidate").status == "error"
    time.sleep(0.15)
    assert not marker.exists()
