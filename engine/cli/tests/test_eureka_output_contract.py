"""Versioned Eureka output envelope and honest terminal outcomes."""

from __future__ import annotations

import json
from types import SimpleNamespace

from engine.agents.client import Completion
from engine.cli.main import cli
from engine.eureka.protocols import StageResult


class _Runner:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __call__(self, query, params=None):
        self.calls.append((query, params or {}))
        return self.rows


_ROWS = [
    {
        "object": name,
        "attributes": ["HAS_EPOCH:monotonic", "REJECTS_EFFECT:stale"],
    }
    for name in ("lease", "schema", "token")
]


def test_json_envelope_contains_consumable_candidates(monkeypatch, capsys):
    runner = _Runner(_ROWS)
    monkeypatch.setattr(
        "engine.cli.runtime.make_kg_runners", lambda: (runner, runner, lambda: None)
    )

    rc = cli(["eureka", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["schema"] == "bhgman.eureka.run.v1"
    assert payload["outcome"] == "PROPOSED"
    assert payload["earned"]["proposed"] >= 1
    assert payload["candidates"][0]["definition"]
    assert payload["candidates"][0]["extent"] == ["lease", "schema", "token"]


def test_empty_context_is_no_candidate_and_nonzero(monkeypatch, capsys):
    runner = _Runner([])
    monkeypatch.setattr(
        "engine.cli.runtime.make_kg_runners", lambda: (runner, runner, lambda: None)
    )

    rc = cli(["eureka", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert payload["outcome"] == "NO_CANDIDATE"
    assert payload["earned"] == {
        "induced": 0,
        "survived": 0,
        "proposed": 0,
        "persisted": 0,
    }
    assert payload["candidates"] == []


def test_accept_without_receipt_path_never_writes(monkeypatch, capsys):
    read, write = _Runner(_ROWS), _Runner([])
    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", lambda: (read, write, lambda: None))

    rc = cli(["eureka", "--accept"])

    assert rc == 2
    assert write.calls == []
    assert (
        "external human/Naesengmoon verdict ingress not implemented; "
        "use --creative --apply for VERDICT_PENDING"
    ) in capsys.readouterr().err


class _CreativeClient:
    def is_local(self):
        return False

    def complete(self, *, system, user, model, **kwargs):
        if "divergent abductive proposer" in system:
            proposal = {
                "name": "temporal authority membrane",
                "definition": (
                    "A boundary that turns ownership transfer into a monotone authority epoch."
                ),
                "mechanism": (
                    "Each transfer emits a higher epoch and refuses effects carrying an older epoch."
                ),
                "scope": "Concurrent systems with transferable single-writer authority.",
                "support_ids": ["lease", "schema", "token"],
                "positive_examples": ["leader handoff", "schema writer", "lease replacement"],
                "adversarial_near_misses": ["logging timestamp", "mutex without transfer"],
                "known_failure_scope": "Byzantine actors may forge authority epochs.",
                "falsifier_procedure": "Replay an old-owner effect after each ownership transfer.",
                "rejection_condition": "Reject if any stale effect mutates state.",
                "novelty_claim": (
                    "This unifies three domains through transfer plus stale-effect rejection."
                ),
                "nearest_existing": "fencing token",
                "semantic_delta": (
                    "It includes the transfer protocol and veto rather than token ordering alone."
                ),
                "held_out_prediction": (
                    "A cache-primary handoff using this rule will reject delayed writes."
                ),
            }
            return Completion(text=json.dumps([proposal]), model="creative-model")
        request = json.loads(user)
        digest = request["proposals"][0]["candidate_digest"]
        review = {
            "candidate_digest": digest,
            "verdict": "PASS",
            "cited_evidence_ids": ["lease", "schema", "token"],
            "strongest_counterargument": "The relation could be analogy rather than shared causality.",
            "cheapest_falsifier": "Replay one stale write after transfer.",
            "scores": {
                "novelty": 0.75,
                "compression": 0.74,
                "discrimination": 0.81,
                "falsifiability": 0.88,
            },
        }
        return Completion(text=json.dumps([review]), model="critic-model")


def test_creative_cli_emits_full_artifact_and_receipt(monkeypatch, capsys):
    runner = _Runner(_ROWS)
    monkeypatch.setattr(
        "engine.cli.runtime.make_kg_runners", lambda: (runner, runner, lambda: None)
    )
    monkeypatch.setattr(
        "engine.cli.commands._agent_runtime",
        lambda: (SimpleNamespace(AgentClient=_CreativeClient), "test"),
    )

    rc = cli(["eureka", "--creative", "--creative-limit", "1", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["mode"] == "creative"
    assert payload["candidates"][0]["candidate_digest"]
    assert payload["candidates"][0]["artifact"]["proposal"]["falsifier_procedure"]
    assert payload["validation_receipts"][0]["gates"]["reviewer_independent"] is True


def test_creative_failed_outcome_is_execution_failed(monkeypatch, capsys):
    runner = _Runner(_ROWS)
    monkeypatch.setattr(
        "engine.cli.runtime.make_kg_runners", lambda: (runner, runner, lambda: None)
    )
    monkeypatch.setattr(
        "engine.cli.commands._agent_runtime",
        lambda: (SimpleNamespace(AgentClient=_CreativeClient), "test"),
    )

    def failed_run(*args, **kwargs):
        return SimpleNamespace(
            stages=[
                StageResult("4-induce-fca", True, {"abstract_classes": 1}),
                StageResult(
                    "4.9-semantic-creative-loop",
                    False,
                    {"outcomes": ["FAILED"]},
                    "proposer failed",
                ),
            ],
            proposals=[],
            creative_artifacts=[],
            creative_receipts=[],
        )

    monkeypatch.setattr("engine.eureka.pipeline.run_from_kg", failed_run)

    rc = cli(["eureka", "--creative", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 3
    assert payload["outcome"] == "EXECUTION_FAILED"


def test_pre_merge_validator_failure_is_execution_failed(monkeypatch, capsys):
    runner = _Runner(_ROWS)
    monkeypatch.setattr(
        "engine.cli.runtime.make_kg_runners", lambda: (runner, runner, lambda: None)
    )

    def fail_validator(*args, **kwargs):
        raise ValueError("validator boom")

    monkeypatch.setattr("engine.eureka.pipeline.gate_before_merge", fail_validator)

    rc = cli(["eureka", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 3
    assert payload["outcome"] == "EXECUTION_FAILED"
    validator = next(
        stage for stage in payload["stages"] if stage["name"] == "5.5-pre-merge-validator"
    )
    assert validator["ok"] is False


def test_agent_client_initialization_failure_closes_runner(monkeypatch, capsys):
    runner = _Runner(_ROWS)
    close_calls = []

    class BrokenClient:
        def __init__(self):
            raise RuntimeError("init boom")

    monkeypatch.setattr(
        "engine.cli.runtime.make_kg_runners",
        lambda: (runner, runner, lambda: close_calls.append(True)),
    )
    monkeypatch.setattr(
        "engine.cli.commands._agent_runtime",
        lambda: (SimpleNamespace(AgentClient=BrokenClient), "test"),
    )

    rc = cli(["eureka", "--creative"])

    assert rc == 2
    assert close_calls == [True]
    assert "agent client initialization failed: init boom" in capsys.readouterr().err


def test_creative_rounds_expand_model_call_budget(monkeypatch, capsys):
    runner = _Runner(_ROWS)
    captured = {}
    monkeypatch.setattr(
        "engine.cli.runtime.make_kg_runners", lambda: (runner, runner, lambda: None)
    )
    monkeypatch.setattr(
        "engine.cli.commands._agent_runtime",
        lambda: (SimpleNamespace(AgentClient=_CreativeClient), "test"),
    )

    def capture_run(run_cypher, config, *args, **kwargs):
        captured["config"] = config
        return SimpleNamespace(stages=[], proposals=[], creative_artifacts=[], creative_receipts=[])

    monkeypatch.setattr("engine.eureka.pipeline.run_from_kg", capture_run)

    rc = cli(["eureka", "--creative", "--creative-rounds", "7", "--json"])
    capsys.readouterr()

    assert rc == 1
    loop_config = captured["config"].creative_enricher._config
    assert loop_config.max_rounds == 7
    assert loop_config.max_model_calls == 14
