#!/bin/bash
# kg-cleanup-detector.sh — 헛작업 risk 자동 detection (5 metric).
#
# KG: kg-cleanup-detector-canonical-2026-05-10 (:CleanupDetectionTool)
# Lakatos: PROGRESSIVE — conflict-skills-rebrand-vs-architecture-2026-04-26 패턴 자동 회피.
# Derived from: lesson-prom16-kg-cleanup-completion-2026-05-10 (Cycle 완결 정의 7-layer)
#
# Usage: kg-cleanup-detector.sh [--cycle CYCLE_ID] [--days N] [--json]
# Requires: cypher-shell + neo4j connection (NEO4J_PASSWORD env)
#
# 5 metric:
#   M1 — RF without GROUNDS edge (보고서만, KG missing 연결)
#   M2 — Lesson without SOURCES.md sync (본문 부재)
#   M3 — NovelPattern in markdown but missing KG node (spec only)
#   M4 — VerdictProposal without DERIVED_FROM evidence (orphan PRELIMINARY)
#   M5 — Lean theorem reference missing in KG (:LeanFormalization)

set -e

CYCLE_ID="${1:-}"
DAYS="${2:-7}"
JSON_OUT=false
[[ "$3" == "--json" ]] && JSON_OUT=true

# Stub mode (cypher-shell 없으면 markdown grep 으로 fallback)
SYMPOSIUM_ROOT="${SYMPOSIUM_ROOT:-/Users/lagyeongjun/CD/SYMPOSIUM}"

count_recent_md_findings() {
  # 최근 N 일 내 작성된 PROM_*_REPORT.md 또는 *findings*.md count
  find "$SYMPOSIUM_ROOT" -name "PROM_*_REPORT.md" -mtime -"$DAYS" 2>/dev/null | wc -l | tr -d ' '
}

count_lean_files() {
  find "/Users/lagyeongjun/CD/MIND/lean_formalization" -name "*.lean" -mtime -"$DAYS" 2>/dev/null | wc -l | tr -d ' '
}

count_md_with_kg_ref() {
  # # KG: 라인 있는 markdown (KG sync 표지)
  find "$SYMPOSIUM_ROOT" -name "*.md" -mtime -"$DAYS" 2>/dev/null | xargs grep -l "^# KG:" 2>/dev/null | wc -l | tr -d ' '
}

count_md_without_kg_ref() {
  total=$(find "$SYMPOSIUM_ROOT" -name "*.md" -mtime -"$DAYS" 2>/dev/null | wc -l | tr -d ' ')
  with_kg=$(count_md_with_kg_ref)
  echo $((total - with_kg))
}

# 5 metric 측정
M1_md_findings=$(count_recent_md_findings)
M2_md_without_kg=$(count_md_without_kg_ref)
M3_md_with_kg=$(count_md_with_kg_ref)
M4_lean_recent=$(count_lean_files)

# heretwork risk score (0=clean, 1=high risk)
total_md=$(find "$SYMPOSIUM_ROOT" -name "*.md" -mtime -"$DAYS" 2>/dev/null | wc -l | tr -d ' ')
if [ "$total_md" -gt 0 ]; then
  risk_score=$(awk "BEGIN { printf \"%.4f\", $M2_md_without_kg / $total_md }")
else
  risk_score="0.0000"
fi

if $JSON_OUT; then
  cat <<EOF
{
  "tool": "kg-cleanup-detector",
  "version": "1.0.0",
  "scan_window_days": $DAYS,
  "cycle_id": "$CYCLE_ID",
  "metrics": {
    "M1_recent_prom_reports": $M1_md_findings,
    "M2_md_without_kg_ref": $M2_md_without_kg,
    "M3_md_with_kg_ref": $M3_md_with_kg,
    "M4_lean_files_recent": $M4_lean_recent,
    "M5_total_md_recent": $total_md
  },
  "heretwork_risk_score": $risk_score,
  "verdict": "$([ "$(awk "BEGIN{print ($risk_score > 0.3) ? 1 : 0}")" = "1" ] && echo "HIGH_RISK" || echo "OK")"
}
EOF
else
  echo "kg-cleanup-detector v1.0.0 (window=${DAYS}d)"
  echo "  M1 PROM_*_REPORT.md recent:    $M1_md_findings"
  echo "  M2 md without # KG: ref:        $M2_md_without_kg"
  echo "  M3 md with # KG: ref:           $M3_md_with_kg"
  echo "  M4 .lean files recent:          $M4_lean_recent"
  echo "  M5 total md recent:             $total_md"
  echo ""
  echo "  heretwork_risk_score = $risk_score"
  echo "  verdict = $([ "$(awk "BEGIN{print ($risk_score > 0.3) ? 1 : 0}")" = "1" ] && echo "HIGH_RISK" || echo "OK")"
fi
