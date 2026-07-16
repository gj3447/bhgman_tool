"""Fail-closed analysis gate for the six-arm diagnostic-repair harness.

The analyzer deliberately consumes a narrow, versioned JSONL contract.  It does not infer absent
arms, fabricate hidden token usage, or turn an under-powered band into a negative efficacy result.
The treatment is ``pi_repair``; controls are ``legacy_repair``, ``bestN``, ``pi_decoy``, and
``plain_baseline``.  ``single`` is retained as the competence-floor reference.

The P1-P5 gate mirrors ``PIERCE_PREREGISTRATION.md`` while adding two migration checks:

* every treatment comparison is reported at both the run and task pairing levels;
* the primary edge is recomputed after truncating each paired trajectory to the smaller cumulative
  token budget, so early exit or overspend cannot manufacture the result.

This is an L_RT experiment harness: deterministic contract validation supplies Constrain/Verify,
and the returned gate reasons supply Correct.  It is measurement machinery, not itself evidence of
cognitive efficacy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from engine.efficacy import lean_oracle, lean_tasks
from engine.legion.diagnostic_repair import candidate_fingerprint
from engine.naesengmoon.diagnostic_oracle import feedback_from_value

SCHEMA = "pi-diagnostic-repair-harness/v2"
MANIFEST_SCHEMA = "pi-diagnostic-repair-harness-manifest/v2"
DEFAULT_MANIFEST_PATH = Path(__file__).with_name("diagnostic_repair_harness_manifest.v2.json")
ARMS = (
    "single",
    "bestN",
    "legacy_repair",
    "pi_repair",
    "pi_decoy",
    "plain_baseline",
)
COMPARATORS = ("legacy_repair", "bestN", "pi_decoy", "plain_baseline")
MANIFEST_ARTIFACT_KEYS = (
    "runner",
    "analyzer",
    "diagnostic_repair",
    "diagnostic_oracle",
    "agent_client",
    "agent_runtime",
    "lean_headroom_run",
    "lean_tasks",
    "lean_oracle",
    "loop_contract",
    "fsm",
    "fsm_traces",
    "lean_sandbox_runner_macos",
    "lean_toolchain",
)
ARTIFACT_HASH_KEYS = (
    *MANIFEST_ARTIFACT_KEYS,
    "manifest",
    "preregistration_v2",
)
ARM_ORDER_POLICY = "cyclic_rotation:(seed_offset+task_index)%6"
ORACLE_ISOLATION = "external-sandbox-runner/v2"
LEAN_TOOLCHAIN = "leanprover/lean4:v4.27.0"
LEAN_VERSION = (
    "Lean (version 4.27.0, arm64-apple-darwin24.6.0, "
    "commit db93fe1608548721853390a10cd40580fe7d22ae, Release)"
)
LEAN_BINARY_SHA256 = "2974847fff2e2621502841f4c2dbac4035b4847d6060a4f2087cbc0d04005e37"
USAGE_KEYS = ("input_tokens", "output_tokens", "model_calls", "oracle_calls")
_HEX = frozenset("0123456789abcdefABCDEF")
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
_REPAIR_REQUESTED_SHA256 = hashlib.sha256(
    b"bounded diagnostic supplied to repair generator"
).hexdigest()
_MIN_SIGN_NON_TIES = 6
_FROZEN_THRESHOLDS = {
    "alpha": 0.05,
    "tost_margin": 1.0,
    "parity_low": 0.8,
    "parity_high": 1.25,
    "min_live_tasks": 6,
    "top_task_concentration": 0.5,
}
_FROZEN_RUN_DESIGN = {
    "backend": "frontier:qwen2.5:32b-instruct",
    "model_id": "qwen2.5:32b-instruct",
    "endpoint_class": "openai-compatible",
    "temperature": 0.8,
    "max_tokens_per_attempt": 3072,
    "oracle_isolation": ORACLE_ISOLATION,
    "lean_toolchain": LEAN_TOOLCHAIN,
    "lean_version": LEAN_VERSION,
    "lean_binary_sha256": LEAN_BINARY_SHA256,
    "k": 4,
    "replications": 10,
    "seed_offsets": list(range(0, 100, 10)),
}


class ContractError(ValueError):
    """The raw batch is incomplete, internally inconsistent, or not the frozen v2 contract."""


@dataclass(frozen=True)
class Attempt:
    """One model-generation/oracle-evaluation step from the raw JSONL."""

    run_id: str
    task: str
    difficulty: str
    arm: str
    index: int
    seed: int
    proven: bool
    compiles: bool
    sorry_tainted: bool
    graded_score: float
    response_model_id: str
    response_model_observed: bool
    used_feedback: bool
    feedback_source: str
    proof_sha256: str
    diagnostic_sha256: str
    supplied_feedback_sha256: str
    prior_proof_sha256: str
    proof: str | None
    diagnostic: str | None
    supplied_feedback: str | None
    pi_run_id: str
    input_tokens: int
    output_tokens: int
    model_calls: int
    oracle_calls: int
    raw_payload_complete: bool

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class DecoySetup:
    """One setup-only mismatched-proof oracle evaluation for ``pi_decoy``."""

    run_id: str
    task: str
    difficulty: str
    source_task: str
    source_task_sha256: str
    source_reference_proof_sha256: str
    compiles: bool
    proven: bool
    sorry_tainted: bool
    graded_score: float
    oracle_diagnostic: str
    oracle_diagnostic_sha256: str
    decoy_seed_diagnostic: str
    decoy_seed_diagnostic_sha256: str


@dataclass
class Run:
    """Validated paired observations for one seed."""

    run_id: str
    backend: str
    model_id: str
    endpoint_class: str
    endpoint_fingerprint: str
    temperature: float
    max_tokens_per_attempt: int
    oracle_isolation: str
    sandbox_runner_sha256: str
    lean_toolchain: str
    lean_version: str
    lean_binary_sha256: str
    k: int
    seed_offset: int
    timestamp_utc: str
    harness_version: str
    payload_mode: str
    git_commit: str
    git_dirty: bool
    git_status_sha256: str
    artifact_hashes: dict[str, str]
    task_summaries: dict[str, dict[str, Any]]
    attempts: dict[tuple[str, str], list[Attempt]]
    decoy_setups: dict[str, DecoySetup]
    task_order: list[str]
    difficulties: dict[str, str]
    task_hashes: dict[str, str]


@dataclass(frozen=True)
class RunStart:
    run_id: str
    backend: str
    model_id: str
    endpoint_class: str
    endpoint_fingerprint: str
    temperature: float
    max_tokens_per_attempt: int
    oracle_isolation: str
    sandbox_runner_sha256: str
    lean_toolchain: str
    lean_version: str
    lean_binary_sha256: str
    k: int
    seed_offset: int
    timestamp_utc: str
    harness_version: str
    payload_mode: str
    artifact_hashes: dict[str, str]
    task_order: list[str]
    task_difficulties: dict[str, str]
    task_hashes: dict[str, str]
    git_commit: str
    git_dirty: bool
    git_status_sha256: str


def sign_test_two_sided(wins: int, losses: int) -> float:
    """Exact two-sided binomial sign test under p=0.5, ignoring ties."""
    if wins < 0 or losses < 0:
        raise ValueError("wins and losses must be non-negative")
    n = wins + losses
    if n == 0:
        return 1.0
    extreme = max(wins, losses)
    tail = sum(math.comb(n, k) for k in range(extreme, n + 1)) / (2**n)
    return min(1.0, 2.0 * tail)


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Numerical Recipes continued fraction for the incomplete beta function."""
    max_iterations = 300
    epsilon = 3e-14
    floor = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < floor:
        d = floor
    d = 1.0 / d
    value = d
    for iteration in range(1, max_iterations + 1):
        even = 2 * iteration
        coefficient = iteration * (b - iteration) * x / ((qam + even) * (a + even))
        d = 1.0 + coefficient * d
        if abs(d) < floor:
            d = floor
        c = 1.0 + coefficient / c
        if abs(c) < floor:
            c = floor
        d = 1.0 / d
        value *= d * c
        coefficient = -(a + iteration) * (qab + iteration) * x / ((a + even) * (qap + even))
        d = 1.0 + coefficient * d
        if abs(d) < floor:
            d = floor
        c = 1.0 + coefficient / c
        if abs(c) < floor:
            c = floor
        d = 1.0 / d
        delta = d * c
        value *= delta
        if abs(delta - 1.0) < epsilon:
            return value
    raise ArithmeticError("incomplete-beta continued fraction did not converge")


def _regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    if not 0.0 <= x <= 1.0 or a <= 0.0 or b <= 0.0:
        raise ValueError("regularized incomplete beta domain error")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    factor = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return factor * _beta_continued_fraction(a, b, x) / a
    return 1.0 - factor * _beta_continued_fraction(b, a, 1.0 - x) / b


def _student_t_cdf(value: float, degrees_of_freedom: int) -> float:
    """Student-t CDF using the regularized incomplete beta identity."""
    if degrees_of_freedom < 1:
        raise ValueError("degrees_of_freedom must be >= 1")
    if value == 0.0:
        return 0.5
    x = degrees_of_freedom / (degrees_of_freedom + value * value)
    tail = 0.5 * _regularized_incomplete_beta(x, degrees_of_freedom / 2.0, 0.5)
    return 1.0 - tail if value > 0 else tail


def tost_equivalence(
    deltas: Sequence[float], *, margin: float, alpha: float = 0.05
) -> dict[str, Any]:
    """Paired TOST for a mean delta within ``(-margin, +margin)``.

    The implementation is dependency-free and uses paired Student-t one-sided tests.  Fewer than
    three runs is explicitly ``ABSENT`` rather than equivalent.
    """
    if margin <= 0:
        raise ValueError("TOST margin must be > 0")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    n = len(deltas)
    mean_delta = sum(deltas) / n if n else 0.0
    result: dict[str, Any] = {
        "method": "paired-student-t-tost",
        "n": n,
        "margin": margin,
        "alpha": alpha,
        "mean_delta": round(mean_delta, 6),
        "small_n_caveat": n < 15,
    }
    if n < 3:
        result.update(
            {
                "status": "ABSENT",
                "equivalent": False,
                "p_lower": None,
                "p_upper": None,
                "reason": "fewer than 3 paired runs",
            }
        )
        return result
    variance = sum((delta - mean_delta) ** 2 for delta in deltas) / (n - 1)
    se = math.sqrt(variance / n)
    if se == 0:
        equivalent = abs(mean_delta) < margin
        result.update(
            {
                "status": "PASS" if equivalent else "FAIL",
                "equivalent": equivalent,
                "p_lower": 0.0 if equivalent else 1.0,
                "p_upper": 0.0 if equivalent else 1.0,
                "standard_error": 0.0,
            }
        )
        return result
    degrees_of_freedom = n - 1
    p_lower = 1.0 - _student_t_cdf((mean_delta + margin) / se, degrees_of_freedom)
    p_upper = _student_t_cdf((mean_delta - margin) / se, degrees_of_freedom)
    equivalent = p_lower < alpha and p_upper < alpha
    result.update(
        {
            "status": "PASS" if equivalent else "FAIL",
            "equivalent": equivalent,
            "p_lower": round(p_lower, 8),
            "p_upper": round(p_upper, 8),
            "standard_error": round(se, 6),
            "degrees_of_freedom": degrees_of_freedom,
        }
    )
    return result


def _jsonl_files(paths: Iterable[str | Path]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(path.glob("*.jsonl")))
        elif path.is_file():
            files.append(path)
        else:
            raise ContractError(f"input path does not exist: {path}")
    unique = list(dict.fromkeys(path.resolve() for path in files))
    if not unique:
        raise ContractError("no JSONL files found")
    return unique


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _lean_task_sha256(task: lean_tasks.LeanTask) -> str:
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
    return hashlib.sha256(canonical.encode("utf-8", "replace")).hexdigest()


def _frozen_lean_task_band() -> list[dict[str, str]]:
    return [
        {
            "name": task.name,
            "difficulty": task.difficulty,
            "task_sha256": _lean_task_sha256(task),
        }
        for task in lean_tasks.TASKS
    ]


def _decoy_source_binding(task_name: str, _start: RunStart) -> dict[str, str]:
    tasks = list(lean_tasks.TASKS)
    try:
        index = next(index for index, task in enumerate(tasks) if task.name == task_name)
    except StopIteration as exc:
        raise ContractError(f"frozen lean_tasks has no decoy target {task_name!r}") from exc
    source = tasks[(index + 1) % len(tasks)]
    return {
        "source_task": source.name,
        "source_task_sha256": _lean_task_sha256(source),
        "source_reference_proof_sha256": hashlib.sha256(
            source.reference_proof.encode("utf-8", "replace")
        ).hexdigest(),
    }


def _fit_decoy(seed_diagnostic: str, real_diagnostic: str) -> str:
    target_length = len(real_diagnostic)
    if target_length <= 0:
        return ""
    marker = seed_diagnostic or "DECOY"
    repeats = (target_length + len(marker) - 1) // len(marker)
    fitted = (marker * repeats)[:target_length]
    if fitted == real_diagnostic:
        replacement = "X" if fitted[0] != "X" else "Y"
        fitted = replacement + fitted[1:]
    return fitted


