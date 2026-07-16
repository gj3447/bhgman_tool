#!/bin/zsh
set -euo pipefail

repo=/Users/lagyeongjun/CD/SYMPOSIUM/GIT/bhgman_tool-wt-pi-runtime-20260716
out_dir=verification/diagnostic-repair-v3-32b
analysis="$out_dir/analysis.json"
stderr=/tmp/pi-diagnostic-repair-v3-analysis-20260717.stderr
rc_path=/tmp/pi-diagnostic-repair-v3-analysis-20260717.rc

cd "$repo"

if [[ -e "$analysis" ]]; then
  print -u2 -- "refusing analysis overwrite: $analysis already exists"
  exit 2
fi

print -- "analysis_started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

set +e
uv run python -m engine.efficacy.analyze_diagnostic_repair_harness \
  --json "$out_dir" \
  > "$analysis" \
  2> "$stderr"
rc=$?
set -e

print -- "$rc" > "$rc_path"
print -- "analysis_finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ) rc=$rc"
exit "$rc"
