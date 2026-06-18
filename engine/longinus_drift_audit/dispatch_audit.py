"""dispatch_audit — PROM 16 cycle ``prom16-parallelism-bhgman-dependency-2026-05-19`` AP1 plug.

Sibling of :mod:`sha256_baseline`: where the latter watches *content drift* of
referenced code (KG ↔ disk hash), this module watches *intent drift* of subagent
dispatch (KG ``intent_N`` ↔ runtime ``actual_N``). Both share the BX-Lens
PutPut-violation pattern — the canonical jaebaeman invariant from
``SKILLS/jaebaeman/references/validation.md V5`` (intent_N == actual_N,
GH anthropics/claude-code#29181) is enforced post-hoc as a 7-day rolling
``cardinality_match`` ratio over ``:DispatchHyperedge`` nodes.

3 modes ⇔ 3 BX Lens Laws (mirrors sha256_baseline structure):
    - ``audit_window`` → GetPut roundtrip: KG dispatch intent matches harness actual
    - ``record_drift``  → PutPut: drift event emit on cardinality_match=false
    - ``ratchet``       → PutGet seed: 7-day ratio baseline calibration

Ratchet thresholds (evidence-free initial guess per PROM 16 D4 caveat;
30-day live observation should re-calibrate before any hard-block):
    - ratio ≥ 0.95 → ``ALLOW``
    - 0.90 ≤ ratio < 0.95 → ``WARN``
    - ratio < 0.90 → ``DENY``

Companion runtime gate (out of scope for this module, observation-only here):
``~/.claude/hooks/pre_tool_dispatch_pattern_check.py`` (live, 165 LOC,
observational warn-only) — once 30-day baseline confirms threshold validity,
hard-block via env ``DISPATCH_PATTERN_HARD_BLOCK=1``.

# KG: finding-prom16-parallelism-bhgman-dep-D4
# KG: ap-bhgman-dispatch-audit-py (ActionPlan, 2026-05-19 cycle)
# KG: lesson-prom16-parallelism-bhgman-dependency-2026-05-19
# KG: seed-bhgman-dispatch-audit-py-2026-05-19 (SubagentTaskSpec)
# KG: 재배맨-v2-subagent-runtime-protocol (canonical SOP)
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Optional

from engine.longinus_drift_audit.kg_client import KgClient
from engine.longinus_drift_audit.models import DriftType, SourceCodeDriftEvent

try:
    from engine.longinus_drift_audit import otel_channel
except ImportError:  # pragma: no cover - otel_channel ships with this package
    otel_channel = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ─── Ratchet thresholds (PROM 16 D4 caveat: 30-day calibration pending) ───

RATCHET_ALLOW_MIN: float = 0.95
RATCHET_WARN_MIN: float = 0.90
DEFAULT_WINDOW_DAYS: int = 7


@dataclass(frozen=True)
class DispatchAuditReport:
    # KG: ATOM_Skill_longinus
    """Result of a single :class:`DispatchAuditor.audit_window` call.

    Mirrors :class:`AuditReport` shape from sha256_baseline but scoped to
    dispatch-cardinality semantics. ``verdict`` drives the OPA gate (see
    ``engine/gate/policies/dispatch_cardinality.rego`` — sibling plug to
    add in a follow-up sprint).
    """

    window_days: int
    total: int
    matched: int
    ratio: float
    verdict: str  # 'ALLOW' | 'WARN' | 'DENY'
    sampled_at: dt.datetime

    @property
    def passes_ratchet(self) -> bool:
        return self.verdict == "ALLOW"


class DispatchAuditor:
    # KG: ATOM_Skill_longinus
    """7-day rolling cardinality_match ratchet over :DispatchHyperedge.

    Invariants enforced (canonical: SKILLS/jaebaeman/references/validation.md V5):
        I_CARDINALITY: he.intent_N == he.actual_N → he.cardinality_match = true
        I_RATCHET: rolling-window ratio ≥ RATCHET_ALLOW_MIN for ALLOW verdict

    Drift events emitted via :meth:`record_drift` flow into the same
    ``:SourceCodeDriftEvent`` KG node stream that ``sha256_baseline`` writes
    to, distinguished by ``drift_type=DISPATCH_DRIFT``. Downstream sweep
    agents can therefore consume a unified drift channel.
    """

    def __init__(self, kg: KgClient) -> None:
        self.kg = kg

    def audit_window(
        self,
        days: int = DEFAULT_WINDOW_DAYS,
        cycle_filter: Optional[str] = None,
    ) -> DispatchAuditReport:
        """Compute rolling cardinality_match ratio over the last ``days`` days.

        Args:
            days: Window size (default 7). 30-day calibration is the target
                baseline before hard-block enforcement.
            cycle_filter: Optional cycle-id prefix to scope the audit (e.g.
                ``'prom16-'`` audits only PROM cycles). ``None`` = all cycles.

        Returns:
            :class:`DispatchAuditReport` with verdict ALLOW/WARN/DENY.
        """
        cypher = """
        MATCH (he:DispatchHyperedge)
        WHERE he.created_at >= datetime() - duration({days: $days})
          AND ($cycle_filter IS NULL OR he.cycle_id STARTS WITH $cycle_filter)
        WITH count(he) AS total,
             count(CASE WHEN he.cardinality_match = true THEN 1 END) AS matched
        RETURN total, matched,
               CASE WHEN total = 0 THEN 1.0
                    ELSE toFloat(matched) / total END AS ratio
        """
        rows = list(self.kg.run(cypher, days=days, cycle_filter=cycle_filter))
        if not rows:
            total, matched, ratio = 0, 0, 1.0
        else:
            row = rows[0]
            total = int(row["total"])
            matched = int(row["matched"])
            ratio = float(row["ratio"])

        verdict = self._verdict_for(ratio)
        return DispatchAuditReport(
            window_days=days,
            total=total,
            matched=matched,
            ratio=ratio,
            verdict=verdict,
            sampled_at=dt.datetime.now(dt.timezone.utc),
        )

    def record_drift(
        self,
        cycle_id: str,
        wave_index: int,
        intent_N: int,
        actual_N: int,
        note: Optional[str] = None,
    ) -> SourceCodeDriftEvent:
        """Emit a :SourceCodeDriftEvent with drift_type=DISPATCH_DRIFT on mismatch.

        Idempotent in (cycle_id, wave_index): re-call with same args MERGEs the
        same event node. Severity follows the same P1/P2 split as
        :C_cycle_topology.md DispatchIntentMismatch:
            intent_N > actual_N → P1_underdispatch (missing seeds)
            intent_N < actual_N → P2_overdispatch (rejected siblings)
        """
        if intent_N == actual_N:
            logger.debug(
                "dispatch_audit.record_drift skipped: cardinality_match=true "
                "(cycle_id=%s wave=%d N=%d)",
                cycle_id,
                wave_index,
                intent_N,
            )
            return None  # type: ignore[return-value]

        severity = "P1_underdispatch" if intent_N > actual_N else "P2_overdispatch"
        recovery = (
            "restore-missing-seeds-status-READY"
            if intent_N > actual_N
            else "archive-overdispatched-with-rejected-reason"
        )
        cypher = """
        MERGE (e:SourceCodeDriftEvent {
            cycle_id: $cycle_id,
            wave_index: $wave_index,
            drift_type: $drift_type
        })
        SET e.intent_N = $intent_N,
            e.actual_N = $actual_N,
            e.delta = $intent_N - $actual_N,
            e.severity = $severity,
            e.recovery = $recovery,
            e.note = $note,
            e.detected_at = datetime()
        WITH e
        MATCH (he:DispatchHyperedge {cycle_id: $cycle_id, wave_index: $wave_index})
        MERGE (he)-[:HAS_DRIFT]->(e)
        RETURN e
        """
        rows = list(
            self.kg.run(
                cypher,
                cycle_id=cycle_id,
                wave_index=wave_index,
                drift_type=DriftType.DISPATCH_DRIFT.value,
                intent_N=intent_N,
                actual_N=actual_N,
                severity=severity,
                recovery=recovery,
                note=note,
            )
        )
        logger.info(
            "dispatch_audit drift emitted: cycle=%s wave=%d intent=%d actual=%d severity=%s",
            cycle_id,
            wave_index,
            intent_N,
            actual_N,
            severity,
        )
        # OTel GenAI: surface drift on any active span (no-op if [otel] absent / no span).
        if otel_channel is not None:
            otel_channel.record_active_drift_event(
                cycle_id=cycle_id,
                wave_index=wave_index,
                intent_n=intent_N,
                actual_n=actual_N,
                severity=severity,
                note=note,
            )
        # Return value shape mirrors the cypher RETURN; concrete decoding
        # is delegated to the caller (audit_runner integrates via .name).
        return rows[0]["e"] if rows else None  # type: ignore[return-value]

    @staticmethod
    def _verdict_for(ratio: float) -> str:
        if ratio >= RATCHET_ALLOW_MIN:
            return "ALLOW"
        if ratio >= RATCHET_WARN_MIN:
            return "WARN"
        return "DENY"


# ─── CLI entry-point (parallel to sha256_baseline daemon style) ──────────


def main() -> None:
    # KG: ATOM_Skill_longinus
    """One-shot CLI: ``python -m engine.longinus_drift_audit.dispatch_audit``.

    Wires to the daemon (``daemon.py``) for periodic scans in a follow-up
    sprint. Current invocation is intended for ``audit_runner`` integration
    only — the daemon plug remains the PRELIMINARY follow-up.
    """
    import argparse
    import sys

    from engine.longinus_drift_audit.kg_client import KgClient as _KgClientBase  # noqa: F401 (typing only)

    parser = argparse.ArgumentParser(
        description=(
            "Dispatch cardinality_match ratchet — 7-day rolling ratio over "
            ":DispatchHyperedge. Threshold ≥0.95 ALLOW, <0.90 DENY."
        )
    )
    parser.add_argument("--days", type=int, default=DEFAULT_WINDOW_DAYS, help="Window size (days)")
    parser.add_argument(
        "--cycle-prefix",
        type=str,
        default=None,
        help="Optional cycle_id prefix filter (e.g. 'prom16-')",
    )
    parser.parse_args()  # validate CLI surface; standalone stub does not yet consume args

    # Concrete KG client wiring delegated to caller (DIP) — production swaps
    # in Neo4jKgClient via the same factory ``audit_runner`` uses. Standalone
    # invocation requires the caller to construct one beforehand; this stub
    # therefore exits with a clear error rather than hardcoding a client.
    print(
        "dispatch_audit CLI requires explicit KG client wiring; "
        "invoke via audit_runner integration (see PROM 16 D4 deliverable).",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