def _load_manifest(path: Path) -> dict[str, Any]:
    """Load the frozen manifest and verify each declared local artifact against disk."""
    if not path.is_file():
        raise ContractError(f"frozen manifest not found: {path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(f"{path}: invalid manifest JSON: {exc.msg}") from exc
    if not isinstance(manifest, dict):
        raise ContractError(f"{path}: manifest must be a JSON object")
    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("status") != "frozen":
        raise ContractError(f"{path}: manifest schema/status is not the frozen v2 contract")
    harness_version = manifest.get("harness_version")
    if not isinstance(harness_version, str) or not harness_version:
        raise ContractError(f"{path}: harness_version must be a non-empty string")
    thresholds = manifest.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ContractError(f"{path}: thresholds must be an object")
    required_thresholds = {
        "alpha",
        "tost_margin",
        "parity_low",
        "parity_high",
        "min_live_tasks",
        "top_task_concentration",
    }
    if set(thresholds) != required_thresholds:
        raise ContractError(
            f"{path}: thresholds must contain exactly {sorted(required_thresholds)!r}"
        )
    normalized_thresholds = {
        "alpha": _finite_number(thresholds["alpha"], label=f"{path}.thresholds.alpha"),
        "tost_margin": _finite_number(
            thresholds["tost_margin"], label=f"{path}.thresholds.tost_margin"
        ),
        "parity_low": _finite_number(
            thresholds["parity_low"], label=f"{path}.thresholds.parity_low"
        ),
        "parity_high": _finite_number(
            thresholds["parity_high"], label=f"{path}.thresholds.parity_high"
        ),
        "min_live_tasks": _strict_int(
            thresholds["min_live_tasks"],
            label=f"{path}.thresholds.min_live_tasks",
            minimum=1,
        ),
        "top_task_concentration": _finite_number(
            thresholds["top_task_concentration"],
            label=f"{path}.thresholds.top_task_concentration",
        ),
    }
    if normalized_thresholds != _FROZEN_THRESHOLDS:
        raise ContractError(
            f"{path}: thresholds differ from the frozen v2 values {_FROZEN_THRESHOLDS!r}"
        )
    run_design = manifest.get("run_design")
    run_design_keys = {*_FROZEN_RUN_DESIGN, "task_band"}
    if not isinstance(run_design, dict) or set(run_design) != run_design_keys:
        raise ContractError(f"{path}: run_design must contain exactly {sorted(run_design_keys)!r}")
    normalized_run_design: dict[str, Any] = {
        "backend": run_design["backend"],
        "model_id": run_design["model_id"],
        "endpoint_class": run_design["endpoint_class"],
        "temperature": _finite_number(
            run_design["temperature"], label=f"{path}.run_design.temperature"
        ),
        "max_tokens_per_attempt": _strict_int(
            run_design["max_tokens_per_attempt"],
            label=f"{path}.run_design.max_tokens_per_attempt",
            minimum=1,
        ),
        "oracle_isolation": run_design["oracle_isolation"],
        "lean_toolchain": run_design["lean_toolchain"],
        "lean_version": run_design["lean_version"],
        "lean_binary_sha256": run_design["lean_binary_sha256"],
        "k": _strict_int(run_design["k"], label=f"{path}.run_design.k", minimum=1),
        "replications": _strict_int(
            run_design["replications"],
            label=f"{path}.run_design.replications",
            minimum=1,
        ),
    }
    raw_seed_offsets = run_design["seed_offsets"]
    if not isinstance(raw_seed_offsets, list):
        raise ContractError(f"{path}: run_design.seed_offsets must be a list")
    normalized_run_design["seed_offsets"] = [
        _strict_int(value, label=f"{path}.run_design.seed_offsets[{index}]")
        for index, value in enumerate(raw_seed_offsets)
    ]
    if not _is_sha256(normalized_run_design["lean_binary_sha256"]):
        raise ContractError(f"{path}: run_design.lean_binary_sha256 must be a SHA-256 digest")
    for key, frozen_value in _FROZEN_RUN_DESIGN.items():
        if normalized_run_design[key] != frozen_value:
            raise ContractError(
                f"{path}: run_design.{key}={normalized_run_design[key]!r} "
                f"!= frozen {frozen_value!r}"
            )
    raw_task_band = run_design["task_band"]
    if not isinstance(raw_task_band, list) or not raw_task_band:
        raise ContractError(f"{path}: run_design.task_band must be a non-empty list")
    task_band: list[dict[str, str]] = []
    seen_tasks: set[str] = set()
    for index, task in enumerate(raw_task_band):
        if not isinstance(task, dict) or set(task) != {
            "name",
            "difficulty",
            "task_sha256",
        }:
            raise ContractError(
                f"{path}: run_design.task_band[{index}] must contain name, difficulty, task_sha256"
            )
        name, difficulty, task_hash = (
            task["name"],
            task["difficulty"],
            task["task_sha256"],
        )
        if not isinstance(name, str) or not name or name in seen_tasks:
            raise ContractError(
                f"{path}: run_design.task_band[{index}].name is empty or duplicated"
            )
        if not isinstance(difficulty, str) or not difficulty:
            raise ContractError(
                f"{path}: run_design.task_band[{index}].difficulty must be non-empty"
            )
        if not _is_sha256(task_hash):
            raise ContractError(
                f"{path}: run_design.task_band[{index}].task_sha256 must be a SHA-256 digest"
            )
        seen_tasks.add(name)
        task_band.append(
            {
                "name": name,
                "difficulty": difficulty,
                "task_sha256": str(task_hash).lower(),
            }
        )
    frozen_task_band = _frozen_lean_task_band()
    if task_band != frozen_task_band:
        raise ContractError(
            f"{path}: run_design.task_band differs from the exact frozen lean_tasks.TASKS band"
        )
    normalized_run_design["task_band"] = task_band
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(MANIFEST_ARTIFACT_KEYS):
        raise ContractError(
            f"{path}: artifacts must contain exactly {list(MANIFEST_ARTIFACT_KEYS)!r}"
        )
    repo_root = path.resolve().parents[2]
    artifact_hashes: dict[str, str] = {}
    artifact_paths: dict[str, str] = {}
    artifact_relative_paths: dict[str, str] = {}
    for name in MANIFEST_ARTIFACT_KEYS:
        entry = artifacts[name]
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise ContractError(f"{path}: artifacts.{name} must contain path and sha256")
        relative_path, declared_hash = entry["path"], entry["sha256"]
        if not isinstance(relative_path, str) or not relative_path:
            raise ContractError(f"{path}: artifacts.{name}.path must be non-empty")
        if not _is_sha256(declared_hash):
            raise ContractError(f"{path}: artifacts.{name}.sha256 must be a SHA-256 digest")
        artifact_path = (repo_root / relative_path).resolve()
        if artifact_path != repo_root and repo_root not in artifact_path.parents:
            raise ContractError(f"{path}: artifacts.{name}.path escapes repository root")
        if not artifact_path.is_file():
            raise ContractError(f"{path}: artifacts.{name}.path does not exist: {artifact_path}")
        if name == "analyzer" and artifact_path != Path(__file__).resolve():
            raise ContractError(f"{path}: artifacts.analyzer.path must point to this analyzer")
        actual_hash = _sha256_file(artifact_path)
        if actual_hash != str(declared_hash).lower():
            raise ContractError(
                f"{path}: artifacts.{name} hash drift: declared {declared_hash}, actual {actual_hash}"
            )
        artifact_hashes[name] = actual_hash
        artifact_paths[name] = str(artifact_path)
        artifact_relative_paths[name] = relative_path
    prereg_relative = manifest.get("preregistration_v2_path")
    if not isinstance(prereg_relative, str) or not prereg_relative:
        raise ContractError(f"{path}: preregistration_v2_path must be non-empty")
    prereg_path = (repo_root / prereg_relative).resolve()
    if prereg_path != repo_root and repo_root not in prereg_path.parents:
        raise ContractError(f"{path}: preregistration_v2_path escapes repository root")
    if not prereg_path.is_file():
        raise ContractError(f"{path}: preregistration v2 file does not exist: {prereg_path}")
    bridge = manifest.get("bridge_conformance")
    if not isinstance(bridge, dict) or set(bridge) != {"path", "sha256", "pytest_nodeid"}:
        raise ContractError(
            f"{path}: bridge_conformance must contain path, sha256, and pytest_nodeid"
        )
    bridge_relative, bridge_hash, bridge_nodeid = (
        bridge["path"],
        bridge["sha256"],
        bridge["pytest_nodeid"],
    )
    if not isinstance(bridge_relative, str) or not bridge_relative:
        raise ContractError(f"{path}: bridge_conformance.path must be non-empty")
    if not _is_sha256(bridge_hash):
        raise ContractError(f"{path}: bridge_conformance.sha256 must be a SHA-256 digest")
    if not isinstance(bridge_nodeid, str) or bridge_nodeid != (
        f"{bridge_relative}::test_legacy_and_pi_repair_have_equivalent_generation_and_oracle_traces"
    ):
        raise ContractError(f"{path}: bridge_conformance.pytest_nodeid is not the frozen B1 test")
    bridge_path = (repo_root / bridge_relative).resolve()
    if bridge_path != repo_root and repo_root not in bridge_path.parents:
        raise ContractError(f"{path}: bridge_conformance.path escapes repository root")
    if not bridge_path.is_file():
        raise ContractError(f"{path}: bridge conformance test does not exist: {bridge_path}")
    actual_bridge_hash = _sha256_file(bridge_path)
    if actual_bridge_hash != str(bridge_hash).lower():
        raise ContractError(
            f"{path}: bridge conformance hash drift: "
            f"declared {bridge_hash}, actual {actual_bridge_hash}"
        )
    return {
        "path": str(path.resolve()),
        "sha256": _sha256_file(path.resolve()),
        "harness_version": harness_version,
        "thresholds": normalized_thresholds,
        "run_design": normalized_run_design,
        "repo_root": str(repo_root),
        "artifact_hashes": artifact_hashes,
        "artifact_paths": artifact_paths,
        "artifact_relative_paths": artifact_relative_paths,
        "manifest_relative_path": str(path.resolve().relative_to(repo_root)),
        "preregistration_v2_path": str(prereg_path),
        "preregistration_v2_relative_path": prereg_relative,
        "preregistration_v2_sha256": _sha256_file(prereg_path),
        "bridge_conformance": {
            "path": str(bridge_path),
            "relative_path": bridge_relative,
            "sha256": actual_bridge_hash,
            "pytest_nodeid": bridge_nodeid,
        },
    }


def _temporal_provenance_checks(
    *,
    commit_timestamp_epoch: int,
    run_timestamps: Sequence[str],
    jsonl_paths: Sequence[Path],
) -> tuple[list[str], dict[str, str]]:
    """Bind runtime evidence to a commit that already existed before collection."""
    errors: list[str] = []
    checked: dict[str, str] = {}
    commit_time = datetime.fromtimestamp(commit_timestamp_epoch, tz=timezone.utc)
    checked["git_commit_timestamp_utc"] = commit_time.isoformat()
    for index, timestamp in enumerate(run_timestamps):
        run_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        checked[f"run_timestamp_utc[{index}]"] = run_time.isoformat()
        if commit_time >= run_time:
            errors.append(
                f"git commit timestamp {commit_time.isoformat()} must predate "
                f"run timestamp {timestamp}"
            )
    for path in jsonl_paths:
        try:
            modified_time = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError as exc:
            errors.append(f"cannot stat JSONL evidence {path}: {exc}")
            continue
        checked[f"jsonl_mtime_utc:{path}"] = modified_time.isoformat()
        if commit_time >= modified_time:
            errors.append(
                f"git commit timestamp {commit_time.isoformat()} must predate "
                f"JSONL mtime {modified_time.isoformat()} for {path}"
            )
    return errors, checked


def _verify_git_provenance(
    *,
    commit: str,
    dirty: bool,
    status_sha256: str,
    manifest: Mapping[str, Any],
    run_timestamps: Sequence[str] = (),
    jsonl_paths: Sequence[Path] = (),
) -> dict[str, Any]:
    """Verify that the recorded clean commit contains every frozen P5 artifact."""
    errors: list[str] = []
    checked: dict[str, str] = {}
    if dirty:
        errors.append("run recorded git_dirty=true")
    if status_sha256 != _EMPTY_SHA256:
        errors.append("git_status_sha256 is not sha256(empty)")
    repo_root = Path(str(manifest["repo_root"]))
    commit_check = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=repo_root,
        capture_output=True,
        check=False,
        timeout=15,
    )
    if commit_check.returncode != 0:
        errors.append(f"git commit does not exist: {commit}")
        return {"ok": False, "errors": errors, "checked": checked}
    timestamp_check = subprocess.run(
        ["git", "show", "-s", "--format=%ct", commit],
        cwd=repo_root,
        capture_output=True,
        check=False,
        timeout=15,
    )
    try:
        commit_timestamp_epoch = int(timestamp_check.stdout.strip())
    except (TypeError, ValueError):
        errors.append(f"cannot read git commit timestamp for {commit}")
    else:
        temporal_errors, temporal_checked = _temporal_provenance_checks(
            commit_timestamp_epoch=commit_timestamp_epoch,
            run_timestamps=run_timestamps,
            jsonl_paths=jsonl_paths,
        )
        errors.extend(temporal_errors)
        checked.update(temporal_checked)

    expected_files = {
        **{
            str(manifest["artifact_relative_paths"][name]): digest
            for name, digest in manifest["artifact_hashes"].items()
        },
        str(manifest["manifest_relative_path"]): str(manifest["sha256"]),
        str(manifest["preregistration_v2_relative_path"]): str(
            manifest["preregistration_v2_sha256"]
        ),
        str(manifest["bridge_conformance"]["relative_path"]): str(
            manifest["bridge_conformance"]["sha256"]
        ),
    }
    for relative_path, expected_hash in expected_files.items():
        shown = subprocess.run(
            ["git", "show", f"{commit}:{relative_path}"],
            cwd=repo_root,
            capture_output=True,
            check=False,
            timeout=15,
        )
        if shown.returncode != 0:
            errors.append(f"{relative_path} is absent at commit {commit}")
            continue
        actual_hash = hashlib.sha256(shown.stdout).hexdigest()
        checked[relative_path] = actual_hash
        if actual_hash != expected_hash:
            errors.append(
                f"{relative_path} hash at commit is {actual_hash}, expected {expected_hash}"
            )
    return {"ok": not errors, "errors": errors, "checked": checked}


