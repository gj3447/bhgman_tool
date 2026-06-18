"""Nightly drift check — stage_7 of the L8 induction pipeline.

Runs once per night via cron. Computes community hypergraph bipartite GED from the
last snapshot, evaluates the 2-phase τ gate (cold-start absolute / steady-state q90),
and emits a :DriftCheck record into the KG via an injected KgClient (NEO4J_* env at the
cron entrypoint; absent → prints only, never silently claims a write). If the gate fires,
also emits a :ReinductionTrigger for the next /prom 16 re-induction cycle.

Cron snippet (install with `crontab -e`):

    # GED drift check — nightly 03:17 KST (eureka-l8-rectification split: drift→longinus_drift)
    # Set BHGMAN_ROOT to your checkout (portable across machines, not a hardcoded home).
    17 3 * * * cd "$BHGMAN_ROOT/engine/longinus_drift" && \\
        /usr/bin/env python3 nightly_drift_check.py >> ~/.bhgman/l8_drift.log 2>&1

Until GDS is installed on the Neo4j VM, the community-detection inputs (nGED, NMI,
silhouette) cannot be computed from Cypher. In that case this script records a
:DriftCheck with status='BLOCKED_GDS_NOT_INSTALLED' and exits 0 (passive baseline
collection only, no false-positive fires).
"""
# KG: ATOM_Skill_longinus

from __future__ import annotations

import datetime as dt
import os
import sys

from engine.longinus_drift.ged_drift_detector import evaluate_drift


COLD_START_ANCHOR_ENV = "L8_COLD_START_ANCHOR"
DEFAULT_COLD_START_ANCHOR = "2026-05-20"


def days_since_cold_start_anchor() -> int:
    anchor_str = os.environ.get(COLD_START_ANCHOR_ENV, DEFAULT_COLD_START_ANCHOR)
    anchor = dt.date.fromisoformat(anchor_str)
    return (dt.date.today() - anchor).days


def compute_community_signals() -> dict:
    """Return {nged, nmi, silhouette, history} from current KG state.

    Without GDS, we cannot run Leiden — return None placeholders so evaluate_drift
    returns no-fire and the script records BLOCKED.
    """
    return {
        "nged": None,
        "nmi": None,
        "silhouette": None,
        "history": [],
        "blocked_reason": "gds-plugin-not-installed",
    }


def emit_drift_check_record(
    day_since_anchor: int,
    signals: dict,
    decision,
) -> dict:
    """Build the :DriftCheck node payload. Caller MERGEs into KG."""
    return {
        "name": f"drift-check-{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')}",
        "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "depth": 0,
        "day_since_cold_start": day_since_anchor,
        "phase": decision.phase if decision else "blocked",
        "nged": signals.get("nged"),
        "nmi": signals.get("nmi"),
        "silhouette": signals.get("silhouette"),
        "threshold": decision.threshold if decision else None,
        "fire": bool(decision.fire) if decision else False,
        "reasons": list(decision.reasons)
        if decision
        else [signals.get("blocked_reason", "unknown")],
        "status": "RECORDED" if decision else "BLOCKED_GDS_NOT_INSTALLED",
    }


def _persist(kg, record: dict) -> None:
    """MERGE the :DriftCheck (+ :ReinductionTrigger when the gate fired) into the KG.
    No-op when no kg client is wired (passive baseline collection / cron without creds)."""
    if kg is None:
        print("[drift-check] (no KG client wired — record not persisted)")
        return
    try:
        kg.merge_drift_check(record, reinduction=bool(record.get("fire")))
        print(f"[drift-check] persisted :DriftCheck {record['name']} (KG)")
    except Exception as e:  # noqa: BLE001 — cron must not crash; surface + continue
        print(f"[drift-check] WARN: KG persist failed ({type(e).__name__}: {e})")


def _kg_from_env():
    """Build a Neo4jKgClient from NEO4J_* env when configured, else None (print-only)."""
    if not os.environ.get("NEO4J_URI"):
        return None
    try:
        from engine.longinus_drift_audit.kg_client import Neo4jKgClient  # noqa: PLC0415

        return Neo4jKgClient(
            os.environ["NEO4J_URI"],
            auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", "")),
        )
    except Exception:  # noqa: BLE001 — missing driver / unreachable → degrade to print-only
        return None


def main(kg=None) -> int:
    day = days_since_cold_start_anchor()
    signals = compute_community_signals()

    if signals.get("nged") is None:
        record = emit_drift_check_record(day, signals, decision=None)
        print(f"[drift-check] {record['name']} status={record['status']} day={day}")
        print(f"[drift-check] reason={record['reasons']}")
        _persist(kg, record)
        return 0

    decision = evaluate_drift(
        nged=signals["nged"],
        nmi=signals["nmi"],
        silhouette=signals["silhouette"],
        day_since_cold_start=day,
        last_30day_nged_history=signals.get("history"),
    )
    record = emit_drift_check_record(day, signals, decision)
    print(
        f"[drift-check] {record['name']} status={record['status']} fire={record['fire']} phase={decision.phase}"
    )
    print(f"[drift-check] nged={decision.nged:.4f} threshold={decision.threshold:.4f}")
    for reason in decision.reasons:
        print(f"[drift-check]   reason: {reason}")

    if decision.fire:
        print("[drift-check] FIRE — emit :ReinductionTrigger for next /prom 16 cycle")

    _persist(kg, record)
    return 0


if __name__ == "__main__":
    sys.exit(main(_kg_from_env()))
