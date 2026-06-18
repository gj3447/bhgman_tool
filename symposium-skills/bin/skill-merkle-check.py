#!/usr/bin/env python3
"""skill-merkle-check.py — Plan-5 phase 2 anti-entropy gate.

Compares MANIFEST.json's merkle_root against the live filesystem/git state.
Drift causes:
  (a) MANIFEST stale (commits since last build) — fix: rerun skill-build-manifest.py
  (b) frontmatter ↔ MANIFEST mismatch — operator drift, needs investigation
  (c) git_tree_sha mismatch (uncommitted changes in working tree) — informational

Exit codes:
  0  OK (manifest in sync)
  1  DRIFT detected (one of a/b/c)
  2  setup/IO error

False-positive normalization rules:
- git_tree_sha == None (file added but not committed) → reported as 'uncommitted' diff,
  not as a hard FAIL when --tolerate-uncommitted is set.
- skills_count check uses sorted(by path) deterministically; ordering-only diffs ignored.
- generatedAt / git_head_commit drift alone NOT a FAIL — those are expected to evolve;
  only merkle_root + per-skill git_tree_sha tuple is the gate.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent
MANIFEST_PATH = SKILLS_DIR / "MANIFEST.json"


def run_git(*args):
    return subprocess.check_output(["git", *args], cwd=SKILLS_DIR, text=True).strip()


def parse_frontmatter(skill_md):
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        m2 = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if not m2:
            continue
        k, raw = m2.group(1), m2.group(2).strip()
        if not raw or raw.startswith(">"):
            continue
        # YAML quoted string handling (PROM 16 F3 — SemVer migration consistency)
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
            fm[k] = raw[1:-1]
        else:
            fm[k] = int(raw) if raw.isdigit() else raw
    return fm


def tree_sha_for_path(p):
    try:
        return run_git("rev-parse", f"HEAD:{p}")
    except subprocess.CalledProcessError:
        return None


def compute_live_state():
    skills = []
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        sm = d / "SKILL.md"
        if not sm.exists():
            continue
        fm = parse_frontmatter(sm)
        skills.append({
            "name": fm.get("name", d.name),
            "path": d.name,
            "version": fm.get("version"),
            "kg_ref": fm.get("kg_ref"),
            "channel": fm.get("channel", "stable"),
            "git_tree_sha": tree_sha_for_path(d.name),
        })
    merkle_input = "\n".join(f"{s['path']}:{s['git_tree_sha']}" for s in skills)
    merkle_root = hashlib.sha256(merkle_input.encode("utf-8")).hexdigest()
    return skills, merkle_root


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tolerate-uncommitted", action="store_true",
                    help="Treat uncommitted skill (git_tree_sha=null) as INFO not DRIFT")
    ap.add_argument("--quiet", action="store_true",
                    help="Only print DRIFT/ERROR; OK is silent")
    ap.add_argument("--json", action="store_true",
                    help="Output structured JSON result")
    args = ap.parse_args()

    if not MANIFEST_PATH.exists():
        print(f"ERROR: MANIFEST.json missing at {MANIFEST_PATH}", file=sys.stderr)
        return 2

    manifest = json.loads(MANIFEST_PATH.read_text())
    stored_root = manifest.get("merkle_root")
    stored_skills = {s["path"]: s for s in manifest.get("skills", [])}

    live_skills, live_root = compute_live_state()
    live_paths = {s["path"]: s for s in live_skills}

    drift = []
    for path, live in live_paths.items():
        stored = stored_skills.get(path)
        if not stored:
            drift.append(("ADDED", path, None, live.get("git_tree_sha")))
            continue
        if live["git_tree_sha"] is None:
            level = "INFO" if args.tolerate_uncommitted else "DRIFT"
            drift.append((f"{level}_UNCOMMITTED", path, stored.get("git_tree_sha"), None))
        elif live["git_tree_sha"] != stored.get("git_tree_sha"):
            drift.append(("TREE_SHA", path, stored.get("git_tree_sha"), live["git_tree_sha"]))
        if live["version"] != stored.get("version"):
            drift.append(("VERSION", path, stored.get("version"), live["version"]))
        if live["kg_ref"] != stored.get("kg_ref"):
            drift.append(("KG_REF", path, stored.get("kg_ref"), live["kg_ref"]))
    for path in stored_skills:
        if path not in live_paths:
            drift.append(("REMOVED", path, stored_skills[path].get("git_tree_sha"), None))

    hard_drift = [d for d in drift if not d[0].startswith("INFO_")]
    root_match = (live_root == stored_root)

    result = {
        "stored_merkle": stored_root,
        "live_merkle": live_root,
        "root_match": root_match,
        "skills_count_stored": len(stored_skills),
        "skills_count_live": len(live_paths),
        "drift_entries": [
            {"kind": k, "path": p, "stored": s, "live": l} for k, p, s, l in drift
        ],
        "verdict": "OK" if (root_match and not hard_drift) else "DRIFT",
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["verdict"] == "OK":
            if not args.quiet:
                print(f"OK    merkle={stored_root[:12]} skills={len(live_paths)}")
        else:
            print(f"DRIFT stored={stored_root[:12]} live={live_root[:12]} entries={len(drift)}")
            for k, p, s, l in drift:
                print(f"  {k:20s} {p:20s} stored={s} live={l}")
            print(f"  → fix: python3 {Path(__file__).parent / 'skill-build-manifest.py'}")

    return 0 if result["verdict"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
