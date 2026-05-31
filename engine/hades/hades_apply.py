"""Hades real apply — Extract-Superclass with a characterization-test gate.

The CLI/engine paths keep refactors dry-run by covenant; this is the *gated*
apply the covenant defers to ("apply = characterization test gate 후"). It is
deliberately **scoped**: the caller supplies the exact test command, so this is
a self-refactor tool for a repo whose tests you trust (e.g. bhgman_tool itself
via pytest), not a generic auto-refactor of arbitrary code.

Safety (hades c6 = "most dangerous"): write → run the test command → keep iff
it passes, else restore the original file byte-for-byte. Reversibility-first —
a failing gate leaves the tree exactly as it was.

Requires libcst ([hades-cst]). Same-file candidates only (the base class is
inserted before the first lifted class in that file).

# KG: hades-canonical-2026-05-27 (실현=추상→구체, c6 materialize danger)
"""

from __future__ import annotations

import ast
import subprocess
from dataclasses import dataclass
from pathlib import Path

from engine.hades.extract_superclass import common_methods


@dataclass(frozen=True)
class GatedApplyResult:
    status: str  # "APPLIED" | "REVERTED" | "REFUSED"
    reason: str
    test_returncode: int | None = None


def _lifted_method_names(src: str, class_names: set[str]) -> list[str]:
    tree = ast.parse(src)
    cds = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in class_names]
    if len(cds) < 2:
        return []
    return common_methods(cds)


def apply_extract_superclass_to_module(
    src: str, base_name: str, class_names: list[str]
) -> str | None:
    """Rewrite a module: insert a shared base class + make each named class inherit
    it and drop the lifted methods. Returns new source, or None if nothing to lift.

    Format-preserving (libcst). Same-file classes only.
    """
    import libcst as cst  # noqa: PLC0415

    nameset = set(class_names)
    methods = _lifted_method_names(src, nameset)
    if not methods:
        return None
    mset = set(methods)

    class _Rewrite(cst.CSTTransformer):
        def leave_ClassDef(self, original: object, updated):  # noqa: ANN001,N802
            if updated.name.value not in nameset:
                return updated
            kept = [
                s
                for s in updated.body.body
                if not (isinstance(s, cst.FunctionDef) and s.name.value in mset)
            ]
            if not kept:
                kept = [cst.SimpleStatementLine([cst.Pass()])]
            return updated.with_changes(
                body=updated.body.with_changes(body=kept),
                bases=[*updated.bases, cst.Arg(value=cst.Name(base_name))],
            )

    module = cst.parse_module(src)
    first = next(s for s in module.body if isinstance(s, cst.ClassDef) and s.name.value in nameset)
    lifted = [s for s in first.body.body if isinstance(s, cst.FunctionDef) and s.name.value in mset]
    base = cst.ClassDef(
        name=cst.Name(base_name),
        body=cst.IndentedBlock(body=lifted),
        leading_lines=[cst.EmptyLine()],
    )
    rewritten = module.visit(_Rewrite())
    body = list(rewritten.body)
    idx = next(
        i for i, s in enumerate(body) if isinstance(s, cst.ClassDef) and s.name.value in nameset
    )
    body.insert(idx, base)
    return rewritten.with_changes(body=body).code


def apply_extract_superclass_gated(
    file_path: Path,
    base_name: str,
    class_names: list[str],
    *,
    test_cmd: list[str],
    cwd: str | Path | None = None,
) -> GatedApplyResult:
    """Apply the refactor to ``file_path`` only if ``test_cmd`` still passes.

    APPLIED  → gate passed, file rewritten.
    REVERTED → gate failed, original file restored byte-for-byte (reversible).
    REFUSED  → nothing to lift (file untouched).
    """
    original = file_path.read_text(encoding="utf-8")
    new = apply_extract_superclass_to_module(original, base_name, class_names)
    if new is None:
        return GatedApplyResult("REFUSED", "no structurally-identical common method to lift")
    file_path.write_text(new, encoding="utf-8")
    rc = subprocess.run(  # noqa: S603 - caller-supplied fixed argv, no shell
        test_cmd, cwd=cwd, capture_output=True
    ).returncode
    if rc == 0:
        return GatedApplyResult("APPLIED", f"characterization gate passed — {base_name} lifted", rc)
    file_path.write_text(original, encoding="utf-8")  # covenant: reversible
    return GatedApplyResult("REVERTED", f"characterization gate FAILED (exit {rc}) — reverted", rc)


__all__ = [
    "GatedApplyResult",
    "apply_extract_superclass_gated",
    "apply_extract_superclass_to_module",
]
