"""FunSearch binpack 게이트 TDD — 돌리기 *전에* 게이트가 공정·정직함을 결정론적으로 증명.

postmortem 교훈(conclusion-before-experiment 금지) 적용: 주입식 fake LLM 으로
(1) read-back 가 도움되면 realized,
(2) **read-back 를 무시하면 ARM2 ≈ ARM1 (spurious 승리 없음 = 하네스가 ARM2 편들지 않음)**,
(3) oracle 가 best-fit > worst-fit 을 실제로 차별화,
(4) ARM1 이 ARM2 와 동일 generator (안 불구).

# KG: lesson-premature-close-confirmation-toward-closure-2026-06-02, prom16-evolve-loop-revival-2026-06-02
"""

from __future__ import annotations

from engine.efficacy.funsearch_binpack import (
    IslandDatabase,
    make_task,
    run_gate,
    score_heuristic,
)

# best-fit(tightest leftover) = 좋음(적은 bin) / worst-fit(emptiest) = 나쁨(많은 bin)
_GOOD = "def priority(item, bins):\n    return [-(b - item) for b in bins]"
_BAD = "def priority(item, bins):\n    return list(bins)"


def _fake_readback_helps(messages, seed):
    """read-back(prior heuristic)이 프롬프트에 있으면 GOOD, 없으면 BAD → 반복이 도움되는 조건."""
    text = " ".join(m["content"] for m in messages)
    code = _GOOD if "prior heuristic" in text else _BAD
    return f"```python\n{code}\n```", 200


def _fake_ignores_readback(messages, seed):
    """read-back 무관 항상 GOOD → ARM2가 ARM1보다 유리할 이유 없음 (하네스 공정성 control)."""
    return f"```python\n{_GOOD}\n```", 200


def test_oracle_differentiates_best_fit_from_worst_fit():
    task = make_task(seed=1)
    good = score_heuristic(_GOOD, task.hidden, task.cap)
    bad = score_heuristic(_BAD, task.hidden, task.cap)
    assert 0.0 < bad < good <= 1.0  # 연속 oracle, best-fit이 strictly 높음 (gradient 존재)


def test_score_zero_on_broken_heuristic():
    broken = "def priority(item, bins):\n    return 'not a list'"  # 계약 위반 → 0.0
    assert score_heuristic(broken, make_task(seed=1).hidden, _CAP := 1.0) == 0.0


def test_gate_realized_when_readback_helps():
    v = run_gate([1, 2, 3], _fake_readback_helps, budget_tokens=1200, n_islands=2)
    assert v.realized is True
    assert v.mean_arm2 > v.mean_arm1  # island-evolve(GOOD via read-back) > best-of-N(BAD)
    assert v.lift[1] > 0  # CI lower bound > 0
    assert v.gen_tokens["best_of_n"] == v.gen_tokens["island_evolve"]  # 토큰 동수


def test_gate_fair_no_spurious_win_when_readback_ignored():
    """하네스 공정성: read-back가 무용하면 ARM2가 ARM1을 *이기면 안 된다*. 안 그러면 rig."""
    v = run_gate([1, 2, 3], _fake_ignores_readback, budget_tokens=1200, n_islands=2)
    assert v.realized is False
    assert abs(v.mean_arm2 - v.mean_arm1) < 1e-9  # 동일 generator → 동일 결과
    assert v.lift == (0.0, 0.0, 0.0)


def test_island_db_migrate_and_best_overall():
    db = IslandDatabase(2)
    db.add(0, "a", 0.5)
    db.add(1, "b", 0.9)
    db.add(0, "c", 0.7)
    assert db.best_overall() == ("b", 0.9)
    assert [c for c, _ in db.best_in(0, 2)] == ["c", "a"]  # island 0 내 점수순
    db.migrate()  # 각 island best → 다음 island 복제
    assert any(c == "b" for c, _ in db.islands[0])  # island1 best(b)가 island0로 이주
