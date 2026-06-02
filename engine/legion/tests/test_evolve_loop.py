"""evolve loop TDD — 검증접지 합성(Verification-Grounded Composition) fixpoint.

결정론 generate + 결정론 oracle 로 LLM 없이 메커니즘을 검증한다.

정직 경계 (critic verdict 2026-06-02): 이 테스트들은 *합성 landscape* 위 존재증명이다 —
(1) 구조 있는 landscape 에선 read-back 가이드 탐색이 동일 제안분포의 blind best-of-N 을
equal-budget 에서 이기고, (2) **기만적 landscape 에선 질 수도 있다**(판별력 증명). 이는
read-back primitive 가 동작함을 보이는 것이지, 4개 실제 oracle task 에서 equal-compute
인지 우위를 보인 것이 아니다 (그건 engine/efficacy 4th gate 몫). 이전 버전은 blind 가지가
구조적으로 optimum 도달 불가였던 rig 였고 — 여기선 blind 도 전 공간을 샘플해 optimum 도달
*가능*하다. 차이는 오직 read-back 활용 여부.

# KG: prom16-bhgman-ci-design-2026-06-02, lesson-bhgman-collective-intelligence-design-2026-06-02
"""

from __future__ import annotations

from engine.legion.evolve_loop import ProgramDatabase, best_of_n, evolve
from engine.naesengmoon.oracle_lens import OracleLens, ScalarOracle, scalar_from_lens

SPACE = 1_000_000
TARGET = 987_654

# 단일 generator (모든 arm 공유). parents 있으면 multi-scale hill-climb(read-back 활용),
# 없으면 전 공간 독립 LCG draw. blind 도 전 공간 cover → optimum 도달 *가능*(barred 아님).
# 차이는 오직 read-back. multi-scale + ±1 step → greedy 가 정확히 TARGET 도달 가능.
_STEPS = (1, -1, 7, -7, 53, -53, 401, -401, 3001, -3001, 21001, -21001)


def _blind_sample(i: int) -> int:
    """결정론 LCG — 전 공간 [0, SPACE] 독립 균일 추출 (seed=i)."""
    return (i * 2654435761 + 12345) % (SPACE + 1)


def _generate(parents, generation):
    if not parents:
        return [_blind_sample(generation)]  # 1 독립 blind draw per call
    base = parents[0]
    return [min(max(base + s, 0), SPACE) for s in _STEPS]  # read-back hill-climb


def _dist_oracle() -> ScalarOracle:
    """외부 결정론 fitness: TARGET 에 가까울수록 높음 (max 0). 구조 있는 landscape."""
    return ScalarOracle(name="dist", kind="test", score=lambda x: float(-abs(x - TARGET)))


# ── ProgramDatabase ─────────────────────────────────────────────────────────


def test_best_k_ties_break_by_index_deterministic():
    db = ProgramDatabase()
    a = db.add(payload="a", score=0.5, generation=0, parent=None)
    b = db.add(payload="b", score=0.5, generation=0, parent=None)
    db.add(payload="c", score=0.1, generation=0, parent=None)
    top = db.best_k(2)
    assert [c.index for c in top] == [a.index, b.index]  # 동률 → 먼저 들어온 것
    assert db.best().payload == "a"


def test_lineage_reconstructs_parent_chain():
    db = ProgramDatabase()
    seed = db.add(payload=0, score=-100, generation=0, parent=None)
    g1 = db.add(payload=10, score=-90, generation=1, parent=seed.index)
    g2 = db.add(payload=20, score=-80, generation=2, parent=g1.index)
    chain = db.lineage(g2)
    assert [c.payload for c in chain] == [0, 10, 20]  # seed → ... → g2


# ── evolve: 핵심 거동 (구조 있는 landscape) ───────────────────────────────────


def test_evolve_climbs_to_exact_optimum():
    res = evolve(0, _generate, _dist_oracle(), max_generations=200, k_parents=1, patience=5)
    assert res.best.payload == TARGET
    assert res.best.score == 0.0  # multi-scale + ±1 → 정확히 도달
    assert res.improved is True
    assert res.lift == float(TARGET)  # seed_score=-TARGET → best 0
    assert res.stop_reason in {"plateau", "converged"}


def test_history_monotone_nondecreasing():
    res = evolve(0, _generate, _dist_oracle(), max_generations=200, k_parents=1)
    assert list(res.history) == sorted(res.history)  # best-so-far 단조 비감소


def test_lineage_of_best_starts_at_seed():
    res = evolve(0, _generate, _dist_oracle(), max_generations=200, k_parents=1)
    chain = res.database.lineage(res.best)
    assert chain[0].generation == 0 and chain[0].parent is None
    assert chain[-1].index == res.best.index


# ── 종료 사유 ─────────────────────────────────────────────────────────────────


