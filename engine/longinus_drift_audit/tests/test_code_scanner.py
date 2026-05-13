from __future__ import annotations

from pathlib import Path

import code_scanner


def _write_py(p: Path, content: str) -> None:
    p.write_text(content)


class TestScanKgRefs:
    def test_single_ref(self, tmp_path):
        p = tmp_path / "a.py"
        _write_py(p, "def x():\n    pass  # KG: lesson-foo-2026\n")
        refs = code_scanner.scan_kg_refs(p)
        assert refs == [(2, ["lesson-foo-2026"])]

    def test_multiple_refs_same_line(self, tmp_path):
        p = tmp_path / "a.py"
        _write_py(p, "def x(): pass  # KG: a-1, b-2, c-3\n")
        refs = code_scanner.scan_kg_refs(p)
        assert refs == [(1, ["a-1", "b-2", "c-3"])]

    def test_no_refs(self, tmp_path):
        p = tmp_path / "a.py"
        _write_py(p, "def x(): pass\n")
        assert code_scanner.scan_kg_refs(p) == []


class TestScanPythonSymbols:
    def test_function_and_class(self, tmp_path):
        p = tmp_path / "a.py"
        _write_py(
            p,
            "class Foo:  # KG: x-y\n"
            "    pass\n"
            "\n"
            "def bar(x, y):  # KG: a-b\n"
            "    return x + y\n",
        )
        syms = code_scanner.scan_python_symbols(p)
        assert len(syms) == 2
        names = {s.name for s in syms}
        assert names == {"Foo", "bar"}
        bar = [s for s in syms if s.name == "bar"][0]
        assert "x, y" in bar.signature
        assert "a-b" in bar.kg_refs

    def test_skip_non_top_level(self, tmp_path):
        p = tmp_path / "a.py"
        _write_py(p, "def outer():\n    def inner(): pass\n")
        syms = code_scanner.scan_python_symbols(p)
        assert len(syms) == 1
        assert syms[0].name == "outer"


class TestScanRoot:
    def test_aggregates_files(self, tmp_path):
        _write_py(tmp_path / "a.py", "def a(): pass  # KG: x-1\n")
        _write_py(tmp_path / "b.py", "def b(): pass  # KG: y-2\n")
        # skip dirs
        (tmp_path / ".venv").mkdir()
        _write_py(tmp_path / ".venv" / "skip.py", "def skip(): pass\n")
        syms, refs = code_scanner.scan_root(tmp_path)
        names = {s.name for s in syms}
        assert names == {"a", "b"}
        kgs = {ref[2] for ref in refs}
        assert kgs == {"x-1", "y-2"}
