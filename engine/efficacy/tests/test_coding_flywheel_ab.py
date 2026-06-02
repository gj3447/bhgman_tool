"""코딩 플라이휠 A/B 순수 부분 테스트 — code 추출 / materialize+score / best-K render.

실 LLM·실 pytest는 main()(백엔드 필요). 여기선 fake runner로 oracle 로직만 결정론 검증.
"""

from __future__ import annotations

from engine.efficacy.coding_flywheel_ab import (
    PROBLEMS,
    CodingOracle,
    coding_render,
    extract_code,
    materialize_and_test,
)
from engine.legion.evolve_loop import Candidate, ScoredCandidate


def test_extract_code_strips_fence():
    assert extract_code("```python\ndef f():\n    return 1\n```") == "def f():\n    return 1"
    assert extract_code("def g(): return 2") == "def g(): return 2"


def test_materialize_and_test_parses_ratio(tmp_path):
    prob = PROBLEMS[0]

    # fake runner: pytest가 3 passed, 1 failed 했다고 가정 → ratio 0.75
    def fake(cmd):
        return 1, "...\n3 passed, 1 failed in 0.1s\n"

    ratio = materialize_and_test("def roman_to_int(s): return 0", prob, tmp_path, fake)
    assert ratio == 0.75
    # solution.py / test_sol.py 실제로 써졌나 (물질화 확인)
    assert (tmp_path / "solution.py").exists()
    assert (tmp_path / "test_sol.py").read_text().startswith("from solution import")


def test_coding_oracle_seed_floor(tmp_path):
    prob = PROBLEMS[1]
    oracle = CodingOracle(
        prob, tmp_path, seed_floor=0.5, runner=lambda c: (0, "2 passed, 2 failed in 0s")
    )
    sc = oracle.score("t", Candidate("def valid_parens(s): return True"))
    assert sc.score == 0.5
    assert sc.passed  # 0.5 >= seed_floor 0.5
    oracle2 = CodingOracle(
        prob, tmp_path, seed_floor=0.6, runner=lambda c: (1, "2 passed, 2 failed in 0s")
    )
    assert not oracle2.score("t", Candidate("x")).passed  # 0.5 < 0.6


def test_timeout_returns_zero_ratio(tmp_path):
    # runner가 timeout(124) → "0 passed" → ratio 0 (무한루프 안전).
    prob = PROBLEMS[2]
    ratio = materialize_and_test(
        "while True: pass", prob, tmp_path, lambda c: (124, "timeout — 0 passed")
    )
    assert ratio == 0.0


def test_coding_render_injects_prior_attempts():
    best = (ScoredCandidate(Candidate("def f(): return 1"), 0.6, True),)
    r = coding_render("PROBLEM: do X", best)
    assert "pass_ratio=0.60" in r and "def f(): return 1" in r and "fix failures" in r
    assert "No prior attempts" in coding_render("PROBLEM: do X", ())
