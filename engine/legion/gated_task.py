"""apt --task — gated single-task attempt (item ⑤ general half, HONEST version).

OVER-CLAIM GUARD (read first): this does NOT make the model smarter. APT's measured cognitive
advantage over a base agent is ~0 (project-bhgman-efficacy-verdict-operational-substrate-2026-06-02).
This wraps ONE task attempt in the same G1/G2/G3 verify-by-default + fail-closed verdict as the legion
runtime. The value is purely OPERATIONAL: the attempt is hashed (reproducible), adversarially reviewed
(audited), and oracle-checked (correct) — or it is honestly marked NOT VERIFIED. The "agent" is
whatever `produce_fn` is (the LLM via AgentClient, or a fake in tests); apt makes no quality claim
about the attempt itself — only about whether it passed three machine checks.

  G1 ARTIFACT_EXISTS    — the attempt produced a non-empty artifact (hashed = reproducible).
  G2 ADVERSARY_RAN      — an independent review actually ran and did not reject (audited).
  G3 GROUND_TRUTH_GREEN — an external oracle (compiler/test) exited 0 (correct). None => SKIPPED.

Fail-closed: verified iff G1 ∧ G2 ∧ G3 all PASS.

# KG: project-apt-ultracode-roadmap-2026-06-02 (⑤ general-task half),
#     project-bhgman-efficacy-verdict-operational-substrate-2026-06-02 (cognitive ~0)
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from engine.legion.gated_run import GateVerdict, eval_g3_ground_truth

ProduceFn = Callable[[str], str]
AdversaryFn = Callable[[str, str], dict]  # (task, artifact) -> {ran, rejected, detail}


@dataclass(frozen=True)
class TaskGatedResult:
    task: str
    artifact: str
    gates: tuple[GateVerdict, ...]
    artifact_sha256: str
    verified: bool

    def gate(self, name: str) -> GateVerdict | None:
        return next((g for g in self.gates if g.name == name), None)


def eval_g1_task(artifact: str) -> GateVerdict:
    if not artifact or not artifact.strip():
        return GateVerdict("G1_ARTIFACT_EXISTS", "FAIL", "attempt produced no artifact")
    return GateVerdict("G1_ARTIFACT_EXISTS", "PASS", f"artifact produced ({len(artifact)} chars)")


def eval_g2_task(review: dict | None) -> GateVerdict:
    if not review or not review.get("ran"):
        return GateVerdict("G2_ADVERSARY_RAN", "FAIL", "no adversarial review ran")
    if review.get("rejected"):
        return GateVerdict(
            "G2_ADVERSARY_RAN", "FAIL", f"adversary rejected: {review.get('detail', '')}"
        )
    return GateVerdict(
        "G2_ADVERSARY_RAN", "PASS", review.get("detail", "adversarial review passed")
    )


def run_task_gated(
    task: str,
    produce_fn: ProduceFn,
    *,
    adversary_fn: AdversaryFn | None = None,
    ground_truth_cmd: str | None = None,
    gt_cwd: str | None = None,
) -> TaskGatedResult:
    """Attempt `task` via produce_fn, then apply G1/G2/G3. Fail-closed. No cognitive claim."""
    artifact = produce_fn(task) or ""
    review = adversary_fn(task, artifact) if adversary_fn else None
    gates = (
        eval_g1_task(artifact),
        eval_g2_task(review),
        eval_g3_ground_truth(ground_truth_cmd, cwd=gt_cwd),
    )
    sha = hashlib.sha256(artifact.encode("utf-8")).hexdigest()
    verified = all(g.passed for g in gates)
    return TaskGatedResult(task, artifact, gates, sha, verified)


__all__ = [
    "AdversaryFn",
    "ProduceFn",
    "TaskGatedResult",
    "eval_g1_task",
    "eval_g2_task",
    "run_task_gated",
]
