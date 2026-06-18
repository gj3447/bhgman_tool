#!/bin/bash
# kg-backup-daily.sh — Daily APOC Cypher export (PROM 16 A10 TIER 1 hot backup)
# Cron: 0 2 * * * /Users/lagyeongjun/CD/SYMPOSIUM/bin/kg-backup-daily.sh
# Retention: 7 days rolling

set -u
NEO4J_URI="${NEO4J_URI:-bolt://100.64.0.3:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASS="${NEO4J_PASS:-neo4jpassword}"
BACKUP_DIR="${KG_BACKUP_DIR:-/Users/lagyeongjun/CD/SYMPOSIUM/_archive/kg-backups}"
RETENTION_DAYS="${KG_BACKUP_RETENTION_DAYS:-7}"
LOG="${BACKUP_DIR}/backup.log"

mkdir -p "$BACKUP_DIR"

ts=$(date -u +%FT%TZ)
DATE=$(date -u +%Y%m%d-%H%M%S)
OUT="$BACKUP_DIR/kg-${DATE}.cypher"

echo "[$ts] starting backup → $OUT" >> "$LOG"

cypher-shell -a "$NEO4J_URI" -u "$NEO4J_USER" -p "$NEO4J_PASS" --format plain \
  "CALL apoc.export.cypher.all(null, {format:'plain', stream:true, batchSize:500, separateFiles:false}) YIELD batches, nodes, relationships, time, cypherStatements RETURN cypherStatements" \
  > "$OUT.raw" 2>>"$LOG"

if [ ! -s "$OUT.raw" ]; then
  echo "[$ts] FAIL: empty output" >> "$LOG"
  exit 1
fi

tail -n +2 "$OUT.raw" > "$OUT"
rm "$OUT.raw"

NODE_COUNT=$(cypher-shell -a "$NEO4J_URI" -u "$NEO4J_USER" -p "$NEO4J_PASS" --format plain \
  "MATCH (n) RETURN count(n) AS nodes" 2>/dev/null | tail -1)
REL_COUNT=$(cypher-shell -a "$NEO4J_URI" -u "$NEO4J_USER" -p "$NEO4J_PASS" --format plain \
  "MATCH ()-[r]->() RETURN count(r) AS rels" 2>/dev/null | tail -1)
SIZE=$(stat -f %z "$OUT" 2>/dev/null || stat -c %s "$OUT" 2>/dev/null)
SHA=$(shasum -a 256 "$OUT" | cut -d' ' -f1)

cat > "${OUT}.meta.json" <<META
{
  "backup_at": "$ts",
  "neo4j_uri": "$NEO4J_URI",
  "node_count": "$NODE_COUNT",
  "relationship_count": "$REL_COUNT",
  "size_bytes": $SIZE,
  "sha256": "$SHA",
  "retention_days": $RETENTION_DAYS,
  "tier": "hot-daily-apoc-cypher-export",
  "prom16_axis": "A10"
}
META

echo "[$ts] OK: $OUT ($SIZE bytes, $NODE_COUNT nodes, $REL_COUNT rels, sha=${SHA:0:12})" >> "$LOG"

find "$BACKUP_DIR" -maxdepth 1 -name "kg-*.cypher" -type f -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null
find "$BACKUP_DIR" -maxdepth 1 -name "kg-*.cypher.meta.json" -type f -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null

echo "[$ts] retention cleanup: kept $(ls "$BACKUP_DIR"/kg-*.cypher 2>/dev/null | wc -l | tr -d ' ') backups (≤ ${RETENTION_DAYS}d)" >> "$LOG"
exit 0
