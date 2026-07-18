"""ooptdd gate result → DiagnosticOracle (HALO-Loop L2, mechanism-3 spine).

Makes an ooptdd trace-gate the AUTHORITATIVE repair oracle for
``legion.diagnostic_repair``: a candidate is COMPLETE only when the ooptdd store
independently confirms ``ok=True`` (present); a reachable-but-RED gate yields a
repairable textual failed-check tail; an unreachable/truncated read is INFRA
(inconclusive) which must never be called success and must never be mistaken for
a falsification that triggers repair (it stops the loop as ``ORACLE_ERROR``).

This is distinct from ``ooptdd/repair_loop_adapter.py`` (Q1): that uses ooptdd to
*audit* whether the loop ran (the store is the judge of the pipeline); this uses
an ooptdd gate result as the *authority that drives* the loop per candidate — the
mechanism-3 external-oracle gen→verify→repair channel of PROM 16.

AlphaCodium fence: a green that got there by WEAKENING the gate (fewer/weaker
gating checks than the anchor baseline, via ``ooptdd.engine.gate.compare_strength``)
is REJECTED as not-a-clean-pass — you may not pass by lowering the bar, exactly as
AlphaCodium refuses a fix that regresses a previously-passing anchor test.

Depends only on ``naesengmoon.diagnostic_oracle``; the ooptdd result dict is
supplied by the caller's ``probe`` (and the strength verdict by ``fence``), so this
module carries NO hard ooptdd import — CI installs neither ooptdd nor its siblings,
yet the mapping stays fully unit-testable on hand-built result dicts.

ooptdd gate result contract (``ooptdd.engine.gate.evaluate`` / ``evaluate_events``):
    {ok: bool, reachable: bool, complete: bool, cid: str,
     checks: [ {passed, optional, pending, kind, ...} ]}
where a *gating* check is one that is neither ``optional`` nor ``pending``.

# KG: project_ultimate_ai_tool_halo_loop_2026_07_19 (HALO-Loop L2 oracle-repair spine)
# KG: finding-ooptdd-bhgman-repairloop-20260712, project_bhgman_ceiling_pierce_programme_2026_07_12
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .diagnostic_oracle import DiagnosticFeedback, feedback_from_value

OoptddResult = Mapping[str, Any]


def _gating(checks: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [c for c in checks if not c.get("optional") and not c.get("pending")]


def _failed_gating(checks: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [c for c in _gating(checks) if not c.get("passed")]


def _check_line(c: Mapping[str, Any]) -> str:
    kind = c.get("kind") or c.get("strength") or "check"
    label = c.get("label") or c.get("event") or c.get("cid") or ""
    reason = c.get("reason") or c.get("detail") or c.get("message") or ""
    got, want = c.get("got"), c.get("want")
    tail = f" (got={got!r} want={want!r})" if got is not None or want is not None else ""
    return f"[{kind}] {label}: {reason}{tail}".strip()


def feedback_from_ooptdd_result(
    result: OoptddResult,
    *,
    lens: str,
    kind: str = "ooptdd-gate",
    weakened: bool = False,
    regressions: Sequence[str] = (),
) -> DiagnosticFeedback:
    """Map one ooptdd gate result → typed repair feedback (pure, no I/O).

    - unreachable / incomplete read → ``unavailable`` (terminal INFRA; never
      success, never a repairable falsification);
    - ``ok`` and strength weakened → ``failed`` (AlphaCodium fence: a cheated green);
    - ``ok`` and no failed gating check → ``passed`` (authoritative COMPLETE);
    - reachable + complete + RED → ``failed`` with the failed gating checks as the
      repair tail and a partial score = passed_gating / gating.
    """
    reachable = bool(result.get("reachable", True))
    complete = bool(result.get("complete", True))
    checks = list(result.get("checks", []))

    if not reachable or not complete:
        why = "store unreachable" if not reachable else "read incomplete (truncated)"
        return feedback_from_value(
            lens=lens, kind=kind, passed=False, score=0.0, status="unavailable",
            diagnostic=(
                f"ooptdd INFRA hold: {why} — inconclusive, NOT a falsification "
                f"(cid={result.get('cid')})"
            ),
        )

    if result.get("ok") and weakened:
        return feedback_from_value(
            lens=lens, kind=kind, passed=False, score=0.0, status="failed",
            diagnostic=(
                "ooptdd gate went GREEN but strength REGRESSED (AlphaCodium fence): "
                + "; ".join(regressions)
            ),
        )

    failed = _failed_gating(checks)
    if result.get("ok") and not failed:
        return feedback_from_value(
            lens=lens, kind=kind, passed=True, score=1.0, status="passed",
            diagnostic="",
        )

    gating = _gating(checks)
    score = (len(gating) - len(failed)) / len(gating) if gating else 0.0
    tail = (
        "ooptdd gate RED — failed gating checks:\n"
        + "\n".join(_check_line(c) for c in failed)
        if failed
        else "ooptdd gate not ok (no specific failed gating check surfaced)"
    )
    return feedback_from_value(
        lens=lens, kind=kind, passed=False, score=score, status="failed",
        diagnostic=tail,
    )


@dataclass(frozen=True)
class OoptddGateOracle:
    """DiagnosticOracle whose authority is an ooptdd trace-gate result.

    ``probe(candidate) -> ooptdd result dict`` runs the gate over the candidate's
    store (e.g. ``ooptdd.engine.gate.evaluate(backend, spec)``). ``fence(candidate)
    -> (weakened, regressions)`` optionally wraps ``ooptdd.engine.gate.compare_strength``
    so a strength-regressing green is rejected as not-a-clean-pass.
    """

    name: str
    probe: Callable[[Any], OoptddResult]
    kind: str = "ooptdd-gate"
    fence: Callable[[Any], tuple[bool, Sequence[str]]] | None = None

    def evaluate(self, candidate: Any) -> DiagnosticFeedback:
        result = self.probe(candidate)
        weakened: bool = False
        regressions: Sequence[str] = ()
        if self.fence is not None:
            weakened, regressions = self.fence(candidate)
        return feedback_from_ooptdd_result(
            result, lens=self.name, kind=self.kind,
            weakened=weakened, regressions=list(regressions),
        )
