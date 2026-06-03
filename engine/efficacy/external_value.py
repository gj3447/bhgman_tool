"""External-value proxy — does the bhgman oracle catch errors a reasoner would *ship*?

VERDICT.md's one genuinely-untested axis is external value. True external *adoption* can't be
manufactured in-session, so this measures the honest utility proxy: on real code tasks, a reasoner
generates a solution AND self-rates it correct/incorrect; the bhgman oracle (hidden-test execution)
gives ground truth. The value the oracle adds = **confident-but-wrong** cases (reasoner says YES,
oracle says FAIL) — exactly what the reasoner's own self-assessment cannot catch (Huang 2310.01798:
intrinsic self-correction fails without an external signal). If that rate > 0, `bhgman verify` has
real utility a reasoner-alone lacks. Honest scope: utility proxy, NOT external adoption.

Run: VLLM_URL=... uv run python -m engine.efficacy.external_value   (or FS_BACKEND=ollama)

# KG: prom16-bhgman-ci-design-2026-06-02, project_bhgman_self_critique_2026_05_28 (external impact untested),
#     naesengmoon-generate-verify-asymmetry-2026-06-01
"""

from __future__ import annotations

import json
import os
import sys

from engine.efficacy.p1_oracle_rerank_pilot import _extract_code, _ollama, _run_tests
from engine.efficacy.p1_tasks import TASKS
from engine.efficacy.run_funsearch_vllm import vllm_complete

_SYS = "You are a Python expert. Return ONLY a single ```python code block. No explanation."


def measure(tasks, complete) -> dict:
    rows = []
    for t in tasks:
        gen, _ = complete(
            [{"role": "system", "content": _SYS}, {"role": "user", "content": t.prompt}], 1
        )
        code = _extract_code(gen)
        rate, _ = complete(
            [
                {
                    "role": "user",
                    "content": f"Task:\n{t.prompt}\n\nProposed solution:\n{code}\n\n"
                    "Is this solution FULLY correct for all inputs? Reply with ONLY one word: YES or NO.",
                }
            ],
            2,
        )
        self_says_correct = rate.strip().upper().startswith("Y")
        oracle_pass = _run_tests(code, t.hidden_tests) == len(t.hidden_tests)
        rows.append({"task": t.name, "self_correct": self_says_correct, "oracle_pass": oracle_pass})

    n = len(rows) or 1
    confident_wrong = [r["task"] for r in rows if r["self_correct"] and not r["oracle_pass"]]
    underconfident = [r["task"] for r in rows if not r["self_correct"] and r["oracle_pass"]]
    self_acc = sum(1 for r in rows if r["self_correct"] == r["oracle_pass"]) / n
    return {
        "n": len(rows),
        "self_assessment_accuracy": round(self_acc, 3),
        "confident_but_wrong": confident_wrong,  # oracle가 잡는 ship-될 뻔한 에러 = 외부 효용
        "confident_but_wrong_rate": round(len(confident_wrong) / n, 3),
        "underconfident": underconfident,
        "oracle_pass_rate": round(sum(1 for r in rows if r["oracle_pass"]) / n, 3),
        "rows": rows,
    }


if __name__ == "__main__":
    complete = _ollama if os.environ.get("FS_BACKEND") == "ollama" else vllm_complete
    print(
        f"external-value proxy — backend={'ollama' if complete is _ollama else 'vllm'} tasks={len(TASKS)}",
        file=sys.stderr,
    )
    print(json.dumps(measure(TASKS, complete), ensure_ascii=False, indent=1))
