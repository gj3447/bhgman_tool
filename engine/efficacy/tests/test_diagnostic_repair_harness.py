from __future__ import annotations

import io
import json
from collections.abc import Iterable
from types import SimpleNamespace
from typing import Any

from engine.efficacy import diagnostic_repair_harness as harness
from engine.efficacy import lean_oracle
from engine.efficacy.lean_tasks import TASKS
from engine.legion import diagnostic_repair as repair_module

ARTIFACT_KEYS = (
    "runner",
    "analyzer",
    "diagnostic_repair",
    "diagnostic_oracle",
    "lean_headroom_run",
    "lean_tasks",
    "lean_oracle",
    "agent_client",
    "agent_runtime",
    "lean_sandbox_runner_macos",
    "lean_toolchain",
    "loop_contract",
    "fsm",
    "fsm_traces",
    "manifest",
    "preregistration_v3",
)


def claim_run_metadata() -> dict[str, Any]:
    return {
        "model_id": "qwen2.5:32b-instruct",
        "endpoint_class": "openai-compatible",
        "endpoint_fingerprint": "d" * 64,
        "temperature": 0.8,
        "max_tokens_per_attempt": 3072,
        "oracle_isolation": "external-sandbox-runner/v2",
        "sandbox_runner_sha256": "e" * 64,
        "lean_toolchain": "leanprover/lean4:v4.27.0",
        "lean_version": (
            "Lean (version 4.27.0, arm64-apple-darwin24.6.0, "
            "commit db93fe1608548721853390a10cd40580fe7d22ae, Release)"
        ),
        "lean_binary_sha256": "f" * 64,
        "timestamp_utc": "2026-07-16T00:00:00+00:00",
    }


class Verdict:
    def __init__(
        self,
        *,
        proven: bool,
        diagnostic: str = "",
        graded: float | None = None,
    ) -> None:
        self.compiles = proven
        self.proven = proven
        self.sorry_tainted = False
        self.error_tail = diagnostic
        self.graded_score = 1.0 if proven else (0.0 if graded is None else graded)


class ScriptedComplete:
    def __init__(
        self,
        outputs: Iterable[str],
        *,
        response_model: str = "injected-test-model",
        model_observed: bool = True,
    ) -> None:
        self.outputs = iter(outputs)
        self.calls: list[dict[str, Any]] = []
        self.last_usage = (0, 0)
        self.last_response_model = response_model
        self.last_response_model_observed = model_observed

    def __call__(self, messages: list[dict[str, str]], seed: int) -> str:
        self.calls.append({"messages": messages, "seed": seed})
        self.last_usage = (10 + seed, 3)
        return next(self.outputs)


def scripted_complete(outputs: Iterable[str]) -> tuple[ScriptedComplete, list[dict[str, Any]]]:
    complete = ScriptedComplete(outputs)
    return complete, complete.calls


def records(log: io.StringIO, kind: str) -> list[dict[str, Any]]:
    return [
        item
        for item in (json.loads(line) for line in log.getvalue().splitlines())
        if item["record_type"] == kind
    ]


