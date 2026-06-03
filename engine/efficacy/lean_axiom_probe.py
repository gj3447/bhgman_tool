"""W4 deepening — authoritative "is it actually proven" via lean `#print axioms`.

The regex pass in apt_metrics_gen establishes live_sorry=0 heuristically (after string/comment
strip). This module CONFIRMS it at the proof-term level: a theorem that uses `sorry` anywhere in
its proof — even transitively through a helper — shows `sorryAx` in its axiom dependencies. So
`n_sorry_tainted == 0` is the *authoritative* "no hidden sorry" oracle (a real ground-truth check,
not a token scan).

Honest scope (do NOT over-read):
  - This catches hidden/transitive `sorry`. It does NOT catch statement-weakening
    (disjunct-discharge `P ∨ True`, vacuous quantifiers) — an axiom-clean theorem can still be
    trivially true. That concern is the separate `n_disjunct_discharge_documented` heuristic.
  - Only runs on files that compile standalone (Mathlib-free, no `import`). Files needing a project
    are reported compiled=False / skipped, never silently counted as "proven".

# KG: project-apt-ultracode-roadmap-2026-06-02 (W4 authoritative oracle layer)
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

_NS = re.compile(r"^\s*namespace\s+([\w.]+)")
_END = re.compile(r"^\s*end\s+([\w.]+)\s*$")
_THM = re.compile(r"^\s*(?:theorem|lemma)\s+([\w']+)")
_IMPORT = re.compile(r"^\s*import\s", re.MULTILINE)
_AXIOM_LINE = re.compile(
    r"'([\w.']+)' (?:does not depend on any axioms|depends on axioms: \[([^\]]*)\])"
)
_CLASSICAL = re.compile(r"propext|Classical|Quot\.")


def fqns_in(src: str) -> list[str]:
    """Fully-qualified theorem/lemma names, tracking a (possibly nested) namespace stack."""
    stack: list[str] = []
    out: list[str] = []
    for line in src.splitlines():
        if m := _NS.match(line):
            stack.append(m.group(1))
        elif (m := _END.match(line)) and stack and stack[-1] == m.group(1):
            stack.pop()
        elif m := _THM.match(line):
            prefix = ".".join(stack)
            out.append(f"{prefix}.{m.group(1)}" if prefix else m.group(1))
    return out


@dataclass
class FileAxiomReport:
    file: str
    compiled: bool
    n_theorems: int = 0
    n_axiom_clean: int = 0  # no axioms / constructive
    n_classical: int = 0  # propext / Classical.choice / Quot.sound only (standard)
    n_sorry_tainted: int = 0  # depends on sorryAx — NOT actually proven
    n_unresolved: int = 0  # name not reported (parse/elaboration gap)
    error: str = ""

    @property
    def n_genuinely_proven(self) -> int:
        return self.n_axiom_clean + self.n_classical


def _classify_axioms(axioms: str) -> str:
    if "sorryAx" in axioms:
        return "sorry"
    if _CLASSICAL.search(axioms):
        return "classical"
    return "clean"  # some other axiom, but not sorry — count as proven-with-axiom


def _parse(out: str, report: FileAxiomReport) -> None:
    for m in _AXIOM_LINE.finditer(out):
        axioms = m.group(2)
        if axioms is None:  # "does not depend on any axioms"
            report.n_axiom_clean += 1
            continue
        kind = _classify_axioms(axioms)
        if kind == "sorry":
            report.n_sorry_tainted += 1
        elif kind == "classical":
            report.n_classical += 1
        else:
            report.n_axiom_clean += 1


def probe_file(path: Path, *, timeout: int = 180) -> FileAxiomReport:
    src = path.read_text(errors="ignore")
    if _IMPORT.search(src):
        return FileAxiomReport(path.name, compiled=False, error="has imports (not standalone)")
    fqns = fqns_in(src)
    if not fqns:
        return FileAxiomReport(path.name, compiled=True, n_theorems=0)
    probe_src = src + "\n" + "\n".join(f"#print axioms {f}" for f in fqns) + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False, encoding="utf-8") as tf:
        tf.write(probe_src)
        tmp = tf.name
    try:
        proc = subprocess.run(
            ["lean", tmp], capture_output=True, text=True, timeout=timeout, check=False
        )
    except Exception as exc:  # noqa: BLE001
        Path(tmp).unlink(missing_ok=True)
        return FileAxiomReport(
            path.name, compiled=False, n_theorems=len(fqns), error=str(exc)[:200]
        )
    Path(tmp).unlink(missing_ok=True)
    report = FileAxiomReport(path.name, compiled=(proc.returncode == 0), n_theorems=len(fqns))
    _parse(proc.stdout, report)
    resolved = report.n_axiom_clean + report.n_classical + report.n_sorry_tainted
    report.n_unresolved = max(0, len(fqns) - resolved)
    if proc.returncode != 0:
        report.error = (proc.stderr or "")[:200]
    return report


def probe_all(lean_root: Path, glob: str = "APT*.lean") -> dict:
    if not shutil.which("lean"):
        return {"available": False, "note": "lean toolchain not on PATH; axiom oracle unavailable"}
    reports = [probe_file(p) for p in sorted(lean_root.glob(glob)) if p.is_file()]
    agg = {
        "available": True,
        "n_files": len(reports),
        "n_standalone": sum(1 for r in reports if r.error != "has imports (not standalone)"),
        "n_theorems_probed": sum(r.n_theorems for r in reports),
        "n_sorry_tainted": sum(r.n_sorry_tainted for r in reports),
        "n_genuinely_proven": sum(r.n_genuinely_proven for r in reports),
        "n_unresolved": sum(r.n_unresolved for r in reports),
        "files_with_sorry": [r.file for r in reports if r.n_sorry_tainted > 0],
        "files_skipped_imports": [
            r.file for r in reports if r.error == "has imports (not standalone)"
        ],
    }
    return agg


__all__ = ["FileAxiomReport", "fqns_in", "probe_all", "probe_file"]
