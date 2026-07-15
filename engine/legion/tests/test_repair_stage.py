"""repair_stage TDD — 1-pass stage를 oracle-guided repair 루프로 승격하는 어댑터 검증.

결정론 generate + 결정론 oracle 로 LLM 없이 메커니즘을 검증한다. 정직 경계(evolve_loop 와 동일):
이 테스트는 repair 루프 *기계*가 production stage 합성에 무손실 배선됨을 증명하는 것이지, 실제
oracle task 의 equal-compute 인지 우위(engine/efficacy 4th gate, dgx)가 아니다. 핵심 정직
property = 기만적 landscape 에서 seed 를 유지한다(개선 없으면 교체 안 함 = 날조 금지).

# KG: LakatosTree_BhgmanCeilingPierce_20260712/repair-loop-production-wire (Q1),
#     adr-seven-commander-legion-architecture-2026-05-27 (legion.run 1-pass → loop 승격)
"""

from __future__ import annotations

import pytest

from engine.legion.legion import Legion
from engine.legion.legion_models import CommanderStage
from engine.legion.repair_stage import REPAIR_KEY, make_repair_stage
from engine.naesengmoon.oracle_lens import ScalarOracle

SPACE = 1_000_000
TARGET = 987_654
# multi-scale ±step: read-back hill-climb 이 정확히 TARGET 도달 가능 (test_evolve_loop 미러).
_STEPS = (1, -1, 7, -7, 53, -53, 401, -401, 3001, -3001, 21001, -21001)


def _generate(parents, generation):
    if not parents:
        return [(generation * 2654435761 + 12345) % (SPACE + 1)]  # blind 독립 draw
    base = parents[0]
    return [min(max(base + s, 0), SPACE) for s in _STEPS]  # read-back hill-climb


def _dist_oracle() -> ScalarOracle:
    """구조 있는 landscape: TARGET 에 가까울수록 높음 (max 0)."""
    return ScalarOracle(name="dist", kind="test", score=lambda x: float(-abs(x - TARGET)))


def _deceptive_oracle() -> ScalarOracle:
    """기만적 landscape: seed(0) 근처 local 봉우리에 greedy 가 갇힘 → read-back 가 진다."""

    def deceptive(x: float) -> float:
        if x < 100_000:
            return -float(x) * 0.001  # 0 에서 최대, 멀어질수록 감소
        return 500.0 - abs(x - TARGET) * 0.0001  # 전역 고지대(멀리)

    return ScalarOracle(name="deceptive", kind="test", score=deceptive)


def _seed_stage(seed: int, *, provides: tuple[str, ...] = ("x",), measure=None) -> CommanderStage:
    """모든 provides 키를 seed 로 채우는 1-pass 창조 stage (repair 대상)."""
    return CommanderStage(
        name="creator",
        verb="창조",
        requires=(),
        provides=provides,
        run=lambda _ctx: {p: seed for p in provides},
        measure=measure,
    )


def test_upgrades_seed_toward_optimum():
    stage = make_repair_stage(
        _seed_stage(0), oracle=_dist_oracle(), generate=_generate, max_generations=200, patience=5
    )
    out = stage.run({})
    assert out["x"] == TARGET  # multi-scale hill-climb reaches exact optimum
    assert out[REPAIR_KEY]["improved"] is True
    assert out[REPAIR_KEY]["lift"] == float(TARGET)  # seed_score -TARGET → best 0


def test_registers_and_legion_run_completes():
    stage = make_repair_stage(
        _seed_stage(0), oracle=_dist_oracle(), generate=_generate, max_generations=200, patience=5
    )
    run = Legion().register(stage).run()
    assert run.completed is True  # wrapped stage satisfies the same Contract
    assert "x" in run.final_context_keys


def test_keeps_seed_on_deceptive_landscape():
    """정직 가드: read-back 가 지는 landscape 에선 seed 를 유지, 개선을 날조하지 않는다."""
    stage = make_repair_stage(
        _seed_stage(0),
        oracle=_deceptive_oracle(),
        generate=_generate,
        max_generations=50,
        patience=5,
    )
    out = stage.run({})
    assert out["x"] == 0  # greedy trapped at local opt (seed) — kept honestly, not fabricated
    assert out[REPAIR_KEY]["improved"] is False
    assert out[REPAIR_KEY]["lift"] <= 1e-9


