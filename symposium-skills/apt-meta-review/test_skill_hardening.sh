#!/bin/bash
# KG: CONTRACT_Hardening_SkillPatches, CONTRACT_Hardening_MetaReview
# TDD RED phase — run before patches to confirm failures
# Run: bash test_skill_hardening.sh

PASS=0
FAIL=0
SKILLS_DIR="$(cd "$(dirname "$0")/.." && pwd)"

ok()   { echo "[PASS] $1"; ((PASS++)); }
fail() { echo "[FAIL] $1"; ((FAIL++)); }

echo "=== Skill Hardening Acceptance Tests ==="
echo "Skills dir: $SKILLS_DIR"
echo ""

# --- TASK 1: Taliban SKILL.md — findings IS NOT NULL HARD BLOCK ---
echo "--- Taliban Sentinel ---"
TALIBAN="$SKILLS_DIR/taliban/SKILL.md"

if grep -q "IS NOT NULL" "$TALIBAN" 2>/dev/null; then
  ok "Taliban: 'IS NOT NULL' HARD BLOCK present"
else
  fail "Taliban: 'IS NOT NULL' HARD BLOCK MISSING"
fi

if grep -q "findings.*null.*REJECTED\|null.*findings.*REJECTED\|RUBBER_STAMP" "$TALIBAN" 2>/dev/null; then
  ok "Taliban: null findings → REJECTED rule present"
else
  fail "Taliban: null findings auto-REJECTED rule MISSING"
fi

# --- TASK 2: apt-sp SKILL.md — :AtomicSpan label in Cypher ---
echo ""
echo "--- APT-SP AtomicSpan Label ---"
APTSP="$SKILLS_DIR/apt-sp/SKILL.md"

if grep -q ":AtomicSpan" "$APTSP" 2>/dev/null; then
  ok "apt-sp: ':AtomicSpan' label in Cypher examples"
else
  fail "apt-sp: ':AtomicSpan' label MISSING from Cypher examples"
fi

if grep -q "SET.*:AtomicSpan\|MERGE.*:AtomicSpan\|labels.*AtomicSpan" "$APTSP" 2>/dev/null; then
  ok "apt-sp: AtomicSpan SET/MERGE Cypher present"
else
  fail "apt-sp: AtomicSpan SET/MERGE Cypher MISSING"
fi

# --- TASK 3: apt-scw SKILL.md — session guard + FulfillmentGate ---
echo ""
echo "--- APT-SCW Session Guard ---"
APTSCW="$SKILLS_DIR/apt-scw/SKILL.md"

if grep -q "세션 재개\|session.*resume\|재개.*invoke\|context compression" "$APTSCW" 2>/dev/null; then
  ok "apt-scw: session resume guard present"
else
  fail "apt-scw: session resume guard MISSING"
fi

if grep -q "FulfillmentGate\|executor.*reviewer\|reviewer.*executor" "$APTSCW" 2>/dev/null; then
  ok "apt-scw: FulfillmentGate / executor!=reviewer rule present"
else
  fail "apt-scw: FulfillmentGate MISSING"
fi

# --- TASK 4: apt-meta-review SKILL.md exists ---
echo ""
echo "--- MetaReview SKILL.md ---"
METAREVIEW="$SKILLS_DIR/apt-meta-review/SKILL.md"

if [ -f "$METAREVIEW" ]; then
  ok "apt-meta-review: SKILL.md exists"
else
  fail "apt-meta-review: SKILL.md MISSING (file not created yet)"
fi

if grep -q "max_depth\|delta.*0\|self.*application.*forbidden\|자기참조" "$METAREVIEW" 2>/dev/null; then
  ok "apt-meta-review: termination conditions present"
else
  fail "apt-meta-review: termination conditions MISSING"
fi

if grep -q "Taliban\|taliban\|검증" "$METAREVIEW" 2>/dev/null; then
  ok "apt-meta-review: Taliban Gate section present"
else
  fail "apt-meta-review: Taliban Gate section MISSING"
fi

echo ""
echo "=== Results: PASS=$PASS  FAIL=$FAIL ==="
[ "$FAIL" -eq 0 ] && echo "ALL PASS ✓" || echo "FAILURES EXIST — implement GREEN phase"
exit "$FAIL"
