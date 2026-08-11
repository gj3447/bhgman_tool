"""One-shot backfill of DispatchInstrumentLog from KG ValidationResult history.

PROM 16 follow-up (2026-05-30): existing KG has ~625 ValidationResult nodes
with numeric metric fields (findings_count N=287, critics_dispatched N=100,
confidence N=35). This script extracts (metric_value, verdict→outcome) pairs
and appends to the instrument log so downstream derivations have data NOW
instead of waiting for instrument hook to accumulate from zero.

Run:
    NEO4J_PASSWORD='...' python -m engine.legion.threshold_derivation.backfill_kg

Idempotency: each entry includes a synthetic dispatch_id derived from the
ValidationResult name + metric, so repeated runs append duplicates.
Recommended pattern: rm log → run once. Or filter by dispatch_id on read.

# KG: actionplan-threshold-derivation-2026-05-30 follow-up
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import json

from engine.legion.threshold_derivation.instrument import DispatchInstrumentLog
from engine.legion.threshold_derivation.roc_youden import label_outcome


def existing_dispatch_ids(log: DispatchInstrumentLog) -> set[str]:
    """Read existing log; return dispatch_id set for dedup on incremental sync."""
    if not log.path.is_file():
        return set()
    seen: set[str] = set()
    with log.path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            did = row.get("dispatch_id")
            if did:
                seen.add(did)
    return seen


# (kg_field_name, commander, metric_name_in_threshold) mappings
BACKFILL_PLAN: tuple[tuple[str, str, str], ...] = (
    ("findings_count", "prometheus", "research_finding_count"),
    ("confidence", "naesengmoon", "confidence_proxy"),
    ("critics_dispatched", "naesengmoon", "critics_dispatched_proxy"),
    ("coverage_score", "prometheus", "coverage_score_proxy"),
)


def _cypher_pairs(driver, field: str) -> list[tuple[float, str, str]]:
    query = (
        f"MATCH (vr:ValidationResult) "
        f"WHERE vr.{field} IS NOT NULL AND vr.verdict IS NOT NULL "
        f"RETURN vr.{field} AS value, vr.verdict AS verdict, "
        f"coalesce(vr.name, 'vr-anonymous') AS dispatch_id"
    )
    with driver.session() as sess:
        result = sess.run(query)
        rows: list[tuple[float, str, str]] = []
        for rec in result:
            try:
                v = float(rec["value"])
            except (TypeError, ValueError):
                continue
            rows.append((v, rec["verdict"], rec["dispatch_id"]))
        return rows


def backfill_one(
    log: DispatchInstrumentLog,
    field: str,
    commander: str,
    metric: str,
    pairs: list[tuple[float, str, str]],
    seen_ids: set[str] | None = None,
) -> tuple[int, int, int]:
    """Append labeled pairs for one mapping. Returns (n_appended, n_skipped_ambiguous, n_skipped_dup)."""
    appended = skipped_ambig = skipped_dup = 0
    seen_ids = seen_ids if seen_ids is not None else set()
    for value, verdict, dispatch_id in pairs:
        outcome = label_outcome(verdict)
        if outcome is None:
            skipped_ambig += 1
            continue
        full_id = f"backfill::{commander}::{metric}::{dispatch_id}"
        if full_id in seen_ids:
            skipped_dup += 1
            continue
        log.record(
            commander=commander,
            metric=metric,
            value=value,
            outcome=outcome,
            cycle_id="kg-backfill-2026-05-30",
            dispatch_id=full_id,
        )
        seen_ids.add(full_id)
        appended += 1
    return appended, skipped_ambig, skipped_dup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KG VR → instrument log backfill")
    parser.add_argument(
        "--bolt",
        default=os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687"),
    )
    parser.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"))
    parser.add_argument(
        "--log-path",
        type=Path,
        default=Path.home() / ".cache" / "bhgman" / "dispatch_instrument.jsonl",
    )
    args = parser.parse_args(argv)
    if not args.password:
        parser.error("--password or NEO4J_PASSWORD is required")

    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("ERROR: neo4j driver not installed (pip install neo4j)", file=sys.stderr)
        return 2

    driver = GraphDatabase.driver(args.bolt, auth=(args.user, args.password))
    log = DispatchInstrumentLog(path=args.log_path)
    seen = existing_dispatch_ids(log)
    totals = {"appended": 0, "ambiguous": 0, "duplicate": 0}
    print(f"Backfill target: {args.log_path}")
    print(f"Existing entries: {len(seen)} (incremental dedup active)")
    print(f"Mappings: {len(BACKFILL_PLAN)}")
    for field, commander, metric in BACKFILL_PLAN:
        pairs = _cypher_pairs(driver, field)
        n_app, n_ambig, n_dup = backfill_one(log, field, commander, metric, pairs, seen)
        totals["appended"] += n_app
        totals["ambiguous"] += n_ambig
        totals["duplicate"] += n_dup
        print(
            f"  {commander}.{metric:30s} ← KG.{field:20s} "
            f"fetched={len(pairs):4d} new={n_app:4d} dup={n_dup:4d} ambig={n_ambig:4d}"
        )
    driver.close()
    print(
        f"\nTOTAL new={totals['appended']} duplicates={totals['duplicate']} "
        f"ambiguous={totals['ambiguous']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
