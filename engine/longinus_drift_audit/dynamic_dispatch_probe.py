"""Hybrid static+runtime dynamic dispatch probe (Longinus v3.3, 2026-05-19).

Closes STATUS.md §6.2 known limitation: "Static-analysis only: Dynamic dispatch
(`getattr`, reflection, eval) misses references." This module supplements
``code_scanner.py`` by detecting *runtime-resolved* symbol references that pure
top-level def/class AST extraction cannot capture.

Two-pass design:

  1. **Static AST scan** (``scan_static`` / ``scan_root_static``): walk file AST
     for 5 canonical dynamic dispatch idioms (see CORPUS below). Each detection
     is emitted as a ``DynamicDispatchSite`` with conservative
     ``models.Confidence`` (INFERRED when target is a literal string we can
     resolve at scan time, AMBIGUOUS when target is computed).

  2. **Runtime trace merge** (``merge_with_runtime_trace``): accept an iterable
     of trace dicts produced by an external instrumentation hook (e.g.
     ``sys.settrace`` callback or Python 3.12+ ``sys.monitoring``). Each trace
     dict carries ``{file_path, line, resolved_target}``; matching sites are
     upgraded to EXTRACTED.

CORPUS (5 static idioms covered):

  - ``getattr(obj, name)`` / ``setattr`` / ``hasattr``
      → AMBIGUOUS when ``name`` is a ``Name`` node (computed)
      → INFERRED when ``name`` is a ``Constant(str)`` (literal target)
  - ``eval(code)`` / ``exec(code)`` / ``compile(...)``
      → always AMBIGUOUS (arbitrary code)
  - ``__import__(name)``
      → AMBIGUOUS (legacy reflective import; bypasses ``import`` statement)
  - ``importlib.import_module(name)``
      → INFERRED when ``name`` is literal, AMBIGUOUS otherwise
  - ``globals()[name]`` / ``locals()[name]`` / ``vars()[name]``
      → AMBIGUOUS subscript-on-namespace-call

HONEST DISCLAIMERS (also in DecisionLog):

  - **Static scan covers 5 common idioms only.** Does NOT cover:
      * ``getattr(obj, "prefix_" + key)`` — computed-string concatenation
      * ``__getattr__`` / ``__getattribute__`` metaclass overrides
      * Descriptor protocol indirection (``__get__`` / ``__set__``)
      * C-extension reflection (e.g. ``ctypes``, Cython ``cdef``)
      * ``pickle.loads`` / ``marshal.loads`` arbitrary deserialization
      * AST-rewriting decorators / runtime monkey-patching
    For full coverage, layer on top of a runtime trace from production.

  - **Runtime trace integration is interface-only.** This module accepts a
    generic iterable of trace dicts; the actual ``sys.settrace`` /
    ``sys.monitoring`` instrumentation hook is NOT included here (production
    deployment provides it). Stub example:

        # Production-side hook (NOT in this module):
        # import sys
        # trace_records: list[dict] = []
        # def tracer(frame, event, arg):
        #     if event == "call":
        #         trace_records.append({
        #             "file_path": frame.f_code.co_filename,
        #             "line": frame.f_lineno,
        #             "resolved_target": frame.f_code.co_qualname,
        #         })
        #     return tracer
        # sys.settrace(tracer)
        # ... run target code ...
        # sys.settrace(None)
        # merge_with_runtime_trace(static_sites, trace_records)

  - **Confidence default is conservative.** Even when ``getattr`` target is a
    literal string resolvable at scan time, we mark INFERRED (not EXTRACTED)
    because the evaluation environment may differ at runtime (e.g. monkey-
    patched class, dynamic subclass). EXTRACTED is reserved for runtime-
    confirmed sites only.

  - **Performance.** AST per-file is O(N) over node count. For huge codebases,
    integrate ``scan_root_static`` with the ProcessPool pattern in
    ``code_scanner.scan_root(parallel=True)``. Empirical break-even ~5000
    files (lesson-longinus-parallel-breakeven-2026-05-18).

# KG: sa-longinus-dynamic-dispatch-probe-2026-05-19,
#     CONTRACT_DynamicDispatchProbe_v1_2026-05-19,
#     wqi-longinus-dynamic-dispatch-probe-v3.3-2026-05-19,
#     decision-longinus-dynamic-dispatch-probe-shipped-2026-05-19
"""

from __future__ import annotations

import ast
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Iterable, Optional

from pydantic import BaseModel, Field, field_validator

from models import Confidence


# ─── Pydantic v2 schemas ──────────────────────────────────────────────────


_VALID_KINDS = {
    "getattr",
    "setattr",
    "hasattr",
    "eval",
    "exec",
    "compile",
    "__import__",
    "importlib.import_module",
    "globals_subscript",
    "locals_subscript",
    "vars_subscript",
}


