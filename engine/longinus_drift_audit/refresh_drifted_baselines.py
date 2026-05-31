"""One-shot: refresh sha256_baseline for files that legitimately drifted.

Path-keyed (NOT sourceId-keyed): the sha256 baseline is a property of the FILE,
so all ReferenceSites sharing a sourcePath get one consistent new baseline.
This avoids the sourceId-as-corpus-label inflation (see
lesson-longinus-audit-sourceid-vs-name-pk-drift-inflation-2026-05-26).

Reads the unique drifted paths from a prior audit report JSON, recomputes each
file's current hash fresh (TOCTOU-safe), and SETs the baseline on every
matching node by sourcePath. Read-modify is idempotent: re-running on an
already-refreshed file is a no-op (current == baseline).

Usage:
    NEO4J_URI=... NEO4J_PASSWORD=... python refresh_drifted_baselines.py REPORT.json
"""
# KG: ATOM_Skill_longinus

from __future__ import annotations

import json
import os
import sys

from engine.longinus_drift_audit import sha256_baseline
from engine.longinus_drift_audit.kg_client import Neo4jKgClient


def main() -> int:
    report_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/longinus_report.json"
    report = json.load(open(report_path))
    # unique drifted FILE paths (collapse the corpus-label / duplicate-node fan-out)
    drifted_paths = sorted(
        {
            e["path"]
            for e in report.get("sha256_drift_events", [])
            if e.get("kind") == "SHA256_MISMATCH"
        }
    )
    print(f"unique drifted files: {len(drifted_paths)}")

    uri = os.environ["NEO4J_URI"]
    pw = os.environ["NEO4J_PASSWORD"]
    user = os.environ.get("NEO4J_USER", "neo4j")
    kg = Neo4jKgClient(uri, (user, pw))

    ts = sha256_baseline._now_iso()
    refreshed_files = 0
    refreshed_nodes = 0
    unresolved = []
    try:
        with kg._driver.session() as s:
            for path in drifted_paths:
                res = sha256_baseline.resolve_path(path)
                if res.status != "FILE":
                    unresolved.append((path, res.status))
                    continue
                assert res.abs_path is not None  # status==FILE ⟹ abs_path set
                sha = sha256_baseline._compute_sha256(res.abs_path)
                rec = s.run(
                    """
                    MATCH (r:ReferenceSite {sourcePath: $path})
                    SET r.sha256 = $sha,
                        r.sha256_baseline = $sha,
                        r.sha256_status = 'BASELINE',
                        r.last_validated = $ts,
                        r.drift_detected_at = null,
                        r.drift_score = 0.0
                    RETURN count(r) AS n
                    """,
                    path=path,
                    sha=sha,
                    ts=ts,
                ).single()
                n = rec["n"] if rec else 0
                refreshed_files += 1
                refreshed_nodes += n
                print(f"  [{n:4d} nodes] {path}  -> {sha[:12]}")
    finally:
        kg.close()

    print(f"\nrefreshed files: {refreshed_files}  / nodes updated: {refreshed_nodes}")
    if unresolved:
        print(f"UNRESOLVED ({len(unresolved)}):")
        for p, st in unresolved:
            print(f"  {st}  {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
