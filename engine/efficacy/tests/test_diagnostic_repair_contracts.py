from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
CONTRACT = ROOT / "diagnostic_repair_harness_contract.json"
FSM = ROOT / "diagnostic_repair_harness_fsm.json"
TRACES = ROOT / "diagnostic_repair_harness_fsm_traces.json"
MANIFEST = ROOT / "diagnostic_repair_harness_manifest.v2.json"
PREREGISTRATION = ROOT / "DIAGNOSTIC_REPAIR_PREREGISTRATION_V2.md"

ARMS = {
    "single",
    "bestN",
    "legacy_repair",
    "pi_repair",
    "pi_decoy",
    "plain_baseline",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_manifest_hashes_every_authoritative_artifact_and_b1_fixture() -> None:
    manifest = _load(MANIFEST)
    assert manifest["schema"] == "pi-diagnostic-repair-harness-manifest/v2"
    assert manifest["status"] == "frozen"
    assert manifest["harness_version"] == "2.0.0"
    assert manifest["thresholds"] == {
        "alpha": 0.05,
        "tost_margin": 1.0,
        "parity_low": 0.8,
        "parity_high": 1.25,
        "min_live_tasks": 6,
        "top_task_concentration": 0.5,
    }
    assert manifest["run_design"] == {
        "backend": "frontier:qwen2.5:32b-instruct",
        "model_id": "qwen2.5:32b-instruct",
        "endpoint_class": "openai-compatible",
        "temperature": 0.8,
        "max_tokens_per_attempt": 3072,
        "oracle_isolation": "external-sandbox-runner/v2",
        "lean_toolchain": "leanprover/lean4:v4.27.0",
        "lean_version": (
            "Lean (version 4.27.0, arm64-apple-darwin24.6.0, "
            "commit db93fe1608548721853390a10cd40580fe7d22ae, Release)"
        ),
        "lean_binary_sha256": ("2974847fff2e2621502841f4c2dbac4035b4847d6060a4f2087cbc0d04005e37"),
        "k": 4,
        "replications": 10,
        "seed_offsets": list(range(0, 100, 10)),
        "task_band": manifest["run_design"]["task_band"],
    }
    assert len(manifest["run_design"]["task_band"]) == 12
    assert all(
        set(task) == {"name", "difficulty", "task_sha256"}
        for task in manifest["run_design"]["task_band"]
    )
    assert manifest["artifacts"]["lean_toolchain"] == {
        "path": "lean/lean-toolchain",
        "sha256": "d55ca0039a5479db5b38919d005b2c427b89b3be4f0184a20f2f4eae931f5bdb",
    }
    assert set(manifest["artifacts"]) == {
        "runner",
        "analyzer",
        "diagnostic_repair",
        "diagnostic_oracle",
        "lean_headroom_run",
        "lean_tasks",
        "lean_oracle",
        "agent_client",
        "agent_runtime",
        "loop_contract",
        "fsm",
        "fsm_traces",
        "lean_sandbox_runner_macos",
        "lean_toolchain",
    }
    for artifact in manifest["artifacts"].values():
        path = REPO_ROOT / artifact["path"]
        assert path.is_file()
        assert _sha256(path) == artifact["sha256"]

    bridge = manifest["bridge_conformance"]
    bridge_path = REPO_ROOT / bridge["path"]
    assert _sha256(bridge_path) == bridge["sha256"]
    assert bridge["pytest_nodeid"].startswith(f"{bridge['path']}::")

    preregistration = PREREGISTRATION.read_text(encoding="utf-8")
    assert "TBD-BEFORE-LIVE-RUN" not in preregistration
    assert _sha256(MANIFEST) in preregistration
    for artifact in manifest["artifacts"].values():
        assert artifact["sha256"] in preregistration
    assert bridge["sha256"] in preregistration


def test_loop_contract_freezes_six_arm_l_rt_boundary() -> None:
    contract = _load(CONTRACT)
    assert contract["schema_version"] == "loop-contract/v1"
    assert contract["tier"] == "L_RT"
    assert contract["conformance_status"] == "TARGET_CONTRACT_NOT_RUNTIME_CONFORMANT"
    assert contract["implemented_slice"] == {
        "local_only": True,
        "fresh_file_x_mode": True,
        "flush_each_record": True,
        "resume": False,
        "atomic_checkpoint_or_rename": False,
        "aggregate_wall_token_cost_governor": False,
        "publication_outbox_or_reconciliation": False,
        "fsm_runtime_reducer": False,
    }
    assert set(contract["experiment"]["arms"]) == ARMS
    assert contract["experiment"]["primary_treatment"] == "pi_repair"
    assert contract["experiment"]["bridge_control"] == "legacy_repair"
    assert contract["experiment"]["minimum_live_discriminating_tasks"] == 6
    assert contract["experiment"]["token_call_parity_bound"] == 1.25
    assert contract["control_owner"]["success_verdict"].startswith("deterministic Lean oracle")
    assert "mutable elan defaults are forbidden" in contract["security"]["compiler_identity"]
    assert any(
        "physical JSONL order" in invariant
        for invariant in contract["verification"]["invariant_checks"]
    )
    assert "Lean child stdout or stderr flood" in contract["verification"]["fault_tests"]
    assert "replays every full-payload Lean attempt" in contract["replay"][
        "implemented_evidence_replay"
    ]
    assert contract["commander_dispatch"]["fixed_uses_edges"] is False


def test_only_authoritative_pass_can_enter_complete_state() -> None:
    fsm = _load(FSM)
    assert fsm["conformance_status"] == "REFERENCE_MODEL_NOT_RUNTIME_REDUCER"
    machine = fsm["machines"][0]
    incoming = [
        transition for transition in machine["transitions"] if transition["to"] == "complete"
    ]
    assert [(transition["from"], transition["event"]) for transition in incoming] == [
        ("evaluating", "EVALUATION_PASSED")
    ]
    final_states = {state["id"] for state in machine["states"] if state["kind"] == "final"}
    assert final_states == {"complete", "capped", "failed"}
    assert not any(transition["from"] in final_states for transition in machine["transitions"])


def test_fsm_traces_cover_every_transition_and_invalid_event_policy() -> None:
    fsm = _load(FSM)
    traces = _load(TRACES)
    machine = fsm["machines"][0]
    transition_pairs = {
        (transition["from"], transition["event"]): transition["id"]
        for transition in machine["transitions"]
    }
    selected: set[str] = set()
    invalid_seen = False
    for case in traces["cases"]:
        state = machine["initial"]
        for step in case["steps"]:
            transition_id = transition_pairs.get((state, step["event"]))
            if transition_id is None:
                invalid_seen = True
                continue
            selected.add(transition_id)
            transition = next(
                item for item in machine["transitions"] if item["id"] == transition_id
            )
            state = transition["to"]
    assert selected == {transition["id"] for transition in machine["transitions"]}
    assert invalid_seen is True
