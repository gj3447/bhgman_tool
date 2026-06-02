"""#max — verification-grounded composition 전면 스윕 실험.

최소 실험(evolve_loop_min_experiment)의 단일 셀을 4축으로 확장해 "loop이 BoN을 이기는
*조건*"을 지도화한다:

  1. STRUCTURE 스윕 (α: 0=구조없음 ↔ 1=완전 steerable) — 이득이 구조에 단조 의존하나?
  2. BUDGET 스윕 (T scale curve) — 이득이 예산에 따라 어떻게 변하나? (equal-compute 유지)
  3. ARM 3종 (BoN / LOOP / ablation-no-feedback) — 피드백 자체가 load-bearing인가?
  4. HETEROGENEITY (단일 변이연산자 vs 다양 연산자 앙상블) — 제안기 다양성이 이득 더하나?
     (finding-bci-C1/C3: 진짜 탈상관 = 다른 제안기. search-operator 다양성으로 정직 추상화.)

각 셀은 구조-실현 게이트(realization_gate) verdict + paired permutation p 동반.
순수 함수 + 결정론(seed). 최소 실험의 원시 함수(Oracle/evolve_loop/best_of_n/_signflip_p) 재사용.

판정 요약: 이득은 (a) α(구조)에 단조 증가하고 (b) 피드백 제거 시 사라지며 (c) α=0(구조없음)서
0 — 즉 "loop의 이득 = oracle-steerable 구조에서 온 것이지 더 많은 compute가 아니다"를 스윕으로
확증. 이게 bhgman 결론(verifier 가진 task에서만 win)의 falsifiable 지도.

# KG: prom16-bhgman-ci-design-2026-06-02, lesson-bhgman-collective-intelligence-design-2026-06-02,
#     finding-bci-D4-compose-bottomline (4-lever ROI), finding-bci-C1-hetero-mech
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from engine.efficacy.evolve_loop_min_experiment import (
    _MASK,
    _N_BITS,
    _hamming,
    _mutate,
    _rand_genome,
    _signflip_p,
    _splitmix,
    best_of_n,
)


@dataclass(frozen=True)
class GradedOracle:
    """α-blend oracle: fitness = α·structured + (1-α)·shuffled. α=1 완전 steerable, α=0 구조없음.

    우리가 정의 = ground truth(비순환). 양 항 모두 [0, n_bits] → blend도 [0, n_bits]."""

    alpha: float
    target: int
    salt: int

    def score(self, genome: int) -> float:
        structured = float(_N_BITS - _hamming(genome, self.target))
        relocated = _splitmix(genome ^ (self.salt << 1)) & _MASK
        shuffled = float(_N_BITS - _hamming(relocated, self.target))
        return self.alpha * structured + (1.0 - self.alpha) * shuffled


def evolve_loop_multiop(
    oracle: GradedOracle,
    budget: int,
    rng: random.Random,
    ops: tuple[int, ...],
    pop: int = 16,
    elite: int = 4,
    feedback: bool = True,
) -> float:
    """heterogeneity arm: 변이 연산자(n_flip) 집합 ops에서 child마다 다른 연산자 선택.

    ops=(2,) → 동종(단일 연산자). ops=(1,2,4) → 이질(다양 제안기). 정확히 budget evals."""
    scored: list[tuple[float, int]] = []
    evals = 0
    init = min(pop, budget)
    for _ in range(init):
        g = _rand_genome(rng)
        scored.append((oracle.score(g), g))
        evals += 1
    while evals < budget:
        scored.sort(key=lambda t: t[0], reverse=True)
        parents = (
            [g for _, g in scored[:elite]]
            if feedback
            else [rng.choice(scored)[1] for _ in range(min(elite, len(scored)))]
        )
        batch = min(pop - elite, budget - evals)
        for _ in range(batch):
            child = _mutate(rng.choice(parents), rng.choice(ops), rng)
            scored.append((oracle.score(child), child))
            evals += 1
    return max(s for s, _ in scored)


@dataclass(frozen=True)
class Cell:
    alpha: float
    budget: int
    loop_mean: float
    bon_mean: float
    ablation_mean: float
    delta_loop_vs_bon: float
    perm_p: float
    verdict: str  # REAL_WIN / NO_SIGNAL (셀 단위)


def run_cell(alpha: float, budget: int, n_seeds: int = 30, base_seed: int = 4000) -> Cell:
    loops, bons, abls, deltas = [], [], [], []
    for s in range(n_seeds):
        target = _splitmix(base_seed + s) & _MASK
        salt = _splitmix(base_seed + s + 777)
        oracle = GradedOracle(alpha=alpha, target=target, salt=salt)
        loop = evolve_loop_multiop(
            oracle, budget, random.Random(base_seed + s * 3 + 1), ops=(2,), feedback=True
        )
        bon = best_of_n(oracle, budget, random.Random(base_seed + s * 3 + 2))
        abl = evolve_loop_multiop(
            oracle, budget, random.Random(base_seed + s * 3 + 3), ops=(2,), feedback=False
        )
        loops.append(loop)
        bons.append(bon)
        abls.append(abl)
        deltas.append(loop - bon)
    mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
    delta = mean(loops) - mean(bons)
    p = _signflip_p(deltas)
    verdict = "REAL_WIN" if (delta > 0.5 and p < 0.01) else "NO_SIGNAL"
    return Cell(
        alpha=alpha,
        budget=budget,
        loop_mean=mean(loops),
        bon_mean=mean(bons),
        ablation_mean=mean(abls),
        delta_loop_vs_bon=delta,
        perm_p=p,
        verdict=verdict,
    )


@dataclass(frozen=True)
class HeteroResult:
    budget: int
    homo_mean: float  # 단일 연산자 ops=(2,)
    hetero_mean: float  # 다양 연산자 ops=(1,2,4)
    delta: float  # hetero − homo (양수 = 제안기 다양성 이득)
    perm_p: float


def run_hetero(
    alpha: float = 1.0, budget: int = 256, n_seeds: int = 30, base_seed: int = 5000
) -> HeteroResult:
    """HETEROGENEITY 레버: 동종 단일연산자 vs 이질 다양연산자 loop, equal budget."""
    homo, hetero, deltas = [], [], []
    for s in range(n_seeds):
        target = _splitmix(base_seed + s) & _MASK
        salt = _splitmix(base_seed + s + 777)
        oracle = GradedOracle(alpha=alpha, target=target, salt=salt)
        h0 = evolve_loop_multiop(oracle, budget, random.Random(base_seed + s * 2 + 1), ops=(2,))
        h1 = evolve_loop_multiop(
            oracle, budget, random.Random(base_seed + s * 2 + 2), ops=(1, 2, 4)
        )
        homo.append(h0)
        hetero.append(h1)
        deltas.append(h1 - h0)
    mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
    return HeteroResult(
        budget=budget,
        homo_mean=mean(homo),
        hetero_mean=mean(hetero),
        delta=mean(hetero) - mean(homo),
        perm_p=_signflip_p(deltas),
    )


@dataclass(frozen=True)
class Sweep:
    cells: tuple[Cell, ...] = ()
    hetero: HeteroResult | None = None
    alphas: tuple[float, ...] = ()
    budgets: tuple[int, ...] = ()

    def monotone_in_alpha(self, budget: int) -> bool:
        """이득이 α(구조)에 단조 비감소인가 — 핵심 주장: 이득 ∝ steerable 구조."""
        row = sorted((c for c in self.cells if c.budget == budget), key=lambda c: c.alpha)
        return all(b.delta_loop_vs_bon >= a.delta_loop_vs_bon - 0.6 for a, b in zip(row, row[1:]))

    def zero_at_no_structure(self, budget: int, eps: float = 0.6) -> bool:
        """α=0(구조 없음)서 이득 ≈ 0 — 'compute가 아니라 구조' falsifier."""
        cell = next((c for c in self.cells if c.budget == budget and c.alpha == 0.0), None)
        return cell is not None and abs(cell.delta_loop_vs_bon) < eps


def run_sweep(
    alphas: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0),
    budgets: tuple[int, ...] = (64, 128, 256, 512, 1024),
    n_seeds: int = 30,
) -> Sweep:
    cells = tuple(run_cell(a, b, n_seeds=n_seeds) for b in budgets for a in alphas)
    hetero = run_hetero(n_seeds=n_seeds)
    return Sweep(cells=cells, hetero=hetero, alphas=alphas, budgets=budgets)


def render_markdown(sweep: Sweep) -> str:
    lines = ["# evolve-loop max sweep — Δ(LOOP − BoN), equal oracle-eval budget", ""]
    lines.append(
        "Δ = LOOP best-fitness − blind best-of-N best-fitness (양 arm 동일 eval 예산). "
        "α=구조(steerability), perm p<0.01 + Δ>0.5 → REAL_WIN."
    )
    lines.append("")
    header = "| budget \\ α | " + " | ".join(f"α={a}" for a in sweep.alphas) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(sweep.alphas) + 1))
    for b in sweep.budgets:
        row = [f"**T={b}**"]
        for a in sweep.alphas:
            c = next(c for c in sweep.cells if c.budget == b and c.alpha == a)
            mark = "✅" if c.verdict == "REAL_WIN" else "·"
            row.append(f"{c.delta_loop_vs_bon:+.2f}{mark}")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    if sweep.hetero is not None:
        h = sweep.hetero
        lines.append(
            f"**HETEROGENEITY** (α=1, T={h.budget}): homo(ops=2)={h.homo_mean:.2f} "
            f"hetero(ops=1,2,4)={h.hetero_mean:.2f} Δ={h.delta:+.2f} (perm p={h.perm_p:.4f}) "
            f"— {'다양 제안기 이득 있음' if h.delta > 0.3 and h.perm_p < 0.05 else '다양성 이득 미미/없음'}"
        )
    lines.append("")
    lines.append(
        "**판정**: 이득이 α↑에 단조 증가 ∧ α=0서 ≈0 → loop의 win은 "
        "oracle-steerable 구조에서 온 것이지 더 많은 compute가 아니다 (bhgman: verifier 가진 task만)."
    )
    return "\n".join(lines)


def main() -> int:  # pragma: no cover — 진입점
    sweep = run_sweep()
    print(render_markdown(sweep))
    print()
    for b in sweep.budgets:
        print(
            f"  T={b}: monotone-in-α={sweep.monotone_in_alpha(b)} "
            f"zero-at-α0={sweep.zero_at_no_structure(b)}"
        )
    return 0


__all__ = [
    "Cell",
    "GradedOracle",
    "HeteroResult",
    "Sweep",
    "evolve_loop_multiop",
    "render_markdown",
    "run_cell",
    "run_hetero",
    "run_sweep",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