def test_plateau_stop_when_no_improvement():
    flat = ScalarOracle(name="flat", kind="test", score=lambda _x: 0.0)
    res = evolve(0, _generate, flat, max_generations=50, k_parents=1, patience=3)
    assert res.stop_reason == "plateau"
    assert res.generations == 3  # patience 만큼만 무개선 후 종료


def test_budget_caps_evaluations():
    res = evolve(0, _generate, _dist_oracle(), max_generations=100, max_evaluations=10, k_parents=1)
    assert res.evaluations <= 10
    assert res.stop_reason == "budget"


def test_target_triggers_converged():
    res = evolve(0, _generate, _dist_oracle(), max_generations=200, k_parents=1, target=-5.0)
    assert res.best.score >= -5.0
    assert res.stop_reason == "converged"


def test_max_generations_zero_only_evaluates_seed():
    res = evolve(0, _generate, _dist_oracle(), max_generations=0)
    assert res.evaluations == 1
    assert res.best.payload == 0
    assert res.generations == 0


# ── load-bearing: read-back 가 equal-budget 에서 blind 를 이긴다 (honest) ────────


def test_guided_beats_blind_at_equal_budget_honest():
    """동일 generator·oracle·평가예산. blind 는 전 공간을 샘플하므로 optimum 도달 *가능*
    (구조적으로 barred 아님) — 단지 gradient 를 못 쓸 뿐. guided 는 read-back 으로 gradient
    를 활용. 유일한 차이 = read-back. 구조 있는 landscape 에서 guided 가 strictly 이긴다."""
    guided = evolve(0, _generate, _dist_oracle(), max_generations=200, k_parents=1, patience=5)
    blind = best_of_n(_generate, _dist_oracle(), n=guided.evaluations)
    assert blind.evaluations == guided.evaluations  # equal-compute, by construction
    assert guided.best.score > blind.best.score  # read-back exploits structure


def test_read_back_can_lose_on_deceptive_landscape():
    """판별력 증명: read-back 가 *항상* 이기는 게 아니다. 0 근처 local 봉우리에 greedy 가
    갇히고, 진짜 고지대(전역)는 멀리 — blind 의 전 공간 샘플이 그걸 친다. read-back 가 진다."""

    def deceptive(x: float) -> float:
        # x<100k: 0 에서 최대(=0), 멀어질수록 감소 → greedy 는 seed(0)에 갇힘.
        # x>=100k: 폭넓은 고지대(~411..500), 전역 최댓값 500 at TARGET.
        if x < 100_000:
            return -float(x) * 0.001
        return 500.0 - abs(x - TARGET) * 0.0001

    oracle = ScalarOracle(name="deceptive", kind="test", score=deceptive)
    guided = evolve(0, _generate, oracle, max_generations=50, k_parents=1, patience=5)
    blind = best_of_n(_generate, oracle, n=max(guided.evaluations, 200))
    assert guided.best.score <= 1e-9  # greedy trapped at local opt (seed 0)
    assert blind.best.score > guided.best.score  # blind escapes via full-space sampling


def test_k_parents_zero_degrades_to_blind():
    """read-back 차단(k_parents=0) → gradient 못 씀 → guided(k_parents=1)보다 나쁨."""
    guided = evolve(0, _generate, _dist_oracle(), max_generations=200, k_parents=1, patience=5)
    no_readback = evolve(0, _generate, _dist_oracle(), max_generations=200, k_parents=0, patience=5)
    assert guided.best.score > no_readback.best.score


def test_best_of_n_empty_generator_is_safe():
    empty = best_of_n(lambda _p, _g: [], _dist_oracle(), n=5)
    assert empty.best is None
    assert empty.stop_reason == "empty"


def test_best_of_n_draws_n_independent_samples():
    """faithful best-of-N: n 회 독립 추출 → evaluations == n (slice rig 아님)."""
    res = best_of_n(_generate, _dist_oracle(), n=37)
    assert res.evaluations == 37
    # 독립 추출이므로 서로 다른 payload 다수 (LCG seed=i)
    assert len({c.payload for c in res.database.all()}) > 1


# ── ScalarOracle ──────────────────────────────────────────────────────────────


def test_scalar_oracle_evaluate_returns_float_score():
    oracle = ScalarOracle(name="double", kind="test", score=lambda x: x * 2)
    score = oracle.evaluate(21)
    assert score.value == 42.0
    assert score.lens == "double"


def test_scalar_from_lens_maps_pass_fail_to_unit_interval():
    passing = OracleLens(name="ok", kind="test", command=("true",))
    failing = OracleLens(name="bad", kind="test", command=("false",))
    pass_runner = lambda _cmd: (0, "PASS")  # noqa: E731
    fail_runner = lambda _cmd: (1, "boom")  # noqa: E731
    assert scalar_from_lens(passing, pass_runner).evaluate(None).value == 1.0
    assert scalar_from_lens(failing, fail_runner).evaluate(None).value == 0.0
