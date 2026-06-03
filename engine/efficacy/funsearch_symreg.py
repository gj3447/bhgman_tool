"""FunSearch gate on a HEADROOM-RICH task — symbolic regression (fit a hidden function).

bin-packing tied across all local models because best-fit is a near-optimal one-liner the model
one-shots → no headroom for evolution. Symbolic regression has no such one-liner: the model must
*search* the formula space, and rich feedback (RMSE + worst residuals of the prior attempt) is
exactly what iterative refinement exploits (AlphaCodium/Mind-Evolution lever). So this is where the
read-back loop has a genuine chance to beat best-of-N — on the SAME dgx vLLM (no console key needed;
the model was never the blocker, the task headroom was).

Task: hidden target g(x) = c0 + c1·x + c2·x² + c3·sin(c4·x) (coeffs per seed). The model writes
`def f(x):` to fit PUBLIC (x,y) points; scored by 1/(1+RMSE). Eval on HIDDEN points (non-circular).
ARM1 best-of-N (independent draws) vs ARM2 island-evolve (read-back of best f + its RMSE + worst
residuals). Token parity, paired across seeds, fixed bootstrap CI.

# KG: prom16-evolve-loop-revival-2026-06-02, lesson-premature-close-confirmation-toward-closure-2026-06-02
"""

from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
import tempfile

from engine.efficacy.funsearch_binpack import IslandDatabase
from engine.efficacy.p1_oracle_rerank_pilot import _bootstrap_ci, _extract_code, _ollama
from engine.efficacy.run_funsearch_vllm import vllm_complete

_TIMEOUT_S = 8
_SYS = {
    "role": "system",
    "content": "You are a numerical-fitting expert. Return ONLY a single ```python code block "
    "defining `def f(x):` (math.* available via `from math import *`). No comments, keep it short.",
}

_RUNNER = """
from math import *  # noqa
import sys, json
{code}
d = json.load(sys.stdin)
errs = []
for x, y in d["points"]:
    try:
        yp = float(f(x))
        errs.append((yp - y) ** 2)
    except Exception:
        errs.append(1e9)
rmse = (sum(errs) / len(errs)) ** 0.5
print(1.0 / (1.0 + rmse))
"""


def make_target(seed: int, n_public: int = 10, n_hidden: int = 10):
    """숨은 target g(x)=c0+c1x+c2x^2+c3 sin(c4 x). (public_points, hidden_points) 반환 (비순환)."""
    rng = random.Random(seed)
    c0, c1, c2 = rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(-1, 1)
    c3, c4 = rng.uniform(-3, 3), rng.uniform(0.5, 2.5)

    def g(x: float) -> float:
        return c0 + c1 * x + c2 * x * x + c3 * math.sin(c4 * x)

    pub = [[round(x, 3), round(g(x), 4)] for x in [rng.uniform(-3, 3) for _ in range(n_public)]]
    hid = [[round(x, 3), round(g(x), 4)] for x in [rng.uniform(-3, 3) for _ in range(n_hidden)]]
    return pub, hid


def score_fit(code: str, points: list[list[float]]) -> float:
    """1/(1+RMSE) ∈ (0,1], 높을수록 좋음. f 미정의/크래시 → 0.0."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(_RUNNER.format(code=code))
        path = fh.name
    try:
        p = subprocess.run(  # noqa: S603
            [sys.executable, path],
            input=json.dumps({"points": points}),
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
        )
        return float(p.stdout.strip()) if p.returncode == 0 else 0.0
    except (subprocess.TimeoutExpired, ValueError):
        return 0.0
    finally:
        os.unlink(path)


def _residual_hint(code: str, pub: list[list[float]]) -> str:
    """prior f 의 최악 잔차 점들 (rich textual feedback = AlphaCodium lever)."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(
            _RUNNER.replace("print(1.0 / (1.0 + rmse))", "print(json.dumps(errs))").format(
                code=code
            )
        )
        path = fh.name
    try:
        p = subprocess.run(
            [sys.executable, path],
            input=json.dumps({"points": pub}),
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
        )  # noqa: S603
        errs = json.loads(p.stdout.strip()) if p.returncode == 0 else [1e9] * len(pub)
    except Exception:  # noqa: BLE001
        errs = [1e9] * len(pub)
    finally:
        os.unlink(path)
    worst = sorted(range(len(pub)), key=lambda i: -errs[i])[:3]
    return "; ".join(f"x={pub[i][0]} want {pub[i][1]} (sq-err {errs[i]:.2f})" for i in worst)