class DynamicDispatchSite(BaseModel):
    """Single dynamic dispatch site detected by static scan.

    Confidence semantics (reuses ``models.Confidence`` 3-tier enum):
      - EXTRACTED: runtime trace confirmed actual target (merge upgrade only)
      - INFERRED: static scan resolved literal target, but runtime may differ
      - AMBIGUOUS: target is computed at runtime, manual review required
    """

    file_path: str
    line: int = Field(ge=1)
    dispatch_kind: str
    target_expr: str = Field(description="Source expression for the target argument.")
    resolved_target: Optional[str] = Field(
        default=None,
        description="Resolved symbol name when literal/runtime-known, else None.",
    )
    confidence: Confidence = Confidence.AMBIGUOUS

    @field_validator("dispatch_kind")
    @classmethod
    def _check_kind(cls, v: str) -> str:
        if v not in _VALID_KINDS:
            raise ValueError(f"dispatch_kind must be one of {_VALID_KINDS}, got {v!r}")
        return v


class DynamicDispatchReport(BaseModel):
    """Aggregate summary of a dynamic dispatch scan."""

    total_sites: int = Field(ge=0)
    extracted_count: int = Field(ge=0)
    inferred_count: int = Field(ge=0)
    ambiguous_count: int = Field(ge=0)
    by_kind: dict[str, int] = Field(default_factory=dict)
    sites: list[DynamicDispatchSite] = Field(default_factory=list)


# ─── Static AST scan ──────────────────────────────────────────────────────


def _expr_source(node: ast.AST, source_lines: list[str]) -> str:
    """Best-effort source text for an AST node (3.8+ unparse fallback)."""
    try:
        return ast.unparse(node)
    except Exception:
        # Fallback: source line range
        if hasattr(node, "lineno"):
            return source_lines[node.lineno - 1].strip()
        return "<unparseable>"


def _is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _is_attr(node: ast.AST, module: str, attr: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == module
        and node.attr == attr
    )


