"""`apt run` gated runtime — wrap a legion run with G1/G2/G3 verify-by-default + a verified artifact.

The north-star "APT-zero" runtime (project-apt-ultracode-roadmap-2026-06-02, item ⑤): the user runs
one command; the closed legion loop executes; three *machine-checked* gates decide whether the run
produced a **verified, auditable artifact**. This is an OPERATIONAL claim (reproducible / audited /
correct-by-oracle), NOT a cognitive-quality claim — APT's measured cognitive advantage is ~0
(project-bhgman-efficacy-verdict-operational-substrate-2026-06-02).

  G1 ARTIFACT_EXISTS    — loop completed AND produced provides-keys; result hashed (sha256) = reproducibility.
  G2 ADVERSARY_RAN      — the 검증(naesengmoon) stage actually ran and passed = auditability (a different lens looked).
  G3 GROUND_TRUTH_GREEN — an external oracle (compiler/test) exited 0 = correctness. No oracle => SKIPPED, never auto-PASS.

Fail-closed: verified=True **iff** G1 ∧ G2 ∧ G3 all PASS. SKIPPED or FAIL ⇒ not verified — the runtime
refuses to certify what it cannot check (the same honesty the W1/W2 gates enforce).

# KG: project-apt-ultracode-roadmap-2026-06-02 (⑤ apt run runtime),
#     adr-seven-commander-legion-architecture-2026-05-27 (closed loop substrate)
"""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
from dataclasses import dataclass

from engine.legion.legion import GateFn, Legion
from engine.legion.legion_models import LegionRun

VERIFY_VERB = "검증"  # the naesengmoon (adversary) stage verb


@dataclass(frozen=True)
class GateVerdict:
    name: str
    status: str  # "PASS" | "FAIL" | "SKIPPED"
    detail: str

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


@dataclass(frozen=True)
class GatedRunResult:
    legion_run: LegionRun
    gates: tuple[GateVerdict, ...]
    artifact_sha256: str
    verified: bool

    def gate(self, name: str) -> GateVerdict | None:
        return next((g for g in self.gates if g.name == name), None)


def artifact_hash(run: LegionRun) -> str:
    """Deterministic sha256 over the run's observable result (provenance / reproducibility anchor)."""
    payload = {
        "completed": run.completed,
        "final_context_keys": sorted(run.final_context_keys),
        "outcomes": [[o.stage, o.verb, o.ok, o.detail] for o in run.outcomes],
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def eval_g1_artifact_exists(run: LegionRun) -> GateVerdict:
    if not run.completed:
        reason = run.contract_violation or run.gate_failure or "loop did not complete"
        return GateVerdict("G1_ARTIFACT_EXISTS", "FAIL", reason)
    produced = [o for o in run.outcomes if o.ok]
    if not produced or not run.final_context_keys:
        return GateVerdict("G1_ARTIFACT_EXISTS", "FAIL", "completed but produced no provides-keys")
    return GateVerdict(
        "G1_ARTIFACT_EXISTS",
        "PASS",
        f"{len(produced)} stage(s) ok, {len(run.final_context_keys)} context keys",
    )


# verdict content that must NOT certify the adversary as "passed" (oracle hard-gate FAIL,
# or the ensemble rejected/failed). 'REJECT' is defensive (verdict sources outside the
# naesengmoon PASS/CONDITIONAL_PASS/FAIL vocabulary).
_REJECTING_ENSEMBLE = frozenset({"REJECT", "FAIL"})


def eval_g2_adversary_ran(run: LegionRun, gate: object | None = None) -> GateVerdict:
    verify = [o for o in run.outcomes if o.verb == VERIFY_VERB]
    if not verify:
        return GateVerdict(
            "G2_ADVERSARY_RAN", "FAIL", "검증(naesengmoon) adversary stage did not run"
        )
    if not all(o.ok for o in verify):
        return GateVerdict("G2_ADVERSARY_RAN", "FAIL", "adversary stage ran but did not pass")
    # A stage can be ok=True (it ran without error) yet carry a FAIL/REJECT verdict —
    # inspect the verdict CONTENT, not just that the stage executed.
    verdict = run.final_verdict or {}
    oracle = verdict.get("oracle")
    ensemble = verdict.get("ensemble")
    if oracle == "FAIL" or ensemble in _REJECTING_ENSEMBLE:
        return GateVerdict(
            "G2_ADVERSARY_RAN",
            "FAIL",
            f"adversary ran but verdict not clean (oracle={oracle}, ensemble={ensemble})",
        )
    # R7/OQ1c: 게이트 주입 시 verdict 서명 진위도 요구 — 위조/미서명 final_verdict 탐지
    # (clean-looking 한 oracle/ensemble 만으로는 G2 통과 불가).
    if gate is not None and not gate.signature_valid(verdict):  # type: ignore[attr-defined]
        return GateVerdict(
            "G2_ADVERSARY_RAN",
            "FAIL",
            "adversary verdict signature invalid/absent (forged or unsigned)",
        )
    return GateVerdict(
        "G2_ADVERSARY_RAN",
        "PASS",
        f"naesengmoon 검증 ran and passed (oracle={oracle}, ensemble={ensemble})",
    )


def eval_g3_ground_truth(
    cmd: str | None, *, cwd: str | None = None, timeout: int = 600
) -> GateVerdict:
    if not cmd:
        return GateVerdict(
            "G3_GROUND_TRUTH_GREEN",
            "SKIPPED",
            "no --ground-truth oracle given; correctness uncertified (not verified)",
        )
    try:
        proc = subprocess.run(
            shlex.split(cmd), cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except Exception as exc:  # noqa: BLE001 — oracle failure is a gate FAIL, not a crash
        return GateVerdict("G3_GROUND_TRUTH_GREEN", "FAIL", f"oracle could not run: {exc}")
    if proc.returncode == 0:
        return GateVerdict("G3_GROUND_TRUTH_GREEN", "PASS", f"`{cmd}` exit 0")
    return GateVerdict("G3_GROUND_TRUTH_GREEN", "FAIL", f"`{cmd}` exit {proc.returncode}")


def run_gated(
    legion: Legion,
    context: dict,
    *,
    ground_truth_cmd: str | None = None,
    per_stage_gate: GateFn | None = None,
    gt_cwd: str | None = None,
) -> GatedRunResult:
    """Execute the closed legion loop, then apply the 3 run-level gates. Fail-closed."""
    run = legion.run(context=context, gate=per_stage_gate)
    gates = (
        eval_g1_artifact_exists(run),
        eval_g2_adversary_ran(run, gate=context.get("verdict_gate")),
        eval_g3_ground_truth(ground_truth_cmd, cwd=gt_cwd),
    )
    verified = all(g.passed for g in gates)
    return GatedRunResult(run, gates, artifact_hash(run), verified)


__all__ = [
    "GateVerdict",
    "GatedRunResult",
    "artifact_hash",
    "eval_g1_artifact_exists",
    "eval_g2_adversary_ran",
    "eval_g3_ground_truth",
    "run_gated",
]