def _gen(complete, seed, pub, parents=None):
    """f 생성. parents 있으면 read-back: prior f 코드 + RMSE + 최악 잔차 점들."""
    pts = ", ".join(f"({x},{y})" for x, y in pub)
    base = f"Fit these (x, y) points with `def f(x):`. Points: {pts}"
    if parents:
        blocks = []
        for code, sc in parents:
            rmse = (1.0 / sc - 1.0) if sc > 0 else 999
            blocks.append(
                f"# prior f (RMSE {rmse:.3f}; worst: {_residual_hint(code, pub)}):\n{code}"
            )
        base += "\n\nImprove on these (lower RMSE = better):\n" + "\n\n".join(blocks)
    text, toks = complete([_SYS, {"role": "user", "content": base}], seed)
    return _extract_code(text), toks


def _arm_best_of_n(pub, hid, complete, budget, seed0):
    cands = []
    tok = 0
    i = 0
    while tok < budget:
        code, t = _gen(complete, seed0 + i, pub)
        tok += t
        i += 1
        cands.append((code, score_fit(code, pub)))
    best = max(cands, key=lambda c: c[1])
    return score_fit(best[0], hid), tok


def _arm_island_evolve(pub, hid, complete, budget, seed0, n_islands=4, k=2):
    db = IslandDatabase(n_islands)
    tok = 0
    i = 0
    for isl in range(n_islands):
        if tok >= budget:
            break
        code, t = _gen(complete, seed0 + i, pub)
        tok += t
        i += 1
        db.add(isl, code, score_fit(code, pub))
    isl = 0
    g = 0
    while tok < budget:
        code, t = _gen(complete, seed0 + i, pub, parents=db.best_in(isl, k))
        tok += t
        i += 1
        db.add(isl, code, score_fit(code, pub))
        isl = (isl + 1) % n_islands
        g += 1
        if g % (n_islands * 2) == 0:
            db.migrate()
    best = db.best_overall()
    return (score_fit(best[0], hid) if best else 0.0), tok


def run_gate(seeds, complete=_ollama, *, budget_tokens, n_islands=4):
    pairs = []
    tk = {"best_of_n": 0, "island_evolve": 0}
    for s in seeds:
        pub, hid = make_target(s)
        a1, t1 = _arm_best_of_n(pub, hid, complete, budget_tokens, s * 1000)
        a2, t2 = _arm_island_evolve(pub, hid, complete, budget_tokens, s * 1000, n_islands)
        pairs.append((a1, a2))
        tk["best_of_n"] += t1
        tk["island_evolve"] += t2
    deltas = [round((b - a) * 1000) for a, b in pairs]
    m, lo, hi = _bootstrap_ci(deltas)
    n = len(pairs) or 1
    return {
        "realized": lo > 0,
        "mean_arm1": round(sum(a for a, _ in pairs) / n, 4),
        "mean_arm2": round(sum(b for _, b in pairs) / n, 4),
        "lift": [round(m / 1000, 4), round(lo / 1000, 4), round(hi / 1000, 4)],
        "per_seed": [(round(a, 4), round(b, 4)) for a, b in pairs],
        "gen_tokens": tk,
        "n_seeds": len(pairs),
    }


if __name__ == "__main__":
    n_seeds = int(os.environ.get("FS_SEEDS", "8"))
    budget = int(os.environ.get("FS_BUDGET", "3000"))
    use_vllm = os.environ.get("FS_BACKEND", "vllm") == "vllm"
    complete = vllm_complete if use_vllm else _ollama
    seeds = list(range(1, n_seeds + 1))
    print(
        f"funsearch symreg — backend={'vllm' if use_vllm else 'ollama'} seeds={n_seeds} budget={budget}",
        file=sys.stderr,
    )
    print(json.dumps(run_gate(seeds, complete, budget_tokens=budget), ensure_ascii=False, indent=1))
