from __future__ import annotations

from pathlib import Path

from engine.longinus_drift_audit import code_scanner


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

    def test_parenthetical_note_stripped(self, tmp_path):
        # legit form: `# KG: anchor (free-text note)` → anchor only.
        p = tmp_path / "a.py"
        _write_py(p, "# KG: hub-harness-3tier (canon in SYMPOSIUM — the family hub)\n")
        assert code_scanner.scan_kg_refs(p) == [(1, ["hub-harness-3tier"])]

    def test_backtick_example_in_docstring_ignored(self, tmp_path):
        # prose example of the syntax, NOT a real anchor — must not be captured.
        p = tmp_path / "a.py"
        _write_py(p, '"""A `# KG: xxx` example, and ``# KG: lesson-foo-2026`` too."""\n')
        assert code_scanner.scan_kg_refs(p) == []

    def test_prose_tail_after_comma_dropped(self, tmp_path):
        # real comment, real first anchor, but a prose tail after the comma.
        p = tmp_path / "a.py"
        _write_py(p, "# KG: lesson-real-2026-04-16, LensSet UNION coverage canon\n")
        assert code_scanner.scan_kg_refs(p) == [(1, ["lesson-real-2026-04-16"])]

    def test_kg_inside_string_literal_dropped(self, tmp_path):
        # `# KG:` mentioned inside a string value is prose, not an anchor.
        p = tmp_path / "a.py"
        _write_py(p, 'NOTE = "scans for # KG: refs and reports orphans"\n')
        assert code_scanner.scan_kg_refs(p) == []

    def test_digit_leading_and_korean_anchor_kept(self, tmp_path):
        p = tmp_path / "a.py"
        _write_py(p, "# KG: 7cmd-need-based-2026-05-30, 재배맨-v2-protocol\n")
        assert code_scanner.scan_kg_refs(p) == [
            (1, ["7cmd-need-based-2026-05-30", "재배맨-v2-protocol"])
        ]


class TestScanPythonSymbols:
    def test_function_and_class(self, tmp_path):
        p = tmp_path / "a.py"
        _write_py(
            p,
            "class Foo:  # KG: x-y\n    pass\n\ndef bar(x, y):  # KG: a-b\n    return x + y\n",
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


class TestAstSignatureUpgrade:
    """Real ast extraction: multi-line sigs, annotations, return, async, bases."""

    def test_multiline_signature_and_return(self, tmp_path):
        p = tmp_path / "m.py"
        p.write_text(
            "def f(\n    a: int,\n    b: str = 'x',\n) -> bool:  # KG: ref-1\n    return True\n",
            encoding="utf-8",
        )
        syms = code_scanner.scan_python_symbols(p)
        f = next(s for s in syms if s.name == "f")
        assert f.signature == "a: int, b: str = 'x' -> bool"
        assert "ref-1" in f.kg_refs  # ref on the `-> bool:` header line, multi-line span

    def test_async_and_varargs(self, tmp_path):
        p = tmp_path / "a.py"
        p.write_text("async def g(a, /, *args, k=1, **kw):\n    pass\n", encoding="utf-8")
        syms = code_scanner.scan_python_symbols(p)
        g = next(s for s in syms if s.name == "g")
        assert g.kind == "async_function"
        assert g.signature == "a, /, *args, k = 1, **kw"

    def test_class_bases_captured(self, tmp_path):
        p = tmp_path / "c.py"
        p.write_text("class Child(Base, Mixin):\n    pass\n", encoding="utf-8")
        syms = code_scanner.scan_python_symbols(p)
        c = next(s for s in syms if s.name == "Child")
        assert c.signature == "Base, Mixin"

    def test_syntax_error_falls_back_to_regex(self, tmp_path):
        p = tmp_path / "broken.py"
        # invalid (unclosed) — ast.parse raises; regex still finds the def line
        p.write_text("def still_found(x, y):  # KG: r\n    return (\n", encoding="utf-8")
        syms = code_scanner.scan_python_symbols(p)
        assert any(s.name == "still_found" and "x, y" in (s.signature or "") for s in syms)
class TestIterFilesSkipScope:
    """iter_files skip 기준은 root 낶 상대경로 (2026-07-29 회귀 봉인).

    절대경로 기준 시절, SYMPOSIUM/GIT/<repo> 배치에서 상위 'GIT' 파트가
    skip_parts 에 매칭돼 전 파일이 스킵됐다 (longinus_audit files_scanned=0).
    """

    def test_repo_under_GIT_dir_not_blanked(self, tmp_path):
        root = tmp_path / "GIT" / "repo"
        (root / "pkg").mkdir(parents=True)
        f = root / "pkg" / "mod.py"
        f.write_text("def f():\n    pass\n")
        assert f in list(code_scanner.iter_files(root))

    def test_intree_GIT_dir_still_skipped(self, tmp_path):
        root = tmp_path / "repo"
        nested = root / "GIT" / "nested"
        nested.mkdir(parents=True)
        bad = nested / "x.py"
        bad.write_text("def x():\n    pass\n")
        good = root / "ok.py"
        good.write_text("def ok():\n    pass\n")
        files = list(code_scanner.iter_files(root))
        assert good in files
        assert bad not in files