def test_preserves_contract_and_measure():
    sentinel = object()
    base = _seed_stage(0, provides=("y", "z"), measure=lambda _ctx: sentinel)
    stage = make_repair_stage(base, oracle=_dist_oracle(), generate=_generate, max_generations=200)
    assert (stage.name, stage.verb) == (base.name, base.verb)
    assert stage.requires == base.requires and stage.provides == base.provides
    assert (
        stage.measure({"any": 1}) is sentinel
    )  # measure preserved verbatim (W2-A dispatch intact)
    out = stage.run({})
    assert out[REPAIR_KEY]["seed_key"] == "y"  # defaults to provides[0]
    assert out["y"] == TARGET  # first provides key repaired
    assert out["z"] == 0  # other provides key untouched but still present (Contract intact)


def test_raises_without_provides():
    empty = CommanderStage(name="void", verb="창조", requires=(), provides=(), run=lambda _c: {})
    with pytest.raises(ValueError, match="provides"):
        make_repair_stage(empty, oracle=_dist_oracle(), generate=_generate)


# ------------------------------- 저널 배선 (GAP-3 / FIX-A: evolve 의 유일한 프로덕션 호출부)


def test_journal_off_by_default_writes_nothing(tmp_path):
    """반대 방향: journal_path 없으면 저널 동작 없음 (현행 동작 보존)."""
    stage = make_repair_stage(
        _seed_stage(0), oracle=_dist_oracle(), generate=_generate, max_generations=200, patience=5
    )
    assert stage.run({})["x"] == TARGET
    assert list(tmp_path.iterdir()) == []


def test_journal_path_reaches_evolve_and_checkpoints_generations(tmp_path):
    """repair_stage 가 evolve 에 저널을 실제로 넘긴다 — 배선 부재면 파일이 안 생긴다."""
    from engine.legion.journal import KIND_EVOLVE_DONE, KIND_EVOLVE_GEN, JsonlJournal

    jp = tmp_path / "repair.jsonl"
    stage = make_repair_stage(
        _seed_stage(0),
        oracle=_dist_oracle(),
        generate=_generate,
        max_generations=200,
        patience=5,
        journal_path=jp,
    )
    out = stage.run({"cycle_id": "c1"})
    assert out["x"] == TARGET

    j = JsonlJournal(jp)
    run_id = "repair:creator:x:c1"  # stage 정체성 + cycle_id 로 scope
    assert j.completed_units(KIND_EVOLVE_GEN, run_id)  # 세대가 체크포인트됨
    assert j.has(KIND_EVOLVE_DONE, run_id)  # 종료 마커


def test_repair_resume_is_idempotent_and_repays_no_oracle(tmp_path):
    """같은 cycle_id 로 재실행 = 재개 → oracle 재지불 0, 결과 동일 (evolve 멱등 계약)."""
    jp = tmp_path / "repair.jsonl"
    calls = {"n": 0}

    def counting(x):
        calls["n"] += 1
        return float(-abs(x - TARGET))

    oracle = ScalarOracle(name="dist", kind="test", score=counting)
    stage = make_repair_stage(
        _seed_stage(0),
        oracle=oracle,
        generate=_generate,
        max_generations=200,
        patience=5,
        journal_path=jp,
    )
    first = stage.run({"cycle_id": "c1"})
    spent = calls["n"]
    assert spent > 0

    calls["n"] = 0
    second = stage.run({"cycle_id": "c1"})  # 크래시 후 같은 cycle 재실행
    assert calls["n"] == 0  # 재지불 0
    assert second["x"] == first["x"]
    assert second[REPAIR_KEY]["lift"] == first[REPAIR_KEY]["lift"]
    assert second[REPAIR_KEY]["stop_reason"] == first[REPAIR_KEY]["stop_reason"]


def test_different_cycles_do_not_share_journal_scope(tmp_path):
    """다른 cycle_id 는 서로의 세대를 물려받지 않는다 (run scope)."""
    jp = tmp_path / "repair.jsonl"
    calls = {"n": 0}

    def counting(x):
        calls["n"] += 1
        return float(-abs(x - TARGET))

    stage = make_repair_stage(
        _seed_stage(0),
        oracle=ScalarOracle(name="dist", kind="test", score=counting),
        generate=_generate,
        max_generations=200,
        patience=5,
        journal_path=jp,
    )
    stage.run({"cycle_id": "c1"})
    calls["n"] = 0
    stage.run({"cycle_id": "c2"})
    assert calls["n"] > 0  # c2 는 fresh
