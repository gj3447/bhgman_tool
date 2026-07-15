"""evolve 세대 저널 + 재개 멱등 (GAP-3, FIX-B).

핵심 계약: **재개 결과 == fresh 결과**, 그리고 재개는 이미 평가한 세대의 oracle 을 다시
부르지 않는다. 크래시 지점이 어디였든 (특히 plateau 창 안이어도) 이 둘이 성립해야 한다.

# KG: prom16-harness-loop-standard (durable state / resume idempotent),
#     prom16-bhgman-ci-design-2026-06-02 (검증접지합성 loop)
"""

from __future__ import annotations

import pytest

from engine.legion.evolve_loop import _reconstruct_stagnation, evolve
from engine.legion.journal import KIND_EVOLVE_GEN, JsonlJournal
from engine.naesengmoon.oracle_lens import ScalarOracle


class _CountingOracle:
    """oracle 호출 수를 세는 래퍼 — '재지불 0' 을 실제로 증명하는 계측기."""

    def __init__(self, score) -> None:
        self._inner = ScalarOracle(name="t", kind="test", score=score)
        self.calls = 0

    def evaluate(self, candidate):
        self.calls += 1
        return self._inner.evaluate(candidate)


def _climb(parents, generation):
    """단조 개선 landscape: 부모 +1 (없으면 0에서 시작)."""
    return [(parents[0] if parents else 0) + 1]


def _flat(parents, _generation):
    """개선 없는 landscape → plateau 유발."""
    return [parents[0] if parents else 0]


def _oracle(score=float):
    return _CountingOracle(score)


# ------------------------------------------------------------------ 저널 OFF = 현행 동작 보존


def test_journal_off_is_default_and_unchanged():
    o = _oracle()
    res = evolve(0, _climb, o, max_generations=3, patience=2)
    assert res.stop_reason == "budget" and res.generations == 3
    assert res.history == (0.0, 1.0, 2.0, 3.0)


def test_journal_requires_run_id():
    """scope 없는 저널은 서로 다른 run 을 뒤섞는다 → fail-closed."""
    j = JsonlJournal("/tmp/never-written.jsonl")
    with pytest.raises(ValueError, match="run_id"):
        evolve(0, _climb, _oracle(), journal=j, run_id=None)


# ------------------------------------------------------------------------- 재개 = fresh (멱등)


def _crash_after_gen(n: int):
    """n 번째 세대 평가 도중 급사시키는 generate 래퍼."""

    class _Crash(Exception):
        pass

    def _gen(parents, generation):
        if generation > n:
            raise _Crash("kill -9")
        return _climb(parents, generation)

    return _gen, _Crash


def test_resume_equals_fresh_and_repays_nothing(tmp_path):
    jp = tmp_path / "evolve.jsonl"
    fresh = evolve(0, _climb, _oracle(), max_generations=5, patience=3)

    gen, Crash = _crash_after_gen(2)
    o1 = _oracle()
    with pytest.raises(Crash):
        evolve(0, gen, o1, max_generations=5, patience=3, journal=JsonlJournal(jp), run_id="r1")
    assert o1.calls == 3  # seed + gen1 + gen2

    o2 = _oracle()
    resumed = evolve(
        0, _climb, o2, max_generations=5, patience=3, journal=JsonlJournal(jp), run_id="r1"
    )
    assert o2.calls == 3  # gen3,4,5 만 — seed/gen1/gen2 는 재지불 0
    assert resumed.history == fresh.history
    assert resumed.evaluations == fresh.evaluations
    assert resumed.generations == fresh.generations
    assert resumed.stop_reason == fresh.stop_reason
    assert resumed.best.payload == fresh.best.payload
    assert resumed.best.score == fresh.best.score


def test_finished_run_is_fully_idempotent(tmp_path):
    """이미 evolve_done 인 run 을 다시 부르면 oracle 0회로 같은 결과를 낸다."""
    jp = tmp_path / "evolve.jsonl"
    first = evolve(
        0, _climb, _oracle(), max_generations=3, patience=2, journal=JsonlJournal(jp), run_id="r1"
    )
    o = _oracle()
    again = evolve(
        0, _climb, o, max_generations=3, patience=2, journal=JsonlJournal(jp), run_id="r1"
    )
    assert o.calls == 0
    assert again.history == first.history and again.stop_reason == first.stop_reason
    assert again.best.payload == first.best.payload


