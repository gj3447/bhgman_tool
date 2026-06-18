#!/usr/bin/env python3
"""
Longinus sha256 verification daemon — PoC.

Reads :ReferenceSite nodes from Neo4j, recomputes sha256 of (sourcePath),
compares to stored sha256, emits :SourceCodeDriftEvent on mismatch.
First run populates sha256 baseline (--init).

KG: Longinus 7-tuple ReferenceSite {sourceId, sourcePath, line_range, sha256, semver, kg_anchor, drift_metric}
KG: fw-longinus-sha256-daemon-2026-05-06

Modes:
  --init        : populate sha256 baseline for all ReferenceSite lacking sha256
  --verify      : recompute + compare, emit drift events on mismatch (one-shot)
  --cron N      : repeat --verify every N seconds (loop)
  --stats       : print summary (total / has_sha256 / has_path / drift_count)

Limitations:
  - File-level sha256 only (no line_range support yet — ReferenceSite schema lacks line_range field)
  - sourcePath resolved relative to FS_BASE env (default: /Users/lagyeongjun/CD/SERVER)
  - No alert webhook (drift event KG node only — operator polls)
  - curl-based Cypher (production should use neo4j-driver)
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time

NEO4J_URL = os.environ.get("NEO4J_URL", "http://neo4j.metahumotonic.com/db/neo4j/tx/commit")
NEO4J_AUTH = os.environ.get("NEO4J_AUTH", "neo4j:neo4jpassword")

# Fallback chain for path resolution. Priority order: explicit FS_BASE override,
# then known repo roots in CD/. Home-relative (~) is expanded inline.
FS_BASE_OVERRIDE = os.environ.get("FS_BASE")
FS_BASE_CHAIN = [FS_BASE_OVERRIDE] if FS_BASE_OVERRIDE else [
    "/Users/lagyeongjun/CD/SERVER",
    "/Users/lagyeongjun/CD/SYMPOSIUM",
    "/Users/lagyeongjun/CD/SYMPOSIUM/SKILLS",
    "/Users/lagyeongjun/CD/SYMPOSIUM/METAHUMOTONIC",
    "/Users/lagyeongjun/CD/SYMPOSIUM/THEORY/CHU",
    "/Users/lagyeongjun/CD/SYMPOSIUM/THEORY/재배맨",
    "/Users/lagyeongjun/CD/MIND",
    "/Users/lagyeongjun/CD",
    os.path.expanduser("~"),
]
FS_BASE_CHAIN = [b for b in FS_BASE_CHAIN if b]


def cypher(stmt, params=None):
    body = {"statement": stmt}
    if params:
        body["parameters"] = params
    payload = json.dumps({"statements": [body]})
    out = subprocess.check_output(
        [
            "curl", "-s", "-m", "10",
            "-u", NEO4J_AUTH,
            "-H", "Content-Type: application/json",
            "-d", payload,
            NEO4J_URL,
        ],
        timeout=15,
    )
    return json.loads(out.decode())


def list_reference_sites(needs_sha256=False):
    where = "WHERE rs.sourcePath IS NOT NULL"
    if needs_sha256:
        where += " AND (rs.sha256 IS NULL OR rs.sha256 = '')"
    res = cypher(
        f"MATCH (rs:ReferenceSite) {where} "
        "RETURN rs.name AS name, rs.sourcePath AS path, rs.sha256 AS sha256, rs.layer AS layer "
        "ORDER BY rs.name LIMIT 5000"
    )
    rows = res.get("results", [{}])[0].get("data", [])
    out = []
    for r in rows:
        row = r["row"]
        out.append({"name": row[0], "path": row[1], "sha256": row[2], "layer": row[3]})
    return out


def compute_sha256(rel_path):
    # Expand ~ inline before fallback chain
    expanded = os.path.expanduser(rel_path)
    if os.path.isabs(expanded):
        candidates = [expanded]
    else:
        candidates = [os.path.join(base, rel_path) for base in FS_BASE_CHAIN]
    for path in candidates:
        if os.path.isfile(path):
            with open(path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
    return None


def cmd_stats() -> int:
    res = cypher(
        "MATCH (rs:ReferenceSite) "
        "RETURN count(rs) AS total, "
        "count(rs.sourcePath) AS has_path, "
        "count(rs.sha256) AS has_sha256"
    )
    row = res["results"][0]["data"][0]["row"]
    print(f"total ReferenceSite: {row[0]}")
    print(f"  has_sourcePath:    {row[1]}")
    print(f"  has_sha256:        {row[2]}")
    print(f"  needs_init:        {row[1] - row[2]}")
    drift_res = cypher("MATCH (e:SourceCodeDriftEvent) RETURN count(e) AS cnt")
    drift_count = drift_res["results"][0]["data"][0]["row"][0]
    print(f"  drift_events:      {drift_count}")
    return 0


def resolve_path_status(rel_path):
    """Return (status, abs_path_if_resolved). status ∈ {FILE, DIRECTORY, MISSING}."""
    expanded = os.path.expanduser(rel_path)
    candidates = [expanded] if os.path.isabs(expanded) else [os.path.join(b, rel_path) for b in FS_BASE_CHAIN]
    for path in candidates:
        if os.path.isfile(path):
            return ("FILE", path)
    for path in candidates:
        if os.path.isdir(path):
            return ("DIRECTORY", path)
    return ("MISSING", None)


def cmd_init():
    sites = list_reference_sites(needs_sha256=True)
    populated = 0
    directory = 0
    missing = 0
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for s in sites:
        status, abs_path = resolve_path_status(s["path"])
        if status == "FILE":
            with open(abs_path, "rb") as f:
                sha = hashlib.sha256(f.read()).hexdigest()
            cypher(
                "MATCH (rs:ReferenceSite {name:$name}) "
                "SET rs.sha256 = $sha, rs.sha256_init_at = $ts, rs.sha256_baseline = $sha, "
                "rs.sha256_status = 'BASELINE', rs.resolved_abs_path = $abs",
                {"name": s["name"], "sha": sha, "ts": ts, "abs": abs_path},
            )
            populated += 1
        elif status == "DIRECTORY":
            cypher(
                "MATCH (rs:ReferenceSite {name:$name}) "
                "SET rs.sha256_status = 'DIRECTORY_SKIP', rs.resolved_abs_path = $abs, rs.sha256_init_at = $ts",
                {"name": s["name"], "ts": ts, "abs": abs_path},
            )
            directory += 1
        else:
            cypher(
                "MATCH (rs:ReferenceSite {name:$name}) "
                "SET rs.sha256_status = 'FILE_MISSING', rs.sha256_init_at = $ts",
                {"name": s["name"], "ts": ts},
            )
            missing += 1
    print(f"init: populated={populated}, directory_skip={directory}, missing_files={missing}, total_seen={len(sites)}")
    return 0


def list_reference_sites_with_status():
    res = cypher(
        "MATCH (rs:ReferenceSite) WHERE rs.sourcePath IS NOT NULL "
        "RETURN rs.name AS name, rs.sourcePath AS path, rs.sha256 AS sha256, "
        "rs.layer AS layer, rs.sha256_status AS status "
        "ORDER BY rs.name LIMIT 5000"
    )
    rows = res.get("results", [{}])[0].get("data", [])
    return [{"name": r["row"][0], "path": r["row"][1], "sha256": r["row"][2],
             "layer": r["row"][3], "status": r["row"][4]} for r in rows]


def cmd_verify():
    sites = list_reference_sites_with_status()
    drift = 0
    missing = 0
    ok = 0
    skipped_baseline = 0
    skipped_dir = 0
    skipped_orphan = 0
    for s in sites:
        if s["status"] == "DIRECTORY_SKIP":
            skipped_dir += 1
            continue
        if s["status"] == "ORPHAN_REFERENCE":
            skipped_orphan += 1
            continue
        if not s["sha256"]:
            skipped_baseline += 1
            continue
        current = compute_sha256(s["path"])
        if current is None:
            missing += 1
            emit_drift(s["name"], s["path"], s["sha256"], None, "FILE_MISSING")
            continue
        if current != s["sha256"]:
            drift += 1
            emit_drift(s["name"], s["path"], s["sha256"], current, "SHA256_MISMATCH")
        else:
            ok += 1
    print(f"verify: ok={ok}, drift={drift}, file_missing={missing}, "
          f"skipped_baseline={skipped_baseline}, skipped_dir={skipped_dir}, skipped_orphan={skipped_orphan}")
    return 0 if drift == 0 and missing == 0 else 1


def emit_drift(ref_site, path, baseline, current, kind):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    name = f"drift-{ref_site}-{ts}"
    cypher(
        "MERGE (e:SourceCodeDriftEvent:AbstractNode {name:$name}) "
        "ON CREATE SET e.created_at = $ts, e.detected_by = 'longinus_sha256_daemon', "
        "  e.ref_site = $ref_site, e.path = $path, e.baseline_sha256 = $baseline, "
        "  e.current_sha256 = $current, e.kind = $kind, e.resolved = false "
        "WITH e MATCH (rs:ReferenceSite {name:$ref_site}) MERGE (e)-[:DRIFTED_FROM]->(rs)",
        {
            "name": name, "ts": ts, "ref_site": ref_site, "path": path,
            "baseline": baseline, "current": current or "FILE_MISSING", "kind": kind,
        },
    )


def cmd_cron(interval: int) -> int:
    print(f"cron mode: verify every {interval}s, Ctrl+C to stop")
    try:
        while True:
            cmd_verify()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nstopped")
        return 0


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    if args[0] == "--stats":
        return cmd_stats()
    if args[0] == "--init":
        return cmd_init()
    if args[0] == "--verify":
        return cmd_verify()
    if args[0] == "--cron" and len(args) >= 2:
        return cmd_cron(int(args[1]))
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
