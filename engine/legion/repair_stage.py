"""Repair stage — 1-pass CommanderStage를 oracle-guided repair 루프로 승격하는 어댑터.

legion.run() 은 단일 선형 패스라 stage가 저품질/FAIL 산출을 받아도 재생성(feedback)을
못 한다 (adr-seven-commander-legion-architecture-2026-05-27 §"legion.run 1-pass → loop 승격";
evolve_loop.py docstring). 이 어댑터는 임의 CommanderStage 를 감싸, 첫 패스 산출(seed)을
evolve_loop 의 검증접지 합성 fixpoint(generate → 외부 결정론 oracle.score → best-K read-back)
로 K회 정제한 뒤 *개선됐을 때만* 해당 provides 키를 교체한다.

Legion.run() 자체는 건드리지 않는다 — default_stages/build_default_legion 층에서 wrap 하므로
legion 은 evolve/oracle/generator 로 hard-import 결합하지 않는다 (ADP/DI 언약 보존,
legion.py docstring "legion 은 occam/oracle_lens 에 hard-import 로 결합하지 않음").

정직 경계: 이 어댑터는 repair 루프 *기계*를 production stage 합성에 배선하는 것이지, 그 자체가
equal-compute 인지 우위를 증명하지 않는다. 인지-리프트 주장은 실제 LLM generator + 외부 oracle
로 3-arm equal-compute A/B(ARM_repair > ARM_bestN AND ARM_base)를 통과해야 성립한다
(engine/efficacy 4th gate, dgx vLLM 필요). 결정론 generate+oracle 로는 루프가 구조적으로
동작함(+ 기만적 landscape 에선 seed 유지)만 증명 가능하다.

read-back(best-K)이 unguided best-of-N 과의 유일한 차이 — deceptive landscape 에선 질 수 있으므로
(evolve_loop test_read_back_can_lose_on_deceptive_landscape) 개선 없으면 seed 를 반드시 유지한다.

# KG: adr-seven-commander-legion-architecture-2026-05-27 (legion.run 1-pass → loop 승격),
#     prom16-bhgman-ci-design-2026-06-02 (검증접지합성 #1 ROI), eureka-canonical-2026-05-26,
#     LakatosTree_BhgmanCeilingPierce_20260712/repair-loop-production-wire (Q1)
"""

from __future__ import annotations

from engine.legion.evolve_loop import GenerateFn, evolve
from engine.legion.legion_models import CommanderStage
from engine.naesengmoon.oracle_lens import ScalarOracle

# telemetry 키 — repair 정제 결과를 context 에 첨부(provides 아님, run-level 관찰용).
REPAIR_KEY = "repair"


def make_repair_stage(
    base: CommanderStage,
    *,
    oracle: ScalarOracle,
    generate: GenerateFn,
    seed_key: str | None = None,
    max_generations: int = 4,
    patience: int = 2,
    max_evaluations: int | None = None,
    target: float | None = None,
) -> CommanderStage:
    """base stage를 oracle-guided repair 루프로 승격한 새 CommanderStage 반환.

    name/verb/requires/provides/measure 를 그대로 보존하므로 Legion.run() 의 requires⊆have
    와 provides-present 계약이 동일하게 성립한다(무손실 wrap). 새 stage 는 base 를 실행해
    seed 를 얻고, seed_key(기본 provides[0]) 값을 evolve() 로 K세대 정제하되 **res.improved
    일 때만** 교체한다. 정제 telemetry 는 context[REPAIR_KEY] 로 첨부한다.

    Args:
        base: 감쌀 원 stage.
        oracle: 외부 결정론 fitness (높을수록 좋음). LLM 판정 금지 (DPI 함정).
        generate: (parents, generation) -> 자식 payload 들 (evolve read-back).
        seed_key: 정제 대상 provides 키 (None=provides[0]).
        max_generations: 최대 repair 세대 (bounded; production 은 작게).
        patience: 무개선 허용 세대 수(초과 시 plateau 종료).
        max_evaluations: 누적 oracle 호출 상한(None=무제한). equal-compute 통제 손잡이.
        target: best score 가 이 값 이상이면 즉시 converged 종료(None=비활성).

    Returns:
        CommanderStage — base 와 동일 계약, run() 이 repair 루프로 정제.

    Raises:
        ValueError: base.provides 가 비어 seed_key 를 정할 수 없을 때.
    """
    if seed_key is None:
        if not base.provides:
            raise ValueError(f"{base.name}: provides 가 비어 repair seed_key 를 정할 수 없음")
        seed_key = base.provides[0]
    key = seed_key

    def _looped_run(ctx: dict) -> dict:
        out = dict(base.run(ctx))
        if (
            key not in out
        ):  # base 계약 위반은 Legion.run 의 _missing_provides 가 잡음 — 여기선 no-op
            return out
        res = evolve(
            out[key],
            generate,
            oracle,
            max_generations=max_generations,
            patience=patience,
            max_evaluations=max_evaluations,
            target=target,
        )
        if res.improved and res.best is not None:  # 정직 가드: 개선 없으면 seed 유지(날조 금지)
            out[key] = res.best.payload
        out[REPAIR_KEY] = {
            "seed_key": key,
            "improved": res.improved,
            "lift": res.lift,
            "generations": res.generations,
            "evaluations": res.evaluations,
            "stop_reason": res.stop_reason,
        }
        return out

    return CommanderStage(
        name=base.name,
        verb=base.verb,
        requires=base.requires,
        provides=base.provides,
        run=_looped_run,
        measure=base.measure,
    )


__all__ = ["REPAIR_KEY", "make_repair_stage"]
