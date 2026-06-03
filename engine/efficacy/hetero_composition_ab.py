"""Heterogeneous 7-commander composition A/B — harness + `realized` gate (offline-falsifiable).

Implements COMPOSITION_HETERO_PREREG.md. Tests whether the *heterogeneous* legion pipeline (재배맨
dispatching 획득→연결→창조→정리→검증→실현, each a DIFFERENT operation) beats a base-LLM at equal
compute — the axis single-agent measurement structurally cannot see. NOT the homogeneous evolve_loop
(`composition_ab.py`), which was retracted to LOOP-HYPOTHESIS=OPEN.

Oracle-AGNOSTIC by design: the three injected callables decouple the gate logic (arms / budget /
realized) from any task oracle, so the gate is unit-testable offline with fakes (proving it *can*
fire both ways), and the real run wires the Lean W4 oracle (public=lake/subgoals, hidden=
#print-axioms + disjunct-discharge + statement-fidelity) when a frontier backend is present.

  ARM1 base-monolith — best-of-N independent solves, pick by PUBLIC score.        (no roles)
  ARM2 hetero-legion — solve, then cycle the 6 distinct stage roles, keep non-worsening. (the hypothesis)
  ARM3 gate-only     — solve, then ONLY the 검증(verify) role.                      (ablation)
  realized = ARM2 > ARM1 AND ARM2 > ARM3  (paired bootstrap CI lower bound > 0, both).

# KG: project-apt-ultracode-roadmap-2026-06-02 (composition A/B pre-reg),
#     adr-seven-commander-legion-architecture-2026-05-27 (7군단장: 재배맨=출격 dispatch, 6 stage)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from engine.efficacy.p1_oracle_rerank_pilot import _bootstrap_ci

# (role, context_artifact, seed) -> (new_artifact, tokens). Injected LLM; fake in tests.
GenerateFn = Callable[[str, str, int], "tuple[str, int]"]
ScoreFn = Callable[[str], float]  # PUBLIC graded signal (what arms optimize)
HiddenFn = Callable[[str], bool]  # HIDDEN non-circular eval (eval only, never seen by arms)

# 6 heterogeneous stage roles (재배맨/출격 is the dispatcher of this pipeline, not a stage).
STAGE_ROLES = ("gather", "connect", "abstract", "prune", "verify", "realize")


@dataclass(frozen=True)
class ArmRun:
    arm: str
    artifact: str
    public: float
    tokens: int
    hidden_ok: bool


def _arm_monolith(
    gen: GenerateFn, public: ScoreFn, budget: int, seed0: int
) -> tuple[str, float, int]:
    best, best_s, tok, i = "", -1.0, 0, 0
    while tok < budget:
        art, t = gen("solve", "", seed0 + i)
        tok += t
        i += 1
        s = public(art)
        if s > best_s:
            best, best_s = art, s
    return best, best_s, tok


def _arm_pipeline(
    gen: GenerateFn, public: ScoreFn, budget: int, seed0: int, roles: tuple[str, ...]
) -> tuple[str, float, int]:
    """solve, then cycle `roles`, keeping a transform only if it does not lower the public score."""
    art, tok = gen("solve", "", seed0)
    i = 0
    while tok < budget:
        progressed = False
        for role in roles:
            if tok >= budget:
                break
            i += 1
            cand, t = gen(role, art, seed0 + i)
            tok += t
            if public(cand) >= public(art):
                if public(cand) > public(art):
                    progressed = True
                art = cand
        if not progressed:  # a full cycle with no gain — stop burning budget
            break
    return art, public(art), tok


def run_arms(
    gen: GenerateFn, public: ScoreFn, hidden: HiddenFn, *, budget: int, seed0: int = 0
) -> dict[str, ArmRun]:
    a1, s1, t1 = _arm_monolith(gen, public, budget, seed0)
    a2, s2, t2 = _arm_pipeline(gen, public, budget, seed0, STAGE_ROLES)
    a3, s3, t3 = _arm_pipeline(gen, public, budget, seed0, ("verify",))
    return {
        "ARM1_monolith": ArmRun("ARM1_monolith", a1, s1, t1, hidden(a1)),
        "ARM2_hetero": ArmRun("ARM2_hetero", a2, s2, t2, hidden(a2)),
        "ARM3_gate_only": ArmRun("ARM3_gate_only", a3, s3, t3, hidden(a3)),
    }


@dataclass(frozen=True)
class RealizedVerdict:
    realized: bool
    delta_21_mean: float
    delta_21_ci_lo: float
    delta_23_mean: float
    delta_23_ci_lo: float
    n_tasks: int


def evaluate_realized(per_task: list[dict[str, ArmRun]]) -> RealizedVerdict:
    """realized iff ARM2 beats ARM1 AND ARM3 — paired bootstrap CI lower bound > 0 on both."""
    d21 = [int(t["ARM2_hetero"].hidden_ok) - int(t["ARM1_monolith"].hidden_ok) for t in per_task]
    d23 = [int(t["ARM2_hetero"].hidden_ok) - int(t["ARM3_gate_only"].hidden_ok) for t in per_task]
    m21, lo21, _ = _bootstrap_ci(d21)
    m23, lo23, _ = _bootstrap_ci(d23)
    return RealizedVerdict(
        realized=(lo21 > 0 and lo23 > 0),
        delta_21_mean=m21,
        delta_21_ci_lo=lo21,
        delta_23_mean=m23,
        delta_23_ci_lo=lo23,
        n_tasks=len(per_task),
    )


__all__ = [
    "STAGE_ROLES",
    "ArmRun",
    "GenerateFn",
    "HiddenFn",
    "RealizedVerdict",
    "ScoreFn",
    "evaluate_realized",
    "run_arms",
]
