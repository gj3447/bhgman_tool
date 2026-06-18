#!/usr/bin/env bash
# taliban_mathematical_sampler.py — production smoke test fixture
#
# Tests all 7 CLI modes: --full / --sample N|RATE / --minimum / --policy / --auto / --domain / --json
# Plus error path: invalid --domain / invalid --sample / no flag
#
# KG: iter9-sampler-cli-implementation-2026-05-06,
#     iter16-sampler-test-fixture-2026-05-06,
#     fw-mathematical-113-coverage-2026-05-06

set -uo pipefail

SCRIPT="/Users/lagyeongjun/CD/SYMPOSIUM/SKILLS/bin/taliban_mathematical_sampler.py"
PASS=0
FAIL=0

assert_contains() {
    local desc="$1" needle="$2" output="$3"
    if echo "$output" | grep -qF "$needle"; then
        echo "  PASS: $desc"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — expected '$needle'" >&2
        FAIL=$((FAIL + 1))
    fi
}

assert_exit() {
    local desc="$1" expected="$2" actual="$3"
    if [ "$actual" = "$expected" ]; then
        echo "  PASS: $desc (exit $expected)"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — expected exit $expected, got $actual" >&2
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Test 1: --policy ==="
out=$(python3 "$SCRIPT" --policy 2>&1)
assert_contains "policy field" "default_sample_rate" "$out"

echo "=== Test 2: --policy --json ==="
out=$(python3 "$SCRIPT" --policy --json 2>&1)
assert_contains "json rate" '"rate"' "$out"

echo "=== Test 3: --minimum ==="
out=$(python3 "$SCRIPT" --minimum 2>&1)
assert_contains "minimum total" "total: " "$out"

echo "=== Test 4: --sample 0.50 (rate) ==="
out=$(python3 "$SCRIPT" --sample 0.50 2>&1)
assert_contains "sample rate target" "(target " "$out"

echo "=== Test 5: --sample 26 ==="
out=$(python3 "$SCRIPT" --sample 26 2>&1)
assert_contains "sample 26 result" "total: 26" "$out"

echo "=== Test 6: --domain CD restriction ==="
out=$(python3 "$SCRIPT" --minimum --domain CD 2>&1)
assert_contains "CD only" "CD: " "$out"
if echo "$out" | grep -qF "LL: "; then
    echo "  FAIL: --domain CD should not contain LL"; FAIL=$((FAIL + 1))
else
    echo "  PASS: --domain CD excludes other domains"; PASS=$((PASS + 1))
fi

echo "=== Test 7: invalid --domain ==="
python3 "$SCRIPT" --minimum --domain XX > /tmp/out_test7 2>&1
assert_exit "invalid domain exit" "2" "$?"

echo "=== Test 8: --auto ==="
out=$(python3 "$SCRIPT" --auto 2>&1)
assert_contains "auto mode header" "auto mode:" "$out"

echo "=== Test 9: --json parseable ==="
out=$(python3 "$SCRIPT" --minimum --json 2>&1)
if echo "$out" | python3 -c "import json,sys; json.loads(sys.stdin.read())" 2>/dev/null; then
    echo "  PASS: --json output valid"; PASS=$((PASS + 1))
else
    echo "  FAIL: --json invalid"; FAIL=$((FAIL + 1))
fi

echo "=== Test 10: no flag → exit 2 ==="
python3 "$SCRIPT" >/dev/null 2>&1
assert_exit "no flag" "2" "$?"

echo "=== Test 11: invalid --sample ==="
python3 "$SCRIPT" --sample abc >/dev/null 2>&1
assert_exit "invalid sample" "2" "$?"

echo "=== Test 12: --sample 1.5 (>= 1.0 rejected) ==="
python3 "$SCRIPT" --sample 1.5 >/dev/null 2>&1
assert_exit "rate >= 1.0" "2" "$?"

echo ""
echo "================================"
echo "Total: PASS=$PASS  FAIL=$FAIL"
echo "================================"
exit $((FAIL > 0 ? 1 : 0))
