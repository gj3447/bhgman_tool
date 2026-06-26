"""ooptdd-loop in_process target — binds hades 실현(realize) to the REAL on-disk gated-apply
engine (``engine.hades.apply_extract_superclass_gated``), closing the legion DAG.

This binds ONE coherent call graph — the on-disk Extract-Superclass refactor behind a
characterization-test gate — NOT the infra-0 KG materialize path (``realize_kg_abstraction``
with ``apply_cypher=None`` is structurally 0 on local infra, so it could never earn APPLIED).

Honest-count contract (verified, STEP-0 baseline):
    - hades_extracted (==1): ``len(common_methods)`` — nonzero only when a real class family
      shares >=1 structurally-identical method (Dog/Cat both ``speak`` -> 'woof' lifts 1). A
      divergent family ('woof' vs 'meow') or a one-class family lifts nothing => 0 => RED.
    - hades_gate_applied (==1, where status:APPLIED): shipped ONLY when
      ``apply_extract_superclass_gated`` returns status APPLIED — the file was rewritten AND a
      real characterization ``test_cmd`` exited 0. A failing test_cmd => REVERTED (file restored
      BYTE-FOR-BYTE), nothing to lift => REFUSED — both ship nothing => RED. APPLIED is backed
      by a genuinely-passing subprocess, never the write alone.

Longinus binding (AST-checked): each must_emit literal lives VERBATIM in its ADAPTER symbol
    (``emit_extract_phase`` / ``emit_gated_apply_phase`` / ``run_hades_pipeline``), NEVER inside
    ``engine/hades/``. Rename => UNBOUND/RED.

# KG: finding-ooptdd-bhgman-hades-adapter-20260625
# KG: hades-canonical-2026-05-27
"""
from __future__ import annotations

import ast
import sys
import tempfile
from pathlib import Path

from engine.hades.extract_superclass import common_methods
from engine.hades.hades_apply import apply_extract_superclass_gated

_KG_ANCHOR = "finding-ooptdd-bhgman-hades-adapter-20260625"
_BASE = "AnimalBase"

# A real class family: Dog and Cat share a STRUCTURALLY-IDENTICAL speak() => 1 liftable method.
_FAMILY_SRC = (
    "import os\n\n"
    "class Dog:\n    def speak(self):\n        return 'woof'\n    def legs(self):\n        return 4\n\n"
    "class Cat:\n    def speak(self):\n        return 'woof'\n    def meow(self):\n        return 'm'\n"
)
# A divergent family: Cat.speak returns 'meow' => no structurally-identical method => nothing lifts.
_DIVERGENT_SRC = _FAMILY_SRC.replace(
    "    def speak(self):\n        return 'woof'\n    def meow",
    "    def speak(self):\n        return 'meow'\n    def meow",
)
_CLASS_NAMES = ["Dog", "Cat"]


def _ev(cid: str, event: str, **attrs) -> dict:
    """Shape one trace event the way the memory backend keys + counts it (cid + event)."""
    return {
        "cid": cid,
        "correlation_id": cid,
        "cycle_id": cid,
        "service": "bhgman.hades",
        "event": event,
        **attrs,
    }


def _make_family_file(*, divergent: bool) -> tuple[Path, Path]:
    """Write the class-family module to a fresh tmp dir. Returns (tmpdir, mod_path)."""
    d = Path(tempfile.mkdtemp(prefix="hades_realize_"))
    f = d / "mod.py"
    f.write_text(_DIVERGENT_SRC if divergent else _FAMILY_SRC, encoding="utf-8")
    return d, f


def _passing_test_cmd(tmpdir: Path) -> list[str]:
    """A real characterization test: import the (rewritten) module and assert behavior is
    preserved AND the lifted base exists. Exits 0 only if the refactor is sound."""
    return [
        sys.executable, "-c",
        f"import sys; sys.path.insert(0, {str(tmpdir)!r}); import mod; "
        "assert mod.Dog().speak() == 'woof'; assert mod.AnimalBase",
    ]


def _common_methods(src: str) -> list[str]:
    """The structurally-identical methods shared across the family (the real ast LGG)."""
    cds = [
        n for n in ast.parse(src).body
        if isinstance(n, ast.ClassDef) and n.name in set(_CLASS_NAMES)
    ]
    return common_methods(cds) if len(cds) >= 2 else []


def emit_extract_phase(backend, cid: str, src: str) -> int:
    """Ship one 'hades_extracted' per structurally-identical method liftable into the base.
    Count == len(common_methods) RE-DERIVED from the real ast LGG (divergent => 0 => RED). The
    literal lives here."""
    methods = _common_methods(src)
    for name in methods:
        backend.ship([_ev(cid, "hades_extracted", method=name, base=_BASE)])
    return len(methods)


def emit_gated_apply_phase(backend, cid: str, file_path: Path, test_cmd: list[str]) -> int:
    """Run the REAL gated apply and ship 'hades_gate_applied' ONLY when status is APPLIED — the
    file was rewritten AND a real characterization test_cmd exited 0. REVERTED (test failed,
    file restored byte-for-byte) and REFUSED (nothing to lift) ship nothing. The literal lives
    here."""
    result = apply_extract_superclass_gated(file_path, _BASE, _CLASS_NAMES, test_cmd=test_cmd)
    if result.status == "APPLIED":
        backend.ship([
            _ev(cid, "hades_gate_applied", status="APPLIED", base=_BASE,
                rc=result.test_returncode)
        ])
        return 1
    return 0  # REVERTED / REFUSED — no realization landed


def run_hades_pipeline(backend, cid: str, *, divergent: bool = False,
                       fail_test: bool = False) -> dict:
    """Loop entry (called as ``run_hades_pipeline(backend, cid)``). Runs the REAL on-disk
    Extract-Superclass realize over a seeded class family and ships the lifecycle under ``cid``.
    The 'hades_realize_started' and 'hades_realize_complete' literals live verbatim in THIS
    symbol. ``divergent``/``fail_test`` default to the green path; the twin test overrides them
    for the no-common-method and reverted-gate RED proofs.

    Extract is computed from the ORIGINAL source BEFORE the gated apply rewrites the file."""
    tmpdir, path = _make_family_file(divergent=divergent)
    original_src = path.read_text(encoding="utf-8")
    test_cmd = (
        [sys.executable, "-c", "import sys; sys.exit(1)"] if fail_test
        else _passing_test_cmd(tmpdir)
    )

    backend.ship([_ev(cid, "hades_realize_started", phase="extract")])
    n_extracted = emit_extract_phase(backend, cid, original_src)
    n_applied = emit_gated_apply_phase(backend, cid, path, test_cmd)
    backend.ship([
        _ev(cid, "hades_realize_complete", extracted=n_extracted, applied=n_applied)
    ])
    return {"extracted": n_extracted, "applied": n_applied}


__all__ = ["emit_extract_phase", "emit_gated_apply_phase", "run_hades_pipeline"]
