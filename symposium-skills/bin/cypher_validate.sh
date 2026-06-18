#!/bin/bash
# cypher_validate.sh v2 — single cypher-shell JVM session, all EXPLAIN in one file
# Per A3 finding (PROM 16): bash regex extract → cypher-shell -f (batch) → exit-code
# v1 had ~6 min runtime (JVM-per-query); v2 ~5 sec (single JVM)

set -u
NEO4J_URI="${NEO4J_URI:-bolt://100.64.0.3:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASS="${NEO4J_PASS:-neo4jpassword}"

if [ $# -eq 0 ]; then
  paths=(
    /Users/lagyeongjun/CD/SYMPOSIUM/SKILLS/_common
    /Users/lagyeongjun/CD/SYMPOSIUM/SKILLS/apt-sa
    /Users/lagyeongjun/CD/SYMPOSIUM/SKILLS/apt-sp
    /Users/lagyeongjun/CD/SYMPOSIUM/SKILLS/apt-st
    /Users/lagyeongjun/CD/SYMPOSIUM/SKILLS/apt-scw
    /Users/lagyeongjun/CD/SYMPOSIUM/SKILLS/apt-meta-review
  )
else
  paths=("$@")
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Build single .cypher file with all queries as EXPLAIN, separated by ;
{
  echo "// cypher_validate.sh v2 batch — $(date -u +%FT%TZ)"
  echo ""
  find "${paths[@]}" -name "*.md" -not -path "*/_legacy/*" 2>/dev/null | while read -r f; do
    awk -v src="$f" '
      /^```cypher$/ { in_block=1; n++; print "// === " src " block " n " ==="; print "EXPLAIN"; next }
      /^```$/ && in_block { in_block=0; print ";"; print ""; next }
      in_block { print }
    ' "$f"
  done
} > "$TMP/all.cypher"

total=$(grep -c "^EXPLAIN$" "$TMP/all.cypher")

# Single JVM session
out=$(cypher-shell -a "$NEO4J_URI" -u "$NEO4J_USER" -p "$NEO4J_PASS" --format plain \
       --fail-at-end -f "$TMP/all.cypher" 2>&1)

# Count failures
fails=$(echo "$out" | grep -cE "SyntaxError|ProcedureNotFoundException|UndefinedAlias|TypeError" || true)
passed=$((total - fails))

echo ""
echo "=== Cypher Template Validation Result (v2 batch) ==="
echo "Total cypher blocks: $total"
echo "PASS: $passed"
echo "FAIL: $fails"
if [ "$fails" -gt 0 ]; then
  echo ""
  echo "FAILURE samples:"
  echo "$out" | grep -BC1 -E "SyntaxError|ProcedureNotFoundException" | head -20
  exit 1
fi
echo "ALL PASS"
exit 0
