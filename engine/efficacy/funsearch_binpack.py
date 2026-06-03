"""engine/efficacy — the FAIR test the close-postmortem said was never run (FunSearch regime).

prom16-evolve-loop-revival §3 + postmortem 2026-06-02: composition_ab tested the loop in the
regime where best-of-N is *provably optimal* (independent toy functions + binary 2-test oracle +
greedy, no island). That negative was a regime artifact. This module builds the FunSearch regime
instead — the one fair test:

  · ONE hard problem with a big search space   — online bin-packing heuristic (FunSearch's own bench)
  · GRADED oracle (gradient to climb)          — mean (lower_bound / bins_used) ∈ (0,1], continuous
  · leak-resistant                             — you either pack well or not; no test to delete
  · REAL island model (F3)                     — n islands, per-island best-K parents, round-robin
  · read-back with score feedback (F4)         — parent code + its PUBLIC score fed into the prompt

PUBLIC instances = read-back/selection signal, HIDDEN instances = eval (non-circular split).
Equal generation-token budget across arms. The FunSearch comparison:

  ARM1 best-of-N      — N independent heuristics, pick best by PUBLIC score, eval on HIDDEN. (no read-back)
  ARM2 island-evolve  — F3 islands + read-back(parent code + PUBLIC score), iterate to budget.   (the loop)

realized = ARM2's HIDDEN score beats ARM1's, paired across seeds, bootstrap CI lower bound > 0.

Built GATE-FIRST (not conclusion-first — the postmortem's process lesson). test_funsearch_binpack.py
proves it fires BOTH ways with an injected fake LLM + a FAIRNESS self-check: a read-back-ignoring
fake yields ARM2 ≈ ARM1 (no spurious win), and ARM1 uses the identical generator (not crippled).

# KG: lesson-premature-close-confirmation-toward-closure-2026-06-02 (proof-analysis),
#     prom16-evolve-loop-revival-2026-06-02, prom16-bhgman-ci-design-2026-06-02
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field

from engine.efficacy.p1_oracle_rerank_pilot import _bootstrap_ci, _extract_code, _ollama

CompleteFn = Callable[[list[dict], int], "tuple[str, int]"]

_CAP = 1.0
_ITEMS_PER_INSTANCE = 50
_TIMEOUT_S = 8

_SYS = {
    "role": "system",
    "content": "You are an algorithms expert. Return ONLY a single ```python code block "
    "defining the requested function. No explanation.",
}
_TASK = (
    "Write `def priority(item, bins):` for ONLINE bin packing. `item` is a float size; "
    "`bins` is a list of remaining capacities of the bins that CAN fit the item. Return a list "
    "of the SAME length as `bins` — a score per bin; the bin with the HIGHEST score is chosen "
    "(higher = prefer). Design the scoring to minimise the total number of bins used. "
    "Return ONLY the function — no docstring, no comments, keep it short (a few lines)."
)

# subprocess scorer: exec candidate `priority`, run online packing over instances, print mean
# (lower_bound / bins_used). Isolated + timeout — arbitrary LLM code never touches the parent.
_RUNNER = """
import sys, json, math
{code}
def _pack(items, cap):
    bins = []
    for it in items:
        feas = [i for i, b in enumerate(bins) if b >= it - 1e-9]
        if feas:
            pr = priority(it, [bins[i] for i in feas])
            if not isinstance(pr, (list, tuple)) or len(pr) != len(feas):
                raise ValueError("priority must return a list matching bins length")
            j = feas[max(range(len(feas)), key=lambda k: pr[k])]
            bins[j] -= it
        else:
            bins.append(cap - it)
    return len(bins)
d = json.load(sys.stdin)
cap = d["cap"]; ratios = []
for items in d["instances"]:
    nb = _pack(items, cap)
    lb = math.ceil(sum(items) / cap)
    ratios.append(lb / nb if nb else 0.0)