def _replay_oracle_integrity(
    *,
    runs: Sequence[Run],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Replay every full-payload attempt through the exact frozen Lean sandbox."""
    all_attempts = [
        attempt
        for run in runs
        for task in run.task_order
        for arm in ARMS
        for attempt in run.attempts[(task, arm)]
    ]
    total = len(all_attempts)
    setup_total = sum(len(run.decoy_setups) for run in runs)
    if any(
        attempt.proof is None or attempt.diagnostic is None or attempt.supplied_feedback is None
        for attempt in all_attempts
    ):
        return {
            "status": "ABSENT",
            "attempt_count": total,
            "replayed_count": 0,
            "setup_count": setup_total,
            "setup_replayed_count": 0,
            "receipt_sha256": None,
            "mismatch_count": 0,
            "mismatches": [],
            "errors": ["full attempt payloads are required for authoritative replay"],
            "identity": None,
        }

    expected_identity = {
        "runner_sha256": str(manifest["artifact_hashes"]["lean_sandbox_runner_macos"]),
        "lean_toolchain": str(manifest["run_design"]["lean_toolchain"]),
        "lean_version": str(manifest["run_design"]["lean_version"]),
        "lean_binary_sha256": str(manifest["run_design"]["lean_binary_sha256"]),
    }
    runner_path = Path(str(manifest["artifact_paths"]["lean_sandbox_runner_macos"]))
    try:
        evaluator = lean_oracle.ExternalSandboxLeanEvaluator(runner=runner_path)
    except Exception as exc:  # noqa: BLE001 -- replay availability must fail closed
        return {
            "status": "FAIL",
            "attempt_count": total,
            "replayed_count": 0,
            "setup_count": setup_total,
            "setup_replayed_count": 0,
            "receipt_sha256": None,
            "mismatch_count": 0,
            "mismatches": [],
            "errors": [f"sandbox unavailable: {type(exc).__name__}: {exc}"],
            "identity": {
                "expected": expected_identity,
                "observed": None,
            },
        }
    observed_identity = {
        "runner_sha256": evaluator.runner_sha256,
        "lean_toolchain": evaluator.lean_toolchain,
        "lean_version": evaluator.lean_version,
        "lean_binary_sha256": evaluator.lean_binary_sha256,
    }
    if observed_identity != expected_identity:
        return {
            "status": "FAIL",
            "attempt_count": total,
            "replayed_count": 0,
            "setup_count": setup_total,
            "setup_replayed_count": 0,
            "receipt_sha256": None,
            "mismatch_count": 0,
            "mismatches": [],
            "errors": ["sandbox runner/compiler identity differs from the frozen manifest"],
            "identity": {
                "expected": expected_identity,
                "observed": observed_identity,
            },
        }

    frozen_task_band = _frozen_lean_task_band()
    if manifest["run_design"]["task_band"] != frozen_task_band:
        return {
            "status": "FAIL",
            "attempt_count": total,
            "replayed_count": 0,
            "setup_count": setup_total,
            "setup_replayed_count": 0,
            "receipt_sha256": None,
            "mismatch_count": 0,
            "mismatches": [],
            "errors": ["manifest task band is not bound to frozen lean_tasks.TASKS"],
            "identity": {
                "expected": expected_identity,
                "observed": observed_identity,
            },
        }
    task_by_name = {
        task_spec["name"]: task
        for task_spec, task in zip(frozen_task_band, lean_tasks.TASKS, strict=True)
    }
    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            {
                "expected_identity": expected_identity,
                "observed_identity": observed_identity,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    digest.update(b"\n")
    mismatches: list[dict[str, Any]] = []
    replayed_count = 0
    setup_replayed_count = 0
    for run in runs:
        for task_name in run.task_order:
            task = task_by_name.get(task_name)
            if task is None:
                return {
                    "status": "FAIL",
                    "attempt_count": total,
                    "replayed_count": replayed_count,
                    "setup_count": setup_total,
                    "setup_replayed_count": setup_replayed_count,
                    "receipt_sha256": digest.hexdigest(),
                    "mismatch_count": len(mismatches),
                    "mismatches": mismatches,
                    "errors": [f"frozen lean_tasks has no task named {task_name!r}"],
                    "identity": {
                        "expected": expected_identity,
                        "observed": observed_identity,
                    },
                }
            setup = run.decoy_setups.get(task_name)
            source_task = task_by_name.get(setup.source_task) if setup is not None else None
            if setup is None or source_task is None:
                return {
                    "status": "FAIL",
                    "attempt_count": total,
                    "replayed_count": replayed_count,
                    "setup_count": setup_total,
                    "setup_replayed_count": setup_replayed_count,
                    "receipt_sha256": digest.hexdigest(),
                    "mismatch_count": len(mismatches),
                    "mismatches": mismatches,
                    "errors": [f"missing frozen pi_decoy_setup binding for {task_name!r}"],
                    "identity": {
                        "expected": expected_identity,
                        "observed": observed_identity,
                    },
                }
            try:
                setup_verdict = evaluator(
                    task.name,
                    task.signature,
                    source_task.reference_proof,
                    preamble=task.preamble,
                )
            except Exception as exc:  # noqa: BLE001 -- setup replay invalidates P5
                return {
                    "status": "FAIL",
                    "attempt_count": total,
                    "replayed_count": replayed_count,
                    "setup_count": setup_total,
                    "setup_replayed_count": setup_replayed_count,
                    "receipt_sha256": digest.hexdigest(),
                    "mismatch_count": len(mismatches),
                    "mismatches": mismatches,
                    "errors": [
                        f"setup replay failed for {run.run_id}/{task_name}: "
                        f"{type(exc).__name__}: {exc}"
                    ],
                    "identity": {
                        "expected": expected_identity,
                        "observed": observed_identity,
                    },
                }
            setup_replayed_count += 1
            replayed_seed_diagnostic = setup_verdict.error_tail or "unsolved goals\n"
            recorded_setup = {
                "compiles": setup.compiles,
                "proven": setup.proven,
                "sorry_tainted": setup.sorry_tainted,
                "graded_score": setup.graded_score,
                "oracle_diagnostic_sha256": setup.oracle_diagnostic_sha256,
                "decoy_seed_diagnostic_sha256": setup.decoy_seed_diagnostic_sha256,
            }
            replayed_setup = {
                "compiles": setup_verdict.compiles,
                "proven": setup_verdict.proven,
                "sorry_tainted": setup_verdict.sorry_tainted,
                "graded_score": setup_verdict.graded_score,
                "oracle_diagnostic_sha256": hashlib.sha256(
                    setup_verdict.error_tail.encode("utf-8", "replace")
                ).hexdigest(),
                "decoy_seed_diagnostic_sha256": hashlib.sha256(
                    replayed_seed_diagnostic.encode("utf-8", "replace")
                ).hexdigest(),
            }
            setup_differences = [
                key for key in recorded_setup if recorded_setup[key] != replayed_setup[key]
            ]
            if (
                setup.oracle_diagnostic != setup_verdict.error_tail
                and "oracle_diagnostic_exact" not in setup_differences
            ):
                setup_differences.append("oracle_diagnostic_exact")
            if (
                setup.decoy_seed_diagnostic != replayed_seed_diagnostic
                and "decoy_seed_diagnostic_exact" not in setup_differences
            ):
                setup_differences.append("decoy_seed_diagnostic_exact")
            setup_row = {
                "kind": "pi_decoy_setup",
                "run_id": run.run_id,
                "task": task_name,
                "source_task": source_task.name,
                "source_reference_proof_sha256": setup.source_reference_proof_sha256,
                "recorded": recorded_setup,
                "replayed": replayed_setup,
                "oracle_diagnostic_exact": (setup.oracle_diagnostic == setup_verdict.error_tail),
                "decoy_seed_diagnostic_exact": (
                    setup.decoy_seed_diagnostic == replayed_seed_diagnostic
                ),
                "differences": setup_differences,
            }
            if setup_differences:
                mismatches.append(setup_row)
            digest.update(
                json.dumps(
                    setup_row,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8", "replace")
            )
            digest.update(b"\n")
            for arm in ARMS:
                for attempt in run.attempts[(task_name, arm)]:
                    proof = attempt.proof
                    diagnostic = attempt.diagnostic
                    if proof is None or diagnostic is None:
                        raise AssertionError("full-payload replay precondition drifted")
                    try:
                        verdict = evaluator(
                            task.name,
                            task.signature,
                            proof,
                            preamble=task.preamble,
                        )
                    except Exception as exc:  # noqa: BLE001 -- replay errors invalidate P5
                        return {
                            "status": "FAIL",
                            "attempt_count": total,
                            "replayed_count": replayed_count,
                            "setup_count": setup_total,
                            "setup_replayed_count": setup_replayed_count,
                            "receipt_sha256": digest.hexdigest(),
                            "mismatch_count": len(mismatches),
                            "mismatches": mismatches,
                            "errors": [
                                f"replay failed for {run.run_id}/{task_name}/{arm}/"
                                f"{attempt.index}: {type(exc).__name__}: {exc}"
                            ],
                            "identity": {
                                "expected": expected_identity,
                                "observed": observed_identity,
                            },
                        }
                    replayed_count += 1
                    recorded = {
                        "compiles": attempt.compiles,
                        "proven": attempt.proven,
                        "sorry_tainted": attempt.sorry_tainted,
                        "graded_score": attempt.graded_score,
                        "diagnostic_sha256": attempt.diagnostic_sha256,
                    }
                    replayed = {
                        "compiles": verdict.compiles,
                        "proven": verdict.proven,
                        "sorry_tainted": verdict.sorry_tainted,
                        "graded_score": verdict.graded_score,
                        "diagnostic_sha256": hashlib.sha256(
                            verdict.error_tail.encode("utf-8", "replace")
                        ).hexdigest(),
                    }
                    differences = [key for key in recorded if recorded[key] != replayed[key]]
                    row = {
                        "kind": "attempt",
                        "run_id": run.run_id,
                        "task": task_name,
                        "arm": arm,
                        "attempt": attempt.index,
                        "proof_sha256": attempt.proof_sha256,
                        "recorded": recorded,
                        "replayed": replayed,
                        "diagnostic_exact": diagnostic == verdict.error_tail,
                        "differences": differences,
                    }
                    if diagnostic != verdict.error_tail and "diagnostic_exact" not in differences:
                        differences.append("diagnostic_exact")
                    if differences:
                        mismatches.append(row)
                    digest.update(
                        json.dumps(
                            row,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8", "replace")
                    )
                    digest.update(b"\n")
    replay_complete = replayed_count == total and setup_replayed_count == setup_total
    return {
        "status": "PASS" if not mismatches and replay_complete else "FAIL",
        "attempt_count": total,
        "replayed_count": replayed_count,
        "setup_count": setup_total,
        "setup_replayed_count": setup_replayed_count,
        "receipt_sha256": digest.hexdigest(),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "errors": (
            []
            if not mismatches and replay_complete
            else [
                "one or more replayed oracle verdicts differ"
                if mismatches
                else "authoritative replay counts are incomplete"
            ]
        ),
        "identity": {
            "expected": expected_identity,
            "observed": observed_identity,
        },
    }


def _read_records(files: Sequence[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in files:
        with path.open(encoding="utf-8") as stream:
            for lineno, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ContractError(f"{path}:{lineno}: invalid JSON: {exc.msg}") from exc
                if not isinstance(record, dict):
                    raise ContractError(f"{path}:{lineno}: each JSONL record must be an object")
                record["_source"] = f"{path}:{lineno}"
                record["_source_path"] = str(path)
                record["_source_lineno"] = lineno
                records.append(record)
    if not records:
        raise ContractError("JSONL batch is empty")
    return records


def _required(record: Mapping[str, Any], key: str) -> Any:
    if key not in record:
        raise ContractError(f"{record.get('_source', '<record>')}: missing required field {key!r}")
    return record[key]


def _strict_int(value: Any, *, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ContractError(f"{label} must be an integer >= {minimum}; got {value!r}")
    return value


def _finite_number(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{label} must be numeric; got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ContractError(f"{label} must be finite; got {value!r}")
    return result


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in _HEX for char in value)


def _validate_timestamp(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{label} must be a timezone-aware ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{label} is not valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError(f"{label} must include a timezone")
    if parsed.utcoffset() != timedelta(0):
        raise ContractError(f"{label} must represent UTC")
    return value


def _validate_start(record: dict[str, Any]) -> RunStart:
    source = record["_source"]
    if record.get("schema") != SCHEMA:
        raise ContractError(f"{source}: schema must be {SCHEMA!r}")
    run_id = _required(record, "run_id")
    backend = _required(record, "backend")
    model_id = _required(record, "model_id")
    endpoint_class = _required(record, "endpoint_class")
    endpoint_fingerprint = _required(record, "endpoint_fingerprint")
    temperature = _finite_number(_required(record, "temperature"), label=f"{source}.temperature")
    max_tokens_per_attempt = _strict_int(
        _required(record, "max_tokens_per_attempt"),
        label=f"{source}.max_tokens_per_attempt",
        minimum=1,
    )
    oracle_isolation = _required(record, "oracle_isolation")
    sandbox_runner_sha256 = _required(record, "sandbox_runner_sha256")
    lean_toolchain = _required(record, "lean_toolchain")
    lean_version = _required(record, "lean_version")
    lean_binary_sha256 = _required(record, "lean_binary_sha256")
    harness_version = _required(record, "harness_version")
    payload_mode = _required(record, "payload_mode")
    timestamp_utc = _validate_timestamp(
        _required(record, "timestamp_utc"), label=f"{source}.timestamp_utc"
    )
    if not isinstance(run_id, str) or not run_id:
        raise ContractError(f"{source}: run_id must be a non-empty string")
    if not isinstance(backend, str) or not backend:
        raise ContractError(f"{source}: backend must be a non-empty string")
    if not isinstance(model_id, str) or not model_id:
        raise ContractError(f"{source}: model_id must be a non-empty string")
    if not isinstance(endpoint_class, str) or not endpoint_class:
        raise ContractError(f"{source}: endpoint_class must be a non-empty string")
    for key, value in (
        ("endpoint_fingerprint", endpoint_fingerprint),
        ("sandbox_runner_sha256", sandbox_runner_sha256),
    ):
        if not _is_sha256(value) or set(str(value)) == {"0"}:
            raise ContractError(f"{source}: {key} must be a nonzero SHA-256 digest")
    if oracle_isolation != ORACLE_ISOLATION:
        raise ContractError(f"{source}: oracle_isolation must be {ORACLE_ISOLATION!r}")
    if lean_toolchain != LEAN_TOOLCHAIN:
        raise ContractError(f"{source}: lean_toolchain must be {LEAN_TOOLCHAIN!r}")
    if lean_version != LEAN_VERSION:
        raise ContractError(f"{source}: lean_version must be the frozen full version line")
    if lean_binary_sha256 != LEAN_BINARY_SHA256:
        raise ContractError(f"{source}: lean_binary_sha256 differs from the frozen Lean binary")
    if not isinstance(harness_version, str) or not harness_version:
        raise ContractError(f"{source}: harness_version must be a non-empty string")
    if payload_mode not in {"full", "redacted"}:
        raise ContractError(f"{source}: payload_mode must be 'full' or 'redacted'")
    k = _strict_int(_required(record, "K"), label=f"{source}.K", minimum=1)
    seed_offset = _strict_int(
        _required(record, "seed_offset"), label=f"{source}.seed_offset", minimum=0
    )
    raw_hashes = _required(record, "artifact_hashes")
    if not isinstance(raw_hashes, dict):
        raise ContractError(f"{source}: artifact_hashes must be an object")
    if set(raw_hashes) != set(ARTIFACT_HASH_KEYS):
        raise ContractError(
            f"{source}: artifact_hashes must contain exactly {list(ARTIFACT_HASH_KEYS)!r}"
        )
    hashes: dict[str, str] = {}
    for key in ARTIFACT_HASH_KEYS:
        value = raw_hashes[key]
        if not _is_sha256(value):
            raise ContractError(f"{source}: artifact_hashes.{key} must be a SHA-256 hex digest")
        hashes[key] = value.lower()
    arms = _required(record, "arms")
    if not isinstance(arms, list) or tuple(arms) != ARMS:
        raise ContractError(f"{source}: arms must exactly match the frozen six-arm order")
    if record.get("arm_order_policy") != ARM_ORDER_POLICY:
        raise ContractError(f"{source}: arm_order_policy must be {ARM_ORDER_POLICY!r}")
    git_commit = _required(record, "git_commit")
    git_dirty = _required(record, "git_dirty")
    git_status_sha256 = _required(record, "git_status_sha256")
    if not (
        isinstance(git_commit, str)
        and len(git_commit) in {40, 64}
        and all(char in _HEX for char in git_commit)
    ):
        raise ContractError(f"{source}: git_commit must be a 40- or 64-character hex object id")
    if not isinstance(git_dirty, bool):
        raise ContractError(f"{source}: git_dirty must be boolean")
    if not _is_sha256(git_status_sha256):
        raise ContractError(f"{source}: git_status_sha256 must be a SHA-256 digest")
    raw_tasks = _required(record, "tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ContractError(f"{source}: tasks must be a non-empty ordered list")
    if _strict_int(_required(record, "n_tasks"), label=f"{source}.n_tasks", minimum=1) != len(
        raw_tasks
    ):
        raise ContractError(f"{source}: n_tasks does not match tasks length")
    task_order: list[str] = []
    task_difficulties: dict[str, str] = {}
    task_hashes: dict[str, str] = {}
    for index, item in enumerate(raw_tasks):
        if not isinstance(item, dict) or set(item) != {
            "name",
            "difficulty",
            "task_sha256",
        }:
            raise ContractError(
                f"{source}: tasks[{index}] must contain name, difficulty, task_sha256"
            )
        name, difficulty, task_hash = (
            item.get("name"),
            item.get("difficulty"),
            item.get("task_sha256"),
        )
        if not isinstance(name, str) or not name:
            raise ContractError(f"{source}: tasks[{index}].name must be non-empty")
        if not isinstance(difficulty, str) or not difficulty:
            raise ContractError(f"{source}: tasks[{index}].difficulty must be non-empty")
        if name in task_difficulties:
            raise ContractError(f"{source}: duplicate task name {name!r}")
        if not _is_sha256(task_hash):
            raise ContractError(f"{source}: tasks[{index}].task_sha256 must be a SHA-256 digest")
        task_order.append(name)
        task_difficulties[name] = difficulty
        task_hashes[name] = str(task_hash).lower()
    return RunStart(
        run_id=run_id,
        backend=backend,
        model_id=model_id,
        endpoint_class=endpoint_class,
        endpoint_fingerprint=str(endpoint_fingerprint).lower(),
        temperature=temperature,
        max_tokens_per_attempt=max_tokens_per_attempt,
        oracle_isolation=oracle_isolation,
        sandbox_runner_sha256=str(sandbox_runner_sha256).lower(),
        lean_toolchain=str(lean_toolchain),
        lean_version=str(lean_version),
        lean_binary_sha256=str(lean_binary_sha256).lower(),
        k=k,
        seed_offset=seed_offset,
        timestamp_utc=timestamp_utc,
        harness_version=harness_version,
        payload_mode=str(payload_mode),
        artifact_hashes=hashes,
        task_order=task_order,
        task_difficulties=task_difficulties,
        task_hashes=task_hashes,
        git_commit=git_commit.lower(),
        git_dirty=git_dirty,
        git_status_sha256=str(git_status_sha256).lower(),
    )


def _validate_common(
    record: Mapping[str, Any],
    *,
    start: RunStart,
) -> None:
    source = record.get("_source", "<record>")
    expected = {
        "schema": SCHEMA,
        "harness_version": start.harness_version,
        "run_id": start.run_id,
        "backend": start.backend,
        "model_id": start.model_id,
        "endpoint_class": start.endpoint_class,
        "endpoint_fingerprint": start.endpoint_fingerprint,
        "temperature": start.temperature,
        "max_tokens_per_attempt": start.max_tokens_per_attempt,
        "oracle_isolation": start.oracle_isolation,
        "sandbox_runner_sha256": start.sandbox_runner_sha256,
        "lean_toolchain": start.lean_toolchain,
        "lean_version": start.lean_version,
        "lean_binary_sha256": start.lean_binary_sha256,
        "K": start.k,
        "seed_offset": start.seed_offset,
        "timestamp_utc": start.timestamp_utc,
        "payload_mode": start.payload_mode,
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise ContractError(
                f"{source}: {key}={record.get(key)!r} does not match run_start {value!r}"
            )


def _validate_decoy_setup(
    record: dict[str, Any],
    *,
    start: RunStart,
) -> DecoySetup:
    _validate_common(record, start=start)
    source = record["_source"]
    task = _required(record, "task")
    difficulty = _required(record, "difficulty")
    arm = _required(record, "arm")
    if (
        not isinstance(task, str)
        or task not in start.task_difficulties
        or difficulty != start.task_difficulties[task]
        or arm != "pi_decoy"
    ):
        raise ContractError(f"{source}: pi_decoy_setup target identity mismatch")
    expected_source = _decoy_source_binding(task, start)
    for key, expected in expected_source.items():
        if record.get(key) != expected:
            raise ContractError(f"{source}: {key} does not match frozen decoy source binding")
    compiles = _required(record, "compiles")
    proven = _required(record, "proven")
    sorry_tainted = _required(record, "sorry_tainted")
    for key, value in (
        ("compiles", compiles),
        ("proven", proven),
        ("sorry_tainted", sorry_tainted),
    ):
        if not isinstance(value, bool):
            raise ContractError(f"{source}: {key} must be boolean")
    graded_score = _finite_number(_required(record, "graded_score"), label=f"{source}.graded_score")
    if proven != (compiles and not sorry_tainted):
        raise ContractError(f"{source}: setup proven must equal compiles and not sorry_tainted")
    expected_grade = 1.0 if proven else (0.5 if compiles else 0.0)
    if graded_score != expected_grade:
        raise ContractError(f"{source}: setup graded_score violates LeanVerdict semantics")
    oracle_diagnostic = _required(record, "oracle_diagnostic")
    decoy_seed_diagnostic = _required(record, "decoy_seed_diagnostic")
    if not isinstance(oracle_diagnostic, str) or not isinstance(decoy_seed_diagnostic, str):
        raise ContractError(f"{source}: setup diagnostics must be strings")
    oracle_hash = _required(record, "oracle_diagnostic_sha256")
    seed_hash = _required(record, "decoy_seed_diagnostic_sha256")
    if oracle_hash != hashlib.sha256(oracle_diagnostic.encode("utf-8", "replace")).hexdigest():
        raise ContractError(f"{source}: oracle_diagnostic hash mismatch")
    if seed_hash != hashlib.sha256(decoy_seed_diagnostic.encode("utf-8", "replace")).hexdigest():
        raise ContractError(f"{source}: decoy_seed_diagnostic hash mismatch")
    expected_seed = oracle_diagnostic or "unsolved goals\n"
    if decoy_seed_diagnostic != expected_seed:
        raise ContractError(
            f"{source}: decoy_seed_diagnostic must equal oracle diagnostic or frozen fallback"
        )
    if (
        _strict_int(
            _required(record, "setup_oracle_calls"),
            label=f"{source}.setup_oracle_calls",
        )
        != 1
    ):
        raise ContractError(f"{source}: setup_oracle_calls must be exactly 1")
    return DecoySetup(
        run_id=start.run_id,
        task=task,
        difficulty=str(difficulty),
        source_task=str(record["source_task"]),
        source_task_sha256=str(record["source_task_sha256"]),
        source_reference_proof_sha256=str(record["source_reference_proof_sha256"]),
        compiles=compiles,
        proven=proven,
        sorry_tainted=sorry_tainted,
        graded_score=graded_score,
        oracle_diagnostic=oracle_diagnostic,
        oracle_diagnostic_sha256=str(oracle_hash),
        decoy_seed_diagnostic=decoy_seed_diagnostic,
        decoy_seed_diagnostic_sha256=str(seed_hash),
    )


def _validate_attempt(
    record: dict[str, Any],
    *,
    start: RunStart,
) -> Attempt:
    _validate_common(record, start=start)
    source = record["_source"]
    task = _required(record, "task")
    difficulty = _required(record, "difficulty")
    arm = _required(record, "arm")
    if not isinstance(task, str) or not task:
        raise ContractError(f"{source}: task must be a non-empty string")
    if not isinstance(difficulty, str) or not difficulty:
        raise ContractError(f"{source}: difficulty must be a non-empty string")
    task_sha256 = _required(record, "task_sha256")
    if task not in start.task_hashes or task_sha256 != start.task_hashes[task]:
        raise ContractError(f"{source}: task_sha256 does not match run_start.tasks")
    if arm not in ARMS:
        raise ContractError(f"{source}: unknown arm {arm!r}")
    index = _strict_int(_required(record, "attempt"), label=f"{source}.attempt", minimum=1)
    seed = _strict_int(_required(record, "seed"), label=f"{source}.seed")
    used_feedback = _required(record, "used_feedback")
    feedback_source = _required(record, "feedback_source")
    proven = _required(record, "proven")
    compiles = _required(record, "compiles")
    sorry_tainted = _required(record, "sorry_tainted")
    response_model_id = _required(record, "response_model_id")
    response_model_observed = _required(record, "response_model_observed")
    if not isinstance(used_feedback, bool):
        raise ContractError(f"{source}: used_feedback must be boolean")
    for key, value in (
        ("proven", proven),
        ("compiles", compiles),
        ("sorry_tainted", sorry_tainted),
    ):
        if not isinstance(value, bool):
            raise ContractError(f"{source}: {key} must be boolean")
    if not isinstance(response_model_id, str) or response_model_id != start.model_id:
        raise ContractError(f"{source}: response_model_id must exactly match run_start.model_id")
    if response_model_observed is not True:
        raise ContractError(f"{source}: response_model_observed must be literal true")
    if feedback_source not in {"none", "real", "decoy"}:
        raise ContractError(f"{source}: feedback_source must be none, real, or decoy")
    graded_score = _finite_number(_required(record, "graded_score"), label=f"{source}.graded_score")
    if proven != (compiles and not sorry_tainted):
        raise ContractError(f"{source}: proven must equal compiles and not sorry_tainted")
    expected_graded_score = 1.0 if proven else (0.5 if compiles else 0.0)
    if graded_score != expected_graded_score:
        raise ContractError(
            f"{source}: graded_score={graded_score} violates LeanVerdict semantics "
            f"(expected {expected_graded_score})"
        )
    for key in ("proof_sha256", "diagnostic_sha256", "supplied_feedback_sha256"):
        if not _is_sha256(_required(record, key)):
            raise ContractError(f"{source}: {key} must be a SHA-256 hex digest")
    proof_sha256 = str(record["proof_sha256"]).lower()
    diagnostic_sha256 = str(record["diagnostic_sha256"]).lower()
    supplied_feedback_sha256 = str(record["supplied_feedback_sha256"]).lower()
    prior_proof_sha256 = _required(record, "prior_proof_sha256")
    if prior_proof_sha256 != "" and not _is_sha256(prior_proof_sha256):
        raise ContractError(f"{source}: prior_proof_sha256 must be empty or a SHA-256 digest")
    pi_run_id = _required(record, "pi_run_id")
    if not isinstance(pi_run_id, str):
        raise ContractError(f"{source}: pi_run_id must be a string")
    raw_payload_complete = all(
        isinstance(record.get(key), str) for key in ("proof", "diagnostic", "supplied_feedback")
    )
    if raw_payload_complete:
        for raw_key, hash_key in (
            ("proof", "proof_sha256"),
            ("diagnostic", "diagnostic_sha256"),
            ("supplied_feedback", "supplied_feedback_sha256"),
        ):
            actual = hashlib.sha256(record[raw_key].encode("utf-8", "replace")).hexdigest()
            if actual != str(record[hash_key]).lower():
                raise ContractError(f"{source}: {raw_key} does not match {hash_key}")
    usage = {
        key: _strict_int(_required(record, key), label=f"{source}.{key}", minimum=1)
        for key in USAGE_KEYS
    }
    if usage["model_calls"] != 1 or usage["oracle_calls"] != 1:
        raise ContractError(f"{source}: every attempt must report model_calls=oracle_calls=1")
    if usage["output_tokens"] > start.max_tokens_per_attempt:
        raise ContractError(
            f"{source}: output_tokens={usage['output_tokens']} exceeds frozen "
            f"max_tokens_per_attempt={start.max_tokens_per_attempt}"
        )
    return Attempt(
        run_id=start.run_id,
        task=task,
        difficulty=difficulty,
        arm=str(arm),
        index=index,
        seed=seed,
        proven=proven,
        compiles=compiles,
        sorry_tainted=sorry_tainted,
        graded_score=graded_score,
        response_model_id=response_model_id,
        response_model_observed=True,
        used_feedback=used_feedback,
        feedback_source=feedback_source,
        proof_sha256=proof_sha256,
        diagnostic_sha256=diagnostic_sha256,
        supplied_feedback_sha256=supplied_feedback_sha256,
        prior_proof_sha256=str(prior_proof_sha256).lower(),
        proof=record.get("proof") if isinstance(record.get("proof"), str) else None,
        diagnostic=(
            record.get("diagnostic") if isinstance(record.get("diagnostic"), str) else None
        ),
        supplied_feedback=(
            record.get("supplied_feedback")
            if isinstance(record.get("supplied_feedback"), str)
            else None
        ),
        pi_run_id=pi_run_id,
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        model_calls=usage["model_calls"],
        oracle_calls=usage["oracle_calls"],
        raw_payload_complete=raw_payload_complete,
    )


def _validate_task_summary(
    record: dict[str, Any],
    *,
    start: RunStart,
    expected_arm_order: Sequence[str],
) -> tuple[str, str, dict[str, Any]]:
    _validate_common(record, start=start)
    source = record["_source"]
    task = _required(record, "task")
    difficulty = _required(record, "difficulty")
    arms = _required(record, "arms")
    if not isinstance(task, str) or not task:
        raise ContractError(f"{source}: task must be a non-empty string")
    if not isinstance(difficulty, str) or not difficulty:
        raise ContractError(f"{source}: difficulty must be a non-empty string")
    task_sha256 = _required(record, "task_sha256")
    if task not in start.task_hashes or task_sha256 != start.task_hashes[task]:
        raise ContractError(f"{source}: task_sha256 does not match run_start.tasks")
    if not isinstance(arms, dict) or set(arms) != set(ARMS):
        raise ContractError(f"{source}: task_summary arms must contain exactly {list(ARMS)!r}")
    arm_order = _required(record, "arm_order")
    if not isinstance(arm_order, list) or arm_order != list(expected_arm_order):
        raise ContractError(
            f"{source}: arm_order does not match the frozen cyclic rotation "
            f"{list(expected_arm_order)!r}"
        )
    normalized: dict[str, Any] = {}
    for arm in ARMS:
        arm_summary = arms[arm]
        if not isinstance(arm_summary, dict):
            raise ContractError(f"{source}: arms.{arm} must be an object")
        proven = _required(arm_summary, "proven")
        if not isinstance(proven, bool):
            raise ContractError(f"{source}: arms.{arm}.proven must be boolean")
        normalized[arm] = {
            "proven": proven,
            "graded_score": _finite_number(
                _required(arm_summary, "graded_score"),
                label=f"{source}.arms.{arm}.graded_score",
            ),
            "attempts": _strict_int(
                _required(arm_summary, "attempts"),
                label=f"{source}.arms.{arm}.attempts",
                minimum=1,
            ),
            "input_tokens": _strict_int(
                _required(arm_summary, "input_tokens"),
                label=f"{source}.arms.{arm}.input_tokens",
            ),
            "output_tokens": _strict_int(
                _required(arm_summary, "output_tokens"),
                label=f"{source}.arms.{arm}.output_tokens",
            ),
            "model_calls": _strict_int(
                _required(arm_summary, "model_calls"),
                label=f"{source}.arms.{arm}.model_calls",
                minimum=1,
            ),
            "oracle_calls": _strict_int(
                _required(arm_summary, "oracle_calls"),
                label=f"{source}.arms.{arm}.oracle_calls",
                minimum=1,
            ),
            "setup_oracle_calls": _strict_int(
                _required(arm_summary, "setup_oracle_calls"),
                label=f"{source}.arms.{arm}.setup_oracle_calls",
            ),
            "pi_stop": _required(arm_summary, "pi_stop"),
        }
        if normalized[arm]["pi_stop"] is not None and not isinstance(
            normalized[arm]["pi_stop"], str
        ):
            raise ContractError(f"{source}: arms.{arm}.pi_stop must be null or string")
    return task, difficulty, normalized


def _summary_count(summary: Mapping[str, Any], arm: str, *, source: str) -> int:
    if arm not in summary:
        raise ContractError(f"{source}: missing aggregate for arm {arm!r}")
    return _strict_int(summary[arm], label=f"{source}.{arm}")


def _validate_run_summary(
    record: dict[str, Any],
    *,
    start: RunStart,
    task_summaries: Mapping[str, Mapping[str, Any]],
    difficulties: Mapping[str, str],
) -> None:
    _validate_common(record, start=start)
    source = record["_source"]
    all_summary = _required(record, "all")
    headroom_summary = _required(record, "headroom_only")
    if not isinstance(all_summary, dict) or not isinstance(headroom_summary, dict):
        raise ContractError(f"{source}: all and headroom_only must be objects")
    expected_headroom_count = sum(difficulty == "headroom" for difficulty in difficulties.values())
    if _strict_int(_required(record, "n_tasks"), label=f"{source}.n_tasks", minimum=1) != len(
        task_summaries
    ):
        raise ContractError(f"{source}: n_tasks does not match task summaries")
    if (
        _strict_int(_required(record, "n_headroom"), label=f"{source}.n_headroom")
        != expected_headroom_count
    ):
        raise ContractError(f"{source}: n_headroom does not match task summaries")
    if _strict_int(_required(all_summary, "of"), label=f"{source}.all.of") != len(task_summaries):
        raise ContractError(f"{source}: all.of does not match task summaries")
    if (
        _strict_int(_required(headroom_summary, "of"), label=f"{source}.headroom_only.of")
        != expected_headroom_count
    ):
        raise ContractError(f"{source}: headroom_only.of does not match task summaries")
    for arm in ARMS:
        expected_all = sum(bool(summary[arm]["proven"]) for summary in task_summaries.values())
        expected_headroom = sum(
            bool(task_summaries[task][arm]["proven"])
            for task, difficulty in difficulties.items()
            if difficulty == "headroom"
        )
        actual_all = _summary_count(all_summary, arm, source=f"{source}.all")
        actual_headroom = _summary_count(headroom_summary, arm, source=f"{source}.headroom_only")
        if actual_all != expected_all:
            raise ContractError(
                f"{source}: all.{arm}={actual_all} but task summaries imply {expected_all}"
            )
        if actual_headroom != expected_headroom:
            raise ContractError(
                f"{source}: headroom_only.{arm}={actual_headroom} "
                f"but task summaries imply {expected_headroom}"
            )
        graded_all = sum(float(summary[arm]["graded_score"]) for summary in task_summaries.values())
        graded_headroom = sum(
            float(task_summaries[task][arm]["graded_score"])
            for task, difficulty in difficulties.items()
            if difficulty == "headroom"
        )
        for aggregate, expected, aggregate_name in (
            (all_summary, graded_all, "all"),
            (headroom_summary, graded_headroom, "headroom_only"),
        ):
            graded_key = f"graded_{arm}"
            actual_graded = _finite_number(
                _required(aggregate, graded_key),
                label=f"{source}.{aggregate_name}.{graded_key}",
            )
            if not math.isclose(actual_graded, expected, abs_tol=1e-6):
                raise ContractError(
                    f"{source}: {aggregate_name}.{graded_key}={actual_graded} "
                    f"but task summaries imply {expected}"
                )
        for field in (
            "model_calls",
            "oracle_calls",
            "setup_oracle_calls",
            "input_tokens",
            "output_tokens",
        ):
            expected_all_usage = sum(
                int(summary[arm][field]) for summary in task_summaries.values()
            )
            expected_headroom_usage = sum(
                int(task_summaries[task][arm][field])
                for task, difficulty in difficulties.items()
                if difficulty == "headroom"
            )
            all_key = f"{field}_{arm}"
            actual_all_usage = _strict_int(
                _required(all_summary, all_key), label=f"{source}.all.{all_key}"
            )
            actual_headroom_usage = _strict_int(
                _required(headroom_summary, all_key),
                label=f"{source}.headroom_only.{all_key}",
            )
            if actual_all_usage != expected_all_usage:
                raise ContractError(
                    f"{source}: all.{all_key}={actual_all_usage} "
                    f"but task summaries imply {expected_all_usage}"
                )
            if actual_headroom_usage != expected_headroom_usage:
                raise ContractError(
                    f"{source}: headroom_only.{all_key}={actual_headroom_usage} "
                    f"but task summaries imply {expected_headroom_usage}"
                )


def _validate_attempt_chain(
    *,
    start: RunStart,
    task: str,
    arm: str,
    attempts: Sequence[Attempt],
    declared_proven: bool,
    decoy_setup: DecoySetup | None,
) -> None:
    label = f"run {start.run_id!r} task {task!r} arm {arm!r}"
    if [attempt.index for attempt in attempts] != list(range(1, len(attempts) + 1)):
        raise ContractError(f"{label}: attempts must be contiguous and 1-based")
    if len(attempts) > start.k:
        raise ContractError(f"{label}: attempts exceed K={start.k}")
    if arm == "single" and len(attempts) != 1:
        raise ContractError(f"{label}: single must contain exactly one attempt")
    if (
        not declared_proven
        and arm in {"bestN", "legacy_repair", "plain_baseline"}
        and len(attempts) != start.k
    ):
        raise ContractError(f"{label}: unsuccessful arm must exhaust K={start.k}")
    proven_indexes = [attempt.index for attempt in attempts if attempt.proven]
    if bool(proven_indexes) != declared_proven:
        raise ContractError(f"{label}: attempt success disagrees with task_summary")
    if proven_indexes and proven_indexes != [len(attempts)]:
        raise ContractError(f"{label}: success must be the final and only successful attempt")

    pi_arm = arm in {"pi_repair", "pi_decoy"}
    if (arm == "pi_decoy") != (decoy_setup is not None):
        raise ContractError(f"{label}: pi_decoy requires exactly one bound setup record")
    expected_pi_run_id = f"{start.run_id}:{task}:{arm}" if pi_arm else ""
    expected_feedback_source = "decoy" if arm == "pi_decoy" else "real"
    chained = arm in {"legacy_repair", "pi_repair", "pi_decoy", "plain_baseline"}
    for position, attempt in enumerate(attempts, start=1):
        if attempt.seed != start.seed_offset + position - 1:
            raise ContractError(
                f"{label}: attempt {position} seed={attempt.seed} "
                f"!= {start.seed_offset + position - 1}"
            )
        if attempt.pi_run_id != expected_pi_run_id:
            raise ContractError(f"{label}: pi_run_id does not match lifecycle identity")
        if position == 1:
            if (
                attempt.used_feedback
                or attempt.feedback_source != "none"
                or attempt.supplied_feedback_sha256 != _EMPTY_SHA256
                or attempt.prior_proof_sha256 != ""
            ):
                raise ContractError(f"{label}: first attempt must have no feedback or parent")
            if attempt.supplied_feedback not in {None, ""}:
                raise ContractError(f"{label}: first supplied_feedback must be empty")
            continue
        previous = attempts[position - 2]
        if not chained:
            if (
                attempt.used_feedback
                or attempt.feedback_source != "none"
                or attempt.supplied_feedback_sha256 != _EMPTY_SHA256
                or attempt.prior_proof_sha256 != ""
            ):
                raise ContractError(f"{label}: independent attempts must not carry feedback")
            continue
        if not attempt.used_feedback or attempt.feedback_source != expected_feedback_source:
            raise ContractError(f"{label}: subsequent attempt has wrong feedback provenance")
        if attempt.prior_proof_sha256 != previous.proof_sha256:
            raise ContractError(f"{label}: prior proof hash does not chain to previous attempt")
        if arm != "pi_decoy":
            if attempt.supplied_feedback_sha256 != previous.diagnostic_sha256:
                raise ContractError(
                    f"{label}: supplied feedback does not chain to previous diagnostic"
                )
        elif (
            decoy_setup is not None
            and attempt.supplied_feedback is not None
            and previous.diagnostic is not None
        ):
            expected_decoy = _fit_decoy(
                decoy_setup.decoy_seed_diagnostic,
                previous.diagnostic,
            )
            if (
                attempt.supplied_feedback != expected_decoy
                or attempt.supplied_feedback_sha256
                != hashlib.sha256(expected_decoy.encode("utf-8", "replace")).hexdigest()
            ):
                raise ContractError(
                    f"{label}: decoy supplied_feedback does not match frozen setup transform"
                )


def _validate_pi_lifecycle(
    *,
    start: RunStart,
    task: str,
    arm: str,
    attempts: Sequence[Attempt],
    summary: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    stops: Sequence[Mapping[str, Any]],
) -> None:
    label = f"run {start.run_id!r} task {task!r} arm {arm!r}"
    if len(stops) != 1:
        raise ContractError(f"{label}: exactly one pi_stop is required")
    if len(events) < 2:
        raise ContractError(f"{label}: PI lifecycle events are required")
    pi_run_id = f"{start.run_id}:{task}:{arm}"
    event_sequences = [
        _strict_int(_required(event, "sequence"), label=f"{event['_source']}.sequence")
        for event in events
    ]
    if event_sequences != list(range(len(events))):
        raise ContractError(f"{label}: PI event sequence must be contiguous 0..N-1")
    expected_events: list[tuple[str, int, Attempt]] = [("oracle_evaluated", 0, attempts[0])]
    for attempt_index in range(1, len(attempts)):
        expected_events.extend(
            (
                ("repair_requested", attempt_index, attempts[attempt_index - 1]),
                ("oracle_evaluated", attempt_index, attempts[attempt_index]),
            )
        )
    expected_events.append(("stopped", len(attempts) - 1, attempts[-1]))
    if len(events) != len(expected_events):
        raise ContractError(
            f"{label}: lifecycle event pattern has {len(events)} records; "
            f"expected exactly {len(expected_events)}"
        )
    previous_elapsed = -1
    for event, (expected_kind, expected_attempt, bound_attempt) in zip(
        events, expected_events, strict=True
    ):
        if (
            event.get("task") != task
            or event.get("difficulty") != start.task_difficulties[task]
            or event.get("arm") != arm
            or event.get("pi_run_id") != pi_run_id
        ):
            raise ContractError(f"{event['_source']}: PI event identity mismatch")
        event_attempt = _strict_int(
            _required(event, "attempt"), label=f"{event['_source']}.attempt"
        )
        elapsed = _strict_int(
            _required(event, "elapsed_ms"), label=f"{event['_source']}.elapsed_ms"
        )
        if event.get("kind") != expected_kind or event_attempt != expected_attempt:
            raise ContractError(
                f"{event['_source']}: lifecycle pattern expected "
                f"{expected_kind}({expected_attempt}), got "
                f"{event.get('kind')}({event_attempt})"
            )
        if elapsed < previous_elapsed:
            raise ContractError(f"{event['_source']}: PI event elapsed_ms must be monotonic")
        previous_elapsed = elapsed
        detail_sha256 = _required(event, "detail_sha256")
        if not _is_sha256(detail_sha256):
            raise ContractError(f"{event['_source']}: detail_sha256 must be SHA-256")
        status = _required(event, "status")
        score = _required(event, "score")
        if not isinstance(status, str):
            raise ContractError(f"{event['_source']}: status must be a string")
        if score is not None:
            _finite_number(score, label=f"{event['_source']}.score")
        for key in ("candidate_fingerprint", "diagnostic_fingerprint"):
            value = _required(event, key)
            if value != "" and not _is_sha256(value):
                raise ContractError(f"{event['_source']}: {key} must be empty or SHA-256")
        expected_candidate = (
            candidate_fingerprint(bound_attempt.proof) if bound_attempt.proof is not None else None
        )
        expected_feedback = (
            feedback_from_value(
                lens="lean-ungameable",
                kind="lean-proof",
                passed=bound_attempt.proven,
                score=bound_attempt.graded_score,
                diagnostic=bound_attempt.diagnostic,
            )
            if bound_attempt.diagnostic is not None
            else None
        )
        if expected_kind == "stopped":
            if event["diagnostic_fingerprint"] != "" or status != "" or score is not None:
                raise ContractError(f"{event['_source']}: stopped event must clear feedback fields")
        else:
            expected_status = "passed" if bound_attempt.proven else "failed"
            if (
                status != expected_status
                or score is None
                or not math.isclose(float(score), bound_attempt.graded_score, abs_tol=1e-12)
            ):
                raise ContractError(
                    f"{event['_source']}: event status/score does not bind its attempt"
                )
            if expected_feedback is not None and (
                event["diagnostic_fingerprint"] != expected_feedback.fingerprint
            ):
                raise ContractError(
                    f"{event['_source']}: diagnostic_fingerprint does not bind attempt payload"
                )
        if expected_candidate is not None and event["candidate_fingerprint"] != expected_candidate:
            raise ContractError(
                f"{event['_source']}: candidate_fingerprint does not bind attempt payload"
            )
        if expected_kind == "oracle_evaluated" and detail_sha256 != _EMPTY_SHA256:
            raise ContractError(f"{event['_source']}: oracle_evaluated detail must be empty")
        if expected_kind == "repair_requested" and detail_sha256 != _REPAIR_REQUESTED_SHA256:
            raise ContractError(
                f"{event['_source']}: repair_requested detail does not match frozen protocol"
            )

    stop = stops[0]
    if (
        stop.get("task") != task
        or stop.get("difficulty") != start.task_difficulties[task]
        or stop.get("arm") != arm
        or stop.get("pi_run_id") != pi_run_id
    ):
        raise ContractError(f"{stop['_source']}: PI stop identity mismatch")
    stop_kind = _required(stop, "stop")
    if not isinstance(stop_kind, str) or not stop_kind:
        raise ContractError(f"{stop['_source']}: stop must be a non-empty string")
    verified = _required(stop, "verified")
    if not isinstance(verified, bool):
        raise ContractError(f"{stop['_source']}: verified must be boolean")
    if not isinstance(_required(stop, "improved"), bool):
        raise ContractError(f"{stop['_source']}: improved must be boolean")
    stop_elapsed = _strict_int(_required(stop, "elapsed_ms"), label=f"{stop['_source']}.elapsed_ms")
    if stop_elapsed < previous_elapsed:
        raise ContractError(f"{stop['_source']}: pi_stop elapsed_ms predates lifecycle events")
    stop_detail_sha256 = _required(stop, "stop_detail_sha256")
    if not _is_sha256(stop_detail_sha256):
        raise ContractError(f"{stop['_source']}: stop_detail_sha256 must be SHA-256")
    if events[-1]["detail_sha256"] != stop_detail_sha256:
        raise ContractError(f"{label}: stopped event detail does not bind pi_stop detail")
    evaluations = _strict_int(
        _required(stop, "evaluations"), label=f"{stop['_source']}.evaluations", minimum=1
    )
    repairs = _strict_int(_required(stop, "repairs"), label=f"{stop['_source']}.repairs")
    event_count = _strict_int(
        _required(stop, "event_count"), label=f"{stop['_source']}.event_count"
    )
    if evaluations != len(attempts) or repairs != len(attempts) - 1:
        raise ContractError(f"{label}: pi_stop evaluations/repairs do not conserve attempts")
    if event_count != len(events):
        raise ContractError(f"{label}: pi_stop event_count does not match PI events")
    if verified != bool(summary["proven"]) or (stop_kind == "complete") != verified:
        raise ContractError(f"{label}: verified/complete/task_summary outcomes disagree")
    if summary["pi_stop"] != stop_kind:
        raise ContractError(f"{label}: task_summary pi_stop disagrees with lifecycle")
    reported_input = _strict_int(
        _required(stop, "reported_input_tokens"),
        label=f"{stop['_source']}.reported_input_tokens",
    )
    reported_output = _strict_int(
        _required(stop, "reported_output_tokens"),
        label=f"{stop['_source']}.reported_output_tokens",
    )
    if reported_input != sum(item.input_tokens for item in attempts[1:]) or reported_output != sum(
        item.output_tokens for item in attempts[1:]
    ):
        raise ContractError(f"{label}: reported repair-token usage does not conserve attempts")
    best_attempt = _strict_int(
        _required(stop, "best_attempt"), label=f"{stop['_source']}.best_attempt"
    )
    current_attempt = _strict_int(
        _required(stop, "current_attempt"), label=f"{stop['_source']}.current_attempt"
    )
    if best_attempt >= len(attempts) or current_attempt >= len(attempts):
        raise ContractError(f"{label}: best/current attempt index is outside lifecycle")
    if current_attempt != len(attempts) - 1:
        raise ContractError(f"{label}: current_attempt must bind the final evaluation")
    if verified and best_attempt != len(attempts) - 1:
        raise ContractError(f"{label}: verified result must bind the final attempt")


def _validate_record_layout(
    ordered_records: Sequence[Mapping[str, Any]],
    *,
    start: RunStart,
) -> None:
    """Validate the runner's exact append-only task/arm block layout."""
    cursor = 1
    for task_index, task in enumerate(start.task_order):
        rotation = (start.seed_offset + task_index) % len(ARMS)
        expected_arm_order = ARMS[rotation:] + ARMS[:rotation]
        for arm in expected_arm_order:
            if arm == "pi_decoy":
                if cursor >= len(ordered_records):
                    raise ContractError(
                        f"run {start.run_id!r}: missing pi_decoy_setup for task {task!r}"
                    )
                setup = ordered_records[cursor]
                if (
                    setup.get("record_type") != "pi_decoy_setup"
                    or setup.get("task") != task
                    or setup.get("arm") != arm
                ):
                    raise ContractError(
                        f"{setup['_source']}: expected pi_decoy_setup before "
                        f"task {task!r} arm {arm!r}"
                    )
                cursor += 1
            block_count = 0
            while cursor < len(ordered_records):
                record = ordered_records[cursor]
                if record.get("record_type") != "attempt":
                    break
                if record.get("task") != task or record.get("arm") != arm:
                    break
                block_count += 1
                raw_attempt = _strict_int(
                    _required(record, "attempt"),
                    label=f"{record['_source']}.attempt",
                    minimum=1,
                )
                if raw_attempt != block_count:
                    raise ContractError(
                        f"{record['_source']}: attempt block for task {task!r} arm {arm!r} "
                        f"must be in file order 1..N; got {raw_attempt} at position {block_count}"
                    )
                cursor += 1
            if block_count == 0:
                observed = (
                    ordered_records[cursor].get("record_type")
                    if cursor < len(ordered_records)
                    else "<eof>"
                )
                raise ContractError(
                    f"run {start.run_id!r}: expected contiguous attempt block for "
                    f"task {task!r} arm {arm!r}, found {observed!r}"
                )
            if arm not in {"pi_repair", "pi_decoy"}:
                continue
            event_count = 0
            while (
                cursor < len(ordered_records)
                and ordered_records[cursor].get("record_type") == "pi_event"
            ):
                record = ordered_records[cursor]
                if record.get("task") != task or record.get("arm") != arm:
                    raise ContractError(
                        f"{record['_source']}: PI event block is not contiguous for "
                        f"task {task!r} arm {arm!r}"
                    )
                event_count += 1
                cursor += 1
            if event_count == 0:
                raise ContractError(
                    f"run {start.run_id!r}: missing contiguous PI event block for "
                    f"task {task!r} arm {arm!r}"
                )
            if cursor >= len(ordered_records):
                raise ContractError(
                    f"run {start.run_id!r}: missing pi_stop after task {task!r} arm {arm!r}"
                )
            stop = ordered_records[cursor]
            if (
                stop.get("record_type") != "pi_stop"
                or stop.get("task") != task
                or stop.get("arm") != arm
            ):
                raise ContractError(
                    f"{stop['_source']}: expected pi_stop after contiguous PI events for "
                    f"task {task!r} arm {arm!r}"
                )
            cursor += 1
        if cursor >= len(ordered_records):
            raise ContractError(f"run {start.run_id!r}: missing task_summary for {task!r}")
        summary = ordered_records[cursor]
        if summary.get("record_type") != "task_summary" or summary.get("task") != task:
            raise ContractError(
                f"{summary['_source']}: task group order mismatch; expected "
                f"task_summary for {task!r}"
            )
        cursor += 1
    if cursor >= len(ordered_records):
        raise ContractError(f"run {start.run_id!r}: missing terminal run_summary")
    terminal = ordered_records[cursor]
    if terminal.get("record_type") != "run_summary":
        raise ContractError(f"{terminal['_source']}: run_summary must terminate the run file")
    cursor += 1
    if cursor != len(ordered_records):
        extra = ordered_records[cursor]
        raise ContractError(f"{extra['_source']}: records after terminal run_summary are forbidden")


def _build_run(run_id: str, records: Sequence[dict[str, Any]]) -> Run:
    source_paths = {str(record["_source_path"]) for record in records}
    if len(source_paths) != 1:
        raise ContractError(f"run {run_id!r}: records must live in exactly one JSONL file")
    ordered_records = sorted(records, key=lambda record: int(record["_source_lineno"]))
    sequences = [
        _strict_int(
            _required(record, "record_sequence"),
            label=f"{record['_source']}.record_sequence",
        )
        for record in ordered_records
    ]
    if sequences != list(range(len(sequences))):
        raise ContractError(
            f"run {run_id!r}: record_sequence must be contiguous 0..N-1 in file order"
        )
    if ordered_records[0].get("record_type") != "run_start":
        raise ContractError(f"run {run_id!r}: record_sequence 0 must be run_start")

    starts = [record for record in records if record.get("record_type") == "run_start"]
    summaries = [record for record in records if record.get("record_type") == "run_summary"]
    if len(starts) != 1:
        raise ContractError(f"run {run_id!r}: expected exactly one run_start, got {len(starts)}")
    if len(summaries) != 1:
        raise ContractError(
            f"run {run_id!r}: expected exactly one run_summary, got {len(summaries)}"
        )
    start = _validate_start(starts[0])
    if start.run_id != run_id:
        raise ContractError(f"run grouping mismatch: {run_id!r} != {start.run_id!r}")
    for record in ordered_records:
        _validate_common(record, start=start)
    _validate_record_layout(ordered_records, start=start)

    task_summaries: dict[str, dict[str, Any]] = {}
    difficulties: dict[str, str] = {}
    for record in ordered_records:
        if record.get("record_type") != "task_summary":
            continue
        raw_task = record.get("task")
        if raw_task not in start.task_difficulties:
            raise ContractError(f"{record['_source']}: task is absent from run_start.tasks")
        task_index = start.task_order.index(str(raw_task))
        rotation = (start.seed_offset + task_index) % len(ARMS)
        expected_arm_order = ARMS[rotation:] + ARMS[:rotation]
        task, difficulty, arms = _validate_task_summary(
            record,
            start=start,
            expected_arm_order=expected_arm_order,
        )
        if task in task_summaries:
            raise ContractError(f"run {run_id!r}: duplicate task_summary for {task!r}")
        task_summaries[task] = arms
        difficulties[task] = difficulty
    if not task_summaries:
        raise ContractError(f"run {run_id!r}: no task_summary records")
    if list(task_summaries) != start.task_order:
        raise ContractError(f"run {run_id!r}: task_summary order must match run_start.tasks")
    if difficulties != start.task_difficulties:
        raise ContractError(f"run {run_id!r}: task difficulties differ from run_start.tasks")
    for task_index, task in enumerate(start.task_order):
        observed_order: list[str] = []
        for record in ordered_records:
            if record.get("record_type") == "attempt" and record.get("task") == task:
                arm = str(record.get("arm"))
                if arm not in observed_order:
                    observed_order.append(arm)
        rotation = (start.seed_offset + task_index) % len(ARMS)
        expected_order = list(ARMS[rotation:] + ARMS[:rotation])
        if observed_order != expected_order:
            raise ContractError(
                f"run {run_id!r} task {task!r}: observed arm execution order "
                f"{observed_order!r} != {expected_order!r}"
            )

    attempts: dict[tuple[str, str], list[Attempt]] = defaultdict(list)
    decoy_setups: dict[str, DecoySetup] = {}
    pi_events: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    pi_stops: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in ordered_records:
        record_type = record.get("record_type")
        if record_type == "attempt":
            attempt = _validate_attempt(record, start=start)
            attempts[(attempt.task, attempt.arm)].append(attempt)
        elif record_type == "pi_decoy_setup":
            setup = _validate_decoy_setup(record, start=start)
            if setup.task in decoy_setups:
                raise ContractError(
                    f"{record['_source']}: duplicate pi_decoy_setup for {setup.task!r}"
                )
            decoy_setups[setup.task] = setup
        elif record_type in {"pi_event", "pi_stop"}:
            lifecycle_task, lifecycle_arm = record.get("task"), record.get("arm")
            if lifecycle_task not in task_summaries or lifecycle_arm not in {
                "pi_repair",
                "pi_decoy",
            }:
                raise ContractError(f"{record['_source']}: invalid PI lifecycle identity")
            target = pi_events if record_type == "pi_event" else pi_stops
            target[(str(lifecycle_task), str(lifecycle_arm))].append(record)
        elif record_type not in {
            "run_start",
            "task_summary",
            "run_summary",
            "pi_event",
            "pi_stop",
            "pi_decoy_setup",
        }:
            raise ContractError(f"{record['_source']}: unknown record_type {record_type!r}")

    expected_pairs = {(task, arm) for task in task_summaries for arm in ARMS}
    if set(attempts) != expected_pairs:
        missing = sorted(expected_pairs - set(attempts))
        extra = sorted(set(attempts) - expected_pairs)
        raise ContractError(
            f"run {run_id!r}: attempt coverage mismatch; missing={missing!r} extra={extra!r}"
        )
    if set(decoy_setups) != set(task_summaries):
        raise ContractError(
            f"run {run_id!r}: pi_decoy_setup coverage must exactly match the task band"
        )
    for (task, arm), arm_attempts in attempts.items():
        if any(attempt.difficulty != difficulties[task] for attempt in arm_attempts):
            raise ContractError(f"run {run_id!r} task {task!r} arm {arm!r}: difficulty mismatch")
        declared = bool(task_summaries[task][arm]["proven"])
        _validate_attempt_chain(
            start=start,
            task=task,
            arm=arm,
            attempts=arm_attempts,
            declared_proven=declared,
            decoy_setup=decoy_setups.get(task) if arm == "pi_decoy" else None,
        )
        expected_usage = {
            "attempts": len(arm_attempts),
            "input_tokens": sum(attempt.input_tokens for attempt in arm_attempts),
            "output_tokens": sum(attempt.output_tokens for attempt in arm_attempts),
            "model_calls": sum(attempt.model_calls for attempt in arm_attempts),
            "oracle_calls": sum(attempt.oracle_calls for attempt in arm_attempts),
        }
        for field, expected in expected_usage.items():
            actual = int(task_summaries[task][arm][field])
            if actual != expected:
                raise ContractError(
                    f"run {run_id!r} task {task!r} arm {arm!r}: "
                    f"task_summary {field}={actual} != attempts {expected}"
                )
        expected_graded = max((attempt.graded_score for attempt in arm_attempts), default=0.0)
        if not math.isclose(
            float(task_summaries[task][arm]["graded_score"]),
            expected_graded,
            abs_tol=1e-12,
        ):
            raise ContractError(
                f"run {run_id!r} task {task!r} arm {arm!r}: "
                "task_summary graded_score disagrees with attempts"
            )
        expected_setup_calls = 1 if arm == "pi_decoy" else 0
        if task_summaries[task][arm]["setup_oracle_calls"] != expected_setup_calls:
            raise ContractError(
                f"run {run_id!r} task {task!r} arm {arm!r}: "
                f"setup_oracle_calls must be {expected_setup_calls}"
            )
        if arm in {"pi_repair", "pi_decoy"}:
            _validate_pi_lifecycle(
                start=start,
                task=task,
                arm=arm,
                attempts=arm_attempts,
                summary=task_summaries[task][arm],
                events=pi_events[(task, arm)],
                stops=pi_stops[(task, arm)],
            )
        elif task_summaries[task][arm]["pi_stop"] is not None:
            raise ContractError(f"run {run_id!r} task {task!r} arm {arm!r}: non-PI arm has pi_stop")

    _validate_run_summary(
        summaries[0],
        start=start,
        task_summaries=task_summaries,
        difficulties=difficulties,
    )
    return Run(
        run_id=run_id,
        backend=start.backend,
        model_id=start.model_id,
        endpoint_class=start.endpoint_class,
        endpoint_fingerprint=start.endpoint_fingerprint,
        temperature=start.temperature,
        max_tokens_per_attempt=start.max_tokens_per_attempt,
        oracle_isolation=start.oracle_isolation,
        sandbox_runner_sha256=start.sandbox_runner_sha256,
        lean_toolchain=start.lean_toolchain,
        lean_version=start.lean_version,
        lean_binary_sha256=start.lean_binary_sha256,
        k=start.k,
        seed_offset=start.seed_offset,
        timestamp_utc=start.timestamp_utc,
        harness_version=start.harness_version,
        payload_mode=start.payload_mode,
        git_commit=start.git_commit,
        git_dirty=start.git_dirty,
        git_status_sha256=start.git_status_sha256,
        artifact_hashes=start.artifact_hashes,
        task_summaries=task_summaries,
        attempts=dict(attempts),
        decoy_setups=decoy_setups,
        task_order=list(start.task_order),
        difficulties=difficulties,
        task_hashes=start.task_hashes,
    )


def _validated_runs(records: Sequence[dict[str, Any]]) -> list[Run]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        run_id = record.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise ContractError(f"{record['_source']}: run_id must be a non-empty string")
        grouped[run_id].append(record)
    runs = sorted(
        (_build_run(run_id, rows) for run_id, rows in grouped.items()), key=lambda r: r.seed_offset
    )
    seed_offsets = [run.seed_offset for run in runs]
    if len(seed_offsets) != len(set(seed_offsets)):
        raise ContractError("seed_offset values must be unique across runs")
    first = runs[0]
    expected_tasks = set(first.task_summaries)
    for run in runs[1:]:
        if (
            run.backend != first.backend
            or run.model_id != first.model_id
            or run.endpoint_class != first.endpoint_class
            or run.endpoint_fingerprint != first.endpoint_fingerprint
            or run.temperature != first.temperature
            or run.max_tokens_per_attempt != first.max_tokens_per_attempt
            or run.oracle_isolation != first.oracle_isolation
            or run.sandbox_runner_sha256 != first.sandbox_runner_sha256
            or run.lean_toolchain != first.lean_toolchain
            or run.lean_version != first.lean_version
            or run.lean_binary_sha256 != first.lean_binary_sha256
            or run.k != first.k
        ):
            raise ContractError(
                "model, endpoint, sandbox, Lean toolchain, or budget design changed inside batch"
            )
        if run.harness_version != first.harness_version:
            raise ContractError("all paired runs must use the same harness_version")
        if run.payload_mode != first.payload_mode:
            raise ContractError("all paired runs must use the same payload_mode")
        if (
            run.git_commit != first.git_commit
            or run.git_dirty != first.git_dirty
            or run.git_status_sha256 != first.git_status_sha256
        ):
            raise ContractError("git provenance changed inside the paired batch")
        if set(run.task_summaries) != expected_tasks or run.task_order != first.task_order:
            raise ContractError("all paired runs must contain the same ordered task band")
        if run.difficulties != first.difficulties or run.task_hashes != first.task_hashes:
            raise ContractError("task band labels or hashes changed inside batch")
        if run.artifact_hashes != first.artifact_hashes:
            raise ContractError("artifact hashes changed inside the paired batch")
    return runs


def _pair_block(values: Iterable[tuple[int, int]], arm_a: str, arm_b: str) -> dict[str, Any]:
    wins = ties = losses = 0
    deltas: list[int] = []
    for a_value, b_value in values:
        delta = a_value - b_value
        deltas.append(delta)
        if delta > 0:
            wins += 1
        elif delta < 0:
            losses += 1
        else:
            ties += 1
    return {
        "treatment": arm_a,
        "baseline": arm_b,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "non_ties": wins + losses,
        "n": wins + ties + losses,
        "p_two_sided": sign_test_two_sided(wins, losses),
        "deltas": deltas,
    }


def _task_rows(runs: Sequence[Run]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n_runs = len(runs)
    for task in sorted(runs[0].task_summaries):
        counts = {
            arm: sum(bool(run.task_summaries[task][arm]["proven"]) for run in runs) for arm in ARMS
        }
        difficulty = runs[0].difficulties[task]
        partial = any(0 < value < n_runs for value in counts.values())
        discriminating = len(set(counts.values())) > 1
        # Frozen definition: partial competence in at least one arm makes a headroom task live.
        # Equal arm totals remain live ties (the historical double/pow2_pos cases).
        live = difficulty == "headroom" and partial
        delta = counts["pi_repair"] - counts["bestN"]
        rows.append(
            {
                "task": task,
                "difficulty": difficulty,
                "runs": n_runs,
                "counts": counts,
                "partial": partial,
                "discriminating": discriminating,
                "live_discriminating": live,
                "delta_pi_repair_bestN": delta,
            }
        )
    rows.sort(key=lambda row: (-row["delta_pi_repair_bestN"], row["task"]))
    return rows


def _comparison(
    runs: Sequence[Run], *, baseline: str, tasks: Sequence[str]
) -> dict[str, dict[str, Any]]:
    per_run = _pair_block(
        (
            (
                sum(bool(run.task_summaries[task]["pi_repair"]["proven"]) for task in tasks),
                sum(bool(run.task_summaries[task][baseline]["proven"]) for task in tasks),
            )
            for run in runs
        ),
        "pi_repair",
        baseline,
    )
    per_task = _pair_block(
        (
            (
                sum(bool(run.task_summaries[task]["pi_repair"]["proven"]) for run in runs),
                sum(bool(run.task_summaries[task][baseline]["proven"]) for run in runs),
            )
            for task in tasks
        ),
        "pi_repair",
        baseline,
    )
    return {"per_run": per_run, "per_task": per_task}


def _success_at_budget(attempts: Sequence[Attempt], budget: int) -> bool:
    cumulative = 0
    for attempt in attempts:
        cumulative += attempt.total_tokens
        if cumulative > budget:
            break
        if attempt.proven:
            return True
    return False


def _matched_budget_comparison(
    runs: Sequence[Run], *, baseline: str, tasks: Sequence[str]
) -> dict[str, Any]:
    paired: dict[tuple[str, str], tuple[bool, bool]] = {}
    budgets: list[int] = []
    hidden_observations: list[dict[str, str]] = []
    for run in runs:
        for task in tasks:
            treatment_attempts = run.attempts[(task, "pi_repair")]
            baseline_attempts = run.attempts[(task, baseline)]
            treatment_total = sum(attempt.total_tokens for attempt in treatment_attempts)
            baseline_total = sum(attempt.total_tokens for attempt in baseline_attempts)
            budget = min(treatment_total, baseline_total)
            if budget <= 0:
                hidden_observations.append(
                    {"run_id": run.run_id, "task": task, "baseline": baseline}
                )
                continue
            budgets.append(budget)
            paired[(run.run_id, task)] = (
                _success_at_budget(treatment_attempts, budget),
                _success_at_budget(baseline_attempts, budget),
            )
    if hidden_observations:
        return {
            "scope": "live_discriminating_headroom_tasks",
            "available": False,
            "reason": "one or more paired observations have hidden 0/0 token usage",
            "hidden_observations": hidden_observations,
            "observations": len(paired),
            "per_run": None,
            "per_task": None,
        }
    per_run = _pair_block(
        (
            (
                sum(paired[(run.run_id, task)][0] for task in tasks),
                sum(paired[(run.run_id, task)][1] for task in tasks),
            )
            for run in runs
        ),
        "pi_repair",
        baseline,
    )
    per_task = _pair_block(
        (
            (
                sum(paired[(run.run_id, task)][0] for run in runs),
                sum(paired[(run.run_id, task)][1] for run in runs),
            )
            for task in tasks
        ),
        "pi_repair",
        baseline,
    )
    return {
        "scope": "live_discriminating_headroom_tasks",
        "available": True,
        "observations": len(paired),
        "budget_min": min(budgets) if budgets else None,
        "budget_max": max(budgets) if budgets else None,
        "budget_mean": round(sum(budgets) / len(budgets), 4) if budgets else None,
        "per_run": per_run,
        "per_task": per_task,
    }


def _usage(runs: Sequence[Run], *, tasks: set[str] | None = None) -> dict[str, dict[str, int]]:
    totals = {
        arm: {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "model_calls": 0,
            "oracle_calls": 0,
        }
        for arm in ARMS
    }
    if tasks is not None and not tasks:
        return totals
    for run in runs:
        for (task, arm), attempts in run.attempts.items():
            if tasks is not None and task not in tasks:
                continue
            for attempt in attempts:
                totals[arm]["input_tokens"] += attempt.input_tokens
                totals[arm]["output_tokens"] += attempt.output_tokens
                totals[arm]["total_tokens"] += attempt.total_tokens
                totals[arm]["model_calls"] += attempt.model_calls
                totals[arm]["oracle_calls"] += attempt.oracle_calls
    for arm, arm_usage in totals.items():
        if any(arm_usage[key] <= 0 for key in ("model_calls", "oracle_calls")):
            raise ContractError(f"missing or zero call accounting for arm {arm!r}")
    return totals


def _run_design_mismatches(runs: Sequence[Run], manifest: Mapping[str, Any]) -> dict[str, Any]:
    expected = manifest["run_design"]
    first = runs[0]
    observed = {
        "backend": first.backend,
        "model_id": first.model_id,
        "endpoint_class": first.endpoint_class,
        "temperature": first.temperature,
        "max_tokens_per_attempt": first.max_tokens_per_attempt,
        "oracle_isolation": first.oracle_isolation,
        "lean_toolchain": first.lean_toolchain,
        "lean_version": first.lean_version,
        "lean_binary_sha256": first.lean_binary_sha256,
        "k": first.k,
        "replications": len(runs),
        "seed_offsets": [run.seed_offset for run in runs],
        "task_band": [
            {
                "name": task,
                "difficulty": first.difficulties[task],
                "task_sha256": first.task_hashes[task],
            }
            for task in first.task_order
        ],
    }
    mismatches = {
        key: {"run": observed[key], "expected": expected[key]}
        for key in observed
        if observed[key] != expected[key]
    }
    sandbox_expected = manifest["artifact_hashes"]["lean_sandbox_runner_macos"]
    if first.sandbox_runner_sha256 != sandbox_expected:
        mismatches["sandbox_runner_sha256"] = {
            "run": first.sandbox_runner_sha256,
            "expected": sandbox_expected,
        }
    return mismatches


def _zero_usage_attempts(runs: Sequence[Run]) -> list[dict[str, Any]]:
    return [
        {
            "run_id": run.run_id,
            "task": task,
            "arm": arm,
            "attempt": attempt.index,
        }
        for run in runs
        for (task, arm), attempts in run.attempts.items()
        for attempt in attempts
        if attempt.input_tokens == 0 and attempt.output_tokens == 0
    ]


def _setup_oracle_usage(runs: Sequence[Run], *, tasks: set[str] | None = None) -> dict[str, int]:
    """Report setup-only oracle work separately; it is excluded from solve-budget parity."""
    return {
        arm: sum(
            int(run.task_summaries[task][arm]["setup_oracle_calls"])
            for run in runs
            for task in run.task_summaries
            if tasks is None or task in tasks
        )
        for arm in ARMS
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _usage_ratios(
    usage: Mapping[str, Mapping[str, int]],
) -> dict[str, dict[str, float | None]]:
    treatment = usage["pi_repair"]
    return {
        baseline: {
            key: _ratio(treatment[key], usage[baseline][key])
            for key in ("total_tokens", "model_calls", "oracle_calls")
        }
        for baseline in COMPARATORS
    }


def _favored(block: Mapping[str, Any], alpha: float) -> bool:
    return (
        block["non_ties"] >= _MIN_SIGN_NON_TIES
        and block["wins"] > block["losses"]
        and block["p_two_sided"] < alpha
    )


def _sign_blocks_ready(*blocks: Mapping[str, Any]) -> bool:
    return all(block["non_ties"] >= _MIN_SIGN_NON_TIES for block in blocks)


def _gate(status: str, reasons: Sequence[str], **evidence: Any) -> dict[str, Any]:
    if status not in {"PASS", "FAIL", "ABSENT"}:
        raise ValueError(f"invalid gate status: {status}")
    return {"status": status, "reasons": list(reasons), **evidence}


def analyze_paths(
    paths: Iterable[str | Path],
    *,
    alpha: float = 0.05,
    tost_margin: float = 1.0,
    parity_low: float = 0.8,
    parity_high: float = 1.25,
    manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate and analyze one or more v2 JSONL files.

    Missing arms/usage fields, non-positive attempt telemetry, missing artifact hashes,
    inconsistent summaries, or mixed provenance raise :class:`ContractError`.
    """
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    if not 0 < parity_low <= 1 <= parity_high:
        raise ValueError("parity bounds must satisfy 0 < low <= 1 <= high")
    manifest = _load_manifest(
        Path(manifest_path).resolve() if manifest_path is not None else DEFAULT_MANIFEST_PATH
    )
    frozen = manifest["thresholds"]
    supplied_thresholds = {
        "alpha": alpha,
        "tost_margin": tost_margin,
        "parity_low": parity_low,
        "parity_high": parity_high,
    }
    threshold_overrides = {
        key: {"supplied": supplied, "frozen": frozen[key]}
        for key, supplied in supplied_thresholds.items()
        if not math.isclose(float(supplied), float(frozen[key]), rel_tol=0.0, abs_tol=1e-12)
    }
    threshold_override = bool(threshold_overrides)
    min_live_tasks = int(frozen["min_live_tasks"])
    concentration_threshold = float(frozen["top_task_concentration"])
    files = _jsonl_files(paths)
    runs = _validated_runs(_read_records(files))
    if runs[0].harness_version != manifest["harness_version"]:
        raise ContractError("run harness_version differs from the frozen manifest")
    try:
        oracle_replay = _replay_oracle_integrity(runs=runs, manifest=manifest)
    except Exception as exc:  # noqa: BLE001 -- replay integrity must fail closed
        oracle_replay = {
            "status": "FAIL",
            "attempt_count": sum(
                len(attempts) for run in runs for attempts in run.attempts.values()
            ),
            "replayed_count": 0,
            "setup_count": sum(len(run.decoy_setups) for run in runs),
            "setup_replayed_count": 0,
            "receipt_sha256": None,
            "mismatch_count": 0,
            "mismatches": [],
            "errors": [f"{type(exc).__name__}: {exc}"],
            "identity": None,
        }
    rows = _task_rows(runs)
    headroom_tasks = [row["task"] for row in rows if row["difficulty"] == "headroom"]
    live_tasks = [row["task"] for row in rows if row["live_discriminating"]]
    if not headroom_tasks:
        raise ContractError("batch has no headroom tasks")

    comparisons: dict[str, Any] = {}
    for baseline in COMPARATORS:
        comparisons[f"pi_repair_vs_{baseline}"] = {
            "all_headroom": _comparison(runs, baseline=baseline, tasks=headroom_tasks),
            "live_discriminating": _comparison(runs, baseline=baseline, tasks=live_tasks),
            "matched_cumulative_tokens": _matched_budget_comparison(
                runs, baseline=baseline, tasks=live_tasks
            ),
        }

    decoy_bestn_per_run = _pair_block(
        (
            (
                sum(bool(run.task_summaries[task]["pi_decoy"]["proven"]) for task in live_tasks),
                sum(bool(run.task_summaries[task]["bestN"]["proven"]) for task in live_tasks),
            )
            for run in runs
        ),
        "pi_decoy",
        "bestN",
    )
    decoy_tost = tost_equivalence(decoy_bestn_per_run["deltas"], margin=tost_margin, alpha=alpha)

    positive_deltas = [
        row["delta_pi_repair_bestN"]
        for row in rows
        if row["difficulty"] == "headroom" and row["delta_pi_repair_bestN"] > 0
    ]
    top_task_delta_fraction = (
        max(positive_deltas) / sum(positive_deltas) if positive_deltas else None
    )
    all_usage = _usage(runs)
    headroom_usage = _usage(runs, tasks=set(headroom_tasks))
    live_usage = _usage(runs, tasks=set(live_tasks))
    ratios = _usage_ratios(live_usage)
    zero_usage_attempts = _zero_usage_attempts(runs)

    primary = comparisons["pi_repair_vs_bestN"]["live_discriminating"]
    if len(live_tasks) < min_live_tasks:
        p1 = _gate(
            "ABSENT",
            [f"only {len(live_tasks)} live-discriminating headroom tasks; need >={min_live_tasks}"],
            live_task_count=len(live_tasks),
        )
    elif not _sign_blocks_ready(primary["per_run"], primary["per_task"]):
        p1 = _gate(
            "ABSENT",
            [f"P1 requires >={_MIN_SIGN_NON_TIES} non-ties per-run and per-task"],
            per_run=primary["per_run"],
            per_task=primary["per_task"],
            live_task_count=len(live_tasks),
        )
    else:
        p1_pass = _favored(primary["per_run"], alpha) and _favored(primary["per_task"], alpha)
        p1 = _gate(
            "PASS" if p1_pass else "FAIL",
            [] if p1_pass else ["pi_repair must beat bestN at p<alpha per-run and per-task"],
            per_run=primary["per_run"],
            per_task=primary["per_task"],
            live_task_count=len(live_tasks),
        )

    decoy_comparison = comparisons["pi_repair_vs_pi_decoy"]["live_discriminating"]
    if len(live_tasks) < min_live_tasks or decoy_tost["status"] == "ABSENT":
        p2 = _gate(
            "ABSENT",
            ["insufficient live tasks or paired runs for oracle-signal isolation"],
            tost=decoy_tost,
        )
    elif not _sign_blocks_ready(decoy_comparison["per_run"], decoy_comparison["per_task"]):
        p2 = _gate(
            "ABSENT",
            [f"P2 requires >={_MIN_SIGN_NON_TIES} non-ties per-run and per-task"],
            pi_vs_decoy=decoy_comparison,
            decoy_vs_bestN_tost=decoy_tost,
        )
    else:
        p2_pass = (
            _favored(decoy_comparison["per_run"], alpha)
            and _favored(decoy_comparison["per_task"], alpha)
            and bool(decoy_tost["equivalent"])
        )
        p2 = _gate(
            "PASS" if p2_pass else "FAIL",
            []
            if p2_pass
            else ["need pi_repair>pi_decoy per-run/per-task and pi_decoy≈bestN by TOST"],
            pi_vs_decoy=decoy_comparison,
            decoy_vs_bestN_tost=decoy_tost,
        )

    plain_comparison = comparisons["pi_repair_vs_plain_baseline"]["live_discriminating"]
    if len(live_tasks) < min_live_tasks:
        p3 = _gate(
            "ABSENT",
            [f"fewer than {min_live_tasks} live-discriminating headroom tasks"],
        )
    elif not _sign_blocks_ready(plain_comparison["per_run"], plain_comparison["per_task"]):
        p3 = _gate(
            "ABSENT",
            [f"P3 requires >={_MIN_SIGN_NON_TIES} non-ties per-run and per-task"],
            per_run=plain_comparison["per_run"],
            per_task=plain_comparison["per_task"],
        )
    else:
        p3_pass = _favored(plain_comparison["per_run"], alpha) and _favored(
            plain_comparison["per_task"], alpha
        )
        p3 = _gate(
            "PASS" if p3_pass else "FAIL",
            []
            if p3_pass
            else ["pi_repair must beat plain_baseline at p<alpha per-run and per-task"],
            per_run=plain_comparison["per_run"],
            per_task=plain_comparison["per_task"],
        )

    ratio_failures = [
        f"{baseline}.{metric}={value}"
        for baseline, fields in ratios.items()
        for metric, value in fields.items()
        if value is not None and not parity_low <= value <= parity_high
    ]
    matched_controls = {
        baseline: comparisons[f"pi_repair_vs_{baseline}"]["matched_cumulative_tokens"]
        for baseline in ("bestN", "pi_decoy", "plain_baseline")
    }
    if len(live_tasks) < min_live_tasks:
        p4 = _gate("ABSENT", [f"fewer than {min_live_tasks} live-discriminating headroom tasks"])
    elif zero_usage_attempts or any(
        not comparison["available"] for comparison in matched_controls.values()
    ):
        p4 = _gate(
            "ABSENT",
            ["token usage is hidden (0/0), so parity and matched-budget efficacy are unmeasurable"],
            raw_ratios=ratios,
            zero_usage_attempts=zero_usage_attempts,
            matched_cumulative_tokens=matched_controls,
        )
    elif any(
        not _sign_blocks_ready(comparison["per_run"], comparison["per_task"])
        for comparison in matched_controls.values()
    ):
        p4 = _gate(
            "ABSENT",
            [
                f"matched-token controls require >={_MIN_SIGN_NON_TIES} "
                "non-ties per-run and per-task"
            ],
            raw_ratios=ratios,
            matched_cumulative_tokens=matched_controls,
        )
    else:
        matched_failures = [
            baseline
            for baseline, comparison in matched_controls.items()
            if not (
                _favored(comparison["per_run"], alpha) and _favored(comparison["per_task"], alpha)
            )
        ]
        matched_pass = not matched_failures
        p4_pass = not ratio_failures and matched_pass
        reasons = []
        if ratio_failures:
            reasons.append(
                f"live-task usage ratios outside [{parity_low}, {parity_high}]: "
                + ", ".join(ratio_failures)
            )
        if matched_failures:
            reasons.append(
                "pi_repair edge does not survive matched cumulative-token budgets "
                f"against {matched_failures!r} with >={_MIN_SIGN_NON_TIES} non-ties"
            )
        p4 = _gate(
            "PASS" if p4_pass else "FAIL",
            reasons,
            raw_ratio_scope="live_discriminating_headroom_tasks",
            raw_ratios=ratios,
            bounds={"low": parity_low, "high": parity_high},
            matched_cumulative_tokens=matched_controls,
        )

    if oracle_replay["status"] != "PASS":
        replay_reasons = [
            "authoritative Lean replay must pass before efficacy gates can be interpreted"
        ]
        p1 = _gate("ABSENT", replay_reasons, oracle_replay=oracle_replay)
        p2 = _gate("ABSENT", replay_reasons, oracle_replay=oracle_replay)
        p3 = _gate("ABSENT", replay_reasons, oracle_replay=oracle_replay)
        p4 = _gate("ABSENT", replay_reasons, oracle_replay=oracle_replay)

    file_hashes = [{"path": str(path), "sha256": _sha256_file(path)} for path in files]
    raw_payload_complete = runs[0].payload_mode == "full" and all(
        attempt.raw_payload_complete
        for run in runs
        for attempts in run.attempts.values()
        for attempt in attempts
    )
    expected_run_hashes = {
        **manifest["artifact_hashes"],
        "manifest": manifest["sha256"],
        "preregistration_v2": manifest["preregistration_v2_sha256"],
    }
    provenance_mismatches = {
        key: {"run": runs[0].artifact_hashes.get(key), "expected": expected}
        for key, expected in expected_run_hashes.items()
        if runs[0].artifact_hashes.get(key) != expected
    }
    design_mismatches = _run_design_mismatches(runs, manifest)
    try:
        git_verification = _verify_git_provenance(
            commit=runs[0].git_commit,
            dirty=runs[0].git_dirty,
            status_sha256=runs[0].git_status_sha256,
            manifest=manifest,
            run_timestamps=[run.timestamp_utc for run in runs],
            jsonl_paths=files,
        )
    except Exception as exc:  # noqa: BLE001 -- provenance must fail closed
        git_verification = {
            "ok": False,
            "errors": [f"{type(exc).__name__}: {exc}"],
            "checked": {},
        }
    if threshold_override:
        p5_status = "FAIL"
        p5_reasons = ["analysis thresholds override the frozen manifest"]
    elif provenance_mismatches:
        p5_status = "FAIL"
        p5_reasons = ["run artifact hashes do not match the frozen manifest/preregistration"]
    elif design_mismatches:
        p5_status = "FAIL"
        p5_reasons = ["run envelope differs from the frozen run_design"]
    elif not git_verification["ok"]:
        p5_status = "FAIL"
        p5_reasons = ["git provenance does not bind the frozen files at the recorded commit"]
    elif oracle_replay["status"] == "FAIL":
        p5_status = "FAIL"
        p5_reasons = ["authoritative Lean replay did not reproduce recorded oracle results"]
    elif not raw_payload_complete:
        p5_status = "ABSENT"
        p5_reasons = [
            "P5 requires payload_mode=full and raw proof/diagnostic/feedback on every attempt"
        ]
    elif oracle_replay["status"] != "PASS":
        p5_status = "ABSENT"
        p5_reasons = ["authoritative Lean replay evidence is absent"]
    else:
        p5_status = "PASS"
        p5_reasons = []
    p5 = _gate(
        p5_status,
        p5_reasons,
        payload_mode=runs[0].payload_mode,
        raw_payload_complete=raw_payload_complete,
        artifact_hashes=runs[0].artifact_hashes,
        manifest=manifest,
        provenance_mismatches=provenance_mismatches,
        run_design_mismatches=design_mismatches,
        threshold_override=threshold_override,
        threshold_overrides=threshold_overrides,
        git={
            "commit": runs[0].git_commit,
            "dirty": runs[0].git_dirty,
            "status_sha256": runs[0].git_status_sha256,
            "verification": git_verification,
        },
        oracle_replay=oracle_replay,
        raw_jsonl_sha256=file_hashes,
        top_task_delta_fraction=top_task_delta_fraction,
        signal_concentrated=(
            top_task_delta_fraction is not None
            and top_task_delta_fraction > concentration_threshold
        ),
    )
    gates = {"P1": p1, "P2": p2, "P3": p3, "P4": p4, "P5": p5}
    confirm = all(gate["status"] == "PASS" for gate in gates.values())
    return {
        "schema": SCHEMA,
        "harness_version": runs[0].harness_version,
        "payload_mode": runs[0].payload_mode,
        "threshold_override": threshold_override,
        "threshold_overrides": threshold_overrides,
        "thresholds": {
            **supplied_thresholds,
            "min_live_tasks": min_live_tasks,
            "top_task_concentration": concentration_threshold,
        },
        "backend": runs[0].backend,
        "model_id": runs[0].model_id,
        "endpoint_class": runs[0].endpoint_class,
        "endpoint_fingerprint": runs[0].endpoint_fingerprint,
        "temperature": runs[0].temperature,
        "max_tokens_per_attempt": runs[0].max_tokens_per_attempt,
        "oracle_isolation": runs[0].oracle_isolation,
        "sandbox_runner_sha256": runs[0].sandbox_runner_sha256,
        "lean_toolchain": runs[0].lean_toolchain,
        "lean_version": runs[0].lean_version,
        "lean_binary_sha256": runs[0].lean_binary_sha256,
        "K": runs[0].k,
        "runs": len(runs),
        "seed_offsets": [run.seed_offset for run in runs],
        "timestamps_utc": [run.timestamp_utc for run in runs],
        "arms": list(ARMS),
        "tasks": rows,
        "headroom_task_count": len(headroom_tasks),
        "live_discriminating_tasks": live_tasks,
        "live_discriminating_task_count": len(live_tasks),
        "top_task_delta_fraction": top_task_delta_fraction,
        "signal_concentrated": (
            top_task_delta_fraction is not None
            and top_task_delta_fraction > concentration_threshold
        ),
        "comparisons": comparisons,
        "decoy_vs_bestN": {
            "per_run": decoy_bestn_per_run,
            "tost": decoy_tost,
        },
        "usage": {
            "all_tasks": all_usage,
            "headroom_tasks": headroom_usage,
            "live_discriminating_tasks": live_usage,
            "pi_repair_ratios": ratios,
            "zero_usage_attempts": zero_usage_attempts,
            "setup_oracle_calls_excluded": {
                "all_tasks": _setup_oracle_usage(runs),
                "headroom_tasks": _setup_oracle_usage(runs, tasks=set(headroom_tasks)),
            },
        },
        "provenance": {
            "artifact_hashes": runs[0].artifact_hashes,
            "manifest": manifest,
            "git": {
                "commit": runs[0].git_commit,
                "dirty": runs[0].git_dirty,
                "status_sha256": runs[0].git_status_sha256,
                "verification": git_verification,
            },
            "oracle_replay": oracle_replay,
            "raw_jsonl_sha256": file_hashes,
        },
        "external_gates": {
            "B1_implementation_bridge": {
                "status": "EXTERNAL_REQUIRED",
                "required_for_final_claim": True,
                "evidence_contract": manifest["bridge_conformance"],
                "note": "This analyzer computes P1-P5 only and does not infer pytest state.",
            }
        },
        "gates": gates,
        "confirm_scope": "P1-P5_STATISTICAL_GATES_ONLY",
        "final_claim_confirm": None,
        "confirm": confirm,
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze the strict six-arm PI diagnostic-repair harness JSONL."
    )
    parser.add_argument("paths", nargs="+", help="JSONL files or directories.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON (the analyzer is JSON-only; retained for explicit scripts).",
    )
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument(
        "--tost-margin",
        type=float,
        default=1.0,
        help="Equivalence margin in successful live tasks per run.",
    )
    parser.add_argument("--parity-low", type=float, default=0.8)
    parser.add_argument("--parity-high", type=float, default=1.25)
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Frozen v2 manifest (default: sibling diagnostic_repair_harness_manifest.v2.json).",
    )
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = analyze_paths(
            args.paths,
            alpha=args.alpha,
            tost_margin=args.tost_margin,
            parity_low=args.parity_low,
            parity_high=args.parity_high,
            manifest_path=args.manifest,
        )
    except (ContractError, ValueError) as exc:
        print(
            json.dumps(
                {"schema": SCHEMA, "ok": False, "error": type(exc).__name__, "detail": str(exc)},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    indent = None if args.compact else 2
    print(json.dumps(result, ensure_ascii=False, indent=indent, sort_keys=True))
    return 0


__all__ = [
    "ARMS",
    "ARM_ORDER_POLICY",
    "ARTIFACT_HASH_KEYS",
    "COMPARATORS",
    "ContractError",
    "DEFAULT_MANIFEST_PATH",
    "MANIFEST_SCHEMA",
    "SCHEMA",
    "analyze_paths",
    "main",
    "sign_test_two_sided",
    "tost_equivalence",
]


if __name__ == "__main__":
    raise SystemExit(main())
