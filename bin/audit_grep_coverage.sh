#!/usr/bin/env bash
# audit_grep_coverage.sh — C5 enforcement stub for lesson-audit-grep-coverage-drift-2026-05-20.
# Reads :GrepPatternCatalog v1 (hard-coded inline; future: fetch from KG).
# Reports: files_scanned / total_py / coverage_pct. Exits non-zero if coverage < threshold.
#
# Usage: bin/audit_grep_coverage.sh [root_dir]
# Default root_dir = engine
#
# KG ref: grep-pattern-catalog-v1-2026-05-20, lesson-audit-grep-coverage-drift-2026-05-20

set -euo pipefail

ROOT="${1:-engine}"
THRESHOLD_WARN=0.15
THRESHOLD_FAIL=0.05

if [[ ! -d "$ROOT" ]]; then
  echo "FAIL: root_dir not found: $ROOT" >&2
  exit 2
fi

# Catalog v1 (mirrors KG :GrepPatternCatalog grep-pattern-catalog-v1-2026-05-20).
PATTERN='GraphDatabase\.|neo4j\.driver|psycopg|asyncpg|aiosqlite|pymongo|sqlalchemy\.create_engine|redis\.Redis|redis\.asyncio|aioredis|httpx|aiohttp|requests\.|urllib\.|websocket|sse_starlette|tornado|sanic|socket\.socket|socket\.create_connection|asyncio\.open_connection|paramiko|fabric|invoke\.run|celery|kombu|pika|kafka|nats|aio_pika|aiokafka|zmq|subprocess|multiprocessing|grpc|xmlrpc|rpyc|Pyro|jsonrpc|fastapi|uvicorn|gunicorn'

TOTAL_PY=$(find "$ROOT" -name "*.py" -not -path "*__pycache__*" | wc -l | tr -d ' ')
HITS=$(grep -rElZ "$PATTERN" "$ROOT" --include="*.py" 2>/dev/null | tr '\0' '\n' | grep -v '^$' | wc -l | tr -d ' ')

if [[ "$TOTAL_PY" -eq 0 ]]; then
  echo "FAIL: no .py files under $ROOT" >&2
  exit 2
fi

COVERAGE=$(awk "BEGIN {printf \"%.4f\", $HITS / $TOTAL_PY}")
PCT=$(awk "BEGIN {printf \"%.1f\", $HITS * 100 / $TOTAL_PY}")

echo "audit_grep_coverage v1"
echo "  root         : $ROOT"
echo "  total_py     : $TOTAL_PY"
echo "  files_hit    : $HITS"
echo "  coverage_pct : ${PCT}%"
echo "  threshold_warn: $(awk "BEGIN {print $THRESHOLD_WARN*100}")%"
echo "  threshold_fail: $(awk "BEGIN {print $THRESHOLD_FAIL*100}")%"

if awk "BEGIN {exit !($COVERAGE < $THRESHOLD_FAIL)}"; then
  echo "FAIL: coverage below fail threshold" >&2
  exit 1
fi
if awk "BEGIN {exit !($COVERAGE < $THRESHOLD_WARN)}"; then
  echo "WARN: coverage below warn threshold (informational only)" >&2
fi
exit 0
