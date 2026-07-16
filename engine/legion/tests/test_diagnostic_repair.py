from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from engine.legion.diagnostic_repair import (
    RepairStop,
    TextRepairGenerator,
    candidate_fingerprint,
    candidate_snapshot,
    diagnostic_repair,
)
from engine.naesengmoon.diagnostic_oracle import (
    CallableDiagnosticOracle,
    CommandDiagnosticOracle,
    feedback_from_value,
)


def _oracle(evaluator):
    return CallableDiagnosticOracle(name="deterministic", kind="test", evaluator=evaluator)


def _feedback(candidate: str, *, passed: bool, score: float, diagnostic: str):
    return feedback_from_value(
        lens="deterministic",
        kind="test",
        passed=passed,
        score=score,
        diagnostic=diagnostic,
    )


def test_diagnostic_is_injected_into_the_next_repair() -> None:
    seen: list[str] = []

    def evaluate(candidate: str):
        if candidate == "answer = 42":
            return _feedback(candidate, passed=True, score=1.0, diagnostic="PASS")
        return _feedback(
            candidate,
            passed=False,
            score=0.0,
            diagnostic="NameError: replace BROKEN with 42",
        )

    def repair(ctx):
        seen.append(ctx.missing)
        assert ctx.feedback is ctx.history[-1].feedback
        return ctx.current.replace("BROKEN", "42")

    result = diagnostic_repair("answer = BROKEN", repair, _oracle(evaluate))
    assert result.stop is RepairStop.COMPLETE
    assert result.verified is True
    assert result.output == "answer = 42"
    assert result.evaluations == 2
    assert seen == ["NameError: replace BROKEN with 42"]


def test_concrete_text_generator_closes_real_python_compile_loop() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.users: list[str] = []

        def complete(self, **kwargs):
            self.users.append(kwargs["user"])
            return SimpleNamespace(
                text="<<<PI_REPLACEMENT>>>\nanswer = 42\n<<<END_PI_REPLACEMENT>>>",
                input_tokens=100,
                output_tokens=10,
            )

    client = FakeClient()
    generator = TextRepairGenerator(client=client, model="fake-model", max_total_tokens=1_000)
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
    result = diagnostic_repair("answer = (", generator, oracle)
    assert result.verified is True
    assert result.output == "answer = 42"
    assert "SyntaxError" in client.users[0]
    assert "answer = (" in client.users[0]
    assert generator.used_tokens == 110


def test_text_generator_reported_token_cap_fails_closed() -> None:
    class ExpensiveClient:
        def __init__(self) -> None:
            self.requested: list[int] = []

        def complete(self, **kwargs):
            self.requested.append(kwargs["max_tokens"])
            return SimpleNamespace(
                text="<<<PI_REPLACEMENT>>>\nfixed\n<<<END_PI_REPLACEMENT>>>",
                input_tokens=10,
                output_tokens=10,
            )

    def evaluate(candidate: str):
        return _feedback(candidate, passed=False, score=0.0, diagnostic="red")

    client = ExpensiveClient()
    generator = TextRepairGenerator(
        client=client,
        model="fake-model",
        max_total_tokens=5,
    )
    result = diagnostic_repair("seed", generator, _oracle(evaluate))
    assert result.stop is RepairStop.CAPPED
    assert "token cap exceeded" in result.stop_detail
    assert result.output == "seed"
    assert client.requested == [5]
    assert result.reported_input_tokens == 10
    assert result.reported_output_tokens == 10


def test_reported_token_receipt_is_per_run_when_generator_is_reused() -> None:
    class ReusedClient:
        def complete(self, **_kwargs):
            return SimpleNamespace(
                text="<<<PI_REPLACEMENT>>>\nfixed\n<<<END_PI_REPLACEMENT>>>",
                input_tokens=7,
                output_tokens=3,
            )

    generator = TextRepairGenerator(client=ReusedClient(), model="fake", max_total_tokens=100)

    def evaluate(candidate: str):
        passed = candidate == "fixed"
        return _feedback(
            candidate,
            passed=passed,
            score=float(passed),
            diagnostic="PASS" if passed else "red",
        )

    first = diagnostic_repair("broken", generator, _oracle(evaluate))
    second = diagnostic_repair("fixed", generator, _oracle(evaluate))
    assert (first.reported_input_tokens, first.reported_output_tokens) == (7, 3)
    assert second.repairs == 0
    assert (second.reported_input_tokens, second.reported_output_tokens) == (0, 0)


