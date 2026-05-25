"""F7 batch ingester: .pytest_apt_invariant_results.tsv -> :TestRunResult KG nodes.

Completes WQI wqi-bhgman-apt-F7-test-tagging-apt-invariants-2026-05-25: the
conftest hook records one TSV row per apt_invariant test (TSV-first so tests stay
decoupled from KG availability); this end-of-session / cron step MERGEs one
:TestRunResult per pytest run, plus one :APTInvariantRule per distinct rule, and
links them to the remediation cycle + the F7 work item.

Idempotent: re-ingesting the same TSV MERGEs by run_id (no duplicates).

Usage:
    NEO4J_URI=... NEO4J_PASSWORD=... python ingest_apt_invariant_runs.py [TSV]

# KG: wqi-bhgman-apt-F7-test-tagging-apt-invariants-2026-05-25
# KG: cycle-bhgman-apt-completeness-remediation-2026-05-25
"""

from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict
from pathlib import Path

from neo4j import GraphDatabase

DEFAULT_TSV = Path(__file__).parent / ".pytest_apt_invariant_results.tsv"
CYCLE = "cycle-bhgman-apt-completeness-remediation-2026-05-25"
WQI = "wqi-bhgman-apt-F7-test-tagging-apt-invariants-2026-05-25"


def parse_runs(tsv_path: Path) -> dict[str, list[dict]]:
    """Group TSV rows by run_id. Tolerates legacy rows (no run_id col)."""
    runs: dict[str, list[dict]] = defaultdict(list)
    with tsv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            run_id = row.get("run_id") or f"legacy-{row.get('ts', 'unknown')}"
            runs[run_id].append(row)
    return runs


def ingest(driver, runs: dict[str, list[dict]]) -> list[dict]:
    summaries = []
    with driver.session() as s:
        for run_id, rows in runs.items():
            total = len(rows)
            passed = sum(1 for r in rows if r.get("outcome") == "passed")
            failed = total - passed
            started = min((r.get("ts", "") for r in rows), default="")
            # per-rule outcome rollup
            by_rule: dict[str, dict[str, int]] = defaultdict(lambda: {"passed": 0, "failed": 0})
            for r in rows:
                rule = r.get("rule", "<unspecified>")
                bucket = "passed" if r.get("outcome") == "passed" else "failed"
                by_rule[rule][bucket] += 1

            s.run(
                """
                MERGE (tr:TestRunResult {run_id: $run_id})
                SET tr.name = 'testrun-' + $run_id,
                    tr.started_at = $started,
                    tr.total = $total,
                    tr.passed = $passed,
                    tr.failed = $failed,
                    tr.suite = 'apt_invariant',
                    tr.detected_by = 'conftest.pytest_runtest_makereport',
                    tr.created = $started
                WITH tr
                OPTIONAL MATCH (c {name: $cycle})
                FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END | MERGE (tr)-[:FROM_CYCLE]->(c))
                WITH tr
                OPTIONAL MATCH (w {name: $wqi})
                FOREACH (_ IN CASE WHEN w IS NULL THEN [] ELSE [1] END | MERGE (tr)-[:FULFILLS]->(w))
                """,
                run_id=run_id,
                started=started,
                total=total,
                passed=passed,
                failed=failed,
                cycle=CYCLE,
                wqi=WQI,
            )
            for rule, oc in by_rule.items():
                s.run(
                    """
                    MERGE (ir:APTInvariantRule {name: $rule})
                    WITH ir
                    MATCH (tr:TestRunResult {run_id: $run_id})
                    MERGE (tr)-[chk:CHECKED]->(ir)
                    SET chk.passed = $passed, chk.failed = $failed
                    """,
                    rule=rule,
                    run_id=run_id,
                    passed=oc["passed"],
                    failed=oc["failed"],
                )
            summaries.append(
                {
                    "run_id": run_id,
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "rules": len(by_rule),
                }
            )
    return summaries


def main() -> int:
    tsv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TSV
    if not tsv_path.exists():
        print(f"no TSV at {tsv_path} — run the apt_invariant tests first", file=sys.stderr)
        return 1
    runs = parse_runs(tsv_path)
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    try:
        summaries = ingest(driver, runs)
    finally:
        driver.close()
    print(f"ingested {len(summaries)} run(s) as :TestRunResult:")
    for sm in summaries:
        print(
            f"  {sm['run_id']}  total={sm['total']} passed={sm['passed']} "
            f"failed={sm['failed']} rules={sm['rules']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
