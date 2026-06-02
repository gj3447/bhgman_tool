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


def test_parse_pytest_counts():
    from engine.efficacy.hades_realkg import parse_pytest_counts

    assert parse_pytest_counts("1 failed, 2 passed in 0.08s") == (2, 3)
    assert parse_pytest_counts("5 passed in 0.1s") == (5, 5)
    assert parse_pytest_counts("3 passed, 1 skipped in 0.2s") == (3, 3)  # skipped 제외
    assert parse_pytest_counts("2 failed, 1 error, 4 passed") == (4, 7)
    assert parse_pytest_counts("collected 0 items") == (0, 0)


def test_mean_test_pass_rate():
    from engine.efficacy.hades_realkg import HadesTask, TaskResult, mean_test_pass_rate

    t = HadesTask("c", "engine/a.py", "engine/tests/test_a.py")
    rs = [TaskResult(t, False, "x", 2, 3), TaskResult(t, False, "y", 4, 5)]
    assert abs(mean_test_pass_rate(rs) - (2 / 3 + 4 / 5) / 2) < 1e-9
    assert mean_test_pass_rate([]) == 0.0


def test_extract_signatures():
    from engine.efficacy.hades_realkg import extract_signatures

    src = 'def foo(a, b=1):\n    """Does foo."""\n    return a\n\nclass Bar:\n    """A bar."""\n'
    sig = extract_signatures(src)
    assert "def foo(a, b=1): Does foo." in sig
    assert "class Bar: A bar." in sig
    assert extract_signatures("this is (not python") == ""  # SyntaxError → ""


def test_bestofn_selectors():
    from engine.efficacy.hades_realkg import (
        Candidate,
        select_majority_at_n,
        select_pass_at_1,
        select_pass_at_n,
    )

    # 첫 샘플 fail, 다수파(2표) pass, 적어도 하나 pass
    cands = [
        Candidate("def f(): return 0", False),
        Candidate("def f(): return 1", True),
        Candidate("def f(): return 1", True),  # 다수파 = return 1 (pass)
    ]
    assert select_pass_at_1(cands) is False        # 첫 샘플
    assert select_majority_at_n(cands) is True      # 다수파 return 1
    assert select_pass_at_n(cands) is True          # 하나라도 pass

    # 다수파가 틀린 경우: majority는 fail이지만 oracle은 잡음
    bad_majority = [
        Candidate("def f(): return 9", False),
        Candidate("def f(): return 9", False),  # 다수파 = 틀림
        Candidate("def f(): return 1", True),
    ]
    assert select_majority_at_n(bad_majority) is False
    assert select_pass_at_n(bad_majority) is True   # oracle이 majority를 이기는 케이스

    assert select_pass_at_1([]) is False
    assert select_pass_at_n([]) is False
