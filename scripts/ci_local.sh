#!/usr/bin/env bash
# CI-parity harness — reproduce EVERY GitHub Actions gate locally so "green" means CI-green.
#
# Why this exists: the integration branch ran NO CI, so local checks (sibling repos installed
# editable, Python 3.14, a different ruff build) silently diverged from main's CI (no siblings,
# Python 3.11–3.13, pinned ruff 0.15.21, mypy+deptry hard gates). A merge that was "1727 passed"
# locally went fully red on main's CI. This script is the single source of truth for CI-green:
# run it, make every gate GREEN, and the GitHub run matches.
#
# Mirrors: .github/workflows/{ci.yml,pytest.yml,deptry-eureka-subpkg.yml}
# Usage:  bash scripts/ci_local.sh            # all gates
#         bash scripts/ci_local.sh ruff mypy  # only named gates
# Exit 0 iff every selected gate is GREEN.

set -u
cd "$(dirname "$0")/.." || exit 2
VENV="${VENV:-.venv/bin}"
SELECT="${*:-}"

PASS=(); FAIL=(); SKIP=()
want() { [ -z "$SELECT" ] && return 0; for g in $SELECT; do [ "$g" = "$1" ] && return 0; done; return 1; }
red()  { printf '  \033[31m✗ RED  %s\033[0m\n' "$1"; FAIL+=("$1"); }
green(){ printf '  \033[32m✓ GREEN %s\033[0m\n' "$1"; PASS+=("$1"); }
skip() { printf '  \033[33m· SKIP %s (%s)\033[0m\n' "$1" "$2"; SKIP+=("$1"); }

# Only git-TRACKED engine *.py — CI checks out HEAD, so it never lints untracked WIP
# (e.g. engine/kg_harness/). Scanning engine/ here would false-RED on files CI can't see.
tracked_py() { git ls-files engine | grep '\.py$'; }

# ── gate 1: ruff check engine/  (ci.yml: ruff, pinned 0.15.21) ───────────────
if want ruff-check; then
  echo "[ruff-check] ruff check (tracked engine/*.py)"
  if "$VENV/ruff" check $(tracked_py) -q 2>/dev/null; then green ruff-check; else
    "$VENV/ruff" check $(tracked_py) 2>&1 | grep -E "Found|error" | tail -3 | sed 's/^/      /'; red ruff-check; fi
fi

# ── gate 2: ruff format --check engine/  (ci.yml: ruff format check) ─────────
if want ruff-format; then
  echo "[ruff-format] ruff format --check (tracked engine/*.py)"
  out=$("$VENV/ruff" format --check $(tracked_py) 2>&1)
  if echo "$out" | grep -q "would be reformatted"; then
    echo "$out" | tail -1 | sed 's/^/      /'; red ruff-format
  else green ruff-format; fi
fi

# ── gate 3: mypy engine  (ci.yml: mypy --all-extras, hard gate) ──────────────
if want mypy; then
  echo "[mypy] mypy engine"
  if out=$("$VENV/mypy" engine 2>&1); then green mypy; else
    echo "$out" | grep -E "error:|Found [0-9]+ error" | tail -6 | sed 's/^/      /'; red mypy; fi
fi

# ── gate 4: deptry engine  (ci.yml: deptry --all-extras, hard gate) ──────────
if want deptry; then
  echo "[deptry] deptry engine"
  if out=$("$VENV/deptry" engine 2>&1); then green deptry; else
    echo "$out" | grep -E "DEP[0-9]{3}|Found [0-9]+ dependency" | tail -6 | sed 's/^/      /'; red deptry; fi
fi