print(sum(ratios) / len(ratios))
"""


@dataclass
class BinPackTask:
    public: list[list[float]]  # read-back/selection signal instances
    hidden: list[list[float]]  # held-out eval instances
    cap: float = _CAP


def make_task(
    seed: int, n_public: int = 5, n_hidden: int = 5, dist: str = "uniform"
) -> BinPackTask:
    """결정론 bin-packing task (seed 고정). dist=uniform U[0.1,0.7] / weibull(FunSearch 분포)."""
    rng = random.Random(seed)

    def _instance() -> list[float]:
        if dist == "weibull":  # FunSearch가 쓴 분포 — 휴리스틱 선택이 가장 민감
            return [
                min(0.99, round(rng.weibullvariate(0.45, 3.0), 3))
                for _ in range(_ITEMS_PER_INSTANCE)
            ]
        return [round(rng.uniform(0.1, 0.7), 3) for _ in range(_ITEMS_PER_INSTANCE)]

    return BinPackTask(
        public=[_instance() for _ in range(n_public)],
        hidden=[_instance() for _ in range(n_hidden)],
    )


def score_heuristic(code: str, instances: list[list[float]], cap: float) -> float:
    """GRADED oracle: mean(lower_bound / bins_used) ∈ (0,1], 높을수록 좋음. 에러/timeout → 0.0."""
    script = _RUNNER.format(code=code)
    payload = json.dumps({"cap": cap, "instances": instances})
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(script)
        path = f.name
    try:
        p = subprocess.run(  # noqa: S603
            [sys.executable, path],
            input=payload,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
        )
        if p.returncode != 0:
            return 0.0
        return float(p.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError):
        return 0.0
    finally:
        os.unlink(path)


def _gen(
    complete: CompleteFn, seed: int, parents: list[tuple[str, float]] | None = None
) -> tuple[str, int]:
    """1 heuristic 생성. parents(코드+PUBLIC 점수) 있으면 read-back(F4 점수 피드백) 프롬프트."""
    if parents:
        prior = "\n\n".join(
            f"# prior heuristic (score {s:.3f} — higher is better, improve it):\n{c}"
            for c, s in parents
        )
        content = f"{_TASK}\n\nImprove on these prior heuristics (keep what scores high):\n{prior}"
    else:
        content = _TASK
    text, toks = complete([_SYS, {"role": "user", "content": content}], seed)
    return _extract_code(text), toks


class IslandDatabase:
    """F3 island program-database — n 분리 population, island별 best-K parent, round-robin + migration.

    greedy global top-K(이전 best_k)의 다양성 0 문제를 고친다 — FunSearch 승리의 load-bearing 부품.
    """

    def __init__(self, n_islands: int) -> None:
        self.islands: list[list[tuple[str, float]]] = [[] for _ in range(max(1, n_islands))]

    def add(self, island: int, code: str, score: float) -> None:
        self.islands[island % len(self.islands)].append((code, score))

    def best_in(self, island: int, k: int) -> list[tuple[str, float]]:
        pool = self.islands[island % len(self.islands)]
        return sorted(pool, key=lambda x: -x[1])[: max(1, k)]

    def best_overall(self) -> tuple[str, float] | None:
        allc = [c for isl in self.islands for c in isl]
        return max(allc, key=lambda x: x[1]) if allc else None

    def migrate(self) -> None:
        """각 island의 best를 다음 island로 복제 (FunSearch migration, 조기수렴 완화)."""
        bests = [max(isl, key=lambda x: x[1]) if isl else None for isl in self.islands]
        n = len(self.islands)
        for i, b in enumerate(bests):
            if b is not None:
                self.islands[(i + 1) % n].append(b)


def arm_best_of_n(
    task: BinPackTask, complete: CompleteFn, budget: int, seed0: int
) -> tuple[float, int]:
    """ARM1 — N 독립 heuristic, PUBLIC 최고 pick, HIDDEN 평가 (read-back 無, 동일 generator)."""
    cands: list[tuple[str, float]] = []
    tok = 0
    i = 0
    while tok < budget:
        code, t = _gen(complete, seed0 + i)
        tok += t
        i += 1
        cands.append((code, score_heuristic(code, task.public, task.cap)))
    best = max(cands, key=lambda x: x[1])
    return score_heuristic(best[0], task.hidden, task.cap), tok


def arm_island_evolve(
    task: BinPackTask,
    complete: CompleteFn,
    budget: int,
    seed0: int,
    *,
    n_islands: int = 4,
    k_parents: int = 2,
) -> tuple[float, int]:
    """ARM2 — F3 island + read-back 루프, HIDDEN 평가. ARM1과 유일 차이 = read-back/island."""
    db = IslandDatabase(n_islands)
    tok = 0
    i = 0
    for isl in range(n_islands):  # seed: island당 1 독립 생성
        if tok >= budget:
            break
        code, t = _gen(complete, seed0 + i)
        tok += t
        i += 1
        db.add(isl, code, score_heuristic(code, task.public, task.cap))
    isl = 0
    gen = 0
    while tok < budget:
        parents = db.best_in(isl, k_parents)
        code, t = _gen(complete, seed0 + i, parents=parents)
        tok += t
        i += 1
        db.add(isl, code, score_heuristic(code, task.public, task.cap))
        isl = (isl + 1) % n_islands
        gen += 1
        if gen % (n_islands * 2) == 0:
            db.migrate()
    best = db.best_overall()
    return (score_heuristic(best[0], task.hidden, task.cap) if best else 0.0), tok


@dataclass
class FunSearchVerdict:
    realized: bool
    mean_arm1: float
    mean_arm2: float
    lift: tuple = (0.0, 0.0, 0.0)  # (mean diff arm2-arm1, lo95, hi95)
    per_seed: list = field(default_factory=list)  # [(arm1_hidden, arm2_hidden)]
    gen_tokens: dict = field(default_factory=dict)
    n_seeds: int = 0
    reason: str = ""


def run_gate(
    seeds: list[int],
    complete: CompleteFn = _ollama,
    *,
    budget_tokens: int,
    n_islands: int = 4,
    dist: str = "uniform",
) -> FunSearchVerdict:
    """seed당 task 1개 → (ARM1 best-of-N, ARM2 island-evolve) HIDDEN 점수 쌍. 동일 토큰 예산."""
    pairs: list[tuple[float, float]] = []
    tk = {"best_of_n": 0, "island_evolve": 0}
    for s in seeds:
        task = make_task(s, dist=dist)
        a1, t1 = arm_best_of_n(task, complete, budget_tokens, seed0=s * 1000)
        a2, t2 = arm_island_evolve(
            task, complete, budget_tokens, seed0=s * 1000, n_islands=n_islands
        )
        pairs.append((a1, a2))
        tk["best_of_n"] += t1
        tk["island_evolve"] += t2
    n = len(pairs) or 1
    m1 = sum(a for a, _ in pairs) / n
    m2 = sum(b for _, b in pairs) / n
    # bootstrap on scaled int deltas (CI helper is integer-domain → ×1000, round)
    deltas = [round((b - a) * 1000) for a, b in pairs]
    mean_d, lo, hi = _bootstrap_ci(deltas)
    realized = lo > 0  # ARM2 strictly above ARM1 at token parity
    return FunSearchVerdict(
        realized=realized,
        mean_arm1=round(m1, 4),
        mean_arm2=round(m2, 4),
        lift=(round(mean_d / 1000, 4), round(lo / 1000, 4), round(hi / 1000, 4)),
        per_seed=[(round(a, 4), round(b, 4)) for a, b in pairs],
        gen_tokens=tk,
        n_seeds=len(pairs),
        reason=(
            "REALIZED: island-evolve beats best-of-N at token parity (graded oracle, FunSearch regime)"
            if realized
            else "UNREALIZED: island-evolve <= best-of-N (CI lower bound <= 0)"
        ),
    )


if __name__ == "__main__":
    n_seeds = int(os.environ.get("FS_SEEDS", "5"))
    budget = int(os.environ.get("FS_BUDGET", "6000"))
    islands = int(os.environ.get("FS_ISLANDS", "4"))
    dist = os.environ.get("FS_DIST", "uniform")
    seeds = list(range(1, n_seeds + 1))
    print(
        f"funsearch binpack gate — seeds={n_seeds} budget={budget} islands={islands} dist={dist}",
        file=sys.stderr,
    )
    v = run_gate(seeds, budget_tokens=budget, n_islands=islands, dist=dist)
    print(json.dumps(v.__dict__, ensure_ascii=False, indent=1))
