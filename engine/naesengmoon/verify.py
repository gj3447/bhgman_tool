"""bhgman verify — the "is this artifact sound?" surface a reasoner (ultracode) calls.

User verdict 2026-06-04: bhgman = oracle substrate, not the loop. This is the single entry point
that routes an artifact to the right deterministic oracle (engine/naesengmoon/oracle_adapters) and
returns a structured Verdict — score (continuous) + passed (binary gate) + detail (diagnostic). It is
substrate-disjoint from the LLM, zero-LLM-token, deterministic, reproducible. Callable as a Python API
(`from engine.naesengmoon.verify import verify`) or via `bhgman-tool oracle --kind ... --target ...`.

# KG: lesson-premature-close-confirmation-toward-closure-2026-06-02, prom16-bhgman-ci-design-2026-06-02,
#     naesengmoon-wired-ensemble-upgrade-2026-05-27
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.naesengmoon.oracle_adapters import (
    drift_recount_oracle,
    lean_goals_oracle,
    occam_twins_oracle,
    pytest_ratio_oracle,
)

KINDS = ("lean-goals", "pytest-ratio", "drift-recount", "occam-twins")


@dataclass(frozen=True)
class Verdict:
    """결정론 검증 결과. score=연속 fitness(높을수록 좋음), passed=건전 게이트, detail=진단."""

    kind: str
    target: str
    score: float
    passed: bool
    detail: str


def verify(
    kind: str,
    target: Any = None,
    *,
    lean_dir: str = ".",
    code_root: str = ".",
    kg: Any = None,
    run_cypher: Any = None,
    scope: str | None = None,
) -> Verdict:
    """artifact를 kind에 맞는 외부 결정론 oracle로 검증 → Verdict.

    lean-goals: target=자족 .lean 파일 / pytest-ratio: target=pytest 대상 /
    drift-recount: code_root+kg(populated) / occam-twins: run_cypher(+scope).
    """
    if kind == "lean-goals":
        score = lean_goals_oracle(lean_dir).evaluate(target).value
        passed = score > -1000
        detail = f"lean exit 0, {int(score)} closed goals" if passed else "lean compile FAILED"
    elif kind == "pytest-ratio":
        score = pytest_ratio_oracle().evaluate(target).value
        passed = score >= 1.0
        detail = f"pytest pass-ratio {score:.3f}"
    elif kind == "drift-recount":
        score = drift_recount_oracle(code_root, kg).evaluate(None).value
        passed = score == 0.0
        detail = f"{int(-score)} KG↔code drift(s)"
    elif kind == "occam-twins":
        score = occam_twins_oracle(run_cypher, scope).evaluate(None).value
        passed = score == 0.0
        detail = f"{int(score)} stale duplicate node(s) supersedable"
    else:
        raise ValueError(f"unknown oracle kind {kind!r}; expected one of {KINDS}")
    return Verdict(kind=kind, target=str(target), score=score, passed=passed, detail=detail)


__all__ = ["KINDS", "Verdict", "verify"]
