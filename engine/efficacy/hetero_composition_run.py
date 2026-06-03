"""Real-run adapter — heterogeneous 7-commander composition A/B on code tasks (reuses p1 infra).

Wires the oracle-agnostic harness (`hetero_composition_ab`) to a live LLM (`_ollama`) + code-task
oracle (`_run_tests` on p1_tasks): public = #public-tests passed (graded), hidden = ALL hidden tests
pass (non-circular eval). The 6 stage roles are distinct code-transformation prompts; ARM2 cycles
them, ARM1 just resolves, ARM3 only verifies.

⚠️ UNDERPOWERED CAVEAT (COMPOSITION_HETERO_PREREG.md §4): a fair test needs a frontier-class model.
The only local backend is qwen 0.5–1.5B — BELOW the strong-model ceiling — so a `realized=False`
here is the *predicted underpowered null*, NOT evidence against the composition hypothesis. Report as
"underpowered, hypothesis OPEN", never as closure. (Closing on a weak-model null is exactly the
evolve_loop premature-close trap, VERDICT.md §3.)

Run: P1_MODEL=qwen2.5:1.5b-instruct HETERO_NTASKS=4 HETERO_BUDGET=1000 uv run python -m engine.efficacy.hetero_composition_run
# KG: project-apt-ultracode-roadmap-2026-06-02
"""

from __future__ import annotations

import json
import os

from engine.efficacy.hetero_composition_ab import evaluate_realized, run_arms
from engine.efficacy.p1_oracle_rerank_pilot import _extract_code, _ollama, _run_tests
from engine.efficacy.p1_tasks import TASKS

_ROLE = {
    "solve": "You are a Python expert. Return ONLY a ```python code block with the requested function.",
    "gather": "Improve the function to handle more edge cases (empty, None, large, boundary inputs).",
    "connect": "Apply the known-correct standard algorithm/pattern for this kind of problem.",
    "abstract": "Refactor to a clean, general, correct form without changing intended behavior.",
    "prune": "Remove incorrect or dead branches; simplify to the minimal correct solution.",
    "verify": "Find and fix any bug that would make a test fail.",
    "realize": "Finalize into one complete, runnable function.",
}
_TAIL = " Return ONLY the full corrected ```python function, no prose."


def _make_gen(task):
    def gen(role: str, context: str, seed: int) -> tuple[str, int]:
        sysmsg = {"role": "system", "content": _ROLE.get(role, _ROLE["solve"]) + _TAIL}
        if role == "solve" or not context:
            content = task.prompt
        else:
            content = f"{task.prompt}\n\nCurrent solution:\n{context}\n\n{_ROLE[role]}{_TAIL}"
        text, toks = _ollama([sysmsg, {"role": "user", "content": content}], seed)
        return _extract_code(text), toks

    return gen


def _public_of(task):
    def public(code: str) -> float:
        return float(_run_tests(code, task.public_tests))

    return public


def _hidden_of(task):
    def hidden(code: str) -> bool:
        return _run_tests(code, task.hidden_tests) == len(task.hidden_tests)

    return hidden


def main() -> int:
    model = os.environ.get("P1_MODEL", "qwen2.5:0.5b-instruct")
    budget = int(os.environ.get("HETERO_BUDGET", "1000"))
    idx_env = os.environ.get("HETERO_TASK_IDX")
    if idx_env:
        tasks = [TASKS[int(i)] for i in idx_env.split(",")]
    else:
        tasks = TASKS[: int(os.environ.get("HETERO_NTASKS", "4"))]
    per_task = []
    print(
        f"[hetero-run] model={model} budget={budget} n={len(tasks)} (UNDERPOWERED — see prereg §4)"
    )
    for t in tasks:
        runs = run_arms(_make_gen(t), _public_of(t), _hidden_of(t), budget=budget, seed0=0)
        per_task.append(runs)
        print(
            f"  {t.name:20s} ARM1={int(runs['ARM1_monolith'].hidden_ok)} "
            f"ARM2={int(runs['ARM2_hetero'].hidden_ok)} ARM3={int(runs['ARM3_gate_only'].hidden_ok)}"
        )
    v = evaluate_realized(per_task)
    out = {
        "model": model,
        "budget": budget,
        "n_tasks": v.n_tasks,
        "realized": v.realized,
        "delta_ARM2_vs_ARM1": {
            "mean": round(v.delta_21_mean, 3),
            "ci_lo": round(v.delta_21_ci_lo, 3),
        },
        "delta_ARM2_vs_ARM3": {
            "mean": round(v.delta_23_mean, 3),
            "ci_lo": round(v.delta_23_ci_lo, 3),
        },
        "caveat": "UNDERPOWERED (weak local model). realized=False is the predicted null, NOT closure.",
    }
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
