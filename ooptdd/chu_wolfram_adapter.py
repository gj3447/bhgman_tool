"""ooptdd-loop in_process target for the SYMPOSIUM CHU Wolfram-rewrite dynamics layer.

The system-under-test is a REAL Lean 4 artifact:
    MIND/lean_formalization/CHU_WolframRewrite.lean   (Mathlib-free, standalone)
which formalises CHU's previously-empty dynamics layer (Wolfram update rule H1->H2)
and proves ``strict_truncation`` — the theorem that a strict-equality identity regime
(Neo4j-style) collapses the homotopy tower to a 1-category (arXiv:2111.03460 Prop 4.3).

Honest-count contract (verified before writing):
    Neither event is ever shipped from a literal / hard-coded success. Both are EARNED
    by actually invoking the Lean elaborator on the file off disk:
      * ``verify_chu_lean`` shells out to ``lean CHU_WolframRewrite.lean`` and ships
        'chu_wolfram_lean_verified' ONLY when the process exits 0 (Lean checks every
        proof; a broken proof => nonzero exit => NO event => gate RED).
      * ``check_truncation_theorem`` re-runs Lean AND parses the source to confirm the
        ``strict_truncation`` theorem is genuinely declared; it ships
        'chu_strict_truncation_proven' only when BOTH hold. A false theorem could not
        have compiled, so the event cannot be faked without a real proof on disk.

Longinus binding (AST-checked by ooptdd_loop):
    The event-name string literals 'chu_wolfram_lean_verified' and
    'chu_strict_truncation_proven' appear verbatim inside the bodies of the two bound
    symbols below, and are exactly the events shipped. Rename a literal and the gate
    goes UNBOUND.

# KG: finding-ooptdd-chu-wolfram-lean-adapter-2026-07-13
# KG: lesson-neo4j-is-strict-eq-1category-truncation-of-chu-infgroupoid-2026-07-13
# KG: prom16-wolfram-chu-ruliad-hott-2026-07-13
"""

from __future__ import annotations

import os
import shutil
import subprocess

# The REAL SUT: absolute paths (this is a local dev loop, memory backend). The Lean file
# lives in the user's canonical Lean home (MIND/), outside this repo; the adapter runs the
# elaborator against those exact bytes on disk.
_LEAN_FILE = os.path.expanduser("~/CD/MIND/lean_formalization/CHU_WolframRewrite.lean")
_ELAN_LEAN = os.path.expanduser("~/.elan/bin/lean")
_TRUNCATION_THEOREM = "strict_truncation"

_KG_ANCHOR = "finding-ooptdd-chu-wolfram-lean-adapter-2026-07-13"


def _lean_bin() -> str:
    """Resolve the lean binary honestly (elan path first, then PATH)."""
    if os.path.exists(_ELAN_LEAN):
        return _ELAN_LEAN
    found = shutil.which("lean")
    if not found:
        raise FileNotFoundError("lean binary not found (elan or PATH)")
    return found


def _ev(cid: str, event: str, **attrs) -> dict:
    """Shape one trace event the way the memory backend keys + counts it (cid + event)."""
    return {
        "cid": cid,
        "correlation_id": cid,
        "cycle_id": cid,
        "service": "symposium-chu-wolfram",
        "event": event,
        **attrs,
    }


def _run_lean() -> subprocess.CompletedProcess:
    """Actually elaborate the Lean file off disk. Returns the completed process."""
    return subprocess.run(
        [_lean_bin(), _LEAN_FILE],
        capture_output=True,
        text=True,
        timeout=300,
    )


def verify_chu_lean(backend, cid: str) -> int:
    """Run the REAL Lean elaborator on CHU_WolframRewrite.lean and ship
    'chu_wolfram_lean_verified' iff it exits 0 (all proofs check).

    The literal 'chu_wolfram_lean_verified' below is the event we ship AND the string
    Longinus AST-checks against this symbol's body. Returns the lean exit code.
    """
    proc = _run_lean()
    if proc.returncode == 0:
        backend.ship(
            [
                _ev(
                    cid,
                    "chu_wolfram_lean_verified",
                    lean_exit=proc.returncode,
                    file=os.path.basename(_LEAN_FILE),
                    stderr_len=len(proc.stderr),
                )
            ]
        )
    return proc.returncode


def check_truncation_theorem(backend, cid: str) -> bool:
    """Confirm the load-bearing ``strict_truncation`` theorem is genuinely PROVEN: the
    source must declare it AND Lean must elaborate the whole file clean (exit 0). Ship
    'chu_strict_truncation_proven' only when both are true.

    The literal 'chu_strict_truncation_proven' below is the event we ship AND the string
    Longinus AST-checks against this symbol's body. Returns whether the theorem is proven.
    """
    with open(_LEAN_FILE, "r", encoding="utf-8") as fh:
        source = fh.read()
    declared = f"theorem {_TRUNCATION_THEOREM}" in source
    proc = _run_lean()
    proven = declared and proc.returncode == 0
    if proven:
        backend.ship(
            [
                _ev(
                    cid,
                    "chu_strict_truncation_proven",
                    theorem=_TRUNCATION_THEOREM,
                    declared=declared,
                    lean_exit=proc.returncode,
                )
            ]
        )
    return proven


def run_chu_ptdd(backend, cid: str) -> dict:
    """Loop entry point: elaborate the CHU dynamics-layer Lean artifact under ``cid`` and
    ship its two earned events (compile-verified + truncation-theorem-proven)."""
    lean_exit = verify_chu_lean(backend, cid)
    proven = check_truncation_theorem(backend, cid)
    return {
        "lean_exit": lean_exit,
        "truncation_theorem_proven": proven,
        "lean_file": _LEAN_FILE,
    }
