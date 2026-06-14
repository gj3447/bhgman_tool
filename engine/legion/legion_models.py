"""Legion value objects — 7군단장 합성 orchestrator (in-process composition).

각 군단장 = substrate(KG dict context) 위 transform stage. handoff는 Contract-bound
(requires ⊆ accumulated provides), stage 사이 나생문 oracle gate(hard).

# KG: adr-seven-commander-legion-architecture-2026-05-27 (§4 닫힌 루프 / §1 substrate),
#     apt-contract-root-axiom-2026-05-27 (handoff = interface 계약), naesengmoon-wired-ensemble-upgrade-2026-05-27
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

# 군단장 stage: KG context(dict) → 새로 제공하는 키/값(dict). 순수 transform.
StageFn = Callable[[dict], dict]


@dataclass(frozen=True)
class CommanderStage:
    """한 군단장. requires/provides = 인터페이스 계약(Contract, 재배맨 dual)."""

    name: str
    verb: str  # 획득/연결/창조/정리/검증/실현 (실현=하데스 종착, abstract→concrete)
    requires: tuple[str, ...]
    provides: tuple[str, ...]
    run: StageFn


@dataclass(frozen=True)
class StageOutcome:
    stage: str
    verb: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class LegionRun:
    """파이프라인 1회 실행 결과. 닫힌 루프는 loops>1로 표현."""

    outcomes: tuple[StageOutcome, ...] = ()
    completed: bool = False
    contract_violation: str | None = None
    gate_failure: str | None = None
    final_context_keys: tuple[str, ...] = field(default_factory=tuple)
    # The naesengmoon (검증) verdict from the final context, surfaced so run-level gates can
    # inspect its CONTENT (oracle / ensemble) — a stage can complete ok=True yet carry a
    # FAIL/REJECT verdict. Empty when no verify stage ran.
    final_verdict: dict = field(default_factory=dict)

    @property
    def ran(self) -> int:
        return len(self.outcomes)
