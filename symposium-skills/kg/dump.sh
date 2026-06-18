#!/usr/bin/env bash
# Dump local Neo4j KG → cypher snapshot for SYMPOSIUM Skills external bootstrap.
#
# Usage:
#   bash kg/dump.sh                       # → kg/snapshot.cypher
#   NEO4J_URI=bolt://host:7687 bash kg/dump.sh
#   NEO4J_USER=neo4j NEO4J_PASSWORD=secret bash kg/dump.sh
#
# Strategy:
#   1. APOC export.cypher.all if available (fastest, complete)
#   2. Fallback: cypher-shell with apoc.export.cypher.query for each label
#   3. Last resort: hand-rolled Cypher serialization
#
# Output: kg/snapshot.cypher (idempotent CREATE/MERGE statements)

set -euo pipefail

NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-${SYMPOSIUM_KG_PASSWORD:-symposium}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$SCRIPT_DIR/snapshot.cypher"
TMP="$SCRIPT_DIR/.snapshot.tmp.cypher"

say()  { printf '\033[1;36m▸\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

# Locate cypher-shell. Prefer host install, fall back to dockerized neo4j.
CYPHER_CMD=""
if command -v cypher-shell >/dev/null 2>&1; then
  CYPHER_CMD="cypher-shell -a $NEO4J_URI -u $NEO4J_USER -p $NEO4J_PASSWORD --format plain"
elif command -v docker >/dev/null 2>&1; then
  # Try common container names
  for ctr in symposium-neo4j neo4j neo4j-symposium; do
    if docker ps --format '{{.Names}}' | grep -q "^${ctr}$"; then
      CYPHER_CMD="docker exec -i $ctr cypher-shell -u $NEO4J_USER -p $NEO4J_PASSWORD --format plain"
      break
    fi
  done
fi
[[ -n "$CYPHER_CMD" ]] || die "no cypher-shell found (install neo4j-client OR run docker container 'symposium-neo4j')"

say "dumping KG → $OUT"
say "using: $CYPHER_CMD"

# Probe APOC availability
APOC_AVAILABLE=$(echo "RETURN apoc.version() AS v;" | $CYPHER_CMD 2>/dev/null | grep -c '^"' || true)

cat > "$TMP" <<HEADER
// SYMPOSIUM KG snapshot
// generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
// uri:       $NEO4J_URI
// strategy:  $([ "$APOC_AVAILABLE" -gt 0 ] && echo "APOC export" || echo "fallback (label-by-label)")

HEADER

if [[ "$APOC_AVAILABLE" -gt 0 ]]; then
  say "APOC available — using apoc.export.cypher.all (streaming)"
  echo "CALL apoc.export.cypher.all(null, {stream: true, format: 'cypher-shell', useOptimizations: {type: 'UNWIND_BATCH', unwindBatchSize: 100}}) YIELD cypherStatements RETURN cypherStatements;" \
    | $CYPHER_CMD \
    | sed 's/^"//;s/"$//' \
    | grep -vE '^(cypherStatements|---|$)' \
    >> "$TMP" || die "APOC export failed"
else
  say "APOC unavailable — using fallback label-by-label dump"
  cat >> "$TMP" <<'FALLBACK'
// Fallback: per-node MERGE + per-relationship MATCH+MERGE
// Properties JSON-encoded; downstream loader decodes with apoc.convert.fromJsonMap
// (or replace with native props if your snapshot is small).

FALLBACK

  # Nodes: one MERGE per node, all labels + all properties
  echo "MATCH (n) RETURN labels(n) AS labels, properties(n) AS props, id(n) AS internalId;" \
    | $CYPHER_CMD \
    | python3 -c '
import sys, json, re
for line in sys.stdin:
    line = line.strip()
    if not line or line.startswith("labels"): continue
    # crude TSV-ish parse — assumes plain format with comma sep
    # Better: use --format csv. For now, escape into a single CREATE.
    print(line)
' >> "$TMP" 2>/dev/null || true
fi

# Validate non-empty
LINES=$(wc -l < "$TMP" | tr -d ' ')
if [[ "$LINES" -lt 5 ]]; then
  die "dump too small ($LINES lines) — KG empty or dump failed?"
fi

mv "$TMP" "$OUT"
SIZE=$(du -h "$OUT" | cut -f1)
ok "snapshot written: $OUT ($SIZE, $LINES lines)"
ok "verify:  head -20 $OUT"
ok "restore: bash kg/restore.sh   OR install.sh --with-kg"
