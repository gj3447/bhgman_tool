#!/bin/zsh
set -euo pipefail

repo=/Users/lagyeongjun/CD/SYMPOSIUM/GIT/bhgman_tool-wt-pi-runtime-20260716
out_dir=verification/diagnostic-repair-v2-32b
rc_path=/tmp/pi-diagnostic-repair-32b-20260716.rc

cd "$repo"

if [[ -n "$(git status --porcelain)" ]]; then
  print -u2 -- "refusing frozen run: worktree is dirty"
  exit 2
fi

if [[ -e "$out_dir" ]]; then
  print -u2 -- "refusing frozen run: output directory already exists: $out_dir"
  exit 2
fi

unset BHGMAN_LLM_ENDPOINTS
unset BHGMAN_LLM_NO_THINK
export BHGMAN_LLM_BASE_URL=http://127.0.0.1:8100/v1
export BHGMAN_LLM_MODEL=qwen2.5:32b-instruct
export LEAN_TEMP=0.8
export LEAN_MAX_TOKENS=3072
export NO_PROXY=127.0.0.1,localhost
export PYTHONUNBUFFERED=1

print -- "frozen diagnostic-repair run starting at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
print -- "git_head=$(git rev-parse HEAD)"
print -- "model=$BHGMAN_LLM_MODEL endpoint=$BHGMAN_LLM_BASE_URL"

set +e
caffeinate -dimsu uv run python -m engine.efficacy.diagnostic_repair_harness \
  --k 4 \
  --replications 10 \
  --seed-offset 0 \
  --seed-step 10 \
  --execute-frozen-run \
  --out-dir "$out_dir"
rc=$?
set -e

print -- "$rc" > "$rc_path"
print -- "frozen diagnostic-repair run finished at $(date -u +%Y-%m-%dT%H:%M:%SZ) rc=$rc"
exit "$rc"