def _literal_str(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


_REFLECTION_BUILTINS = ("getattr", "setattr", "hasattr")
_EVAL_FAMILY_BUILTINS = ("eval", "exec", "compile")


def _try_reflection_builtin(
    node: ast.Call,
    source_lines: list[str],
    file_path: str,
) -> Optional[DynamicDispatchSite]:
    for builtin in _REFLECTION_BUILTINS:
        if not _is_name(node.func, builtin):
            continue
        if len(node.args) < 2:
            return None
        name_arg = node.args[1]
        literal = _literal_str(name_arg)
        return DynamicDispatchSite(
            file_path=file_path,
            line=node.lineno,
            dispatch_kind=builtin,
            target_expr=_expr_source(name_arg, source_lines),
            resolved_target=literal,
            confidence=Confidence.INFERRED if literal else Confidence.AMBIGUOUS,
        )
    return None


def _try_eval_family(
    node: ast.Call,
    source_lines: list[str],
    file_path: str,
) -> Optional[DynamicDispatchSite]:
    for builtin in _EVAL_FAMILY_BUILTINS:
        if not _is_name(node.func, builtin):
            continue
        if not node.args:
            return None
        return DynamicDispatchSite(
            file_path=file_path,
            line=node.lineno,
            dispatch_kind=builtin,
            target_expr=_expr_source(node.args[0], source_lines),
            resolved_target=None,
            confidence=Confidence.AMBIGUOUS,
        )
    return None


def _try_dunder_import(
    node: ast.Call,
    source_lines: list[str],
    file_path: str,
) -> Optional[DynamicDispatchSite]:
    if not _is_name(node.func, "__import__") or not node.args:
        return None
    return DynamicDispatchSite(
        file_path=file_path,
        line=node.lineno,
        dispatch_kind="__import__",
        target_expr=_expr_source(node.args[0], source_lines),
        resolved_target=_literal_str(node.args[0]),
        confidence=Confidence.AMBIGUOUS,
    )


def _try_importlib_import_module(
    node: ast.Call,
    source_lines: list[str],
    file_path: str,
) -> Optional[DynamicDispatchSite]:
    if not _is_attr(node.func, "importlib", "import_module") or not node.args:
        return None
    name_arg = node.args[0]
    literal = _literal_str(name_arg)
    return DynamicDispatchSite(
        file_path=file_path,
        line=node.lineno,
        dispatch_kind="importlib.import_module",
        target_expr=_expr_source(name_arg, source_lines),
        resolved_target=literal,
        confidence=Confidence.INFERRED if literal else Confidence.AMBIGUOUS,
    )


def _scan_call(
    node: ast.Call, source_lines: list[str], file_path: str
) -> Optional[DynamicDispatchSite]:
    """Classify a Call node against the 5-idiom corpus."""
    classifiers = (
        _try_reflection_builtin,
        _try_eval_family,
        _try_dunder_import,
        _try_importlib_import_module,
    )
    for classifier in classifiers:
        result = classifier(node, source_lines, file_path)
        if result is not None:
            return result
    return None


def _scan_subscript(
    node: ast.Subscript, source_lines: list[str], file_path: str
) -> Optional[DynamicDispatchSite]:
    """Detect ``globals()[name]`` / ``locals()[name]`` / ``vars()[name]``."""
    val = node.value
    if not isinstance(val, ast.Call):
        return None
    func = val.func
    for ns in ("globals", "locals", "vars"):
        if _is_name(func, ns):
            slice_node = node.slice
            literal = _literal_str(slice_node)
            return DynamicDispatchSite(
                file_path=file_path,
                line=node.lineno,
                dispatch_kind=f"{ns}_subscript",
                target_expr=_expr_source(slice_node, source_lines),
                resolved_target=literal,
                confidence=Confidence.AMBIGUOUS,
            )
    return None


def scan_static(file_path: str) -> list[DynamicDispatchSite]:
    """Scan a single Python file for dynamic dispatch idioms via AST.

    Returns a list of DynamicDispatchSite. On parse error or read failure,
    returns an empty list (conservative: report nothing rather than crash).
    """
    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return []

    source_lines = source.splitlines()
    sites: list[DynamicDispatchSite] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            site = _scan_call(node, source_lines, file_path)
            if site is not None:
                sites.append(site)
        elif isinstance(node, ast.Subscript):
            site = _scan_subscript(node, source_lines, file_path)
            if site is not None:
                sites.append(site)

    return sites


_DEFAULT_PARALLEL_THRESHOLD = int(os.environ.get("LONGINUS_PARALLEL_FILE_THRESHOLD", "5000"))


def _iter_py_files(root: Path) -> Iterable[Path]:
    skip_parts = {".pytest_cache", "__pycache__", ".lake", ".venv", "node_modules"}
    for p in root.rglob("*.py"):
        if any(part in skip_parts for part in p.parts):
            continue
        if p.is_file():
            yield p


def scan_root_static(root_path: str, parallel: bool = False) -> list[DynamicDispatchSite]:
    """Walk ``root_path`` for .py files and aggregate static scan results.

    Args:
        root_path: directory to recurse.
        parallel: if True, use ProcessPoolExecutor (recommended only for >5000
            files per ``lesson-longinus-parallel-breakeven-2026-05-18``).
    """
    files = list(_iter_py_files(Path(root_path)))
    if not files:
        return []
    if parallel and len(files) >= _DEFAULT_PARALLEL_THRESHOLD:
        with ProcessPoolExecutor() as pool:
            results = list(pool.map(scan_static, [str(f) for f in files]))
    else:
        results = [scan_static(str(f)) for f in files]
    out: list[DynamicDispatchSite] = []
    for r in results:
        out.extend(r)
    return out


# ─── Runtime trace merge ──────────────────────────────────────────────────


def merge_with_runtime_trace(
    static_sites: list[DynamicDispatchSite],
    runtime_trace: Iterable[dict],
) -> list[DynamicDispatchSite]:
    """Upgrade INFERRED/AMBIGUOUS sites to EXTRACTED when runtime resolves target.

    Args:
        static_sites: output of ``scan_static`` / ``scan_root_static``.
        runtime_trace: iterable of dicts with keys ``file_path``, ``line``,
            ``resolved_target``. May come from ``sys.settrace`` callback or
            ``sys.monitoring`` (Python 3.12+) — instrumentation is external.

    Returns:
        New list with matched sites upgraded:
          - confidence → EXTRACTED
          - resolved_target ← runtime value (overrides static literal if both)

    Sites with no matching trace entry are returned unchanged.
    """
    # Index trace by (file_path, line) — first match wins for repeated lines
    index: dict[tuple[str, int], str] = {}
    for rec in runtime_trace:
        try:
            key = (rec["file_path"], int(rec["line"]))
        except (KeyError, TypeError, ValueError):
            continue
        target = rec.get("resolved_target")
        if target is None:
            continue
        index.setdefault(key, str(target))

    out: list[DynamicDispatchSite] = []
    for site in static_sites:
        key = (site.file_path, site.line)
        if key in index:
            out.append(
                site.model_copy(
                    update={
                        "confidence": Confidence.EXTRACTED,
                        "resolved_target": index[key],
                    }
                )
            )
        else:
            out.append(site)
    return out


# ─── Summary ──────────────────────────────────────────────────────────────


def summarize(sites: list[DynamicDispatchSite]) -> DynamicDispatchReport:
    """Aggregate counts by confidence tier and dispatch kind."""
    by_kind: dict[str, int] = {}
    extracted = inferred = ambiguous = 0
    for s in sites:
        by_kind[s.dispatch_kind] = by_kind.get(s.dispatch_kind, 0) + 1
        if s.confidence == Confidence.EXTRACTED:
            extracted += 1
        elif s.confidence == Confidence.INFERRED:
            inferred += 1
        else:
            ambiguous += 1
    return DynamicDispatchReport(
        total_sites=len(sites),
        extracted_count=extracted,
        inferred_count=inferred,
        ambiguous_count=ambiguous,
        by_kind=by_kind,
        sites=sites,
    )
