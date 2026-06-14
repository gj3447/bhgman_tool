"""Legion orchestrator — 7군단장 in-process 합성 (closed loop).

stage를 USES 순서로 등록(프로메테우스→롱기누스→유레카→오캄→나생문→하데스) → run()이
Contract-bound handoff(requires ⊆ accumulated provides)로 순차 실행, stage 사이 나생문
oracle gate(hard, 주입식). 닫힌 루프는 loops>1. substrate = KG context dict.

종착 = 하데스(실현: 추상 spec→구체 코드, APT/SCW). 정방향 합성의 거울 = TPA 역방향
7-stage (tpa-7stage-eureka-core-2026-05-30). 재배맨(출격)은 stage가 아니라 dispatch
substrate(이 run() 루프가 곧 재배맨의 in-process instantiation)이므로 CANONICAL_ORDER 제외.

oracle gate는 주입식 — legion은 occam/oracle_lens에 hard-import로 결합하지 않음
(in-process지만 모듈 결합은 DI로 끊음, ADP).

# KG: adr-seven-commander-legion-architecture-2026-05-27, naesengmoon-wired-ensemble-upgrade-2026-05-27,
#     hades-canonical-2026-05-27 (실현 종착 stage), tpa-7stage-eureka-core-2026-05-30 (역방향 거울)
"""

from __future__ import annotations

from collections.abc import Callable

from engine.legion.legion_models import CommanderStage, LegionRun, StageOutcome

# gate(context) -> (passed, detail). 나생문 oracle gate를 주입 (없으면 gate 생략).
GateFn = Callable[[dict], "tuple[bool, str]"]

# 닫힌 루프 canonical verb 순서 (참조용; 등록 순서가 실제 실행 순서).
# 종착 = 실현(하데스): 검증 통과한 추상 설계를 구체 코드로 내려보냄 (APT/SCW, 유레카 dual).
CANONICAL_ORDER = ("획득", "연결", "창조", "정리", "검증", "실현")


def _missing_requires(stage: CommanderStage, have: set[str]) -> tuple[str, ...]:
    return tuple(k for k in stage.requires if k not in have)


def _missing_provides(stage: CommanderStage, output: dict) -> tuple[str, ...]:
    return tuple(k for k in stage.provides if k not in output)


def _verdict_dict(ctx: dict) -> dict:
    """The naesengmoon verdict from the context as a dict (run-level gates inspect its
    oracle/ensemble content). Tolerates a non-dict / absent verdict → {}."""
    v = ctx.get("verdict")
    return dict(v) if isinstance(v, dict) else {}


class Legion:
    """등록된 군단장 stage를 Contract-bound + gated 파이프라인으로 실행."""

    def __init__(self) -> None:
        self._stages: list[CommanderStage] = []

    def register(self, stage: CommanderStage) -> "Legion":
        self._stages.append(stage)
        return self  # chaining

    @property
    def stage_names(self) -> tuple[str, ...]:
        return tuple(s.name for s in self._stages)

    def run(self, context: dict | None = None, gate: GateFn | None = None) -> LegionRun:
        ctx = dict(context or {})
        have = set(ctx)
        outcomes: list[StageOutcome] = []

        for stage in self._stages:
            missing = _missing_requires(stage, have)
            if missing:
                return LegionRun(
                    outcomes=tuple(outcomes),
                    contract_violation=f"{stage.name} requires {list(missing)} not in context",
                    final_context_keys=tuple(have),
                )

            output = stage.run(dict(ctx))
            lacks = _missing_provides(stage, output)
            if lacks:
                return LegionRun(
                    outcomes=tuple(outcomes),
                    contract_violation=f"{stage.name} did not provide {list(lacks)}",
                    final_context_keys=tuple(have),
                )

            ctx.update(output)
            have |= set(output)
            outcomes.append(StageOutcome(stage.name, stage.verb, True, f"provided {list(output)}"))

            if gate is not None:
                passed, detail = gate(ctx)
                if not passed:
                    outcomes.append(StageOutcome(stage.name, "검증", False, detail))
                    return LegionRun(
                        outcomes=tuple(outcomes),
                        gate_failure=f"oracle gate FAIL after {stage.name}: {detail}",
                        final_context_keys=tuple(have),
                        final_verdict=_verdict_dict(ctx),
                    )

        return LegionRun(
            outcomes=tuple(outcomes),
            completed=True,
            final_context_keys=tuple(have),
            final_verdict=_verdict_dict(ctx),
        )
