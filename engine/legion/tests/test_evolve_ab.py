"""evolve_loop 3-arm A/B 테스트 — 구조 task서 FLYWHEEL이 BON 이김(REAL_WIN), 평평 task서 NO_SIGNAL."""

from __future__ import annotations

import random

from engine.legion.evolve_ab import run_3arm
from engine.legion.evolve_loop import Candidate, ScoredCandidate


class _StructuredGen:
    n_bits = 20

    def propose(self, task, best, rng: random.Random) -> Candidate:
        if best:
            bits = list(best[0].candidate.payload)
            i = rng.randrange(self.n_bits)
            bits[i] = "1" if bits[i] == "0" else "0"
            return Candidate("".join(bits), generation=best[0].candidate.generation + 1)
        return Candidate("".join(rng.choice("01") for _ in range(self.n_bits)))


class _StructuredOracle:
    def score(self, task, candidate) -> ScoredCandidate:
        s = float(candidate.payload.count("1"))
        return ScoredCandidate(candidate, s, s >= 8.0)


class _FlatOracle:
    """구조 없음: 점수가 payload와 무관(고정). steering 불가 → loop 이득 0."""

    def score(self, task, candidate) -> ScoredCandidate:
        return ScoredCandidate(candidate, 10.0, True)


def test_flywheel_real_win_on_structured():
    report = run_3arm(
        "maximize ones",
        budget=30,
        sessions=5,
        make_generator=_StructuredGen,
        oracle=_StructuredOracle(),
        base_seed=42,
    )
    assert report.verdict == "REAL_WIN"
    assert report.delta_flywheel_vs_bon > 0.5
    assert report.flywheel.total_evals == 150  # equal compute (30×5)
    assert report.bon.total_evals == 150


def test_no_signal_on_flat_oracle():
    report = run_3arm(
        "flat",
        budget=30,
        sessions=5,
        make_generator=_StructuredGen,
        oracle=_FlatOracle(),
        base_seed=42,
    )
    # 구조 없으면 모든 arm 동률 → FLYWHEEL이 BON 못 이김.
    assert report.verdict == "NO_SIGNAL"
