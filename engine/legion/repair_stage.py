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

from engine.legion.diagnostic_repair import (
    CandidateFingerprintFn,
    CandidateSnapshotFn,
    EventSink,
    RepairFn,
    candidate_fingerprint,
    candidate_snapshot,
    diagnostic_repair,
)
from engine.legion.evolve_loop import GenerateFn, evolve
from engine.legion.legion_models import CommanderStage
from engine.naesengmoon.diagnostic_oracle import DiagnosticOracle
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
    telemetry_key: str = REPAIR_KEY,
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
    if telemetry_key in base.provides:
        raise ValueError(f"{base.name}: telemetry_key collides with provides: {telemetry_key}")
    key = seed_key

    def _looped_run(ctx: dict) -> dict:
        if telemetry_key in ctx:
            raise ValueError(f"{base.name}: telemetry_key already exists in input context")
        out = dict(base.run(ctx))
        if (
            key not in out
        ):  # base 계약 위반은 Legion.run 의 _missing_provides 가 잡음 — 여기선 no-op
            return out
        if telemetry_key in out:
            raise ValueError(f"{base.name}: telemetry_key already exists in stage output")
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
        out[telemetry_key] = {
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


def make_diagnostic_repair_stage(
    base: CommanderStage,
    *,
    oracle: DiagnosticOracle,
    repair: RepairFn,
    seed_key: str | None = None,
    max_attempts: int = 3,
    max_evaluations: int | None = None,
    max_wall_seconds: float | None = 300.0,
    max_repeated_states: int = 2,
    fingerprint: CandidateFingerprintFn = candidate_fingerprint,
    snapshot: CandidateSnapshotFn = candidate_snapshot,
    event_sink: EventSink | None = None,
    adopt_unverified_improvement: bool = False,
    telemetry_key: str = REPAIR_KEY,
) -> CommanderStage:
    """Wrap a stage with prompt-visible diagnostic repair and re-verification.

    Unlike :func:`make_repair_stage`, which gives a generator only scalar-ranked
    parents, this adapter passes the last oracle diagnostic to ``repair`` through
    ``RepairContext.feedback``/``missing``.  The wrapped stage keeps its original
    Contract and, by default, only replaces the seed when an authoritative oracle
    passes.  A scalar improvement that still fails verification remains visible in
    telemetry but is not adopted unless ``adopt_unverified_improvement=True`` is
    explicitly selected for an experimental caller.

    This is opt-in because only tasks with a deterministic external verifier
    qualify.  Narrative, canon, and subjective judgment stages must not be
    wrapped with an LLM-as-oracle approximation.
    """
    if seed_key is None:
        if not base.provides:
            raise ValueError(f"{base.name}: provides is empty; cannot select repair seed_key")
        seed_key = base.provides[0]
    if telemetry_key in base.provides:
        raise ValueError(f"{base.name}: telemetry_key collides with provides: {telemetry_key}")
    key = seed_key

    def _looped_run(ctx: dict) -> dict:
        if telemetry_key in ctx:
            raise ValueError(f"{base.name}: telemetry_key already exists in input context")
        out = dict(base.run(ctx))
        if key not in out:
            return out
        if telemetry_key in out:
            raise ValueError(f"{base.name}: telemetry_key already exists in stage output")
        result = diagnostic_repair(
            out[key],
            repair,
            oracle,
            max_attempts=max_attempts,
            max_evaluations=max_evaluations,
            max_wall_seconds=max_wall_seconds,
            max_repeated_states=max_repeated_states,
            fingerprint=fingerprint,
            snapshot=snapshot,
            event_sink=event_sink,
        )
        adopted = result.verified or (adopt_unverified_improvement and result.improved)
        if adopted:
            out[key] = result.output
        out[telemetry_key] = {
            "mode": "diagnostic",
            "run_id": result.run_id,
            "seed_key": key,
            "verified": result.verified,
            "improved": result.improved,
            "adopted": adopted,
            "adopt_unverified_improvement": adopt_unverified_improvement,
            "stop_reason": result.stop.value,
            "repairs": result.repairs,
            "evaluations": result.evaluations,
            "reported_input_tokens": result.reported_input_tokens,
            "reported_output_tokens": result.reported_output_tokens,
            "best_attempt": result.best.index,
            "attempts": [
                {
                    "index": item.index,
                    "status": item.feedback.status,
                    "score": item.feedback.score,
                    "candidate_fingerprint": item.candidate_fingerprint,
                    "diagnostic_fingerprint": item.feedback.fingerprint,
                }
                for item in result.attempts
            ],
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


__all__ = ["REPAIR_KEY", "make_diagnostic_repair_stage", "make_repair_stage"]
