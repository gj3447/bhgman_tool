"""Nightly drift check — stage_7 of the L8 induction pipeline.

Runs once per night via cron. Computes community hypergraph bipartite GED from the
last snapshot, evaluates the 2-phase τ gate (cold-start absolute / steady-state q90),
and emits a :DriftCheck record into the KG. If the gate fires, also emits a
:ReinductionTrigger record for the next /prom 16 re-induction cycle.

Cron snippet (install with `crontab -e`):

    # GED drift check — nightly 03:17 KST (eureka-l8-rectification split: drift→longinus_drift)
    17 3 * * * cd /Users/lagyeongjun/CD/bhgman_tool/engine/longinus_drift && \\
        /usr/bin/env python3 nightly_drift_check.py >> ~/.bhgman/l8_drift.log 2>&1

Until GDS is installed on the Neo4j VM, the community-detection inputs (nGED, NMI,
silhouette) cannot be computed from Cypher. In that case this script records a
:DriftCheck with status='BLOCKED_GDS_NOT_INSTALLED' and exits 0 (passive baseline
collection only, no false-positive fires).
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from ged_drift_detector import evaluate_drift  # noqa: E402 (sys.path setup above is intentional for cron-launched script)


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


def main() -> int:
    day = days_since_cold_start_anchor()
    signals = compute_community_signals()

    if signals.get("nged") is None:
        record = emit_drift_check_record(day, signals, decision=None)
        print(f"[drift-check] {record['name']} status={record['status']} day={day}")
        print(f"[drift-check] reason={record['reasons']}")
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

    return 0


if __name__ == "__main__":
    sys.exit(main())
