#!/usr/bin/env bash
# Restore KG snapshot.cypher → external Neo4j.
#
# Usage:
#   bash kg/restore.sh                                                    # localhost:7687
#   NEO4J_URI=bolt://other:7687 NEO4J_PASSWORD=x bash kg/restore.sh
#   bash kg/restore.sh --container symposium-neo4j                        # via docker exec
#   bash kg/restore.sh --reset                                            # CAUTION: wipes target DB first

set -euo pipefail

NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-${SYMPOSIUM_KG_PASSWORD:-symposium}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SNAPSHOT="${1:-$SCRIPT_DIR/snapshot.cypher}"
RESET=0
CONTAINER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reset)     RESET=1; shift ;;
    --container) CONTAINER="$2"; shift 2 ;;
    --snapshot)  SNAPSHOT="$2"; shift 2 ;;
    *) shift ;;
  esac
done

say()  { printf '\033[1;36m▸\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

[[ -f "$SNAPSHOT" ]] || die "snapshot not found: $SNAPSHOT (run kg/dump.sh first)"

if [[ -n "$CONTAINER" ]]; then
  CYPHER_CMD="docker exec -i $CONTAINER cypher-shell -u $NEO4J_USER -p $NEO4J_PASSWORD"
elif command -v cypher-shell >/dev/null 2>&1; then
  CYPHER_CMD="cypher-shell -a $NEO4J_URI -u $NEO4J_USER -p $NEO4J_PASSWORD"
elif command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -q '^symposium-neo4j$'; then
  CYPHER_CMD="docker exec -i symposium-neo4j cypher-shell -u $NEO4J_USER -p $NEO4J_PASSWORD"
else
  die "no cypher-shell available (install OR run 'symposium-neo4j' container OR pass --container <name>)"
fi

if [[ $RESET -eq 1 ]]; then
  say "RESET: wiping target DB (--reset given)"
  read -r -p "wipe ALL nodes/edges at $NEO4J_URI? [y/N] " r
  [[ "$r" =~ ^[Yy]$ ]] || die "abort"
  echo "MATCH (n) DETACH DELETE n;" | $CYPHER_CMD >/dev/null
  ok "target DB wiped"
fi

say "restoring $SNAPSHOT → Neo4j"
$CYPHER_CMD < "$SNAPSHOT" >/dev/null
ok "restore complete"
say "verify: echo 'MATCH (n) RETURN count(n);' | $CYPHER_CMD"
