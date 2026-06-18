#!/bin/bash
# kg-mirror-monthly.sh — TIER 3 offsite mirror (PROM 16 A10)
# Cron: 0 3 1 * * /Users/lagyeongjun/CD/SYMPOSIUM/bin/kg-mirror-monthly.sh
# Mirror /Users/lagyeongjun/CD/SYMPOSIUM/_archive/kg-backups/ → minio dgx:30900/kg-offsite/<YYYYMM>/
# Retention: 12 months

set -u
MC="${MC:-/opt/homebrew/bin/mc}"
ALIAS="${MC_ALIAS:-localminio}"
BUCKET="${MC_BUCKET:-kg-offsite}"
SRC="${KG_BACKUP_DIR:-/Users/lagyeongjun/CD/SYMPOSIUM/_archive/kg-backups}"
LOG="${SRC}/mirror.log"
RETENTION_MONTHS="${KG_MIRROR_RETENTION_MONTHS:-12}"

ts=$(date -u +%FT%TZ)
MONTH=$(date -u +%Y%m)

echo "[$ts] starting mirror → ${ALIAS}/${BUCKET}/${MONTH}/" >> "$LOG"

if [ ! -d "$SRC" ] || ! ls "$SRC"/kg-*.cypher 2>/dev/null > /dev/null; then
  echo "[$ts] FAIL: no kg-*.cypher backups in $SRC" >> "$LOG"
  exit 1
fi

# Upload all kg-*.cypher and .meta.json from current month (or all if monthly)
for f in "$SRC"/kg-*.cypher "$SRC"/kg-*.cypher.meta.json; do
  [ -f "$f" ] || continue
  bn=$(basename "$f")
  "$MC" cp -q "$f" "${ALIAS}/${BUCKET}/${MONTH}/${bn}" 2>>"$LOG"
done

# Verify
count=$("$MC" ls "${ALIAS}/${BUCKET}/${MONTH}/" 2>/dev/null | wc -l | tr -d ' ')
echo "[$ts] uploaded $count files to ${ALIAS}/${BUCKET}/${MONTH}/" >> "$LOG"

# Retention: remove months older than N
CUTOFF=$(date -u -v -${RETENTION_MONTHS}m +%Y%m 2>/dev/null || date -u --date="${RETENTION_MONTHS} months ago" +%Y%m 2>/dev/null)
if [ -n "$CUTOFF" ]; then
  "$MC" ls "${ALIAS}/${BUCKET}/" 2>/dev/null | awk '{print $NF}' | sed 's|/$||' | while read month_dir; do
    if [[ "$month_dir" =~ ^[0-9]{6}$ ]] && [ "$month_dir" \< "$CUTOFF" ]; then
      "$MC" rb --force "${ALIAS}/${BUCKET}/${month_dir}" >> "$LOG" 2>&1
      echo "[$ts] retention cleanup: removed ${month_dir} (< $CUTOFF)" >> "$LOG"
    fi
  done
fi

exit 0
