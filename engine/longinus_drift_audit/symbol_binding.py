"""Longinus forward binding at *symbol* granularity (L5-L7).

The drift audit found concept↔code binding lives only at module-docstring
granularity: 0/2656 functions/classes carry a `# KG:` ref inside their *header
span* (the lines the scanner attributes to a symbol). So a file may declare a
concept, but no individual `def`/`class` is traceable to it — the "float" lesson
(`lesson-concept-nodes-created-without-longinus-binding-float-2026-05-29`) at code
granularity.

This module distributes a file's *already-declared* module concept down onto its
public symbols, inserting `# KG: <concept>` in each symbol's header span so the
scanner attributes it. Covenant (drift-safe):

  • NEVER invents a concept — only binds one already present at module level in
    the same file (or one the caller explicitly passes after verifying it).
  • Idempotent — a symbol already carrying any `# KG:` in its header is skipped.
  • AST-anchored — insertion point is just before the symbol's first body
    statement, so it lands inside the header span the scanner reads; multi-line
    signatures handled. SyntaxError → file left untouched (never corrupts).
  • Public-only by default — dunder / single-underscore privates are skipped
    (binding every helper is noise, not traceability).

# KG: ATOM_Skill_longinus, lesson-concept-nodes-created-without-longinus-binding-float-2026-05-29,
#     project-legion-unification-kg-engine-2026-06-01
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

_KG_REF = re.compile(r"(?<!`)#\s*KG:\s*(.+)")
_KG_NAME = re.compile(r"^[\w][\w\-./]*$")


def module_concepts(content: str) -> list[str]:
    # KG: ATOM_Skill_longinus
    """`# KG:` concepts declared *outside* any top-level def/class body — i.e. the
    module-docstring / header anchors that describe the file as a whole."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    body_ranges = [
        (n.lineno, n.end_lineno or n.lineno)
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]

    def inside_symbol(ln: int) -> bool:
        return any(a < ln <= b for a, b in body_ranges)  # a< : the def line itself = header

    out: list[str] = []
    for i, line in enumerate(content.splitlines(), start=1):
        if inside_symbol(i):
            continue
        m = _KG_REF.search(line)
        if not m:
            continue
        for part in m.group(1).split(","):
            name = re.sub(r"\s*\(.*$", "", part).strip()
            if _KG_NAME.match(name) and name not in out:
                out.append(name)
    return out


def _header_has_kg(node: ast.AST, lines: list[str]) -> bool:
    start = node.lineno
    decos = getattr(node, "decorator_list", []) or []
    if decos:
        start = min(start, min(d.lineno for d in decos))
    body = getattr(node, "body", None)
    end = (body[0].lineno - 1) if body else node.lineno
    return any(_KG_REF.search(lines[ln - 1]) for ln in range(start, max(start, end) + 1))


def _is_public(name: str) -> bool:
    return not name.startswith("_")


@dataclass(frozen=True)
class BindPlan:
    # KG: ATOM_Skill_longinus
    """One pending insertion: a `# KG:` line for ``symbol`` at 0-based ``index``."""

    symbol: str
    index: int  # insert BEFORE this source-line index (0-based)
    text: str


@dataclass(frozen=True)
class BindResult:
    # KG: ATOM_Skill_longinus
    path: str
    concept: str
    bound: tuple[str, ...]
    skipped_existing: tuple[str, ...]
    dry_run: bool

    @property
    def summary(self) -> str:
        mode = "DRY-RUN" if self.dry_run else "WROTE"
        return (
            f"longinus[symbol-bind] {self.path}: {mode} {len(self.bound)} bound, "
            f"{len(self.skipped_existing)} already-bound (concept={self.concept})"
        )


def plan_file(
    content: str, concept: str, *, only: Iterable[str] | None = None, public_only: bool = True
) -> tuple[list[BindPlan], list[str]]:
    # KG: ATOM_Skill_longinus
    """Compute insertions binding ``concept`` to each eligible top-level symbol.

    Returns (plans, already_bound). ``only`` restricts to named symbols (e.g. a
    file's ``__all__``); None = every top-level def/class.
    """
    if not _KG_NAME.match(concept):
        raise ValueError(f"refusing non-identifier concept {concept!r}")
    tree = ast.parse(content)  # caller guards SyntaxError
    lines = content.splitlines()
    allow = set(only) if only is not None else None

    plans: list[BindPlan] = []
    already: list[str] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        name = node.name
        if allow is not None and name not in allow:
            continue
        if public_only and not _is_public(name):
            continue
        if _header_has_kg(node, lines):
            already.append(name)
            continue
        first = node.body[0]
        indent = " " * (first.col_offset)
        plans.append(BindPlan(symbol=name, index=first.lineno - 1, text=f"{indent}# KG: {concept}"))
    return plans, already


def apply_plans(content: str, plans: list[BindPlan]) -> str:
    # KG: ATOM_Skill_longinus
    """Insert all planned lines. Applied bottom-up so earlier indices stay valid."""
    lines = content.splitlines(keepends=True)
    nl = "\n"
    if lines and not lines[-1].endswith("\n"):
        lines[-1] = lines[-1] + nl  # normalise so inserts are clean
    for plan in sorted(plans, key=lambda p: -p.index):
        lines.insert(plan.index, plan.text + nl)
    return "".join(lines)


def bind_file(
    path: Path,
    concept: str | None = None,
    *,
    only: Iterable[str] | None = None,
    public_only: bool = True,
    apply: bool = False,
) -> BindResult:
    # KG: ATOM_Skill_longinus
    """Bind ``concept`` (default: the file's first module-level concept) to its
    public top-level symbols. PROPOSE by default; writes only when ``apply``."""
    content = path.read_text()
    try:
        ast.parse(content)
    except SyntaxError:
        return BindResult(str(path), concept or "", (), (), dry_run=not apply)

    if concept is None:
        mods = module_concepts(content)
        if not mods:
            return BindResult(str(path), "", (), (), dry_run=not apply)  # nothing to distribute
        concept = mods[0]

    plans, already = plan_file(content, concept, only=only, public_only=public_only)
    if apply and plans:
        path.write_text(apply_plans(content, plans))
    return BindResult(
        path=str(path),
        concept=concept,
        bound=tuple(p.symbol for p in plans),
        skipped_existing=tuple(already),
        dry_run=not apply,
    )


__all__ = [
    "BindPlan",
    "BindResult",
    "module_concepts",
    "plan_file",
    "apply_plans",
    "bind_file",
]