def test_distinct_flat_score_failures_can_progress_to_green() -> None:
    """Binary scores stay flat while diagnostics move; scalar plateau must not stop repair."""

    def evaluate(candidate: str):
        if candidate == "c":
            return _feedback(candidate, passed=True, score=1.0, diagnostic="PASS")
        return _feedback(
            candidate, passed=False, score=0.0, diagnostic=f"missing after {candidate}"
        )

    def repair(ctx):
        return {"a": "b", "b": "c"}[ctx.current]

    result = diagnostic_repair("a", repair, _oracle(evaluate), max_attempts=2)
    assert result.verified is True
    assert [a.candidate for a in result.attempts] == ["a", "b", "c"]
    assert [a.feedback.score for a in result.attempts] == [0.0, 0.0, 1.0]


def test_repeated_candidate_and_diagnostic_stops_as_stuck() -> None:
    def evaluate(candidate: str):
        return _feedback(candidate, passed=False, score=0.0, diagnostic="same failure")

    result = diagnostic_repair(
        "unchanged",
        lambda ctx: ctx.current,
        _oracle(evaluate),
        max_attempts=10,
        max_repeated_states=1,
    )
    assert result.stop is RepairStop.STUCK
    assert result.repairs == 1
    assert result.evaluations == 2


def test_best_candidate_is_retained_after_later_regression() -> None:
    scores = {"seed": 0.5, "better": 0.8, "worse": 0.1}

    def evaluate(candidate: str):
        return _feedback(
            candidate,
            passed=False,
            score=scores[candidate],
            diagnostic=f"still failing at {candidate}",
        )

    def repair(ctx):
        return "better" if ctx.attempt == 1 else "worse"

    result = diagnostic_repair("seed", repair, _oracle(evaluate), max_attempts=2)
    assert result.stop is RepairStop.CAPPED
    assert result.current.candidate == "worse"
    assert result.output == "better"
    assert result.improved is True


def test_oracle_evaluation_cap_includes_seed() -> None:
    def evaluate(candidate: str):
        return _feedback(candidate, passed=False, score=0.0, diagnostic=candidate)

    result = diagnostic_repair(
        "seed",
        lambda ctx: f"candidate-{ctx.attempt}",
        _oracle(evaluate),
        max_attempts=10,
        max_evaluations=2,
    )
    assert result.stop is RepairStop.CAPPED
    assert result.evaluations == 2
    assert result.repairs == 1
    assert "evaluation cap" in result.stop_detail


def test_generator_error_is_a_typed_terminal_state() -> None:
    def evaluate(candidate: str):
        return _feedback(candidate, passed=False, score=0.0, diagnostic="red")

    def broken(_ctx):
        raise RuntimeError("model backend unavailable")

    result = diagnostic_repair("seed", broken, _oracle(evaluate))
    assert result.stop is RepairStop.GENERATOR_ERROR
    assert "model backend unavailable" in result.stop_detail
    assert result.output == "seed"


def test_oracle_exception_fails_closed() -> None:
    def broken_oracle(_candidate):
        raise RuntimeError("verifier crashed")

    result = diagnostic_repair("seed", lambda _ctx: "fix", _oracle(broken_oracle))
    assert result.stop is RepairStop.ORACLE_ERROR
    assert result.verified is False
    assert result.seed.feedback.status == "error"
    assert "verifier crashed" in result.stop_detail


def test_loop_defends_against_post_construction_feedback_corruption() -> None:
    bad = _feedback("seed", passed=False, score=0.0, diagnostic="red")
    object.__setattr__(bad, "passed", True)  # simulate a hostile Protocol implementation
    result = diagnostic_repair(
        "seed",
        lambda _ctx: None,
        _oracle(lambda _candidate: bad),
        max_attempts=0,
    )
    assert result.verified is False
    assert result.stop is RepairStop.ORACLE_ERROR


def test_append_only_events_and_receipt_are_json_safe() -> None:
    emitted = []

    def evaluate(candidate: str):
        return _feedback(
            candidate,
            passed=candidate == "fixed",
            score=float(candidate == "fixed"),
            diagnostic="PASS" if candidate == "fixed" else "fix it",
        )

    result = diagnostic_repair(
        "broken",
        lambda _ctx: "fixed",
        _oracle(evaluate),
        event_sink=emitted.append,
    )
    assert [event.sequence for event in emitted] == list(range(len(emitted)))
    assert {event.run_id for event in emitted} == {result.run_id}
    assert tuple(emitted) == result.events
    assert emitted[-1].kind == "stopped"
    encoded = json.dumps(result.receipt(), allow_nan=False)
    assert '"stop": "complete"' in encoded
    assert "candidate" not in result.receipt()["attempts"][0]
    assert "diagnostic" not in result.receipt()["attempts"][0]["feedback"]
    assert "command" not in result.receipt()["attempts"][0]["feedback"]
    private = result.receipt(include_diagnostics=True)
    assert private["attempts"][0]["feedback"]["diagnostic"] == "fix it"


