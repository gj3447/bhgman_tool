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
from engine.legion.repair_stage import (
    REPAIR_KEY,
    make_diagnostic_repair_stage,
    make_repair_stage,
)
from engine.naesengmoon.diagnostic_oracle import (
    CallableDiagnosticOracle,
    feedback_from_value,
)
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


def test_diagnostic_stage_feeds_failure_to_next_attempt_and_preserves_contract():
    seen: list[str] = []

    def evaluate(candidate: str):
        passed = candidate == "answer = 42"
        return feedback_from_value(
            lens="python",
            kind="test",
            passed=passed,
            score=float(passed),
            diagnostic="PASS" if passed else "NameError: replace BROKEN with 42",
        )

    def repair(ctx):
        seen.append(ctx.missing)
        return ctx.current.replace("BROKEN", "42")

    base = CommanderStage(
        name="code-creator",
        verb="실현",
        requires=(),
        provides=("source",),
        run=lambda _ctx: {"source": "answer = BROKEN"},
    )
    stage = make_diagnostic_repair_stage(
        base,
        oracle=CallableDiagnosticOracle("python", "test", evaluate),
        repair=repair,
    )
    out = stage.run({})
    assert out["source"] == "answer = 42"
    assert out[REPAIR_KEY]["mode"] == "diagnostic"
    assert out[REPAIR_KEY]["verified"] is True
    assert out[REPAIR_KEY]["stop_reason"] == "complete"
    assert seen == ["NameError: replace BROKEN with 42"]
    assert (stage.name, stage.verb, stage.requires, stage.provides) == (
        base.name,
        base.verb,
        base.requires,
        base.provides,
    )
    assert Legion().register(stage).run().completed is True


def test_diagnostic_stage_keeps_seed_when_no_candidate_improves():
    def evaluate(candidate: str):
        score = {"seed": 1.0, "regression": 0.0}[candidate]
        return feedback_from_value(
            lens="test",
            kind="test",
            passed=False,
            score=score,
            diagnostic="still red",
        )

    base = CommanderStage(
        name="code-creator",
        verb="실현",
        requires=(),
        provides=("source",),
        run=lambda _ctx: {"source": "seed"},
    )
    stage = make_diagnostic_repair_stage(
        base,
        oracle=CallableDiagnosticOracle("test", "test", evaluate),
        repair=lambda _ctx: "regression",
        max_attempts=1,
    )
    out = stage.run({})
    assert out["source"] == "seed"
    assert out[REPAIR_KEY]["verified"] is False
    assert out[REPAIR_KEY]["improved"] is False


def test_diagnostic_stage_keeps_unverified_improvement_by_default():
    def evaluate(candidate: str):
        return feedback_from_value(
            lens="test",
            kind="test",
            passed=False,
            score={0: 0.0, "improved-but-red": 1.0}[candidate],
            diagnostic="still red",
        )

    stage = make_diagnostic_repair_stage(
        _seed_stage(0, provides=("source",)),
        oracle=CallableDiagnosticOracle("test", "test", evaluate),
        repair=lambda _ctx: "improved-but-red",
        max_attempts=1,
    )
    out = stage.run({})
    assert out["source"] == 0
    assert out[REPAIR_KEY]["verified"] is False
    assert out[REPAIR_KEY]["improved"] is True
    assert out[REPAIR_KEY]["adopted"] is False
    assert out[REPAIR_KEY]["adopt_unverified_improvement"] is False


def test_diagnostic_stage_can_opt_in_to_unverified_improvement():
    def evaluate(candidate):
        return feedback_from_value(
            lens="test",
            kind="test",
            passed=False,
            score={0: 0.0, "improved-but-red": 1.0}[candidate],
            diagnostic="still red",
        )

    stage = make_diagnostic_repair_stage(
        _seed_stage(0, provides=("source",)),
        oracle=CallableDiagnosticOracle("test", "test", evaluate),
        repair=lambda _ctx: "improved-but-red",
        max_attempts=1,
        adopt_unverified_improvement=True,
    )
    out = stage.run({})
    assert out["source"] == "improved-but-red"
    assert out[REPAIR_KEY]["verified"] is False
    assert out[REPAIR_KEY]["improved"] is True
    assert out[REPAIR_KEY]["adopted"] is True
    assert out[REPAIR_KEY]["adopt_unverified_improvement"] is True


def test_repair_telemetry_cannot_overwrite_business_output():
    base = CommanderStage(
        name="business-repair",
        verb="실현",
        requires=(),
        provides=(REPAIR_KEY,),
        run=lambda _ctx: {REPAIR_KEY: "business-value"},
    )
    with pytest.raises(ValueError, match="telemetry_key collides"):
        make_repair_stage(base, oracle=_dist_oracle(), generate=_generate)

    oracle = CallableDiagnosticOracle(
        "test",
        "test",
        lambda candidate: feedback_from_value(
            lens="test",
            kind="test",
            passed=False,
            score=0.0,
            diagnostic=str(candidate),
        ),
    )
    with pytest.raises(ValueError, match="telemetry_key collides"):
        make_diagnostic_repair_stage(base, oracle=oracle, repair=lambda ctx: ctx.current)


def test_custom_telemetry_key_preserves_repair_business_value():
    base = CommanderStage(
        name="business-repair",
        verb="실현",
        requires=(),
        provides=(REPAIR_KEY,),
        run=lambda _ctx: {REPAIR_KEY: "business-value"},
    )
    stage = make_repair_stage(
        base,
        oracle=ScalarOracle(name="flat", kind="test", score=lambda _candidate: 0.0),
        generate=lambda _parents, _generation: (),
        telemetry_key="_pi_repair_telemetry",
    )
    out = stage.run({})
    assert out[REPAIR_KEY] == "business-value"
    assert out["_pi_repair_telemetry"]["improved"] is False


@pytest.mark.parametrize("diagnostic", [False, True])
def test_repair_telemetry_cannot_overwrite_incoming_context(diagnostic: bool):
    base = CommanderStage(
        name="context-collision",
        verb="실현",
        requires=(REPAIR_KEY,),
        provides=("source",),
        run=lambda _ctx: {"source": "seed"},
    )
    if diagnostic:
        oracle = CallableDiagnosticOracle(
            "test",
            "test",
            lambda candidate: feedback_from_value(
                lens="test",
                kind="test",
                passed=False,
                score=0.0,
                diagnostic=str(candidate),
            ),
        )
        stage = make_diagnostic_repair_stage(
            base,
            oracle=oracle,
            repair=lambda ctx: ctx.current,
        )
    else:
        stage = make_repair_stage(base, oracle=_dist_oracle(), generate=_generate)
    with pytest.raises(ValueError, match="input context"):
        stage.run({REPAIR_KEY: "business-value"})
