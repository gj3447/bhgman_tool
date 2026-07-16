#!/bin/zsh
set -euo pipefail

repo=/Users/lagyeongjun/CD/SYMPOSIUM/GIT/bhgman_tool-wt-pi-runtime-20260716
nodeid=engine/efficacy/tests/test_diagnostic_repair_harness.py::test_legacy_and_pi_repair_have_equivalent_generation_and_oracle_traces

cd "$repo"

print -- "b1_started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
print -- "git_head=$(git rev-parse HEAD)"
print -- "git_status_sha256=$(git status --porcelain=v1 | shasum -a 256 | awk '{print $1}')"
print -- "command=uv run --all-extras pytest -q $nodeid"

uv run --all-extras pytest -q "$nodeid"
rc=$?

print -- "exit_code=$rc"
print -- "b1_finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
exit "$rc"
