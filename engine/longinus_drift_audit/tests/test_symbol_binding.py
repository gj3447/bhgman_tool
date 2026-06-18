"""Tests for longinus symbol-level forward binding."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from engine.longinus_drift_audit.symbol_binding import (
    bind_file,
    module_concepts,
    plan_file,
)
from engine.longinus_drift_audit.code_scanner import scan_python_symbols


SRC = textwrap.dedent('''\
    """Module doc.

    # KG: concept-primary, concept-second
    """
    # KG: concept-third


    def public_fn(x):
        """A public function."""
        return x


    def _private_fn():
        return 1


    class PublicCls:
        # KG: already-here
        """Already bound in header."""

        def method(self):
            return 2
''')


def test_module_concepts_only_outside_symbols():
    cs = module_concepts(SRC)
    assert cs == ["concept-primary", "concept-second", "concept-third"]


def test_plan_binds_public_skips_private_and_already_bound():
    plans, already = plan_file(SRC, "concept-primary")
    bound = {p.symbol for p in plans}
    assert bound == {"public_fn"}          # _private_fn skipped, PublicCls already has header KG
    assert "PublicCls" in already
    assert "_private_fn" not in bound


def test_concept_must_be_identifier():
    with pytest.raises(ValueError, match="non-identifier"):
        plan_file(SRC, "not a concept; DROP")


def test_apply_then_scanner_attributes_symbol(tmp_path: Path):
    f = tmp_path / "m.py"
    f.write_text(SRC)
    # before: public_fn has no header KG ref
    pre = {s.name: s.kg_refs for s in scan_python_symbols(f)}
    assert pre["public_fn"] == []

    res = bind_file(f, apply=True)
    assert res.dry_run is False and "public_fn" in res.bound and res.concept == "concept-primary"

    # after: the scanner now attributes the concept to the symbol's header span
    post = {s.name: s.kg_refs for s in scan_python_symbols(f)}
    assert "concept-primary" in post["public_fn"]
    assert post["_private_fn"] == []  # untouched


def test_idempotent_second_run_binds_nothing(tmp_path: Path):
    f = tmp_path / "m.py"
    f.write_text(SRC)
    bind_file(f, apply=True)
    again = bind_file(f, apply=True)
    assert again.bound == ()  # everything already bound


def test_dry_run_writes_nothing(tmp_path: Path):
    f = tmp_path / "m.py"
    f.write_text(SRC)
    before = f.read_text()
    res = bind_file(f, apply=False)
    assert res.dry_run is True and "public_fn" in res.bound
    assert f.read_text() == before


def test_only_restricts_to_named_symbols():
    plans, _ = plan_file(SRC, "c", only={"public_fn"})
    assert {p.symbol for p in plans} == {"public_fn"}


def test_multiline_signature_inserts_in_header_span(tmp_path: Path):
    src = textwrap.dedent('''\
        # KG: c-multi
        def wide(
            a,
            b,
        ):
            return a + b
    ''')
    f = tmp_path / "w.py"
    f.write_text(src)
    bind_file(f, apply=True)
    refs = {s.name: s.kg_refs for s in scan_python_symbols(f)}
    assert "c-multi" in refs["wide"]


def test_syntax_error_file_untouched(tmp_path: Path):
    f = tmp_path / "bad.py"
    f.write_text("def broken(:\n")
    before = f.read_text()
    res = bind_file(f, apply=True)
    assert res.bound == () and f.read_text() == before
