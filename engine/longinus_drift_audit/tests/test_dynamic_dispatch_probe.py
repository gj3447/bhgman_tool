"""Tests for hybrid static+runtime dynamic dispatch probe (v3.3, 2026-05-19).

# KG: CONTRACT_DynamicDispatchProbe_v1_2026-05-19,
#     sa-longinus-dynamic-dispatch-probe-2026-05-19,
#     wqi-longinus-dynamic-dispatch-probe-v3.3-2026-05-19
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from engine.longinus_drift_audit.dynamic_dispatch_probe import (
    DynamicDispatchReport,
    DynamicDispatchSite,
    merge_with_runtime_trace,
    scan_root_static,
    scan_static,
    summarize,
)
from engine.longinus_drift_audit.models import Confidence


def _write(tmp_path: Path, name: str, src: str) -> str:
    p = tmp_path / name
    p.write_text(textwrap.dedent(src), encoding="utf-8")
    return str(p)


# ── 1. getattr literal target → INFERRED ──────────────────────────────────


def test_getattr_literal_target_is_inferred(tmp_path: Path):
    f = _write(
        tmp_path,
        "g_lit.py",
        """
        def f(obj):
            return getattr(obj, "my_attr")
        """,
    )
    sites = scan_static(f)
    assert len(sites) == 1
    s = sites[0]
    assert s.dispatch_kind == "getattr"
    assert s.resolved_target == "my_attr"
    assert s.confidence == Confidence.INFERRED


# ── 2. getattr dynamic name → AMBIGUOUS ───────────────────────────────────


def test_getattr_dynamic_name_is_ambiguous(tmp_path: Path):
    f = _write(
        tmp_path,
        "g_dyn.py",
        """
        def f(obj, name):
            return getattr(obj, name)
        """,
    )
    sites = scan_static(f)
    assert len(sites) == 1
    assert sites[0].dispatch_kind == "getattr"
    assert sites[0].resolved_target is None
    assert sites[0].confidence == Confidence.AMBIGUOUS


# ── 3. importlib.import_module literal → INFERRED ─────────────────────────


def test_importlib_literal_is_inferred(tmp_path: Path):
    f = _write(
        tmp_path,
        "imp.py",
        """
        import importlib
        def loader():
            return importlib.import_module("os.path")
        """,
    )
    sites = scan_static(f)
    assert len(sites) == 1
    assert sites[0].dispatch_kind == "importlib.import_module"
    assert sites[0].resolved_target == "os.path"
    assert sites[0].confidence == Confidence.INFERRED


# ── 4. eval / exec → AMBIGUOUS ────────────────────────────────────────────


def test_eval_and_exec_are_ambiguous(tmp_path: Path):
    f = _write(
        tmp_path,
        "ev.py",
        """
        def f(code):
            eval(code)
            exec(code)
        """,
    )
    sites = scan_static(f)
    kinds = sorted(s.dispatch_kind for s in sites)
    assert kinds == ["eval", "exec"]
    assert all(s.confidence == Confidence.AMBIGUOUS for s in sites)


# ── 5. globals()[name] subscript → AMBIGUOUS ──────────────────────────────


def test_globals_subscript_is_ambiguous(tmp_path: Path):
    f = _write(
        tmp_path,
        "gl.py",
        """
        def f(name):
            return globals()[name]
        """,
    )
    sites = scan_static(f)
    assert len(sites) == 1
    assert sites[0].dispatch_kind == "globals_subscript"
    assert sites[0].confidence == Confidence.AMBIGUOUS


# ── 6. __import__ → AMBIGUOUS ─────────────────────────────────────────────


def test_dunder_import_is_ambiguous(tmp_path: Path):
    f = _write(
        tmp_path,
        "di.py",
        """
        def f(modname):
            return __import__(modname)
        """,
    )
    sites = scan_static(f)
    assert len(sites) == 1
    assert sites[0].dispatch_kind == "__import__"
    assert sites[0].confidence == Confidence.AMBIGUOUS


# ── 7. clean file → 0 sites ───────────────────────────────────────────────


def test_clean_file_zero_sites(tmp_path: Path):
    f = _write(
        tmp_path,
        "clean.py",
        """
        def add(x, y):
            return x + y

        class Foo:
            def bar(self):
                return 42
        """,
    )
    assert scan_static(f) == []


# ── 8. merge_with_runtime_trace upgrades AMBIGUOUS → EXTRACTED ────────────


def test_runtime_trace_upgrades_to_extracted(tmp_path: Path):
    f = _write(
        tmp_path,
        "merge.py",
        """
        def f(obj, name):
            return getattr(obj, name)
        """,
    )
    sites = scan_static(f)
    assert sites[0].confidence == Confidence.AMBIGUOUS
    # Provide a runtime trace that resolves the target on the right line
    trace = [
        {
            "file_path": f,
            "line": sites[0].line,
            "resolved_target": "computed_attr_name",
        }
    ]
    upgraded = merge_with_runtime_trace(sites, trace)
    assert len(upgraded) == 1
    assert upgraded[0].confidence == Confidence.EXTRACTED
    assert upgraded[0].resolved_target == "computed_attr_name"
    # Original list unmodified (functional)
    assert sites[0].confidence == Confidence.AMBIGUOUS


def test_runtime_trace_no_match_leaves_unchanged(tmp_path: Path):
    f = _write(
        tmp_path,
        "merge_nomatch.py",
        """
        def f(obj, name):
            return getattr(obj, name)
        """,
    )
    sites = scan_static(f)
    trace = [{"file_path": "/some/other/file.py", "line": 1, "resolved_target": "x"}]
    upgraded = merge_with_runtime_trace(sites, trace)
    assert upgraded[0].confidence == Confidence.AMBIGUOUS
    assert upgraded[0].resolved_target is None


# ── 9. summarize counts correctly ─────────────────────────────────────────


def test_summarize_counts(tmp_path: Path):
    f = _write(
        tmp_path,
        "mix.py",
        """
        import importlib
        def f(obj, name, code):
            getattr(obj, "lit")          # INFERRED
            getattr(obj, name)            # AMBIGUOUS
            importlib.import_module("os") # INFERRED
            eval(code)                     # AMBIGUOUS
            return globals()[name]         # AMBIGUOUS
        """,
    )
    sites = scan_static(f)
    rep = summarize(sites)
    assert isinstance(rep, DynamicDispatchReport)
    assert rep.total_sites == 5
    assert rep.inferred_count == 2
    assert rep.ambiguous_count == 3
    assert rep.extracted_count == 0
    assert rep.by_kind["getattr"] == 2
    assert rep.by_kind["importlib.import_module"] == 1
    assert rep.by_kind["eval"] == 1
    assert rep.by_kind["globals_subscript"] == 1


# ── 10. Pydantic round-trip ───────────────────────────────────────────────


def test_pydantic_round_trip():
    s = DynamicDispatchSite(
        file_path="/x/y.py",
        line=42,
        dispatch_kind="getattr",
        target_expr='"foo"',
        resolved_target="foo",
        confidence=Confidence.INFERRED,
    )
    dumped = s.model_dump()
    restored = DynamicDispatchSite.model_validate(dumped)
    assert restored == s

    rep = DynamicDispatchReport(
        total_sites=1,
        extracted_count=0,
        inferred_count=1,
        ambiguous_count=0,
        by_kind={"getattr": 1},
        sites=[s],
    )
    rep2 = DynamicDispatchReport.model_validate(rep.model_dump())
    assert rep2 == rep


def test_invalid_dispatch_kind_rejected():
    with pytest.raises(ValueError):
        DynamicDispatchSite(
            file_path="/x.py",
            line=1,
            dispatch_kind="not_a_real_kind",
            target_expr="x",
        )


# ── 11. scan_root_static walks directory ──────────────────────────────────


def test_scan_root_static_walks_directory(tmp_path: Path):
    _write(
        tmp_path,
        "a.py",
        """
        def f(o, n): return getattr(o, n)
        """,
    )
    _write(
        tmp_path,
        "b.py",
        """
        def g(): return eval("1+1")
        """,
    )
    _write(
        tmp_path,
        "clean.py",
        """
        def h(): return 1
        """,
    )
    sites = scan_root_static(str(tmp_path), parallel=False)
    kinds = sorted(s.dispatch_kind for s in sites)
    assert kinds == ["eval", "getattr"]


# ── 12. Malformed file does not crash ─────────────────────────────────────


def test_syntax_error_returns_empty(tmp_path: Path):
    f = _write(
        tmp_path,
        "bad.py",
        """
        def broken(:
            pass
        """,
    )
    assert scan_static(f) == []


def test_missing_file_returns_empty(tmp_path: Path):
    assert scan_static(str(tmp_path / "does_not_exist.py")) == []