# ── gate 5: dependency resolvability WITHOUT sibling path-sources ────────────
# CI has no ../ooptdd ../ooptdd-loop ../omd, so `uv ... --all-extras` cannot resolve the
# [tool.uv.sources] path overrides. `uv lock --no-sources` reproduces that exactly (ignores the
# path overrides → resolves from the registry → the unpublished siblings are not found). Non-
# mutating: uv.lock is backed up + restored.
if want dep-resolve; then
  echo "[dep-resolve] uv lock --no-sources (reproduces CI 'ooptdd not found')"
  [ -f uv.lock ] && cp uv.lock /tmp/.uv.lock.bak.$$
  if out=$(timeout 90 uv lock --no-sources 2>&1); then green dep-resolve; else
    echo "$out" | grep -iE "not found|no version|because|conclude" | head -3 | sed 's/^/      /'; red dep-resolve; fi
  [ -f /tmp/.uv.lock.bak.$$ ] && mv /tmp/.uv.lock.bak.$$ uv.lock
fi

# ── gate 6: pytest (engine)  (ci.yml: --all-extras pytest matrix 3.11–3.13) ──
# NOTE: the full CI matrix (3 Pythons × --all-extras) cannot be reproduced from one interpreter.
# This runs the local engine suite; it passes here ONLY because the siblings are installed —
# which is the very gap gate 5 guards. Treat green here as necessary-not-sufficient for CI.
if want pytest; then
  echo "[pytest] $VENV/pytest -q (tracked engine suite; CI runs --all-extras × py3.11-3.13)"
  # --ignore every UNTRACKED .py — CI checks out HEAD, so untracked WIP tests (engine/kg_harness/
  # tests, test_kg_guard_wiring.py, …) never run there; collecting them here is a false signal.
  ig=()
  while IFS= read -r p; do [ -n "$p" ] && ig+=("--ignore=$p"); done < <(git ls-files --others --exclude-standard engine | grep -E '\.py$')
  if "$VENV/pytest" "${ig[@]}" -q -p no:cacheprovider >/tmp/.pt.$$ 2>&1; then
    tail -1 /tmp/.pt.$$ | sed 's/^/      /'; green pytest; else
    grep -E "failed|error|Error" /tmp/.pt.$$ | tail -4 | sed 's/^/      /'; red pytest; fi
  rm -f /tmp/.pt.$$
fi

# ── gate 7: oracle dogfood  (ci.yml: bhgman-tool oracle --kind pytest-ratio) ─
if want oracle; then
  echo "[oracle] bhgman-tool oracle --kind pytest-ratio (verify surface dogfood)"
  # filename MUST match pytest's test_*.py pattern (CI uses /tmp/test_verify_surface.py) or
  # pytest collects 0 tests → pass-ratio 0/0 → false. (Harness bug found 2026-06-26.)
  vf="${TMPDIR:-/tmp}/test_ci_parity_surface_$$.py"
  printf 'def test_surface_ok():\n    assert 1 + 1 == 2\n' > "$vf"
  if "$VENV/bhgman-tool" oracle --kind pytest-ratio --target "$vf" --json >/dev/null 2>&1; then
    green oracle; else red oracle; fi
  rm -f "$vf"
fi

# ── gate 8: wip-leak — tracked code must not import untracked modules ─────────
# CI never sees the dev tree's untracked WIP (e.g. engine/kg_harness/) or editable siblings,
# so a committed `from engine.kg_harness import …` passes here but ModuleNotFoundErrors on CI.
# The pytest gate (working tree) can't catch this; this static check does.
if want wip-leak; then
  echo "[wip-leak] tracked engine code importing untracked modules"
  if out=$("$VENV/python" scripts/check_wip_leak.py 2>&1); then green wip-leak; else
    echo "$out" | tail -6 | sed 's/^/      /'; red wip-leak; fi
fi

echo ""
echo "════ CI-parity summary ════"
printf '  GREEN: %s\n' "${PASS[*]:-—}"
printf '  RED:   %s\n' "${FAIL[*]:-—}"
[ ${#SKIP[@]} -gt 0 ] && printf '  SKIP:  %s\n' "${SKIP[*]}"
[ ${#FAIL[@]} -eq 0 ] && { echo "  → CI-green ✓"; exit 0; } || { echo "  → CI would FAIL on: ${FAIL[*]}"; exit 1; }
