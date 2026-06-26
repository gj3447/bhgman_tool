#!/usr/bin/env bash
# orbits.bhgman.sh — OMD (입체운행물방울) orbit partition for bhgman_tool.
#
# Declares ~13 PAIRWISE-DISJOINT write-set "orbits" over bhgman_tool's REAL
# directories, so that up to 13 droplets (물방울) can develop in parallel with a
# structurally-guaranteed merge-conflict count of ZERO (the SINGULON invariant).
#
# Each orbit is a `omd declare <task> --writes <glob...>`. The globs are
# subtree directory globs ("<dir>/**") that DO NOT NEST: no glob's match-set is
# a subset of, or intersects, another's. Disjointness is enforced by OMD's own
# omd_server.disjoint.sets_overlap and re-proved by README.bhgman.md.
#
# IDEMPOTENT: declaring the same task_id again is a no-op upsert in the store,
# so re-running this script does not multiply orbits. Safe to run repeatedly.
#
# This script DECLARES the partition and prints `omd status`. It never calls
# start/connect (no git worktree, no merge into main).
#
# CLI signature verified against /data/kjra/PROJECT/PI/omd/omd_server/cli.py:
#   omd --db <db> declare <task> [--name N] [--writes G...] [--reads G...] ...
#   omd --db <db> status
set -euo pipefail

# Absolute OMD binary; DB defaults next to this script (gitignored).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
omd() {
  /data/kjra/PROJECT/PI/bhgman_tool/.venv/bin/omd \
    --db "${OMD_DB:-${SCRIPT_DIR}/omd.bhgman.db}" "$@"
}

echo "== OMD orbit partition for bhgman_tool =="
echo "DB: ${OMD_DB:-${SCRIPT_DIR}/omd.bhgman.db}"
echo

# ---- 5 orbits over engine/ subsystems (grouped, non-nesting subtrees) ----
# 1) Longinus drift detector + its audit subsystem (sibling dirs, disjoint).
omd declare orbit_longinus --name "engine/longinus(drift+audit)" \
  --writes "engine/longinus_drift/**" "engine/longinus_drift_audit/**"

# 2) Execution fabric: harness + legion (parallel run) + agents.
omd declare orbit_fabric --name "engine/harness+legion+agents" \
  --writes "engine/harness/**" "engine/legion/**" "engine/agents/**"

# 3) Knowledge-graph plumbing: code->kg, local kg, memory, resolver.
omd declare orbit_kg --name "engine/code_to_kg+kg_local+memory+resolver" \
  --writes "engine/code_to_kg/**" "engine/kg_local/**" \
           "engine/memory/**" "engine/resolver/**"

# 4) Reasoning subsystems: occam, prometheus, eureka.
omd declare orbit_reason --name "engine/occam+prometheus+eureka" \
  --writes "engine/occam/**" "engine/prometheus/**" "engine/eureka/**"

# 5) Interfaces: cli, mcp_server, gate.
omd declare orbit_iface --name "engine/cli+mcp_server+gate" \
  --writes "engine/cli/**" "engine/mcp_server/**" "engine/gate/**"

# ---- 8 top-level orbits (each a single real dir subtree) ----
omd declare orbit_theory          --name "theory"          --writes "theory/**"
omd declare orbit_lean            --name "lean"            --writes "lean/**"
omd declare orbit_verification    --name "verification"    --writes "verification/**"
omd declare orbit_worked          --name "worked"          --writes "worked/**"
omd declare orbit_skills          --name "skills"          --writes "skills/**"
omd declare orbit_symposium       --name "symposium-skills" --writes "symposium-skills/**"
omd declare orbit_docs            --name "docs"            --writes "docs/**"
omd declare orbit_scripts         --name "scripts"         --writes "scripts/**"

echo
echo "== omd status =="
omd status
