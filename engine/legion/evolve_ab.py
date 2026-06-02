"""evolve_loop 3-arm equal-budget A/B — 플라이휠이 단일 에이전트를 실제로 이기나 측정.

3 arm, 모두 *동일 총 oracle-eval 예산*(budget×sessions):
  · BON          — blind best-of-(B×S). feedback off, corpus 없음 = "예산 B×S 받은 단일 에이전트".
  · LOOP_NOMEM   — feedback on, 세션마다 fresh corpus(세션 내 steering만). cross-session 기억 없음.
  · FLYWHEEL     — feedback on, corpus 영속(세션 가로질러 복리). 본 시스템의 주장.

판정: FLYWHEEL이 BON을 margin 초과로 이기면 REAL_WIN(시스템 > 단일 에이전트). memory_adds =
FLYWHEEL > LOOP_NOMEM (cross-session 기억이 세션내 steering 위에 *추가* 이득 주나).

generator/oracle 주입식(generic) — toy(결정론)·LlmGenerator·실 Lean/pytest oracle 모두 동일 하네스.
equal-compute 축 = oracle-eval 횟수(=generate-verify 사이클). LLM 토큰축은 generator.output_tokens로 별도 회계.

# KG: prom16-bhgman-ci-design-2026-06-02, lesson-bhgman-collective-intelligence-design-2026-06-02,
#     efficacy-longinus-2026-06-01 (A/B 양식)
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from engine.legion.evolve_loop import (
    Candidate,
    CandidateCorpus,
    Generator,
    InMemoryCorpus,
    ScalarOracle,
    ScoredCandidate,
    run_evolve,
    run_sessions,
)


@dataclass(frozen=True)
class ArmResult:
    arm: str
    best_score: float
    total_evals: int


@dataclass(frozen=True)
class ABReport:
    task: str
    bon: ArmResult
    loop_nomem: ArmResult
    flywheel: ArmResult
    verdict: str  # REAL_WIN / NO_SIGNAL
    memory_adds: bool  # FLYWHEEL > LOOP_NOMEM (cross-session 기억 추가 이득)

    @property
    def delta_flywheel_vs_bon(self) -> float:
        return self.flywheel.best_score - self.bon.best_score

    @property
    def delta_flywheel_vs_nomem(self) -> float:
        return self.flywheel.best_score - self.loop_nomem.best_score

    @property
    def summary(self) -> str:
        return (
            f"[{self.task}] BON={self.bon.best_score:.3f} "
            f"LOOP_NOMEM={self.loop_nomem.best_score:.3f} FLYWHEEL={self.flywheel.best_score:.3f} "
            f"Δ(fly-bon)={self.delta_flywheel_vs_bon:+.3f} → {self.verdict} "
            f"(memory_adds={self.memory_adds})"
        )


def run_3arm(
    task: str,
    budget: int,
    sessions: int,
    make_generator: Callable[[], Generator],
    oracle: ScalarOracle,
    make_corpus: Callable[[], CandidateCorpus] = InMemoryCorpus,
    margin: float = 0.5,
    base_seed: int = 0,
) -> ABReport:
    """3 arm을 동일 총 예산(budget×sessions)으로 실행. make_* factory = arm마다 fresh 상태."""
    total = budget * sessions

    bon = run_evolve(
        task,
        total,
        make_generator(),
        oracle,
        make_corpus(),
        rng=random.Random(base_seed + 1),
        feedback=False,
    )

    nomem_best = float("-inf")
    for s in range(sessions):  # 세션마다 fresh corpus = cross-session 기억 차단
        r = run_evolve(
            task,
            budget,
            make_generator(),
            oracle,
            make_corpus(),
            rng=random.Random(base_seed + 100 + s),
            feedback=True,
        )
        nomem_best = max(nomem_best, r.best_score)

    fly_runs = run_sessions(  # 영속 corpus = 플라이휠
        task,
        budget,
        sessions,
        make_generator(),
        oracle,
        make_corpus(),
        base_seed=base_seed + 200,
        feedback=True,
    )
    fly_best = fly_runs[-1].best_score

    verdict = "REAL_WIN" if fly_best > bon.best_score + margin else "NO_SIGNAL"
    return ABReport(
        task=task,
        bon=ArmResult("BON", bon.best_score, total),
        loop_nomem=ArmResult("LOOP_NOMEM", nomem_best, total),
        flywheel=ArmResult("FLYWHEEL", fly_best, total),
        verdict=verdict,
        memory_adds=fly_best > nomem_best + margin,
    )


# ── runnable demo (결정론, 백엔드 불요) — structured popcount task ─────────────
class _DemoGenerator:
    """demo 생성기: best top을 1비트 변이(steer) / 없으면 무작위. 결정론."""

    n_bits = 20

    def propose(self, task: str, best, rng: random.Random) -> Candidate:
        if best:
            bits = list(best[0].candidate.payload)
            i = rng.randrange(self.n_bits)
            bits[i] = "1" if bits[i] == "0" else "0"
            return Candidate("".join(bits), generation=best[0].candidate.generation + 1)
        return Candidate("".join(rng.choice("01") for _ in range(self.n_bits)))


@dataclass(frozen=True)
class _DemoOracle:
    """demo scalar oracle: '1' 개수 (structured). pass_min 미만은 검증 실패(누적 거부)."""

    pass_min: float = 8.0

    def score(self, task: str, candidate: Candidate) -> ScoredCandidate:
        s = float(candidate.payload.count("1"))
        return ScoredCandidate(candidate, s, s >= self.pass_min)


def main() -> int:  # pragma: no cover — 진입점
    report = run_3arm(
        task="maximize ones (demo structured task)",
        budget=30,
        sessions=5,
        make_generator=_DemoGenerator,
        oracle=_DemoOracle(),
        base_seed=42,
    )
    print(report.summary)
    return 0


__all__ = ["ABReport", "ArmResult", "run_3arm"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
