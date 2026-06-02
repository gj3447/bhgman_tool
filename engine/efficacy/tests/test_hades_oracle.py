"""hades realization oracle 순수 함수 테스트 — module_name / import 파싱 / BFS 도달."""

from __future__ import annotations

from pathlib import Path

from engine.efficacy.hades_oracle import (
    _imports_of,
    module_name,
    reachable_modules,
)


# ── module_name ────────────────────────────────────────────────────────────────
def test_module_name_strips_suffix_and_init():
    root = Path("/repo")
    assert module_name(Path("/repo/engine/occam/occam.py"), root) == "engine.occam.occam"
    assert module_name(Path("/repo/engine/occam/__init__.py"), root) == "engine.occam"


# ── _imports_of (import 스타일 양쪽) ─────────────────────────────────────────────
def test_imports_absolute_and_from(tmp_path):
    f = tmp_path / "m.py"
    f.write_text(
        "import engine.a\n"
        "from engine.b.c import thing\n"
        "from engine.b import submod\n"  # from-pkg-import-submod → engine.b.submod 후보
        "import os\n",  # 비-engine 무시
        encoding="utf-8",
    )
    got = _imports_of(f, "engine.x")
    assert "engine.a" in got
    assert "engine.b.c" in got
    assert "engine.b.submod" in got  # 핵심: 서브모듈 후보 포함 (undercount 버그 회귀 방지)
    assert not any(m == "os" for m in got)


def test_imports_relative_resolved(tmp_path):
    f = tmp_path / "m.py"
    f.write_text("from . import sibling\nfrom .deep import x\n", encoding="utf-8")
    got = _imports_of(f, "engine.pkg.mod")
    assert "engine.pkg.sibling" in got
    assert "engine.pkg.deep" in got


def test_imports_syntax_error_is_empty(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("def (:\n", encoding="utf-8")
    assert _imports_of(f, "engine.x") == set()


# ── reachable_modules (BFS) ──────────────────────────────────────────────────────
def test_reachable_transitive_and_universe_intersect():
    universe = {"engine.a", "engine.b", "engine.c", "engine.unreached"}
    edges = {"engine.a": {"engine.b"}, "engine.b": {"engine.c"}, "engine.c": set()}
    seeds = {"engine.a"}  # 테스트가 a만 직접 import → b,c 전이 도달
    reached = reachable_modules(universe, edges, seeds)
    assert reached == {"engine.a", "engine.b", "engine.c"}
    assert "engine.unreached" not in reached


def test_reachable_seed_outside_universe_ignored():
    universe = {"engine.a"}
    reached = reachable_modules(universe, {}, {"engine.testonly"})
    assert reached == set()  # universe 교집합 → 테스트 전용 seed는 안 셈