def test_legacy_and_pi_repair_have_equivalent_generation_and_oracle_traces(
    monkeypatch,
) -> None:
    task = TASKS[2]

    def evaluate(
        name: str,
        signature: str,
        proof: str,
        *,
        preamble: str = "",
    ) -> Verdict:
        del name, signature, preamble
        return (
            Verdict(proven=True)
            if proof == "GOOD"
            else Verdict(proven=False, diagnostic=f"REAL:{proof}")
        )

    legacy_complete, legacy_calls = scripted_complete(["P0", "P1", "GOOD"])
    pi_complete, pi_calls = scripted_complete(["P0", "P1", "GOOD"])
    meta = harness.RunMeta("trace-run", "fake", 3, 7)
    legacy_log = io.StringIO()
    pi_log = io.StringIO()

    legacy_outcome = harness._run_legacy_repair(meta, task, legacy_complete, evaluate, legacy_log)

    called: dict[str, Any] = {}
    original = repair_module.diagnostic_repair

    def spy(*args: Any, **kwargs: Any):
        called.update(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(harness, "diagnostic_repair", spy)
    pi_outcome = harness._run_pi_repair(
        meta,
        task,
        pi_complete,
        evaluate,
        pi_log,
        decoy=False,
        tasks=(task, TASKS[3]),
    )

    assert called["max_attempts"] == 2
    assert called["max_evaluations"] == 3
    assert legacy_outcome.proven is True
    assert pi_outcome.proven is True
    assert [call["seed"] for call in legacy_calls] == [7, 8, 9]
    assert [call["seed"] for call in pi_calls] == [7, 8, 9]
    assert [call["messages"] for call in legacy_calls] == [call["messages"] for call in pi_calls]

    fields = (
        "attempt",
        "seed",
        "used_feedback",
        "feedback_source",
        "proven",
        "graded_score",
        "proof_sha256",
        "diagnostic_sha256",
        "supplied_feedback_sha256",
        "prior_proof_sha256",
        "input_tokens",
        "output_tokens",
        "model_calls",
        "oracle_calls",
    )
    legacy_trace = [
        tuple(item[field] for field in fields) for item in records(legacy_log, "attempt")
    ]
    pi_trace = [tuple(item[field] for field in fields) for item in records(pi_log, "attempt")]
    assert pi_trace == legacy_trace
    pi_stop = records(pi_log, "pi_stop")
    assert len(pi_stop) == 1
    assert pi_stop[0]["stop"] == "complete"
    assert pi_stop[0]["evaluations"] == 3
    assert pi_stop[0]["repairs"] == 2


def test_unsafe_model_payload_is_a_failed_attempt_in_direct_and_pi_loops() -> None:
    task = TASKS[2]
    other = TASKS[3]
    meta = harness.RunMeta("unsafe-run", "fake", 2, 0)

    evaluator_calls: list[str] = []

    def evaluate_setup_only(
        name: str,
        signature: str,
        proof: str,
        *,
        preamble: str = "",
    ) -> Verdict:
        del name, signature, preamble
        evaluator_calls.append(proof)
        return Verdict(proven=False, diagnostic="trusted setup failure")

    unsafe = "by\n  trivial\n#check Nat"
    plain_complete = ScriptedComplete([unsafe, unsafe])
    pi_complete = ScriptedComplete([unsafe, unsafe])
    plain_log = io.StringIO()
    pi_log = io.StringIO()

    plain = harness._run_plain_baseline(
        meta,
        task,
        plain_complete,
        evaluate_setup_only,
        plain_log,
    )
    pi = harness._run_pi_repair(
        meta,
        task,
        pi_complete,
        evaluate_setup_only,
        pi_log,
        decoy=False,
        tasks=(task, other),
    )

    assert plain.proven is False
    assert pi.proven is False
    assert len(plain.attempts) == len(pi.attempts) == 2
    assert all(
        item["diagnostic"] == lean_oracle.UNSAFE_PAYLOAD_DIAGNOSTIC
        for item in plain.attempts
    )
    assert all(
        item["diagnostic"] == lean_oracle.UNSAFE_PAYLOAD_DIAGNOSTIC
        for item in pi.attempts
    )
    assert records(pi_log, "pi_stop")[0]["stop"] == "capped"
    assert evaluator_calls == []


def test_unsafe_first_candidate_preserves_legacy_pi_bridge_trace() -> None:
    task = TASKS[2]
    unsafe = "by\n  trivial\n#check Nat"

    def evaluator_must_not_run(*args: Any, **kwargs: Any) -> Verdict:
        del args, kwargs
        raise AssertionError("unsafe generated candidates must be rejected before the evaluator")

    legacy_complete = ScriptedComplete([unsafe, unsafe])
    pi_complete = ScriptedComplete([unsafe, unsafe])
    meta = harness.RunMeta("unsafe-bridge", "fake", 2, 7)
    legacy_log = io.StringIO()
    pi_log = io.StringIO()

    legacy = harness._run_legacy_repair(
        meta,
        task,
        legacy_complete,
        evaluator_must_not_run,
        legacy_log,
    )
    pi = harness._run_pi_repair(
        meta,
        task,
        pi_complete,
        evaluator_must_not_run,
        pi_log,
        decoy=False,
        tasks=(task, TASKS[3]),
    )

    fields = (
        "attempt",
        "seed",
        "used_feedback",
        "feedback_source",
        "proven",
        "graded_score",
        "proof_sha256",
        "diagnostic_sha256",
        "supplied_feedback_sha256",
        "prior_proof_sha256",
        "input_tokens",
        "output_tokens",
        "model_calls",
        "oracle_calls",
    )
    legacy_trace = [
        tuple(item[field] for field in fields) for item in records(legacy_log, "attempt")
    ]
    pi_trace = [tuple(item[field] for field in fields) for item in records(pi_log, "attempt")]
    assert legacy.proven is pi.proven is False
    assert legacy_trace == pi_trace
    assert records(pi_log, "pi_stop")[0]["stop"] == "capped"


def test_all_six_arms_record_unsafe_candidates_without_aborting() -> None:
    tasks = (TASKS[2], TASKS[3])
    unsafe = "by\n  trivial\n#check Nat"
    complete = ScriptedComplete([unsafe] * 22)
    evaluator_calls: list[str] = []

    def evaluate_setup(
        name: str,
        signature: str,
        proof: str,
        *,
        preamble: str = "",
    ) -> Verdict:
        del name, signature, preamble
        evaluator_calls.append(proof)
        return Verdict(proven=False, diagnostic="trusted decoy setup failure")

    metadata = {**claim_run_metadata(), "model_id": "injected-test-model"}
    log = io.StringIO()
    summary = harness.run_once(
        complete,
        "frontier:injected-test-model",
        k=2,
        seed_offset=0,
        log=log,
        run_id="unsafe-six-arm",
        tasks=tasks,
        evaluate_fn=evaluate_setup,
        include_payloads=True,
        git_provenance={
            "git_commit": "a" * 40,
            "git_dirty": False,
            "git_status_sha256": "0" * 64,
        },
        run_metadata=metadata,
    )

    attempts = records(log, "attempt")
    assert len(attempts) == 22
    assert {
        arm: sum(item["arm"] == arm for item in attempts)
        for arm in harness.ARMS
    } == {
        "single": 2,
        "bestN": 4,
        "legacy_repair": 4,
        "pi_repair": 4,
        "pi_decoy": 4,
        "plain_baseline": 4,
    }
    assert all(
        item["diagnostic"] == lean_oracle.UNSAFE_PAYLOAD_DIAGNOSTIC
        for item in attempts
    )
    assert all(
        item["model_calls"] == item["oracle_calls"] == 1
        and item["input_tokens"] > 0
        and item["output_tokens"] > 0
        for item in attempts
    )
    assert len(evaluator_calls) == len(tasks)
    assert all(item["stop"] == "capped" for item in records(log, "pi_stop"))
    assert all(item["kind"] != "oracle_error" for item in records(log, "pi_event"))
    assert summary["all"]["of"] == len(tasks)


def test_pi_decoy_uses_wrong_diagnostic_but_real_oracle_acceptance() -> None:
    task = TASKS[2]
    other = TASKS[3]
    evaluator_calls: list[str] = []

    def evaluate(
        name: str,
        signature: str,
        proof: str,
        *,
        preamble: str = "",
    ) -> Verdict:
        del name, signature, preamble
        evaluator_calls.append(proof)
        if proof == other.reference_proof:
            return Verdict(proven=False, diagnostic="WRONG_TASK_DIAGNOSTIC")
        if proof == "GOOD":
            return Verdict(proven=True)
        return Verdict(proven=False, diagnostic=f"REAL_DIAGNOSTIC:{proof}")

    complete, calls = scripted_complete(["BAD", "GOOD", "UNREACHED"])
    log = io.StringIO()
    outcome = harness._run_pi_repair(
        harness.RunMeta("decoy-run", "fake", 3, 0),
        task,
        complete,
        evaluate,
        log,
        decoy=True,
        tasks=(task, other),
    )

    assert outcome.proven is True
    assert outcome.setup_oracle_calls == 1
    assert evaluator_calls == [other.reference_proof, "BAD", "GOOD"]
    first_user = calls[0]["messages"][1]["content"]
    second_user = calls[1]["messages"][1]["content"]
    assert "Lean reported" not in first_user
    supplied = records(log, "attempt")[1]["supplied_feedback"]
    assert supplied in second_user
    assert len(supplied) == len("REAL_DIAGNOSTIC:BAD")
    assert supplied != "REAL_DIAGNOSTIC:BAD"
    assert "REAL_DIAGNOSTIC:BAD" not in second_user
    setup = records(log, "pi_decoy_setup")
    assert setup == [
        {
            "record_type": "pi_decoy_setup",
            **harness.RunMeta("decoy-run", "fake", 3, 0).record(),
            "task": task.name,
            "difficulty": task.difficulty,
            "arm": "pi_decoy",
            "source_task": other.name,
            "source_task_sha256": harness._task_sha256(other),
            "source_reference_proof_sha256": harness._sha256(other.reference_proof),
            "compiles": False,
            "proven": False,
            "sorry_tainted": False,
            "graded_score": 0.0,
            "oracle_diagnostic": "WRONG_TASK_DIAGNOSTIC",
            "oracle_diagnostic_sha256": harness._sha256("WRONG_TASK_DIAGNOSTIC"),
            "decoy_seed_diagnostic": "WRONG_TASK_DIAGNOSTIC",
            "decoy_seed_diagnostic_sha256": harness._sha256("WRONG_TASK_DIAGNOSTIC"),
            "setup_oracle_calls": 1,
            "record_sequence": 0,
        }
    ]
    attempts = records(log, "attempt")
    assert [item["feedback_source"] for item in attempts] == ["none", "decoy"]
    assert attempts[0]["diagnostic_sha256"] == harness._sha256("REAL_DIAGNOSTIC:BAD")
    assert attempts[1]["proven"] is True
    assert records(log, "pi_stop")[0]["stop"] == "complete"


def test_run_once_emits_full_v2_contract_and_counterbalanced_order(monkeypatch) -> None:
    tasks = (TASKS[0], TASKS[1])
    monkeypatch.setattr(
        harness,
        "_artifact_hashes",
        lambda: {key: "a" * 64 for key in ARTIFACT_KEYS},
    )

    def evaluate(
        name: str,
        signature: str,
        proof: str,
        *,
        preamble: str = "",
    ) -> Verdict:
        del name, signature, proof, preamble
        return Verdict(proven=True)

    class AlwaysProves:
        last_usage = (0, 0)
        last_response_model = "qwen2.5:32b-instruct"
        last_response_model_observed = True

        def __call__(self, messages: list[dict[str, str]], seed: int) -> str:
            del messages, seed
            self.last_usage = (4, 2)
            return "by omega"

    complete = AlwaysProves()
    log = io.StringIO()
    result = harness.run_once(
        complete,
        "fake",
        k=2,
        seed_offset=11,
        log=log,
        run_id="schema-run",
        tasks=tasks,
        evaluate_fn=evaluate,
        run_metadata=claim_run_metadata(),
        git_provenance={
            "git_commit": "b" * 40,
            "git_dirty": False,
            "git_status_sha256": "c" * 64,
        },
    )

    starts = records(log, "run_start")
    assert len(starts) == 1
    assert starts[0]["schema"] == "pi-diagnostic-repair-harness/v2"
    assert starts[0]["arms"] == list(harness.ARMS)
    assert set(starts[0]["artifact_hashes"]) == set(ARTIFACT_KEYS)
    assert starts[0]["payload_mode"] == "full"
    assert starts[0]["arm_order_policy"] == harness.ARM_ORDER_POLICY
    assert starts[0]["git_dirty"] is False
    for key, value in claim_run_metadata().items():
        assert starts[0][key] == value
    assert all(len(item["task_sha256"]) == 64 for item in starts[0]["tasks"])
    attempts = records(log, "attempt")
    assert {item["arm"] for item in attempts} == set(harness.ARMS)
    assert all({"proof", "diagnostic", "supplied_feedback"} <= set(item) for item in attempts)
    assert all(item["model_calls"] == item["oracle_calls"] == 1 for item in attempts)
    assert all(item["response_model_id"] == "qwen2.5:32b-instruct" for item in attempts)
    assert all(item["response_model_observed"] is True for item in attempts)
    summaries = records(log, "task_summary")
    assert len(summaries) == 2
    assert all(set(item["arms"]) == set(harness.ARMS) for item in summaries)
    assert all(
        {"proven", "graded_score", "setup_oracle_calls"} <= set(arm_summary)
        for item in summaries
        for arm_summary in item["arms"].values()
    )
    for task_index, task in enumerate(tasks):
        task_attempts = [item for item in attempts if item["task"] == task.name]
        rotation = (11 + task_index) % len(harness.ARMS)
        expected = list(harness.ARMS[rotation:] + harness.ARMS[:rotation])
        assert [item["arm"] for item in task_attempts] == expected
        assert summaries[task_index]["arm_order"] == expected
    run_summaries = records(log, "run_summary")
    assert len(run_summaries) == 1
    assert result["all"]["single"] == 2
    assert result["headroom_only"]["of"] == 0


def test_cli_contract_supports_replications_seed_offsets_and_isolated_run_files(
    tmp_path,
    monkeypatch,
) -> None:
    args = harness._parse_args(
        [
            "--k",
            "8",
            "--replications",
            "3",
            "--seed-offset",
            "20",
            "--seed-step",
            "5",
            "--out-dir",
            str(tmp_path),
        ]
    )
    assert args.k == 8
    assert args.replications == 3
    assert args.seed_offset == 20
    assert args.seed_step == 5
    assert args.out_dir == str(tmp_path)

    seen_offsets: list[int] = []
    seen_timestamps: list[str] = []

    def fake_run_once(
        complete: Any,
        backend: str,
        *,
        k: int,
        seed_offset: int,
        log: Any,
        run_id: str,
        evaluate_fn: Any,
        include_payloads: bool,
        git_provenance: dict[str, Any],
        run_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        del complete, backend, k
        assert run_id
        assert callable(evaluate_fn)
        assert include_payloads is True
        assert git_provenance["git_dirty"] is False
        assert run_metadata["model_id"] == "qwen2.5:32b-instruct"
        assert run_metadata["endpoint_class"] == "openai-compatible"
        assert run_metadata["temperature"] == 0.8
        assert run_metadata["max_tokens_per_attempt"] == 3072
        seen_offsets.append(seed_offset)
        seen_timestamps.append(run_metadata["timestamp_utc"])
        log.write('{"record_type":"fake"}\n')
        return {"seed_offset": seed_offset}

    class FakeSandbox:
        runner_sha256 = "e" * 64
        lean_toolchain = "leanprover/lean4:v4.27.0"
        lean_version = (
            "Lean (version 4.27.0, arm64-apple-darwin24.6.0, "
            "commit db93fe1608548721853390a10cd40580fe7d22ae, Release)"
        )
        lean_binary_sha256 = "f" * 64

        def __call__(self, *args: Any, **kwargs: Any) -> Verdict:
            del args, kwargs
            return Verdict(proven=True)

    monkeypatch.setattr(
        harness.lean_oracle.ExternalSandboxLeanEvaluator,
        "from_environment",
        lambda: FakeSandbox(),
    )
    monkeypatch.setattr(
        harness,
        "_git_provenance",
        lambda: {
            "git_commit": "b" * 40,
            "git_dirty": False,
            "git_status_sha256": "c" * 64,
        },
    )
    monkeypatch.setattr(
        harness.legacy,
        "_make_complete",
        lambda: (ScriptedComplete(["unused"]), "fake"),
    )
    monkeypatch.setattr(harness, "_assert_frozen_run_design", lambda **kwargs: None)
    monkeypatch.setenv("BHGMAN_LLM_BASE_URL", "http://127.0.0.1:8000/v1")
    monkeypatch.setenv("BHGMAN_LLM_MODEL", "qwen2.5:32b-instruct")
    monkeypatch.setenv("LEAN_TEMP", "0.8")
    monkeypatch.setenv("LEAN_MAX_TOKENS", "3072")
    monkeypatch.setattr(harness, "run_once", fake_run_once)
    cli = [
        "--k",
        "2",
        "--replications",
        "2",
        "--seed-offset",
        "20",
        "--seed-step",
        "5",
        "--out-dir",
        str(tmp_path),
        "--execute-frozen-run",
    ]
    assert harness.main(cli) == 0
    assert harness.main(cli) == 0
    assert seen_offsets == [20, 25, 20, 25]
    assert len(set(seen_timestamps)) == 4
    files = sorted(tmp_path.glob("*.jsonl"))
    assert len(files) == 4
    assert all(path.read_text().count('"fake"') == 1 for path in files)


def test_cli_refuses_missing_sandbox_before_model_initialization(
    monkeypatch,
    capsys,
) -> None:
    model_initialized = False

    def missing_sandbox():
        raise harness.lean_oracle.SandboxUnavailable("missing")

    def make_complete():
        nonlocal model_initialized
        model_initialized = True
        raise AssertionError("model initialization must not run")

    monkeypatch.setattr(
        harness.lean_oracle.ExternalSandboxLeanEvaluator,
        "from_environment",
        missing_sandbox,
    )
    monkeypatch.setattr(harness.legacy, "_make_complete", make_complete)

    assert harness.main(["--execute-frozen-run"]) == 2
    assert model_initialized is False
    assert "sandbox unavailable" in capsys.readouterr().out


def test_cli_requires_frozen_acknowledgement_before_any_preflight(
    monkeypatch,
) -> None:
    touched = False

    def sandbox():
        nonlocal touched
        touched = True
        raise AssertionError("sandbox preflight must not run without acknowledgement")

    monkeypatch.setattr(
        harness.lean_oracle.ExternalSandboxLeanEvaluator,
        "from_environment",
        sandbox,
    )
    assert harness.main([]) == 2
    assert touched is False


def test_claim_bearing_cli_refuses_redacted_payloads_before_preflight(
    monkeypatch,
) -> None:
    touched = False

    def sandbox():
        nonlocal touched
        touched = True
        raise AssertionError("sandbox preflight must not run for redacted claim")

    monkeypatch.setattr(
        harness.lean_oracle.ExternalSandboxLeanEvaluator,
        "from_environment",
        sandbox,
    )
    assert harness.main(["--execute-frozen-run", "--redact-payloads"]) == 2
    assert touched is False


def test_plain_baseline_uses_shared_varied_seed_schedule() -> None:
    complete = ScriptedComplete(["bad", "bad", "bad"])

    def evaluate(*args: Any, **kwargs: Any) -> Verdict:
        del args, kwargs
        return Verdict(proven=False, diagnostic="REAL")

    harness._run_plain_baseline(
        harness.RunMeta("plain-seeds", "fake", 3, 5),
        TASKS[0],
        complete,
        evaluate,
        io.StringIO(),
    )
    assert [item["seed"] for item in complete.calls] == [5, 6, 7]


def test_redacted_mode_keeps_hashes_and_record_sequence(monkeypatch) -> None:
    monkeypatch.setattr(
        harness,
        "_artifact_hashes",
        lambda: {key: "a" * 64 for key in ARTIFACT_KEYS},
    )

    def evaluate(*args: Any, **kwargs: Any) -> Verdict:
        del args, kwargs
        return Verdict(proven=True)

    complete = ScriptedComplete(
        ["by omega"] * len(harness.ARMS),
        response_model="qwen2.5:32b-instruct",
    )
    log = io.StringIO()
    harness.run_once(
        complete,
        "fake",
        k=1,
        seed_offset=0,
        log=log,
        run_id="redacted-run",
        tasks=(TASKS[0],),
        evaluate_fn=evaluate,
        include_payloads=False,
        run_metadata=claim_run_metadata(),
        git_provenance={
            "git_commit": "b" * 40,
            "git_dirty": True,
            "git_status_sha256": "c" * 64,
        },
    )
    all_records = [json.loads(line) for line in log.getvalue().splitlines()]
    assert [item["record_sequence"] for item in all_records] == list(range(len(all_records)))
    assert records(log, "run_start")[0]["payload_mode"] == "redacted"
    attempts = records(log, "attempt")
    assert all(
        "proof" not in item and "diagnostic" not in item and "supplied_feedback" not in item
        for item in attempts
    )
    assert all(
        len(item["proof_sha256"]) == len(item["diagnostic_sha256"]) == 64 for item in attempts
    )


def test_git_provenance_hashes_status_without_exposing_it(monkeypatch) -> None:
    outputs = iter(["d" * 40 + "\n", " M secret-path\n"])

    def fake_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return SimpleNamespace(stdout=next(outputs))

    monkeypatch.setattr(harness.subprocess, "run", fake_run)
    provenance = harness._git_provenance()
    assert provenance == {
        "git_commit": "d" * 40,
        "git_dirty": True,
        "git_status_sha256": harness._sha256(" M secret-path\n"),
    }
    assert "secret" not in json.dumps(provenance)


def test_environment_metadata_matches_frozen_openai_compatible_design() -> None:
    metadata = harness._environment_run_metadata(
        "frontier:qwen2.5:32b-instruct",
        sandbox_runner_sha256="e" * 64,
        lean_toolchain="leanprover/lean4:v4.27.0",
        lean_version=claim_run_metadata()["lean_version"],
        lean_binary_sha256="f" * 64,
        environ={
            "BHGMAN_LLM_BASE_URL": "http://127.0.0.1:8000/v1/",
            "BHGMAN_LLM_MODEL": "qwen2.5:32b-instruct",
            "LEAN_TEMP": "0.8",
            "LEAN_MAX_TOKENS": "3072",
        },
        timestamp_utc="2026-07-16T00:00:00+00:00",
    )
    assert metadata == claim_run_metadata() | {
        "endpoint_fingerprint": harness._sha256("http://127.0.0.1:8000/v1")
    }


def test_environment_metadata_rejects_unfrozen_routing_overrides() -> None:
    base = {
        "BHGMAN_LLM_BASE_URL": "http://127.0.0.1:8000/v1",
        "BHGMAN_LLM_MODEL": "qwen2.5:32b-instruct",
        "LEAN_TEMP": "0.8",
        "LEAN_MAX_TOKENS": "3072",
    }
    for key, value in (
        ("BHGMAN_LLM_ENDPOINTS", '[{"model":"other"}]'),
        ("BHGMAN_LLM_NO_THINK", "1"),
    ):
        try:
            harness._environment_run_metadata(
                "frontier:qwen2.5:32b-instruct",
                sandbox_runner_sha256="e" * 64,
                lean_toolchain="leanprover/lean4:v4.27.0",
                lean_version=claim_run_metadata()["lean_version"],
                lean_binary_sha256="f" * 64,
                environ={**base, key: value},
                timestamp_utc="2026-07-16T00:00:00+00:00",
            )
        except ValueError as exc:
            assert key in str(exc)
        else:
            raise AssertionError(f"{key} must be rejected for a frozen run")


def test_run_once_rejects_invalid_budget_and_duplicate_tasks() -> None:
    complete, _calls = scripted_complete(["unused"])
    try:
        harness.run_once(
            complete,
            "fake",
            k=0,
            seed_offset=0,
            tasks=(TASKS[0],),
        )
    except ValueError as exc:
        assert "k must be" in str(exc)
    else:
        raise AssertionError("k=0 must fail")

    try:
        harness.run_once(
            complete,
            "fake",
            k=1,
            seed_offset=0,
            tasks=(TASKS[0], TASKS[0]),
        )
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate tasks must fail")


def test_attempt_rejects_missing_or_mismatched_response_model() -> None:
    meta = harness.RunMeta("model-binding", "fake", 1, 0)
    task = TASKS[0]
    verdict = Verdict(proven=True)

    missing = ScriptedComplete(["by rfl"], model_observed=False)
    try:
        harness._run_single(meta, task, missing, lambda *args, **kwargs: verdict, io.StringIO())
    except RuntimeError as exc:
        assert "omitted the model identity" in str(exc)
    else:
        raise AssertionError("missing response model must fail")

    mismatched = ScriptedComplete(["by rfl"], response_model="other-model")
    try:
        harness._run_single(
            meta,
            task,
            mismatched,
            lambda *args, **kwargs: verdict,
            io.StringIO(),
        )
    except RuntimeError as exc:
        assert "response model mismatch" in str(exc)
    else:
        raise AssertionError("mismatched response model must fail")
