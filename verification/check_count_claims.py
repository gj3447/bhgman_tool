#!/usr/bin/env python3
"""Count-claim drift guard.

Re-measures the count claims that appear in README*.md / docs/ and compares
them to the single source of truth in ``verification/count_claims.json``.

Why this exists
---------------
The repo's own README warns that theorem/sorry/pytest counts are
Goodhart-vulnerable, yet nothing *checked* that the documented numbers matched
reality — so they silently drifted (docs said "50 theorems / 5 files" long
after the lean tree had grown to 71/13; the README reproduce-table pointed at a
``lean/src/`` directory that does not exist; pytest counts lagged by ~2x). This
guard makes that class of drift loud instead of silent.

Gating policy (deliberately asymmetric — see ADRs/count-claim-drift-guard-2026-05-31.md):

* ``lean`` counts are **deterministic** (a grep over ``lean/``) and were the
  metric that actually rotted, so they are **HARD-gated**: any mismatch is a
  non-zero exit.
* ``pytest`` collected counts **grow** as tests are added (often by a
  concurrent session), so hard-pinning them would manufacture churn. They are
  **soft-banded**: the guard fails only on an *over-claim* (a documented number
  larger than reality — the credibility-damaging direction) and merely *warns*
  on a stale-low number, nudging a refresh.

Usage
-----
    python verification/check_count_claims.py            # check (CI / pre-push)
    python verification/check_count_claims.py --update    # rewrite the manifest from live measurement
    python verification/check_count_claims.py --json      # machine-readable report

Pytest measurement uses ``pytest --co -q`` (collect-only): fast (~1.5s) and
independent of whether an ANTHROPIC_API_KEY / optional extras are present
(skipped tests are still *collected*).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "verification" / "count_claims.json"
LEAN_DIR = REPO / "lean"

_THM_RE = re.compile(r"^(theorem|lemma)\s")
_SORRY_RE = re.compile(r"(:=|\bby)\s+sorry\b")
_COLLECTED_RE = re.compile(r"(\d+) tests? collected")


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def _lean_files(tree: bool) -> list[Path]:
    return sorted(LEAN_DIR.rglob("*.lean") if tree else LEAN_DIR.glob("*.lean"))


def measure_lean() -> dict[str, int]:
    def thms(files: list[Path]) -> int:
        return sum(
            1
            for f in files
            for line in f.read_text(encoding="utf-8").splitlines()
            if _THM_RE.match(line)
        )

    def sorries(files: list[Path]) -> int:
        return sum(
            1
            for f in files
            for line in f.read_text(encoding="utf-8").splitlines()
            if _SORRY_RE.search(line)
        )

    tree, standalone = _lean_files(True), _lean_files(False)
    return {
        "theorems_tree": thms(tree),
        "theorems_standalone": thms(standalone),
        "proof_position_sorry": sorries(tree),
    }


def _pytest_collected(path: str | None) -> int:
    cmd = [sys.executable, "-m", "pytest", "--co", "-q"]
    if path:
        cmd.append(path)
    out = subprocess.run(  # noqa: S603 - fixed argv, no shell
        cmd, cwd=REPO, capture_output=True, text=True
    ).stdout
    hits = _COLLECTED_RE.findall(out)
    if not hits:
        raise RuntimeError(f"could not parse collected count from pytest output:\n{out[-500:]}")
    return int(hits[-1])


def measure_pytest() -> dict[str, int]:
    return {
        "engine_subset_collected": _pytest_collected("engine/longinus_drift_audit/tests"),
        "full_repo_collected": _pytest_collected(None),
    }


# --------------------------------------------------------------------------- #
# Check
# --------------------------------------------------------------------------- #
def run_check() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures: list[str] = []
    warnings: list[str] = []

    # 1. lean — HARD, exact
    live_lean = measure_lean()
    for key, expected in manifest["lean"].items():
        if key.startswith("_"):
            continue
        actual = live_lean[key]
        if actual != expected:
            failures.append(f"lean.{key}: doc says {expected}, repo has {actual} (HARD)")

    # 2. pytest — SOFT band: fail on over-claim, warn on stale-low
    live_pytest = measure_pytest()
    for key, expected in manifest["pytest"].items():
        if key.startswith("_"):
            continue
        actual = live_pytest[key]
        if expected > actual:
            failures.append(
                f"pytest.{key}: doc OVER-CLAIMS {expected} but only {actual} collected (HARD)"
            )
        elif expected < actual:
            warnings.append(
                f"pytest.{key}: doc says {expected}, repo now has {actual} — stale-low, run --update"
            )

    # 3. doc-presence — the manifest's numbers must literally appear in the prose
    for rel, values in manifest.get("doc_presence", {}).items():
        if rel.startswith("_"):
            continue
        text = (REPO / rel).read_text(encoding="utf-8")
        for v in values:
            if not re.search(rf"(?<!\d){v}(?!\d)", text):
                failures.append(
                    f"doc-presence: {rel} no longer contains {v} (prose drifted from manifest)"
                )

    for w in warnings:
        print(f"  WARN  {w}")
    if failures:
        print("\nCOUNT-CLAIM DRIFT (guard FAILED):")
        for f in failures:
            print(f"  FAIL  {f}")
        print(
            "\nFix: correct the doc/manifest, or `python verification/check_count_claims.py --update`."
        )
        return 1
    print(f"count-claim guard OK (lean {live_lean}, pytest {live_pytest})")
    return 0


def run_update() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["lean"].update(measure_lean())
    manifest["pytest"].update(measure_pytest())
    # keep _note keys and ordering stable; json.dumps re-emits with 2-space indent
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"manifest refreshed: {MANIFEST.relative_to(REPO)}")
    print("Now refresh the doc prose (README badges/table, lean-theorems.md) to match.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--update", action="store_true", help="rewrite the manifest from live measurement"
    )
    ap.add_argument("--json", action="store_true", help="print measured values as JSON and exit 0")
    args = ap.parse_args(argv)
    if args.json:
        print(json.dumps({"lean": measure_lean(), "pytest": measure_pytest()}, indent=2))
        return 0
    return run_update() if args.update else run_check()


if __name__ == "__main__":
    raise SystemExit(main())
