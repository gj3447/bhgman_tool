"""거기 probe — does composition beat a BARE single-shot when the model is UNSATURATED?

The within-competence runs were uninformative because ARM1 (base) saturated. Here we force headroom:
use the WEAK model (qwen 0.5b) so a single generation fails often, then ask which composition (if any)
beats one bare shot. This ISOLATES the win source:

  ARM0_single        — ONE generation, no oracle.            (the bare model)
  ARM1_oracle_select — best-of-N, pick by PUBLIC tests.      (generate-and-verify = value-source ② oracle)
  ARM2_hetero        — the 6-stage heterogeneous pipeline.   (prompt-orchestration)

Hidden tests (non-circular) are the eval. Prediction (from the root-cause analysis): ARM1 > ARM0
(the oracle selects passing samples the bare model wouldn't reliably emit) but ARM2 ≈ ARM1 (same-model
prompt-orchestration adds nothing beyond oracle selection). A POSITIVE here means the win is the ORACLE
(ground truth the model lacks), NOT orchestration — confirming the operational-substrate verdict
constructively rather than only by null.

Run: P1_MODEL=qwen2.5:0.5b-instruct HETERO_BUDGET=1200 uv run python -m engine.efficacy.hetero_headroom_probe
# KG: project-apt-ultracode-roadmap-2026-06-02
"""

from __future__ import annotations

import json
import os

from engine.efficacy.hetero_composition_ab import run_arms
from engine.efficacy.hetero_composition_run import _hidden_of, _make_gen, _public_of
from engine.efficacy.p1_oracle_rerank_pilot import _bootstrap_ci
from engine.efficacy.p1_tasks import TASKS


def main() -> int:
    model = os.environ.get("P1_MODEL", "qwen2.5:0.5b-instruct")
    budget = int(os.environ.get("HETERO_BUDGET", "1200"))
    idx_env = os.environ.get("HETERO_TASK_IDX")
    tasks = (
        [TASKS[int(i)] for i in idx_env.split(",")]
        if idx_env
        else TASKS[: int(os.environ.get("HETERO_NTASKS", str(len(TASKS))))]
    )
    print(
        f"[headroom-probe] model={model} budget={budget} n={len(tasks)} (weak model = forced headroom)"
    )
    rows = []
    for t in tasks:
        gen, pub, hid = _make_gen(t), _public_of(t), _hidden_of(t)
        single_art, _ = gen("solve", "", 0)
        single = hid(single_art)
        runs = run_arms(gen, pub, hid, budget=budget, seed0=1)  # seed0=1 ≠ single's seed 0
        sel = runs["ARM1_monolith"].hidden_ok
        het = runs["ARM2_hetero"].hidden_ok
        rows.append((single, sel, het))
        print(f"  {t.name:20s} single={int(single)} oracle_select={int(sel)} hetero={int(het)}")

    n = len(rows)
    p_single = sum(r[0] for r in rows)
    p_sel = sum(r[1] for r in rows)
    p_het = sum(r[2] for r in rows)
    d_sel = [int(r[1]) - int(r[0]) for r in rows]  # oracle_select − single
    d_het = [int(r[2]) - int(r[0]) for r in rows]  # hetero − single
    m_sel, lo_sel, _ = _bootstrap_ci(d_sel)
    m_het, lo_het, _ = _bootstrap_ci(d_het)
    out = {
        "model": model,
        "n_tasks": n,
        "pass_rate": {"single": p_single, "oracle_select": p_sel, "hetero": p_het, "of": n},
        "oracle_select_minus_single": {
            "mean": round(m_sel, 3),
            "ci_lo": round(lo_sel, 3),
            "wins": lo_sel > 0,
        },
        "hetero_minus_single": {
            "mean": round(m_het, 3),
            "ci_lo": round(lo_het, 3),
            "wins": lo_het > 0,
        },
        "saturated": p_single == n,  # if single already solves all, no headroom (uninformative)
    }
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
