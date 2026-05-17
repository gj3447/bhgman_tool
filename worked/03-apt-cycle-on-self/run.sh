#!/usr/bin/env bash
# worked-3 smoke harness — re-verify artifacts produced by the Phase 3 APT cycle.
# Does NOT re-execute the cycle. Reports raw pass/fail per step; no derived score.
# KG: span-worked-example-apt-cycle-on-self-2026-05-13 (:AtomicSpan)

set -u  # don't abort the whole script if one check fails — report each independently

# Walk up to repo root from worked/03-apt-cycle-on-self/.
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
cd "$REPO_ROOT" || { echo "FATAL: cannot cd to $REPO_ROOT"; exit 2; }

PASS=0
FAIL=0
SKIP=0

print_step() { echo; echo "=== $1 ==="; }
record_pass() { PASS=$((PASS+1)); echo "[PASS] $1"; }
record_fail() { FAIL=$((FAIL+1)); echo "[FAIL] $1"; }
record_skip() { SKIP=$((SKIP+1)); echo "[SKIP] $1 ($2)"; }

# Step 1 — CLI entry point ----------------------------------------------------
print_step "Step 1: bhgman-tool version (CLI entry registered)"
if ! command -v uv >/dev/null 2>&1; then
  record_skip "uv not installed" "install uv first: https://docs.astral.sh/uv/"
else
  if uv run bhgman-tool version 2>&1 | tee /tmp/worked-03-step1.out | grep -q "^bhgman-tool 0\\."; then
    record_pass "bhgman-tool version emits version string"
  else
    record_fail "bhgman-tool version did not emit expected header"
  fi
fi

# Step 2 — pytest on new modules ---------------------------------------------
print_step "Step 2: pytest engine/cli + engine/mcp_server (35 new tests)"
if ! command -v uv >/dev/null 2>&1; then
  record_skip "uv not installed" "see step 1"
else
  if uv run --with pytest python -m pytest engine/cli engine/mcp_server -q 2>&1 | tee /tmp/worked-03-step2.out | tail -1 | grep -qE "[0-9]+ passed"; then
    record_pass "pytest passed (see /tmp/worked-03-step2.out for count)"
  else
    record_fail "pytest did not report a passing summary"
  fi
fi

# Step 3 — apt-progress.md anchor on disk ------------------------------------
print_step "Step 3: SemanticAnchor name persisted in apt-progress.md"
if [ -f "$REPO_ROOT/apt-progress.md" ]; then
  if grep -q "sa-bhgman_tool-ruflo-utility-parity-2026-05-13" "$REPO_ROOT/apt-progress.md"; then
    record_pass "anchor name found in apt-progress.md"
  else
    record_fail "anchor name missing from apt-progress.md"
  fi
else
  record_fail "apt-progress.md missing at repo root"
fi

# Step 4 — git log shows Phase 3 commits anywhere in history -----------------
# 정정 2026-05-17: 원래 `git log -3` 은 brittle 가정 — wave10/longinus 등 후속 commit 누적 시
# Phase 3 commit 이 자연스럽게 최근 3 밖으로 밀려나 false FAIL. Phase 3 작업 자체는 history
# 어딘가에 *persisted* 되어 있으면 충분 (commit 영속성이 본질, 최근 위치가 본질 아님).
print_step "Step 4: Phase 3 commit persists in git history"
if git -C "$REPO_ROOT" log --all --oneline --grep='Phase 3' 2>/dev/null | tee /tmp/worked-03-step4.out | grep -q "Phase 3"; then
  record_pass "Phase 3 commit found in git history"
else
  record_fail "no Phase 3 commit anywhere in history"
fi

# Summary --------------------------------------------------------------------
# C9-01 remediation: distinguish gate-enforced (PASS) from step-executed-without-verification (SKIP).
# Exit 0 here means "no FAIL was recorded"; it does NOT mean "all gates passed". Consumers must
# check $SKIP > 0 separately — skipped steps were not verified, just not failed.
print_step "Summary"
echo "pass=$PASS  fail=$FAIL  skip=$SKIP"
if [ "$SKIP" -gt 0 ]; then
  echo "NOTE: $SKIP step(s) were SKIPPED — those gates are NOT verified. See per-step output above."
fi
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
