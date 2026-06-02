"""hades_realkg 순수부 — task 선택 + 코드펜스 제거 + pass@1."""

from __future__ import annotations

from engine.efficacy.git_oracle import FeatureTestCommit
from engine.efficacy.hades_realkg import (
    HadesTask,
    TaskResult,
    pass_at_1,
    pick_tasks,
    strip_code_fence,
)


def _ft(commit, impls, tests, date="2026-06-01"):
    return FeatureTestCommit(commit=commit, date=date, impl_paths=impls, test_paths=tests)


def test_pick_tasks_only_clean_single_impl_test():
    fts = [
        _ft("c1", ("engine/a.py",), ("engine/tests/test_a.py",)),
        _ft("c2", ("engine/b.py", "engine/c.py"), ("engine/tests/test_b.py",)),  # 2 impl → 제외
        _ft("c3", ("engine/__init__.py",), ("engine/tests/test_i.py",)),  # __init__ → 제외
        _ft("c4", ("docs/d.py",), ("docs/test_d.py",)),  # scope 밖 → 제외
    ]
    tasks = pick_tasks(fts, n=10, scope_prefix="engine/")
    assert [t.commit for t in tasks] == ["c1"]
    assert tasks[0].impl_path == "engine/a.py"
    assert tasks[0].parent == "c1^"


def test_pick_tasks_caps_n_and_sorts():
    fts = [_ft(c, (f"engine/{c}.py",), (f"engine/tests/test_{c}.py",)) for c in ("c3", "c1", "c2")]
    tasks = pick_tasks(fts, n=2)
    assert [t.commit for t in tasks] == ["c1", "c2"]  # commit 정렬 후 앞 2


def test_strip_code_fence():
    assert strip_code_fence("```python\nx = 1\n```").strip() == "x = 1"
    assert strip_code_fence("```\ny = 2\n```").strip() == "y = 2"
    assert strip_code_fence("z = 3").strip() == "z = 3"  # 펜스 없음


def test_pass_at_1():
    t = HadesTask("c", "engine/a.py", "engine/tests/test_a.py")
    rs = [TaskResult(t, True, "ok"), TaskResult(t, False, "x"), TaskResult(t, True, "ok")]
    assert abs(pass_at_1(rs) - 2 / 3) < 1e-9
    assert pass_at_1([]) == 0.0
