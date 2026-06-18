#!/usr/bin/env bash
# skill-resolve-check.sh — pre-build validator for ${MIC_v1.SLOT} placeholders.
#
# A6 L2 build step (apt-hardening-master-plan iter 24).
# Runs resolve_slot.py --check on every SKILL.md under SKILLS/.
# Exits 0 if all placeholders resolvable (or none present).
# Exits 1 if any SKILL.md has unresolved placeholder.
#
# Integrate into skill-build-manifest.py as pre-build invariant by adding:
#   subprocess.run([str(SKILLS_DIR / "bin/skill-resolve-check.sh")], check=True)
# OR run in CI before merging.
#
# KG: APT_v26_A6_2026-04-21, fw-a6-resolver-runtime-2026-05-06

set -euo pipefail

SKILLS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESOLVER="$SKILLS_DIR/bin/resolve_slot.py"

if [ ! -x "$RESOLVER" ]; then
  echo "ERROR: $RESOLVER not found or not executable" >&2
  exit 2
fi

failed=0
total=0
with_placeholders=0
clean=0

for skill_md in "$SKILLS_DIR"/*/SKILL.md; do
  [ -f "$skill_md" ] || continue
  total=$((total + 1))
  if grep -q '\${MIC_v1\.' "$skill_md" 2>/dev/null; then
    with_placeholders=$((with_placeholders + 1))
    if ! python3 "$RESOLVER" --check "$skill_md" 2>&1; then
      failed=$((failed + 1))
      echo "FAIL: $skill_md" >&2
    fi
  else
    clean=$((clean + 1))
  fi
done

echo "skill-resolve-check: total=$total clean=$clean with_placeholders=$with_placeholders failed=$failed"

if [ "$failed" -gt 0 ]; then
  exit 1
fi
exit 0