def test_each_run_has_distinct_durable_event_identity() -> None:
    def evaluate(candidate: str):
        return _feedback(candidate, passed=True, score=1.0, diagnostic="PASS")

    first = diagnostic_repair("green", lambda _ctx: "unused", _oracle(evaluate))
    second = diagnostic_repair("green", lambda _ctx: "unused", _oracle(evaluate))
    assert first.run_id != second.run_id
    assert (first.events[0].run_id, first.events[0].sequence) != (
        second.events[0].run_id,
        second.events[0].sequence,
    )


def test_green_seed_is_verified_but_not_improved() -> None:
    def evaluate(candidate: str):
        return _feedback(candidate, passed=True, score=1.0, diagnostic="PASS")

    result = diagnostic_repair("already green", lambda _ctx: "unused", _oracle(evaluate))
    assert result.verified is True
    assert result.improved is False
    assert result.repairs == 0


def test_mutable_candidate_is_snapshotted_before_generator_mutation() -> None:
    seed = {"value": 1}

    def evaluate(candidate: dict[str, int]):
        return feedback_from_value(
            lens="score",
            kind="test",
            passed=False,
            score=float(candidate["value"]),
            diagnostic="still red",
        )

    def mutate(ctx):
        ctx.current["value"] = 0
        return ctx.current

    result = diagnostic_repair(seed, mutate, _oracle(evaluate), max_attempts=1)
    assert seed == {"value": 1}
    assert result.seed.candidate == {"value": 1}
    assert result.current.candidate == {"value": 0}
    assert result.output == {"value": 1}
    assert result.improved is False


def test_default_receipt_redacts_terminal_error_detail() -> None:
    def broken(_candidate):
        raise RuntimeError("TOP_SECRET_ORACLE_DETAIL")

    result = diagnostic_repair("seed", lambda _ctx: "unused", _oracle(broken))
    assert "TOP_SECRET" not in json.dumps(result.receipt())
    assert "TOP_SECRET" in result.receipt(include_diagnostics=True)["stop_detail"]


def test_directory_candidate_requires_explicit_workspace_digest(tmp_path) -> None:
    with pytest.raises(ValueError, match="explicit snapshot"):
        candidate_fingerprint(tmp_path)


def test_nested_filesystem_candidate_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="filesystem references"):
        candidate_snapshot({"path": tmp_path / "candidate.py"})


def test_custom_deepcopy_hooks_cannot_bypass_default_snapshot() -> None:
    class AliasingCandidate:
        def __deepcopy__(self, _memo):
            return self

    with pytest.raises(ValueError, match="explicit snapshot"):
        candidate_snapshot(AliasingCandidate())


def test_invalid_generated_candidate_has_typed_terminal_result(tmp_path) -> None:
    def evaluate(candidate: str):
        return _feedback(candidate, passed=False, score=0.0, diagnostic="red")

    result = diagnostic_repair(
        "seed",
        lambda _ctx: tmp_path / "candidate.py",
        _oracle(evaluate),
    )
    assert result.stop is RepairStop.GENERATOR_ERROR
    assert result.repairs == 1
    assert result.output == "seed"
    assert result.events[-2].kind == "generator_error"
    assert result.events[-1].kind == "stopped"


@pytest.mark.parametrize("wall", [float("nan"), float("inf"), -float("inf")])
def test_wall_time_cap_must_be_finite(wall: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        diagnostic_repair(
            "seed",
            lambda _ctx: "unused",
            _oracle(
                lambda candidate: _feedback(candidate, passed=False, score=0.0, diagnostic="red")
            ),
            max_wall_seconds=wall,
        )


def test_seed_only_run_is_explicitly_capped() -> None:
    def evaluate(candidate: str):
        return _feedback(candidate, passed=False, score=0.0, diagnostic="red")

    result = diagnostic_repair("seed", lambda _ctx: "unused", _oracle(evaluate), max_attempts=0)
    assert result.stop is RepairStop.CAPPED
    assert result.evaluations == 1
    assert result.repairs == 0