def test_separate_run_ids_do_not_contaminate(tmp_path):
    """한 저널 파일에 여러 run 이 누적돼도 서로를 오염시키지 않는다 (run scope)."""
    jp = tmp_path / "evolve.jsonl"
    evolve(0, _climb, _oracle(), max_generations=2, journal=JsonlJournal(jp), run_id="r1")
    o = _oracle()
    second = evolve(100, _climb, o, max_generations=2, journal=JsonlJournal(jp), run_id="r2")
    assert o.calls == 3  # r2 는 fresh — r1 의 세대를 물려받지 않는다
    assert second.seed_score == 100.0


# ------------------------------------------------- FIX-B: plateau 창 안에서 크래시해도 멱등


def test_resume_after_plateau_triggering_generation_spawns_no_extra_generation(tmp_path):
    """plateau 를 유발한 세대 직후 크래시 → 재개는 여분 세대(추가 oracle 지출) 없이 종료.

    pre-fix: 재개가 loop 를 다시 돌려 세대를 하나 더 낳아 fresh 보다 긴 history + 추가
    oracle 호출을 냈다 (같은 입력에 다른 결과 = 재개 비멱등).
    기존 evolve 재개 테스트는 단조개선(plateau 없음) landscape 만 덮어 이 창을 놓쳤다.
    """
    jp = tmp_path / "evolve.jsonl"
    # patience=2 → gen1,gen2 무개선이면 gen2 에서 plateau 로 fresh 는 종료한다.
    fresh = evolve(0, _flat, _oracle(), max_generations=10, patience=2)
    assert fresh.stop_reason == "plateau" and fresh.generations == 2

    # gen2 까지 저널되고 evolve_done 직전 급사 (= plateau 창 안 크래시).
    def _crash_before_done(parents, generation):
        if generation > 2:
            raise AssertionError("fresh 는 gen2 에서 plateau 로 멈춰야 한다")
        return _flat(parents, generation)

    class _Crash(Exception):
        pass

    o1 = _oracle()
    j1 = JsonlJournal(jp)

    def _die_on_done(*_a, **_k):
        raise _Crash("kill -9 before evolve_done")

    orig_append = j1.append

    def _append(kind, run_id, unit="", payload=None):
        if kind != KIND_EVOLVE_GEN:
            _die_on_done()
        orig_append(kind, run_id, unit=unit, payload=payload)

    j1.append = _append  # type: ignore[method-assign]
    with pytest.raises(_Crash):
        evolve(0, _crash_before_done, o1, max_generations=10, patience=2, journal=j1, run_id="r1")
    assert o1.calls == 3  # seed + gen1 + gen2 (plateau 유발 세대까지 저널됨)

    o2 = _oracle()
    resumed = evolve(
        0, _flat, o2, max_generations=10, patience=2, journal=JsonlJournal(jp), run_id="r1"
    )
    assert o2.calls == 0, "재개가 여분 세대를 낳아 oracle 을 추가 지불했다"
    assert resumed.generations == fresh.generations  # 여분 세대 없음
    assert resumed.history == fresh.history  # fresh 보다 길지 않음
    assert resumed.evaluations == fresh.evaluations
    assert resumed.stop_reason == "plateau"


def test_plateau_check_is_noop_for_fresh_runs():
    """loop-top plateau 검사가 fresh 실행을 바꾸지 않는다 (양방향)."""
    assert evolve(0, _climb, _oracle(), max_generations=4, patience=1).generations == 4
    assert evolve(0, _climb, _oracle(), max_generations=4, patience=0).generations == 4
    flat = evolve(0, _flat, _oracle(), max_generations=4, patience=0)
    assert flat.stop_reason == "plateau" and flat.generations == 1


# --------------------------------------------------------------------- stagnation 복원 술어


@pytest.mark.parametrize(
    "history,expected",
    [
        ([0.0], 0),
        ([0.0, 1.0, 2.0], 0),  # 계속 개선
        ([0.0, 1.0, 1.0], 1),  # 마지막 1세대 무개선
        ([0.0, 1.0, 1.0, 1.0], 2),
        ([0.0, 0.0, 0.0], 2),
        ([0.0, 1.0, 1.0, 2.0], 0),  # 개선이 카운터를 리셋
    ],
)
def test_reconstruct_stagnation_matches_accumulation(history, expected):
    assert _reconstruct_stagnation(history) == expected
