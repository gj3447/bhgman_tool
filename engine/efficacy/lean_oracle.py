"""Ungameable Lean oracle for the 거기 (headroom) composition test.

The task fixes the THEOREM STATEMENT; the model supplies ONLY the proof term/tactic block. So
statement-fidelity and no-weakening are enforced BY CONSTRUCTION — the model cannot rename or weaken
`theorem T <sig> := <proof>` because we own `T` and `<sig>`. The hidden eval is therefore ungameable:

  proven  ⇔  assemble(sig + proof) compiles with no `error:`  AND  `#print axioms T` shows no `sorryAx`.

A `sorry` compiles (warning only) but taints axioms → caught. A wrong proof fails to compile → caught.
A weakened/renamed statement is impossible → the model never sees the `theorem ... :=` line.

`public` (the repair signal the loop MAY see) = compiles-clean + the lean error text (for oracle-guided
repair). Standalone Mathlib-free (matches the W4 corpus; `lean` resolves core only).

# KG: project-apt-ultracode-roadmap-2026-06-02 (거기/headroom faithful test), lean_axiom_probe (W4)
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

_ERROR_RE = re.compile(r"\berror:", re.IGNORECASE)


@dataclass(frozen=True)
class LeanVerdict:
    compiles: bool  # no `error:` (the public/repair signal)
    proven: bool  # compiles AND no sorryAx — the ungameable hidden eval
    sorry_tainted: bool
    error_tail: str  # last lean output (for oracle-guided repair feedback)

    @property
    def public_score(self) -> float:
        return 1.0 if self.compiles else 0.0

    @property
    def graded_score(self) -> float:
        """3-level partial-progress fitness: 0 = no compile, 0.5 = compiles but sorry-tainted
        (incomplete), 1.0 = proven (compiles + no sorryAx). Gives read-back/repair a gradient
        that the binary `proven` hides."""
        if self.proven:
            return 1.0
        if self.compiles:
            return 0.5
        return 0.0


def lean_available() -> bool:
    return shutil.which("lean") is not None


def _run_lean(src: str, timeout: int) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    try:
        proc = subprocess.run(
            ["lean", path], capture_output=True, text=True, timeout=timeout, check=False
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return 1, f"lean run failed: {exc}"
    finally:
        Path(path).unlink(missing_ok=True)


def evaluate(
    name: str, signature: str, proof: str, *, preamble: str = "", timeout: int = 60
) -> LeanVerdict:
    """Assemble preamble(defs) + the FIXED statement + model proof, compile, check genuine provenness."""
    head = f"{preamble}\n" if preamble else ""
    src = f"{head}theorem {name} {signature} := {proof}\n#print axioms {name}\n"
    rc, out = _run_lean(src, timeout)
    has_error = rc != 0 or bool(_ERROR_RE.search(out))
    compiles = not has_error
    sorry_tainted = "sorryAx" in out
    return LeanVerdict(
        compiles=compiles,
        proven=compiles and not sorry_tainted,
        sorry_tainted=sorry_tainted,
        error_tail=out[-700:],
    )


__all__ = ["LeanVerdict", "evaluate", "lean_available"]
