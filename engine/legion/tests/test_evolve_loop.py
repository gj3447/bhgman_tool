"""evolve_loop 검증 지식 플라이휠 테스트.

핵심 증명: 같은 corpus를 가로질러 세션이 쌓일수록 best가 단조 상승(복리) + feedback(steering)이
load-bearing + oracle-gating(검증분만 누적) + LocalKg 영속(cross-session read-back) + LensScalarOracle
어댑터가 나생문 boolean oracle을 scalar로 감싼다.
"""

from __future__ import annotations

import random

from engine.kg_local.store import LocalKgStore
from engine.legion.evolve_loop import (
    Candidate,
    FnScalarOracle,
    InMemoryCorpus,
    LensScalarOracle,
    LocalKgCorpus,
    ScoredCandidate,
    candidate_id,
    run_evolve,
    run_sessions,
)
from engine.naesengmoon.oracle_lens import OracleLens

_N = 20  # genome = 20-bit "0/1" 문자열. target = all '1' (score = popcount).


class HillClimbGenerator:
    """toy 생성기: best가 있으면 top을 1비트 변이(steer), 없으면 무작위(cold start)."""

    def propose(self, task: str, best, rng: random.Random) -> Candidate:
        if best:
            parent = best[0].candidate
            bits = list(parent.payload)
            i = rng.randrange(_N)
            bits[i] = "1" if bits[i] == "0" else "0"
            return Candidate(
                payload="".join(bits),
                parent=candidate_id(task, parent.payload),
                generation=parent.generation + 1,
            )
        return Candidate(payload="".join(rng.choice("01") for _ in range(_N)))


def _popcount_oracle(pass_min: float = 8.0) -> FnScalarOracle:
    # structured scalar oracle: '1' 개수. pass_min 미만은 oracle-gated(누적 거부).
    return FnScalarOracle(score_fn=lambda task, c: float(c.payload.count("1")), pass_min=pass_min)


def test_equal_budget_consumed():
    run = run_evolve(
        "t",
        budget=50,
        generator=HillClimbGenerator(),
        oracle=_popcount_oracle(0.0),
        corpus=InMemoryCorpus(),
        rng=random.Random(1),
    )
    assert run.evals == 50


def test_flywheel_compounds_across_sessions():
    # 같은 corpus를 가로질러 5세션: best가 단조 비감소 + 최종 > 첫 세션 (복리).
    corpus = InMemoryCorpus()
    runs = run_sessions(
        "t",
        budget=40,
        n_sessions=5,
        generator=HillClimbGenerator(),
        oracle=_popcount_oracle(8.0),
        corpus=corpus,
        base_seed=10,
    )
    scores = [r.best_score for r in runs]
    assert scores == sorted(scores)  # 단조 비감소 (best-ever 보존)
    assert runs[-1].best_score > runs[0].best_score  # 복리 상승
    assert runs[0].read_back == 0  # 첫 세션 = cold (단일 에이전트 baseline)
    assert runs[-1].read_back > 0  # 마지막 세션 = 이전 세션 자산 상속


def test_feedback_is_load_bearing():
    # feedback(steering) ON vs OFF(blind): 같은 세션×예산서 ON이 훨씬 높이 도달.
    fb = run_sessions(
        "t",
        budget=40,
        n_sessions=5,
        generator=HillClimbGenerator(),
        oracle=_popcount_oracle(8.0),
        corpus=InMemoryCorpus(),
        base_seed=10,
        feedback=True,
    )
    abl = run_sessions(
        "t",
        budget=40,
        n_sessions=5,
        generator=HillClimbGenerator(),
        oracle=_popcount_oracle(8.0),
        corpus=InMemoryCorpus(),
        base_seed=10,
        feedback=False,
    )
    assert fb[-1].best_score > abl[-1].best_score + 2.0  # steering이 load-bearing


def test_oracle_gating_rejects_unverified():
    # passed=False는 corpus에 누적 안 됨 (쓰레기 차단).
    corpus = InMemoryCorpus()
    corpus.record("t", ScoredCandidate(Candidate("00"), score=1.0, passed=False))
    assert corpus.read_best("t", 4) == ()
    corpus.record("t", ScoredCandidate(Candidate("11"), score=2.0, passed=True))
    assert len(corpus.read_best("t", 4)) == 1


def test_lens_scalar_oracle_wraps_boolean():
    # 나생문 OracleLens(boolean) → scalar 어댑터. fake runner로 PASS/FAIL.
    lens = OracleLens(name="pytest", kind="test", command=("true",))
    oracle = LensScalarOracle(lens=lens, runner=lambda cmd: (0, "PASS"))
    ok = oracle.score("t", Candidate("x"))
    assert ok.passed and ok.score == 1.0
    fail_oracle = LensScalarOracle(lens=lens, runner=lambda cmd: (1, "boom"))
    bad = fail_oracle.score("t", Candidate("x"))
    assert not bad.passed and bad.score == 0.0


def test_localkg_corpus_persists_cross_session(tmp_path):
    # LocalKg 영속: 세션1이 기록 → 새 store 재로드 → 세션2가 read_back (플라이휠 핵심).
    path = tmp_path / "kg.json"
    c1 = LocalKgCorpus(LocalKgStore(path))
    run_evolve(
        "t",
        budget=40,
        generator=HillClimbGenerator(),
        oracle=_popcount_oracle(8.0),
        corpus=c1,
        rng=random.Random(7),
    )
    # 완전히 새 store 인스턴스(=새 프로세스/세션 시뮬레이션)로 재로드.
    c2 = LocalKgCorpus(LocalKgStore(path))
    best = c2.read_best("t", 4)
    assert len(best) > 0  # 이전 세션 검증분이 디스크에서 복원됨
    run2 = run_evolve(
        "t",
        budget=40,
        generator=HillClimbGenerator(),
        oracle=_popcount_oracle(8.0),
        corpus=c2,
        rng=random.Random(8),
    )
    assert run2.read_back > 0  # cross-session 자산 상속 확인
