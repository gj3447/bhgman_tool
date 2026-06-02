"""재배맨 production solve 진입 테스트 — gated dispatch + 영속 corpus + telemetry."""

from __future__ import annotations

import random

from engine.jaebaeman.dispatch_policy import DispatchPolicy
from engine.jaebaeman.dispatch_runtime import solve
from engine.legion.evolve_loop import Candidate, LocalKgCorpus, ScoredCandidate
from engine.kg_local.store import LocalKgStore


class _SolveGen:
    def propose(self, task, best, rng: random.Random) -> Candidate:
        return Candidate("1" * 10)  # 1-shot 정답


class _Popcount:
    def score(self, task, cand) -> ScoredCandidate:
        s = float(cand.payload.count("1"))
        return ScoredCandidate(cand, s, s >= 1.0)


def test_solve_inmemory_solved():
    out = solve(
        "t", _SolveGen(), _Popcount(), random.Random(1),
        policy=DispatchPolicy(solve_threshold=10.0),
    )
    assert out.result.solved
    assert out.result.escalated is False  # 1-shot 풀림 → escalate 안 함
    assert out.run_record.dispatched == out.result.evals == 1
    assert out.run_record.collected == 1 and out.run_record.failed == 0


def test_solve_persists_to_kg(tmp_path):
    # kg_path 주면 검증 해답이 디스크에 영속 → 새 store가 read_back (복리 기억).
    path = tmp_path / "kg.json"
    solve(
        "t", _SolveGen(), _Popcount(), random.Random(2),
        kg_path=path, policy=DispatchPolicy(solve_threshold=10.0),
    )
    fresh = LocalKgCorpus(LocalKgStore(path))
    assert len(fresh.read_best("t", 4)) >= 1  # 이전 solve의 검증분 복원


def test_solve_emits_telemetry():
    calls: list[tuple] = []

    def fake_cypher(query, params=None):
        calls.append((query, params))
        return []

    out = solve(
        "t", _SolveGen(), _Popcount(), random.Random(3),
        policy=DispatchPolicy(solve_threshold=10.0),
        write_cypher=fake_cypher, run_id="r1", created_at="2026-06-02T00:00:00Z",
    )
    assert out.run_record.run_id == "r1"
    assert len(calls) >= 1  # RunRecord 발행됨
