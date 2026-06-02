"""재배맨 production solve 진입 — gated dispatch + 영속 corpus(복리) + telemetry (load-bearing).

oracle_gated_dispatch(harm-free + cheap, 측정 확증)를 *기본 호출 surface*로 승격한다. 이전엔
정책이 라이브러리 함수였고 실 호출 경로는 raw run_evolve였다(정책 미적용). 이 진입이 재배맨 3책무를
한 곳에 닫는다:
  · plan/dispatch — oracle_gated_dispatch (1-shot→풀리면 early-exit / miss면 explore+feedback escalate),
  · 영속 memory — kg_path 주면 LocalKgCorpus(cross-session 복리), 없으면 InMemoryCorpus(휘발),
  · audit — write_cypher 주면 RunRecord 발행(telemetry).

이로써 "harm 0 + 4-6배 cheap + (영속 시) 복리"가 *default*로 적용된다 (raw run_evolve 직접 호출 대신).

# KG: jaebaeman-planfirst-essence-reframe-2026-05-27 (재배맨=plan→dispatch→audit),
#     7cmd-measurement-driven-conditional-dispatch-2026-05-30, prom16-bhgman-ci-design-2026-06-02,
#     lesson-bhgman-collective-intelligence-design-2026-06-02
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from engine.jaebaeman.dispatch_policy import (
    DispatchPolicy,
    DispatchResult,
    oracle_gated_dispatch,
)
from engine.jaebaeman.lifecycle import CypherRunner
from engine.jaebaeman.telemetry import RunRecord, record_to_kg
from engine.legion.evolve_loop import (
    CandidateCorpus,
    Generator,
    InMemoryCorpus,
    LocalKgCorpus,
    ScalarOracle,
)
from engine.kg_local.store import LocalKgStore


@dataclass(frozen=True)
class SolveOutcome:
    """production solve 결과 + 감사 레코드."""

    result: DispatchResult
    run_record: RunRecord

    @property
    def summary(self) -> str:
        return f"{self.result.summary} | record={self.run_record.run_id}"


def _make_corpus(kg_path: str | Path | None) -> CandidateCorpus:
    """kg_path 주면 영속 LocalKgCorpus(복리 기억), 없으면 InMemoryCorpus(휘발)."""
    if kg_path is None:
        return InMemoryCorpus()
    return LocalKgCorpus(LocalKgStore(kg_path))


def solve(
    task: str,
    generator: Generator,
    oracle: ScalarOracle,
    rng: random.Random,
    *,
    kg_path: str | Path | None = None,
    policy: DispatchPolicy | None = None,
    run_id: str = "solve",
    write_cypher: CypherRunner | None = None,
    created_at: str = "",
) -> SolveOutcome:
    """재배맨 production solve. gated dispatch + (kg_path 시)영속 corpus + (write_cypher 시)telemetry.

    rng는 주입식(테스트 결정론). created_at은 호출자가 stamp(datetime 비결정 회피).
    """
    corpus = _make_corpus(kg_path)
    result = oracle_gated_dispatch(task, generator, oracle, corpus, rng, policy)
    record = RunRecord(
        run_id=run_id,
        goal=task[:120],
        planned_seeds=1,
        depth_max=1,
        leaf_count=1,
        dispatched=result.evals,
        collected=1 if result.solved else 0,
        failed=0 if result.solved else 1,
        created_at=created_at,
    )
    if write_cypher is not None:
        record_to_kg(record, write_cypher)
    return SolveOutcome(result=result, run_record=record)


__all__ = ["SolveOutcome", "solve"]
