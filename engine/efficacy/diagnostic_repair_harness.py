"""Six-arm Lean bridge for measuring the diagnostic-repair engine.

This module deliberately leaves :mod:`lean_headroom_run` frozen.  It reuses its
prompt and completion adapters, but adds two arms that exercise the production
``engine.legion.diagnostic_repair`` loop directly:

``single``
    One model attempt and one authoritative Lean evaluation.
``bestN``
    Up to K independent attempts; no diagnostic is returned to the model.
``legacy_repair``
    The frozen hand-written attempt/error loop, reproduced as a control.
``pi_repair``
    The same prompts, seeds, and Lean oracle routed through
    :func:`diagnostic_repair`.
``pi_decoy``
    Real Lean acceptance, but repair generations receive a diagnostic produced
    by a different task.
``plain_baseline``
    The frozen fair generic coding-agent transcript loop.

Claim-bearing JSONL defaults to full replay payloads (proof, authoritative
diagnostic, and supplied feedback) plus SHA-256 digests. Private smoke runs may
explicitly redact those payloads, but such evidence cannot satisfy provenance
gate P5.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import os
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, TextIO
from urllib.parse import urlsplit

from engine.agents import client as agent_client
from engine.cli import runtime as cli_runtime
from engine.efficacy import lean_headroom_run as legacy
from engine.efficacy import lean_oracle, lean_tasks
from engine.efficacy.lean_oracle import LeanVerdict
from engine.efficacy.lean_tasks import LeanTask
from engine.legion.diagnostic_repair import (
    DiagnosticRepairResult,
    RepairContext,
    diagnostic_repair,
)
from engine.naesengmoon.diagnostic_oracle import DiagnosticFeedback, feedback_from_value

SCHEMA = "pi-diagnostic-repair-harness/v2"
HARNESS_VERSION = "2.0.0"
ARMS = (
    "single",
    "bestN",
    "legacy_repair",
    "pi_repair",
    "pi_decoy",
    "plain_baseline",
)
ARM_ORDER_POLICY = "cyclic_rotation:(seed_offset+task_index)%6"
_RUN_METADATA_KEYS = {
    "model_id",
    "endpoint_class",
    "endpoint_fingerprint",
    "temperature",
    "max_tokens_per_attempt",
    "oracle_isolation",
    "sandbox_runner_sha256",
    "lean_toolchain",
    "lean_version",
    "lean_binary_sha256",
    "timestamp_utc",
}
_FROZEN_MANIFEST = Path(__file__).with_name("diagnostic_repair_harness_manifest.v2.json")
_RUN_DESIGN_KEYS = {
    "backend",
    "model_id",
    "endpoint_class",
    "temperature",
    "max_tokens_per_attempt",
    "oracle_isolation",
    "lean_toolchain",
    "lean_version",
    "lean_binary_sha256",
    "k",
    "replications",
    "seed_offsets",
    "task_band",
}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_path(value: Any) -> Path:
    path = inspect.getsourcefile(value)
    if path is None:
        raise RuntimeError(f"cannot resolve source path for {value!r}")
    return Path(path).resolve()


def _artifact_hashes() -> dict[str, str]:
    efficacy = Path(__file__).resolve().parent
    return {
        "runner": _file_sha256(Path(__file__).resolve()),
        "analyzer": _file_sha256(efficacy / "analyze_diagnostic_repair_harness.py"),
        "diagnostic_repair": _file_sha256(_source_path(diagnostic_repair)),
        "diagnostic_oracle": _file_sha256(efficacy.parent / "naesengmoon" / "diagnostic_oracle.py"),
        "lean_headroom_run": _file_sha256(Path(legacy.__file__).resolve()),
        "lean_tasks": _file_sha256(Path(lean_tasks.__file__).resolve()),
        "lean_oracle": _file_sha256(Path(lean_oracle.__file__).resolve()),
        "agent_client": _file_sha256(Path(agent_client.__file__).resolve()),
        "agent_runtime": _file_sha256(Path(cli_runtime.__file__).resolve()),
        "lean_sandbox_runner_macos": _file_sha256(
            Path(lean_oracle.__file__).with_name("lean_sandbox_runner_macos.py")
        ),
        "lean_toolchain": _file_sha256(
            Path(__file__).resolve().parents[2] / "lean" / "lean-toolchain"
        ),
        "loop_contract": _file_sha256(efficacy / "diagnostic_repair_harness_contract.json"),
        "fsm": _file_sha256(efficacy / "diagnostic_repair_harness_fsm.json"),
        "fsm_traces": _file_sha256(efficacy / "diagnostic_repair_harness_fsm_traces.json"),
        "manifest": _file_sha256(efficacy / "diagnostic_repair_harness_manifest.v2.json"),
        "preregistration_v2": _file_sha256(efficacy / "DIAGNOSTIC_REPAIR_PREREGISTRATION_V2.md"),
    }


def _git_provenance(repo_root: Path | None = None) -> dict[str, Any]:
    """Snapshot git state without writing the status payload into evidence."""
    root = repo_root or Path(__file__).resolve().parents[2]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if len(commit) not in (40, 64) or any(char not in "0123456789abcdef" for char in commit):
        raise RuntimeError("git rev-parse returned an invalid commit object id")
    return {
        "git_commit": commit,
        "git_dirty": bool(status),
        "git_status_sha256": _sha256(status),
    }


def _task_sha256(task: LeanTask) -> str:
    canonical = json.dumps(
        {
            "name": task.name,
            "difficulty": task.difficulty,
            "signature": task.signature,
            "preamble": task.preamble,
            "reference_proof": task.reference_proof,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _sha256(canonical)


def _sanitized_endpoint(raw: str) -> str:
    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.hostname:
        return raw.rstrip("/")
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{parsed.scheme.lower()}://{parsed.hostname.lower()}{port}{parsed.path.rstrip('/')}"


def _environment_run_metadata(
    backend: str,
    *,
    sandbox_runner_sha256: str,
    lean_toolchain: str,
    lean_version: str,
    lean_binary_sha256: str,
    environ: Mapping[str, str] | None = None,
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    forbidden_overrides = [
        key
        for key in ("BHGMAN_LLM_ENDPOINTS", "BHGMAN_LLM_NO_THINK")
        if env.get(key)
    ]
    if forbidden_overrides:
        raise ValueError(
            "frozen diagnostic-repair runs forbid semantic endpoint overrides: "
            + ", ".join(forbidden_overrides)
        )
    model_id = env.get("BHGMAN_LLM_MODEL") or env.get("P1_MODEL")
    if not model_id:
        _prefix, _separator, suffix = backend.partition(":")
        model_id = suffix or backend
    base_url = env.get("BHGMAN_LLM_BASE_URL")
    if base_url:
        endpoint_class = "openai-compatible"
        endpoint_descriptor = _sanitized_endpoint(base_url)
    elif env.get("ANTHROPIC_API_KEY"):
        endpoint_class = "anthropic"
        endpoint_descriptor = "anthropic-api"
    else:
        endpoint_class = "local-ollama"
        endpoint_descriptor = env.get("OLLAMA_HOST", "local-ollama")
    temperature = float(env.get("LEAN_TEMP") or env.get("P1_TEMP", "0.8"))
    max_tokens = int(env.get("LEAN_MAX_TOKENS", "3072"))
    if not math.isfinite(temperature) or temperature < 0:
        raise ValueError("Lean experiment temperature must be finite and >= 0")
    if max_tokens <= 0:
        raise ValueError("LEAN_MAX_TOKENS must be > 0")
    return {
        "model_id": model_id,
        "endpoint_class": endpoint_class,
        "endpoint_fingerprint": _sha256(endpoint_descriptor),
        "temperature": temperature,
        "max_tokens_per_attempt": max_tokens,
        "oracle_isolation": lean_oracle.ORACLE_ISOLATION,
        "sandbox_runner_sha256": sandbox_runner_sha256,
        "lean_toolchain": lean_toolchain,
        "lean_version": lean_version,
        "lean_binary_sha256": lean_binary_sha256,
        "timestamp_utc": timestamp_utc or datetime.now(timezone.utc).isoformat(),
    }


def _assert_frozen_run_design(
    *,
    manifest_path: Path,
    backend: str,
    metadata: Mapping[str, Any],
    k: int,
    replications: int,
    seed_offset: int,
    seed_step: int,
    tasks: tuple[LeanTask, ...],
) -> None:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"frozen manifest is unavailable: {manifest_path}") from exc
    if not isinstance(manifest, dict) or manifest.get("status") != "frozen":
        raise RuntimeError("diagnostic repair manifest is not frozen")
    design = manifest.get("run_design")
    if not isinstance(design, dict) or set(design) != _RUN_DESIGN_KEYS:
        raise RuntimeError("manifest run_design is absent or has an invalid field set")
    expected = {
        "backend": backend,
        "model_id": metadata["model_id"],
        "endpoint_class": metadata["endpoint_class"],
        "temperature": metadata["temperature"],
        "max_tokens_per_attempt": metadata["max_tokens_per_attempt"],
        "oracle_isolation": metadata["oracle_isolation"],
        "lean_toolchain": metadata["lean_toolchain"],
        "lean_version": metadata["lean_version"],
        "lean_binary_sha256": metadata["lean_binary_sha256"],
        "k": k,
        "replications": replications,
        "seed_offsets": [seed_offset + index * seed_step for index in range(replications)],
        "task_band": [
            {
                "name": task.name,
                "difficulty": task.difficulty,
                "task_sha256": _task_sha256(task),
            }
            for task in tasks
        ],
    }
    if design != expected:
        mismatches = sorted(key for key in _RUN_DESIGN_KEYS if design.get(key) != expected[key])
        raise RuntimeError(f"runtime does not match frozen run_design: {', '.join(mismatches)}")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise RuntimeError("manifest artifacts are absent")
    current_hashes = _artifact_hashes()
    for key, entry in artifacts.items():
        if (
            key not in current_hashes
            or not isinstance(entry, dict)
            or entry.get("sha256") != current_hashes[key]
        ):
            raise RuntimeError(f"frozen artifact mismatch: {key}")
    sandbox_artifact = artifacts.get("lean_sandbox_runner_macos")
    if (
        not isinstance(sandbox_artifact, dict)
        or sandbox_artifact.get("sha256") != metadata["sandbox_runner_sha256"]
    ):
        raise RuntimeError("configured sandbox runner is not the frozen artifact")


def _write(log: TextIO | None, record: dict[str, Any]) -> None:
    if log is None:
        return
    if "record_sequence" in record:
        raise ValueError("record_sequence is owned by the JSONL writer")
    sequence = int(getattr(log, "_pi_record_sequence", 0))
    sequenced = {**record, "record_sequence": sequence}
    log.write(json.dumps(sequenced, ensure_ascii=False, sort_keys=True) + "\n")
    log.flush()
    setattr(log, "_pi_record_sequence", sequence + 1)


def _usage(complete: Any) -> tuple[int, int, str]:
    raw = getattr(complete, "last_usage", (0, 0))
    if not isinstance(raw, tuple) or len(raw) != 2:
        raise TypeError("complete.last_usage must be an (input_tokens, output_tokens) tuple")
    input_tokens, output_tokens = (int(raw[0]), int(raw[1]))
    if input_tokens <= 0 or output_tokens <= 0:
        raise ValueError("backend token telemetry must be positive for every attempt")
    response_model_id = getattr(complete, "last_response_model", "")
    if not isinstance(response_model_id, str) or not response_model_id:
        raise RuntimeError("backend response did not report a non-empty model identity")
    if getattr(complete, "last_response_model_observed", False) is not True:
        raise RuntimeError("backend response omitted the model identity field")
    return input_tokens, output_tokens, response_model_id


@dataclass(frozen=True)
class RunMeta:
    run_id: str
    backend: str
    k: int
    seed_offset: int
    include_payloads: bool = True
    model_id: str = "injected-test-model"
    endpoint_class: str = "injected-test"
    endpoint_fingerprint: str = "0" * 64
    temperature: float = 0.0
    max_tokens_per_attempt: int = 1
    oracle_isolation: str = "injected-evaluator/test-only"
    sandbox_runner_sha256: str = "0" * 64
    lean_toolchain: str = "injected-test-toolchain"
    lean_version: str = "injected-test-version"
    lean_binary_sha256: str = "0" * 64
    timestamp_utc: str = "1970-01-01T00:00:00+00:00"

    def record(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "harness_version": HARNESS_VERSION,
            "run_id": self.run_id,
            "backend": self.backend,
            "K": self.k,
            "seed_offset": self.seed_offset,
            "payload_mode": "full" if self.include_payloads else "redacted",
            "model_id": self.model_id,
            "endpoint_class": self.endpoint_class,
            "endpoint_fingerprint": self.endpoint_fingerprint,
            "temperature": self.temperature,
            "max_tokens_per_attempt": self.max_tokens_per_attempt,
            "oracle_isolation": self.oracle_isolation,
            "sandbox_runner_sha256": self.sandbox_runner_sha256,
            "lean_toolchain": self.lean_toolchain,
            "lean_version": self.lean_version,
            "lean_binary_sha256": self.lean_binary_sha256,
            "timestamp_utc": self.timestamp_utc,
        }


@dataclass(frozen=True)
class PendingAttempt:
    attempt: int
    seed: int
    used_feedback: bool
    supplied_feedback: str
    feedback_source: str
    prior_proof: str | None
    proof: str
    input_tokens: int
    output_tokens: int
    response_model_id: str


@dataclass(frozen=True)
class ArmOutcome:
    proven: bool
    graded_score: float
    attempts: tuple[dict[str, Any], ...]
    pi_stop: str | None = None
    setup_oracle_calls: int = 0

    def summary(self) -> dict[str, Any]:
        return {
            "proven": self.proven,
            "graded_score": self.graded_score,
            "attempts": len(self.attempts),
            "model_calls": sum(int(item["model_calls"]) for item in self.attempts),
            "oracle_calls": sum(int(item["oracle_calls"]) for item in self.attempts),
            "setup_oracle_calls": self.setup_oracle_calls,
            "input_tokens": sum(int(item["input_tokens"]) for item in self.attempts),
            "output_tokens": sum(int(item["output_tokens"]) for item in self.attempts),
            "pi_stop": self.pi_stop,
        }


def _attempt_record(
    meta: RunMeta,
    task: LeanTask,
    arm: str,
    pending: PendingAttempt,
    verdict: LeanVerdict,
    *,
    pi_run_id: str = "",
) -> dict[str, Any]:
    diagnostic = verdict.error_tail
    if pending.response_model_id != meta.model_id:
        raise RuntimeError(
            "backend response model mismatch: "
            f"{pending.response_model_id!r} != frozen {meta.model_id!r}"
        )
    record = {
        "record_type": "attempt",
        **meta.record(),
        "task": task.name,
        "difficulty": task.difficulty,
        "task_sha256": _task_sha256(task),
        "arm": arm,
        "attempt": pending.attempt,
        "seed": pending.seed,
        "used_feedback": pending.used_feedback,
        "feedback_source": pending.feedback_source,
        "proven": verdict.proven,
        "compiles": verdict.compiles,
        "sorry_tainted": verdict.sorry_tainted,
        "graded_score": verdict.graded_score,
        "proof_sha256": _sha256(pending.proof),
        "diagnostic_sha256": _sha256(diagnostic),
        "supplied_feedback_sha256": _sha256(pending.supplied_feedback),
        "prior_proof_sha256": (
            _sha256(pending.prior_proof) if pending.prior_proof is not None else ""
        ),
        "input_tokens": pending.input_tokens,
        "output_tokens": pending.output_tokens,
        "response_model_id": pending.response_model_id,
        "response_model_observed": True,
        "model_calls": 1,
        "oracle_calls": 1,
        "pi_run_id": pi_run_id,
        "pi_stop_reason": None,
        "pi_event_count": None,
    }
    if meta.include_payloads:
        record.update(
            {
                "proof": pending.proof,
                "diagnostic": diagnostic,
                "supplied_feedback": pending.supplied_feedback,
            }
        )
    return record


def _evaluate_attempt(
    meta: RunMeta,
    task: LeanTask,
    arm: str,
    pending: PendingAttempt,
    evaluate_fn: Any,
    log: TextIO | None,
) -> tuple[LeanVerdict, dict[str, Any]]:
    verdict = evaluate_fn(
        task.name,
        task.signature,
        pending.proof,
        preamble=task.preamble,
    )
    record = _attempt_record(meta, task, arm, pending, verdict)
    _write(log, record)
    return verdict, record


def _outcome(records: list[dict[str, Any]], *, setup_oracle_calls: int = 0) -> ArmOutcome:
    return ArmOutcome(
        proven=any(bool(item["proven"]) for item in records),
        graded_score=max((float(item["graded_score"]) for item in records), default=0.0),
        attempts=tuple(records),
        setup_oracle_calls=setup_oracle_calls,
    )


def _run_single(
    meta: RunMeta,
    task: LeanTask,
    complete: Any,
    evaluate_fn: Any,
    log: TextIO | None,
) -> ArmOutcome:
    proof = legacy._gen(task, complete, meta.seed_offset)
    input_tokens, output_tokens, response_model_id = _usage(complete)
    pending = PendingAttempt(
        attempt=1,
        seed=meta.seed_offset,
        used_feedback=False,
        supplied_feedback="",
        feedback_source="none",
        prior_proof=None,
        proof=proof,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        response_model_id=response_model_id,
    )
    _verdict, record = _evaluate_attempt(meta, task, "single", pending, evaluate_fn, log)
    return _outcome([record])


def _run_bestn(
    meta: RunMeta,
    task: LeanTask,
    complete: Any,
    evaluate_fn: Any,
    log: TextIO | None,
) -> ArmOutcome:
    records: list[dict[str, Any]] = []
    for index in range(meta.k):
        seed = meta.seed_offset + index
        proof = legacy._gen(task, complete, seed)
        input_tokens, output_tokens, response_model_id = _usage(complete)
        pending = PendingAttempt(
            attempt=index + 1,
            seed=seed,
            used_feedback=False,
            supplied_feedback="",
            feedback_source="none",
            prior_proof=None,
            proof=proof,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_model_id=response_model_id,
        )
        verdict, record = _evaluate_attempt(meta, task, "bestN", pending, evaluate_fn, log)
        records.append(record)
        if verdict.proven:
            break
    return _outcome(records)


def _run_legacy_repair(
    meta: RunMeta,
    task: LeanTask,
    complete: Any,
    evaluate_fn: Any,
    log: TextIO | None,
) -> ArmOutcome:
    records: list[dict[str, Any]] = []
    prior: str | None = None
    diagnostic: str | None = None
    for index in range(meta.k):
        seed = meta.seed_offset + index
        proof = legacy._gen(task, complete, seed, prior, diagnostic)
        input_tokens, output_tokens, response_model_id = _usage(complete)
        pending = PendingAttempt(
            attempt=index + 1,
            seed=seed,
            used_feedback=prior is not None,
            supplied_feedback=diagnostic or "",
            feedback_source="real" if prior is not None else "none",
            prior_proof=prior,
            proof=proof,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_model_id=response_model_id,
        )
        verdict, record = _evaluate_attempt(meta, task, "legacy_repair", pending, evaluate_fn, log)
        records.append(record)
        if verdict.proven:
            break
        prior, diagnostic = proof, verdict.error_tail
    return _outcome(records)


def _decoy_diagnostic(
    meta: RunMeta,
    task: LeanTask,
    tasks: tuple[LeanTask, ...],
    evaluate_fn: Any,
    log: TextIO | None,
) -> tuple[str, int]:
    """Return a real but task-mismatched Lean diagnostic outside measured calls."""
    if len(tasks) < 2:
        raise ValueError("pi_decoy requires at least two frozen tasks")
    index = next(i for i, item in enumerate(tasks) if item.name == task.name)
    other = tasks[(index + 1) % len(tasks)]
    verdict = evaluate_fn(
        task.name,
        task.signature,
        other.reference_proof,
        preamble=task.preamble,
    )
    oracle_diagnostic = verdict.error_tail
    decoy_seed_diagnostic = oracle_diagnostic or "unsolved goals\n"
    _write(
        log,
        {
            "record_type": "pi_decoy_setup",
            **meta.record(),
            "task": task.name,
            "difficulty": task.difficulty,
            "arm": "pi_decoy",
            "source_task": other.name,
            "source_task_sha256": _task_sha256(other),
            "source_reference_proof_sha256": _sha256(other.reference_proof),
            "compiles": verdict.compiles,
            "proven": verdict.proven,
            "sorry_tainted": verdict.sorry_tainted,
            "graded_score": verdict.graded_score,
            "oracle_diagnostic": oracle_diagnostic,
            "oracle_diagnostic_sha256": _sha256(oracle_diagnostic),
            "decoy_seed_diagnostic": decoy_seed_diagnostic,
            "decoy_seed_diagnostic_sha256": _sha256(decoy_seed_diagnostic),
            "setup_oracle_calls": 1,
        },
    )
    return decoy_seed_diagnostic, 1


class _PiLeanOracle:
    name = "lean-ungameable"
    kind = "lean-proof"

    def __init__(
        self,
        meta: RunMeta,
        task: LeanTask,
        arm: str,
        evaluate_fn: Any,
        pi_run_id: str,
        log: TextIO | None,
    ) -> None:
        self.meta = meta
        self.task = task
        self.arm = arm
        self.evaluate_fn = evaluate_fn
        self.pi_run_id = pi_run_id
        self.log = log
        self.pending: PendingAttempt | None = None
        self.records: list[dict[str, Any]] = []

    def set_pending(self, pending: PendingAttempt) -> None:
        if self.pending is not None:
            raise RuntimeError("previous PI attempt was not consumed by the oracle")
        self.pending = pending

    def evaluate(self, candidate: Any) -> DiagnosticFeedback:
        if not isinstance(candidate, str):
            raise TypeError("Lean PI candidate must be a proof string")
        pending = self.pending
        if pending is None:
            raise RuntimeError("PI oracle evaluation has no pending attempt metadata")
        if _sha256(candidate) != _sha256(pending.proof):
            raise RuntimeError("PI candidate does not match pending attempt metadata")
        self.pending = None
        verdict = self.evaluate_fn(
            self.task.name,
            self.task.signature,
            candidate,
            preamble=self.task.preamble,
        )
        record = _attempt_record(
            self.meta,
            self.task,
            self.arm,
            pending,
            verdict,
            pi_run_id=self.pi_run_id,
        )
        self.records.append(record)
        _write(self.log, record)
        return feedback_from_value(
            lens=self.name,
            kind=self.kind,
            passed=verdict.proven,
            score=verdict.graded_score,
            diagnostic=verdict.error_tail,
        )


class _PiRepairGenerator:
    def __init__(
        self,
        *,
        task: LeanTask,
        complete: Any,
        seed_offset: int,
        oracle: _PiLeanOracle,
        decoy: str | None,
    ) -> None:
        self.task = task
        self.complete = complete
        self.seed_offset = seed_offset
        self.oracle = oracle
        self.decoy = decoy
        self.used_input_tokens = 0
        self.used_output_tokens = 0

    def __call__(self, ctx: RepairContext) -> str:
        supplied = (
            _fit_decoy(self.decoy, ctx.feedback.diagnostic)
            if self.decoy is not None
            else ctx.feedback.diagnostic
        )
        seed = self.seed_offset + ctx.attempt
        proof = legacy._gen(self.task, self.complete, seed, ctx.current, supplied)
        input_tokens, output_tokens, response_model_id = _usage(self.complete)
        self.used_input_tokens += input_tokens
        self.used_output_tokens += output_tokens
        self.oracle.set_pending(
            PendingAttempt(
                attempt=ctx.attempt + 1,
                seed=seed,
                used_feedback=True,
                supplied_feedback=supplied,
                feedback_source="decoy" if self.decoy is not None else "real",
                prior_proof=ctx.current,
                proof=proof,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                response_model_id=response_model_id,
            )
        )
        return proof


def _fit_decoy(decoy: str, real_diagnostic: str) -> str:
    """Match real-diagnostic context volume without copying its content."""
    target_length = len(real_diagnostic)
    if target_length <= 0:
        return ""
    marker = decoy or "DECOY"
    repeats = (target_length + len(marker) - 1) // len(marker)
    fitted = (marker * repeats)[:target_length]
    if fitted == real_diagnostic:
        replacement = "X" if fitted[0] != "X" else "Y"
        fitted = replacement + fitted[1:]
    return fitted


def _emit_pi_lifecycle(
    meta: RunMeta,
    task: LeanTask,
    arm: str,
    result: DiagnosticRepairResult,
    log: TextIO | None,
) -> None:
    for event in result.events:
        _write(
            log,
            {
                "record_type": "pi_event",
                **meta.record(),
                "task": task.name,
                "difficulty": task.difficulty,
                "arm": arm,
                "pi_run_id": result.run_id,
                "sequence": event.sequence,
                "kind": event.kind,
                "attempt": event.attempt,
                "elapsed_ms": event.elapsed_ms,
                "candidate_fingerprint": event.candidate_fingerprint,
                "diagnostic_fingerprint": event.diagnostic_fingerprint,
                "status": event.status,
                "score": event.score,
                "detail_sha256": _sha256(event.detail),
            },
        )
    _write(
        log,
        {
            "record_type": "pi_stop",
            **meta.record(),
            "task": task.name,
            "difficulty": task.difficulty,
            "arm": arm,
            "pi_run_id": result.run_id,
            "stop": result.stop.value,
            "verified": result.verified,
            "improved": result.improved,
            "evaluations": result.evaluations,
            "repairs": result.repairs,
            "elapsed_ms": result.elapsed_ms,
            "reported_input_tokens": result.reported_input_tokens,
            "reported_output_tokens": result.reported_output_tokens,
            "best_attempt": result.best.index,
            "current_attempt": result.current.index,
            "event_count": len(result.events),
            "stop_detail_sha256": _sha256(result.stop_detail),
        },
    )


def _run_pi_repair(
    meta: RunMeta,
    task: LeanTask,
    complete: Any,
    evaluate_fn: Any,
    log: TextIO | None,
    *,
    decoy: bool,
    tasks: tuple[LeanTask, ...],
) -> ArmOutcome:
    arm = "pi_decoy" if decoy else "pi_repair"
    decoy_text, setup_calls = (
        _decoy_diagnostic(meta, task, tasks, evaluate_fn, log)
        if decoy and meta.k > 1
        else (None, 0)
    )
    pi_run_id = f"{meta.run_id}:{task.name}:{arm}"
    oracle = _PiLeanOracle(meta, task, arm, evaluate_fn, pi_run_id, log)

    seed_proof = legacy._gen(task, complete, meta.seed_offset)
    input_tokens, output_tokens, response_model_id = _usage(complete)
    oracle.set_pending(
        PendingAttempt(
            attempt=1,
            seed=meta.seed_offset,
            used_feedback=False,
            supplied_feedback="",
            feedback_source="none",
            prior_proof=None,
            proof=seed_proof,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_model_id=response_model_id,
        )
    )
    repair = _PiRepairGenerator(
        task=task,
        complete=complete,
        seed_offset=meta.seed_offset,
        oracle=oracle,
        decoy=decoy_text,
    )
    result = diagnostic_repair(
        seed_proof,
        repair,
        oracle,
        max_attempts=meta.k - 1,
        max_evaluations=meta.k,
        max_wall_seconds=None,
        max_repeated_states=max(1, meta.k),
        run_id=pi_run_id,
    )
    if oracle.pending is not None:
        raise RuntimeError("PI loop stopped after generation without consuming its candidate")
    _emit_pi_lifecycle(meta, task, arm, result, log)
    return ArmOutcome(
        proven=result.verified,
        graded_score=max(
            (float(item["graded_score"]) for item in oracle.records),
            default=0.0,
        ),
        attempts=tuple(oracle.records),
        pi_stop=result.stop.value,
        setup_oracle_calls=setup_calls,
    )


def _run_plain_baseline(
    meta: RunMeta,
    task: LeanTask,
    complete: Any,
    evaluate_fn: Any,
    log: TextIO | None,
) -> ArmOutcome:
    records: list[dict[str, Any]] = []
    transcript: list[tuple[str, str]] = []
    for index in range(meta.k):
        seed = meta.seed_offset + index
        proof = legacy._extract_proof(complete(legacy._plain_prompt(task, transcript), seed))
        input_tokens, output_tokens, response_model_id = _usage(complete)
        pending = PendingAttempt(
            attempt=index + 1,
            seed=seed,
            used_feedback=bool(transcript),
            supplied_feedback=transcript[-1][1] if transcript else "",
            feedback_source="real" if transcript else "none",
            prior_proof=transcript[-1][0] if transcript else None,
            proof=proof,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_model_id=response_model_id,
        )
        verdict, record = _evaluate_attempt(meta, task, "plain_baseline", pending, evaluate_fn, log)
        records.append(record)
        if verdict.proven:
            break
        transcript.append((proof, verdict.error_tail))
    return _outcome(records)


def _subset_summary(
    rows: list[dict[str, ArmOutcome]],
) -> dict[str, Any]:
    summary: dict[str, Any] = {"of": len(rows)}
    for arm in ARMS:
        outcomes = [row[arm] for row in rows]
        summary[arm] = sum(1 for outcome in outcomes if outcome.proven)
        summary[f"graded_{arm}"] = round(
            sum(outcome.graded_score for outcome in outcomes),
            6,
        )
        summary[f"model_calls_{arm}"] = sum(
            outcome.summary()["model_calls"] for outcome in outcomes
        )
        summary[f"oracle_calls_{arm}"] = sum(
            outcome.summary()["oracle_calls"] for outcome in outcomes
        )
        summary[f"setup_oracle_calls_{arm}"] = sum(
            outcome.setup_oracle_calls for outcome in outcomes
        )
        summary[f"input_tokens_{arm}"] = sum(
            outcome.summary()["input_tokens"] for outcome in outcomes
        )
        summary[f"output_tokens_{arm}"] = sum(
            outcome.summary()["output_tokens"] for outcome in outcomes
        )
    return summary


def _run_id(seed_offset: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return f"pi-diagnostic-repair-{stamp}-{uuid.uuid4().hex[:8]}-seed-{seed_offset}"


def run_once(
    complete: Any,
    backend: str,
    *,
    k: int,
    seed_offset: int,
    log: TextIO | None = None,
    run_id: str | None = None,
    tasks: tuple[LeanTask, ...] | None = None,
    evaluate_fn: Any | None = None,
    include_payloads: bool = True,
    git_provenance: dict[str, Any] | None = None,
    run_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if type(k) is not int or k < 1:
        raise ValueError("k must be >= 1")
    if type(include_payloads) is not bool:
        raise TypeError("include_payloads must be a bool")
    selected_tasks = tuple(lean_tasks.TASKS if tasks is None else tasks)
    if not selected_tasks:
        raise ValueError("at least one Lean task is required")
    if len({task.name for task in selected_tasks}) != len(selected_tasks):
        raise ValueError("Lean task names must be unique")
    resolved_evaluator = evaluate_fn
    sandbox_hash = "0" * 64
    compiler_identity = lean_oracle.LeanCompilerIdentity(
        toolchain="injected-test-toolchain",
        version="injected-test-version",
        binary_sha256="0" * 64,
    )
    if resolved_evaluator is None:
        sandbox_evaluator = lean_oracle.ExternalSandboxLeanEvaluator.from_environment()
        resolved_evaluator = sandbox_evaluator
        sandbox_hash = sandbox_evaluator.runner_sha256
        compiler_identity = sandbox_evaluator.compiler_identity
    if run_metadata is None:
        metadata = _environment_run_metadata(
            backend,
            sandbox_runner_sha256=sandbox_hash,
            lean_toolchain=compiler_identity.toolchain,
            lean_version=compiler_identity.version,
            lean_binary_sha256=compiler_identity.binary_sha256,
        )
        if evaluate_fn is not None:
            metadata["oracle_isolation"] = "injected-evaluator/test-only"
    else:
        metadata = dict(run_metadata)
    if set(metadata) != _RUN_METADATA_KEYS:
        raise ValueError("run_metadata has an invalid field set")
    meta = RunMeta(
        run_id=run_id or _run_id(seed_offset),
        backend=backend,
        k=k,
        seed_offset=seed_offset,
        include_payloads=include_payloads,
        model_id=str(metadata["model_id"]),
        endpoint_class=str(metadata["endpoint_class"]),
        endpoint_fingerprint=str(metadata["endpoint_fingerprint"]),
        temperature=float(metadata["temperature"]),
        max_tokens_per_attempt=int(metadata["max_tokens_per_attempt"]),
        oracle_isolation=str(metadata["oracle_isolation"]),
        sandbox_runner_sha256=str(metadata["sandbox_runner_sha256"]),
        lean_toolchain=str(metadata["lean_toolchain"]),
        lean_version=str(metadata["lean_version"]),
        lean_binary_sha256=str(metadata["lean_binary_sha256"]),
        timestamp_utc=str(metadata["timestamp_utc"]),
    )
    provenance = _git_provenance() if git_provenance is None else dict(git_provenance)
    if set(provenance) != {"git_commit", "git_dirty", "git_status_sha256"}:
        raise ValueError("git_provenance has an invalid field set")
    if type(provenance["git_dirty"]) is not bool:
        raise TypeError("git_provenance.git_dirty must be a bool")
    commit = provenance["git_commit"]
    status_hash = provenance["git_status_sha256"]
    if not (
        isinstance(commit, str)
        and len(commit) in (40, 64)
        and all(char in "0123456789abcdefABCDEF" for char in commit)
    ):
        raise ValueError("git_provenance.git_commit must be a git object id")
    if not (
        isinstance(status_hash, str)
        and len(status_hash) == 64
        and all(char in "0123456789abcdefABCDEF" for char in status_hash)
    ):
        raise ValueError("git_provenance.git_status_sha256 must be a SHA-256 digest")
    _write(
        log,
        {
            "record_type": "run_start",
            **meta.record(),
            "n_tasks": len(selected_tasks),
            "arms": list(ARMS),
            "arm_order_policy": ARM_ORDER_POLICY,
            "tasks": [
                {
                    "name": task.name,
                    "difficulty": task.difficulty,
                    "task_sha256": _task_sha256(task),
                }
                for task in selected_tasks
            ],
            "artifact_hashes": _artifact_hashes(),
            **provenance,
        },
    )

    rows: list[dict[str, ArmOutcome]] = []
    for task_index, task in enumerate(selected_tasks):
        rotation = (seed_offset + task_index) % len(ARMS)
        arm_order = ARMS[rotation:] + ARMS[:rotation]
        outcomes: dict[str, ArmOutcome] = {}
        for arm in arm_order:
            if arm == "single":
                outcome = _run_single(meta, task, complete, resolved_evaluator, log)
            elif arm == "bestN":
                outcome = _run_bestn(meta, task, complete, resolved_evaluator, log)
            elif arm == "legacy_repair":
                outcome = _run_legacy_repair(meta, task, complete, resolved_evaluator, log)
            elif arm == "pi_repair":
                outcome = _run_pi_repair(
                    meta,
                    task,
                    complete,
                    resolved_evaluator,
                    log,
                    decoy=False,
                    tasks=selected_tasks,
                )
            elif arm == "pi_decoy":
                outcome = _run_pi_repair(
                    meta,
                    task,
                    complete,
                    resolved_evaluator,
                    log,
                    decoy=True,
                    tasks=selected_tasks,
                )
            else:
                outcome = _run_plain_baseline(meta, task, complete, resolved_evaluator, log)
            outcomes[arm] = outcome
        rows.append(outcomes)
        _write(
            log,
            {
                "record_type": "task_summary",
                **meta.record(),
                "task": task.name,
                "difficulty": task.difficulty,
                "task_sha256": _task_sha256(task),
                "arm_order": list(arm_order),
                "arms": {arm: outcomes[arm].summary() for arm in ARMS},
            },
        )

    all_summary = _subset_summary(rows)
    headroom_summary = _subset_summary(
        [
            outcomes
            for task, outcomes in zip(selected_tasks, rows, strict=True)
            if task.difficulty == "headroom"
        ]
    )
    result = {
        **meta.record(),
        "n_tasks": len(rows),
        "n_headroom": headroom_summary["of"],
        "all": all_summary,
        "headroom_only": headroom_summary,
    }
    _write(log, {"record_type": "run_summary", **result})
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the exact six-arm Lean diagnostic-repair harness."
    )
    parser.add_argument("--k", type=int, default=int(os.environ.get("LEAN_K", "4")))
    parser.add_argument(
        "--replications",
        type=int,
        default=int(os.environ.get("LEAN_REPLICATIONS", "1")),
    )
    parser.add_argument(
        "--seed-offset",
        type=int,
        default=int(os.environ.get("SEED_OFFSET", "0")),
    )
    parser.add_argument(
        "--seed-step",
        type=int,
        default=int(os.environ.get("LEAN_SEED_STEP", "10")),
    )
    parser.add_argument("--out-dir", default=os.environ.get("LEAN_OUT_DIR"))
    parser.add_argument(
        "--redact-payloads",
        action="store_true",
        help="Omit raw replay payloads; redacted runs cannot pass P5.",
    )
    parser.add_argument(
        "--execute-frozen-run",
        action="store_true",
        help="Acknowledge execution of the exact manifest-frozen claim-bearing design.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.k < 1 or args.replications < 1:
        print("[pi-diagnostic-repair] --k and --replications must be >= 1.")
        return 2
    if not args.execute_frozen_run:
        print("[pi-diagnostic-repair] --execute-frozen-run acknowledgement is required.")
        return 2
    if args.redact_payloads:
        print("[pi-diagnostic-repair] frozen claim-bearing runs require full payloads.")
        return 2
    forbidden_overrides = [
        key
        for key in ("BHGMAN_LLM_ENDPOINTS", "BHGMAN_LLM_NO_THINK")
        if os.environ.get(key)
    ]
    if forbidden_overrides:
        print(
            "[pi-diagnostic-repair] frozen runs forbid semantic endpoint overrides: "
            + ", ".join(forbidden_overrides)
        )
        return 2
    try:
        sandbox_evaluator = lean_oracle.ExternalSandboxLeanEvaluator.from_environment()
    except (lean_oracle.SandboxUnavailable, lean_oracle.SandboxProtocolError) as exc:
        print(f"[pi-diagnostic-repair] sandbox unavailable: {exc}")
        return 2
    provenance = _git_provenance()
    if provenance["git_dirty"]:
        print("[pi-diagnostic-repair] git worktree is dirty; frozen execution refused.")
        return 2
    complete, backend = legacy._make_complete()
    base_metadata = _environment_run_metadata(
        backend,
        sandbox_runner_sha256=sandbox_evaluator.runner_sha256,
        lean_toolchain=sandbox_evaluator.lean_toolchain,
        lean_version=sandbox_evaluator.lean_version,
        lean_binary_sha256=sandbox_evaluator.lean_binary_sha256,
    )
    selected_tasks = tuple(lean_tasks.TASKS)
    try:
        _assert_frozen_run_design(
            manifest_path=_FROZEN_MANIFEST,
            backend=backend,
            metadata=base_metadata,
            k=args.k,
            replications=args.replications,
            seed_offset=args.seed_offset,
            seed_step=args.seed_step,
            tasks=selected_tasks,
        )
    except RuntimeError as exc:
        print(f"[pi-diagnostic-repair] frozen-run preflight failed: {exc}")
        return 2
    out_dir = Path(args.out_dir) if args.out_dir else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, Any]] = []
    for replication in range(args.replications):
        seed_offset = args.seed_offset + replication * args.seed_step
        run_id = _run_id(seed_offset)
        run_metadata = {
            **base_metadata,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        if out_dir is None:
            summaries.append(
                run_once(
                    complete,
                    backend,
                    k=args.k,
                    seed_offset=seed_offset,
                    run_id=run_id,
                    evaluate_fn=sandbox_evaluator,
                    include_payloads=not args.redact_payloads,
                    git_provenance=provenance,
                    run_metadata=run_metadata,
                )
            )
            continue
        path = out_dir / f"{run_id}.jsonl"
        with path.open("x", encoding="utf-8") as log:
            summaries.append(
                run_once(
                    complete,
                    backend,
                    k=args.k,
                    seed_offset=seed_offset,
                    log=log,
                    run_id=run_id,
                    evaluate_fn=sandbox_evaluator,
                    include_payloads=not args.redact_payloads,
                    git_provenance=provenance,
                    run_metadata=run_metadata,
                )
            )
        print(f"[pi-diagnostic-repair] new_jsonl={path}")
    print(json.dumps({"replications": len(summaries), "runs": summaries}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ARMS",
    "ARM_ORDER_POLICY",
    "HARNESS_VERSION",
    "SCHEMA",
    "main",
    "run_once",
]
