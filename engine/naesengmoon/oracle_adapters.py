"""4 deterministic oracle adapters — bhgman's confirmed value: verification, not the loop.

User verdict 2026-06-04 (after the evolve-loop investigation closed: loop = neutral-to-worse at
bhgman's scale, the deterministic ORACLE was the one consistently-valuable piece): confirm bhgman as
the *oracle substrate* a reasoner (ultracode) calls. These wire the 4 qualifying-task oracles — which
had existed only as a `kind:` enum string — into real, runnable `ScalarOracle` objects using verified
commands. Each is substrate-disjoint from the LLM (process exit code / proof checker / KG count), so a
reasoner cannot fake its verdict; each is zero-LLM-token, deterministic, reproducible, auditable.

  lean-goals    — `lean <self-contained .lean>` exit 0 → (#theorem/lemma/example − #sorry/admit), else −1000
  pytest-ratio  — `pytest <target>` → passed / (passed+failed+errors)
  drift-recount — LonginusAudit(code_root,kg).run_full().total_drifts, negated (0 drift = best)
  occam-twins   — run_occam(...).report.superseded_count (lossless dead-node removals; twin-backed only)

# KG: lesson-premature-close-confirmation-toward-closure-2026-06-02, prom16-bhgman-ci-design-2026-06-02,
#     naesengmoon-wired-ensemble-upgrade-2026-05-27 (oracle lens-class), efficacy-measurement-line-2026-06-01
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from engine.naesengmoon.oracle_lens import ScalarOracle

_LEAN_DECL = re.compile(r"^(theorem|lemma|example)\b", re.MULTILINE)
_LEAN_HOLE = re.compile(r"\b(sorry|admit)\b")


def _strip_lean_comments(src: str) -> str:
    """Remove Lean line comments (``-- … EOL``) and nested block comments (``/- … -/``)
    before counting holes/decls.

    A ``sorry``/``admit`` written in a comment is NOT an open goal — counting it as one
    underreports closed goals behind a passing ``lean`` compile. axiom_audit.py already
    excludes comment-position sorry; this keeps the oracle consistent. Block comments may
    nest in Lean, so a regex won't do — scan with a depth counter. Newlines are preserved
    so line-anchored ``_LEAN_DECL`` matches are unaffected.
    """
    out: list[str] = []
    i, n, depth = 0, len(src), 0
    while i < n:
        two = src[i : i + 2]
        if depth == 0 and two == "--":
            j = src.find("\n", i)
            if j == -1:
                break
            i = j  # keep the newline, drop the comment body
            continue
        if two == "/-":
            depth += 1
            i += 2
            continue
        if depth > 0 and two == "-/":
            depth -= 1
            i += 2
            continue
        if depth == 0:
            out.append(src[i])
        elif src[i] == "\n":
            out.append("\n")  # preserve line structure inside block comments
        i += 1
    return "".join(out)


def lean_goals_oracle(lean_dir: str | Path = ".", timeout_s: int = 240) -> ScalarOracle:
    # KG: naesengmoon-canonical-2026-05-19
    """Lean proof-search oracle. score(lean_filename) = closed goals if `lean` exits 0, else −1000.

    Self-contained files only (no non-prelude imports — cross-import needs a lakefile the repo root
    lacks). Counting theorems−sorry is sound only behind the exit-0 hard gate. leak-resistant.
    """
    root = Path(lean_dir)

    def _score(lean_file: Any) -> float:
        path = Path(lean_file)
        if not path.is_absolute() and not path.exists():
            # Resolve against lean_dir only when the target isn't already found as-given.
            # Prevents lean_dir/lean_dir/X doubling when the caller passes a target that
            # already includes the lean_dir prefix (e.g. --target lean/X --lean-dir lean).
            path = root / path
        try:
            proc = subprocess.run(  # noqa: S603, S607
                ["lean", str(path)], capture_output=True, text=True, timeout=timeout_s, check=False
            )
        except (subprocess.TimeoutExpired, OSError):
            # OSError covers FileNotFoundError (no lean on PATH, e.g. CI) AND PermissionError
            # (non-executable lean) — a missing/broken toolchain → FAIL gate, never a crash.
            return -1000.0
        if proc.returncode != 0:
            return -1000.0
        src = _strip_lean_comments(path.read_text())
        return float(len(_LEAN_DECL.findall(src)) - len(_LEAN_HOLE.findall(src)))

    return ScalarOracle(name="lean", kind="lean-goals", score=_score)


def pytest_ratio_oracle(timeout_s: int = 120) -> ScalarOracle:
    # KG: naesengmoon-canonical-2026-05-19
    """pytest pass-ratio oracle. score(test_target) = passed/(passed+failed+errors). collect-fail → 0."""

    def _score(test_target: Any) -> float:
        try:
            proc = subprocess.run(  # noqa: S603, S607
                [
                    "uv",
                    "run",
                    "pytest",
                    str(test_target),
                    "-q",
                    "--no-header",
                    "-p",
                    "no:cacheprovider",
                ],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError):
            return 0.0
        out = proc.stdout + proc.stderr

        def _n(word: str) -> int:
            m = re.search(rf"(\d+) {word}", out)
            return int(m.group(1)) if m else 0

        passed, failed, errors = _n("passed"), _n("failed"), _n("error")
        total = passed + failed + errors
        if total == 0:
            return 1.0 if proc.returncode == 0 else 0.0
        return passed / total

    return ScalarOracle(name="pytest", kind="pytest-ratio", score=_score)


def drift_recount_oracle(code_root: str | Path, kg: Any) -> ScalarOracle:
    # KG: naesengmoon-canonical-2026-05-19
    """longinus KG↔code drift oracle. score = −total_drifts (0 = clean = best). candidate ignored.

    kg MUST be a populated client (JsonFileKgClient / Neo4j-backed). A MockKgClient returns 0 drift
    for any input = a signal-absent false oracle — caller's responsibility to pass real state.
    """

    def _score(_candidate: Any = None) -> float:
        from engine.longinus_drift_audit.audit_runner import LonginusAudit

        report = LonginusAudit(kg=kg, code_root=code_root).run_full(verify_sha256=False)
        return -float(report.total_drifts)

    return ScalarOracle(name="longinus", kind="drift-recount", score=_score)


def occam_twins_oracle(
    run_cypher: Any, scope: str | None = None, repo_root: str | Path | None = None
) -> ScalarOracle:
    # KG: naesengmoon-canonical-2026-05-19
    """occam supersession oracle. score = superseded_count (lossless dead-node removals, twin-backed
    only — disk-orphans excluded per the no-delete covenant). candidate ignored (measures KG state)."""

    def _score(_candidate: Any = None) -> float:
        from engine.occam.occam_runner import run_occam

        res = run_occam(run_cypher, scope=scope, apply=False, repo_root=repo_root)
        return float(res.report.superseded_count)

    return ScalarOracle(name="occam", kind="occam-twins", score=_score)


__all__ = [
    "drift_recount_oracle",
    "lean_goals_oracle",
    "occam_twins_oracle",
    "pytest_ratio_oracle",
]
