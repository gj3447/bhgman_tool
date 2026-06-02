"""#min — verification-grounded composition (FunSearch loop) 최소 효능 실험.

선행 PROM 3종(prom16-ma-intel / -eci-existence / -bhgman-ci-design)의 결론을 *재는* 첫
실험: "집단 지능 = fan-out 아니라 *외부 oracle 가진 loop*에서 나온다." bhgman의 결정론
oracle(Lean/pytest/cypher-recount/disk-hash)을 가진 task에서 generate→oracle.score→
accumulate(best-K read)→generate 루프가 같은 oracle-eval 예산의 blind best-of-N을 이기나?

핵심 falsifier (bitter lesson + DPI): LOOP가 BoN을 이기는 건 oracle 피드백이 다음 후보를
*조종*할 수 있는 **구조(locality)** 가 있을 때뿐이다.
  · STRUCTURED landscape (near 후보 점수 상관 = 진짜 task) → LOOP ≫ BoN (steering 가능).
  · SHUFFLED landscape (같은 점수 분포, locality 파괴 = 구조 없음) → LOOP ≈ BoN (steer 불가).
이 "구조 없으면 이득 소멸"이 곧 *증거*: 이득은 더 많은 compute가 아니라 oracle-steerable
구조에서 온다. SHUFFLED에서도 LOOP가 이기면 누수/버그 의심(STRUCTURE_LEAK).

순수 함수 + 결정론(seed). LLM/KG/IO 없음 — oracle은 결정론 scalar scorer로 추상화.
oracle-eval 예산은 양 arm 정확히 동일(equal compute). longinus_ab_experiment.py 양식 미러.

# KG: prom16-bhgman-ci-design-2026-06-02 (D3 FunSearch synthesis),
#     lesson-bhgman-collective-intelligence-design-2026-06-02,
#     efficacy-longinus-2026-06-01 (실험 양식), project_bhgman_ab_falsifier_2026_05_30
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

_N_BITS = 24  # genome = 24-bit int. 2^24 공간 — blind 샘플로 target 못 맞히기 충분히 큼.
_MASK = (1 << _N_BITS) - 1


class Scorer(Protocol):
    """결정론 scalar oracle 인터페이스. Oracle/GradedOracle 모두 구조적으로 만족."""

    def score(self, genome: int) -> float: ...


class Landscape(str, Enum):
    STRUCTURED = "STRUCTURED"  # fitness = n - hamming(g,target): 부드러움(locality)
    SHUFFLED = "SHUFFLED"  # 같은 점수 분포, locality 파괴 — steering 신호 없음


def _splitmix(x: int) -> int:
    """결정론 64-bit 해시 (PYTHONHASHSEED 비의존). genome→안정 난수."""
    x = (x + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    return x ^ (x >> 31)


def _hamming(a: int, b: int) -> int:
    return bin((a ^ b) & _MASK).count("1")


@dataclass(frozen=True)
class Oracle:
    """결정론 scalar scorer. 우리가 정의 = ground truth, 비순환. fitness ∈ [0, n_bits]."""

    landscape: Landscape
    target: int
    salt: int  # SHUFFLED 재배치용 seed

    def score(self, genome: int) -> float:
        if self.landscape is Landscape.STRUCTURED:
            return float(_N_BITS - _hamming(genome, self.target))
        # SHUFFLED: 같은 분포를 유지하되 locality 파괴 — genome을 안정 난수 재배치 후 동일 metric.
        relocated = _splitmix(genome ^ (self.salt << 1)) & _MASK
        return float(_N_BITS - _hamming(relocated, self.target))


def _rand_genome(rng: random.Random) -> int:
    return rng.getrandbits(_N_BITS)


def _mutate(genome: int, n_flip: int, rng: random.Random) -> int:
    out = genome
    for _ in range(n_flip):
        out ^= 1 << rng.randrange(_N_BITS)
    return out


def best_of_n(oracle: Scorer, budget: int, rng: random.Random) -> float:
    """ARM-BoN (= 단일 best-of-N = oracle-only filter): budget개 독립 무작위 샘플 중 최고."""
    best = 0.0
    for _ in range(budget):
        best = max(best, oracle.score(_rand_genome(rng)))
    return best


def evolve_loop(
    oracle: Scorer,
    budget: int,
    rng: random.Random,
    pop: int = 16,
    elite: int = 4,
    n_flip: int = 2,
    feedback: bool = True,
) -> float:
    """ARM-LOOP: generate→score→accumulate(best-K read)→mutate. 정확히 budget evals 소비.

    feedback=True: top-elite에서 변이(=oracle 피드백으로 다음 후보 steer, stigmergy).
    feedback=False: history에서 *무작위* 부모 변이(피드백 제거 ablation → BoN으로 붕괴해야).
    """
    scored: list[tuple[float, int]] = []
    evals = 0
    init = min(pop, budget)
    for _ in range(init):
        g = _rand_genome(rng)
        scored.append((oracle.score(g), g))
        evals += 1
    while evals < budget:
        scored.sort(key=lambda t: t[0], reverse=True)
        if feedback:
            parents = [g for _, g in scored[:elite]]
        else:  # ablation: 피드백 없이 본 적 있는 것 중 무작위 부모 (steering 제거)
            parents = [rng.choice(scored)[1] for _ in range(min(elite, len(scored)))]
        batch = min(pop - elite, budget - evals)
        for _ in range(batch):
            child = _mutate(rng.choice(parents), n_flip, rng)
            scored.append((oracle.score(child), child))
            evals += 1
    return max(s for s, _ in scored)


@dataclass(frozen=True)
class ABResult:
    landscape: Landscape
    n_seeds: int
    budget: int
    loop_mean: float
    bon_mean: float
    ablation_mean: float  # feedback 제거 LOOP (BoN으로 붕괴해야)
    delta_loop_vs_bon: float  # LOOP − BoN (양수 = oracle-steering 우위)
    delta_loop_vs_ablation: float  # LOOP − no-feedback (양수 = 피드백 자체의 기여)
    perm_p_loop_vs_bon: float  # paired sign-flip permutation p

    @property
    def summary(self) -> str:
        return (
            f"[{self.landscape.value}] n={self.n_seeds} budget={self.budget}: "
            f"LOOP={self.loop_mean:.2f} BoN={self.bon_mean:.2f} ablation={self.ablation_mean:.2f} "
            f"Δ(loop-bon)={self.delta_loop_vs_bon:+.2f} (perm p={self.perm_p_loop_vs_bon:.4f}) "
            f"Δ(loop-ablation)={self.delta_loop_vs_ablation:+.2f}"
        )


def _signflip_p(deltas: list[float], n_resamples: int = 20000, seed: int = 0) -> float:
    """paired sign-flip permutation p (양측). 결정론(seed). longinus_ab와 동일 방식."""
    if not deltas:
        return 1.0
    obs = abs(sum(deltas) / len(deltas))
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_resamples):
        m = sum(d if rng.random() < 0.5 else -d for d in deltas) / len(deltas)
        if abs(m) >= obs - 1e-12:
            hits += 1
    return hits / n_resamples


def run_ab(
    landscape: Landscape,
    n_seeds: int = 30,
    budget: int = 256,
    base_seed: int = 2000,
) -> ABResult:
    """multi-seed paired A/B. 각 seed = 같은 oracle(target) 마주한 3 arm, 독립 RNG. 결정론."""
    loops, bons, ablations, deltas = [], [], [], []
    for s in range(n_seeds):
        target = _splitmix(base_seed + s) & _MASK
        salt = _splitmix(base_seed + s + 777)
        oracle = Oracle(landscape=landscape, target=target, salt=salt)
        loop = evolve_loop(oracle, budget, random.Random(base_seed + s * 3 + 1), feedback=True)
        bon = best_of_n(oracle, budget, random.Random(base_seed + s * 3 + 2))
        abl = evolve_loop(oracle, budget, random.Random(base_seed + s * 3 + 3), feedback=False)
        loops.append(loop)
        bons.append(bon)
        ablations.append(abl)
        deltas.append(loop - bon)
    mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
    return ABResult(
        landscape=landscape,
        n_seeds=n_seeds,
        budget=budget,
        loop_mean=mean(loops),
        bon_mean=mean(bons),
        ablation_mean=mean(ablations),
        delta_loop_vs_bon=mean(loops) - mean(bons),
        delta_loop_vs_ablation=mean(loops) - mean(ablations),
        perm_p_loop_vs_bon=_signflip_p(deltas),
    )


class GateVerdict(str, Enum):
    REAL_WIN = "REAL_WIN"  # STRUCTURED서 이기고 SHUFFLED선 이득 소멸 = oracle-steering 진짜
    NO_SIGNAL = "NO_SIGNAL"  # STRUCTURED서도 BoN 못 이김 = steerable 구조 없음
    STRUCTURE_LEAK = "STRUCTURE_LEAK"  # SHUFFLED서도 이김 = 누수/버그 (더 많은 compute 의심)


@dataclass(frozen=True)
class RealizationGate:
    """구조-실현 게이트: LOOP의 이득이 oracle-steerable 구조에서 오는지 판정.

    REAL_WIN ⟺ STRUCTURED서 유의하게 이기고(Δ>margin, p<alpha) ∧ SHUFFLED선 이득 사라짐.
    """

    structured: ABResult
    shuffled: ABResult
    verdict: GateVerdict
    reason: str


def realization_gate(
    structured: ABResult, shuffled: ABResult, margin: float = 0.5, alpha: float = 0.01
) -> RealizationGate:
    won_structured = structured.delta_loop_vs_bon > margin and structured.perm_p_loop_vs_bon < alpha
    won_shuffled = shuffled.delta_loop_vs_bon > margin and shuffled.perm_p_loop_vs_bon < alpha
    if won_structured and not won_shuffled:
        v, r = GateVerdict.REAL_WIN, "구조서 유의 우위 + 구조 파괴 시 소멸 = oracle-steering 진짜"
    elif not won_structured:
        v, r = GateVerdict.NO_SIGNAL, "구조 landscape서도 BoN 못 이김 = steerable 신호 없음"
    else:
        v, r = GateVerdict.STRUCTURE_LEAK, "구조 파괴된 SHUFFLED서도 이김 = 누수/버그 의심"
    return RealizationGate(structured=structured, shuffled=shuffled, verdict=v, reason=r)


def main() -> int:  # pragma: no cover — 진입점
    structured = run_ab(Landscape.STRUCTURED)
    shuffled = run_ab(Landscape.SHUFFLED)
    gate = realization_gate(structured, shuffled)
    print(structured.summary)
    print(shuffled.summary)
    print(f"GATE: {gate.verdict.value} — {gate.reason}")
    return 0


__all__ = [
    "ABResult",
    "GateVerdict",
    "Landscape",
    "Oracle",
    "RealizationGate",
    "Scorer",
    "best_of_n",
    "evolve_loop",
    "realization_gate",
    "run_ab",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
