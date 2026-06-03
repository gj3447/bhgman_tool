"""거기 (headroom) — does an UNGAMEABLE-oracle composition let a strong-ish model PROVE Lean lemmas
it cannot one-shot? The faithful test that fixes the strawman audit.

Faithful on every axis my code-prompt strawman violated EXCEPT two it cannot (no frontier model, no
cross-session):
  - REAL Lean (not toy code), via lean_oracle.
  - UNGAMEABLE non-circular oracle: statement fixed by construction + `#print axioms` no-sorryAx.
    (sorry → caught; wrong proof → no compile; weakened/renamed statement → impossible.)
  - HEADROOM tasks: omega/simp do NOT one-shot them (verified in lean_tasks).
  - CAPABILITY-heterogeneous: the second capability is the REAL Lean compiler oracle, not another prompt.
  - strong-ish model: best local = qwen2.5:32b (≫ the 1.5b floor; not frontier).

Arms (budget K attempts):
  ARM_single  — one proof attempt.                                          (bare model)
  ARM_repair  — attempt → if not proven, feed the lean error back → repair → ... (model + ungameable oracle, K)
  ARM_bestN   — K independent attempts, take the first that PROVES.          (generate-and-verify, K)

Honest read: if ARM_repair/ARM_bestN PROVE headroom tasks that ARM_single fails, the cell opens
(partially) — composition reaches beyond the single shot via the ungameable oracle. If 32b can't even
produce compiling core-Lean, that is a model-capability null (honest, not a composition verdict).

Run: P1_MODEL=qwen2.5:32b-instruct LEAN_K=4 uv run python -m engine.efficacy.lean_headroom_run
# KG: project-apt-ultracode-roadmap-2026-06-02
"""

from __future__ import annotations

import json
import os
import re

from engine.efficacy.lean_oracle import evaluate, lean_available
from engine.efficacy.lean_tasks import TASKS
from engine.efficacy.p1_oracle_rerank_pilot import _ollama

_FENCE = re.compile(r"```(?:lean)?\s*(.*?)```", re.DOTALL)


def _extract_proof(text: str) -> str:
    m = _FENCE.search(text)
    body = m.group(1) if m else text
    if ":=" in body:  # model echoed the theorem line — take the proof after the last :=
        body = body.split(":=", 1)[1]
    return body.strip()


def _prompt(task, prior=None, error=None):
    sys = {
        "role": "system",
        "content": "You are a Lean 4 expert (core, NO Mathlib). Output ONLY the proof term that goes "
        "after ':=' — e.g. `by induction n with | zero => rfl | succ k ih => simp [..] <;> omega`. "
        "No theorem line, no markdown, no prose.",
    }
    pre = f"Given:\n{task.preamble}\n\n" if task.preamble else ""
    ask = f"{pre}Prove:\ntheorem {task.name} {task.signature} := ?\n\nProvide the proof after ':='."
    if prior is not None:
        ask += f"\n\nYour previous proof:\n{prior}\n\nLean reported (fix it):\n{error}"
    return [sys, {"role": "user", "content": ask}]


def _gen(task, model, prior=None, error=None):
    text, _ = _ollama(_prompt(task, prior, error), 0)
    return _extract_proof(text)


def _arm_single(task, model):
    return evaluate(task.name, task.signature, _gen(task, model), preamble=task.preamble).proven


def _arm_repair(task, model, k):
    prior, err = None, None
    for _ in range(k):
        proof = _gen(task, model, prior, err)
        v = evaluate(task.name, task.signature, proof, preamble=task.preamble)
        if v.proven:
            return True
        prior, err = proof, v.error_tail
    return False


def _arm_bestn(task, model, k):
    for _ in range(k):
        if evaluate(task.name, task.signature, _gen(task, model), preamble=task.preamble).proven:
            return True
    return False


def main() -> int:
    if not lean_available():
        print("[lean-headroom] lean toolchain not on PATH — cannot run.")
        return 2
    model = os.environ.get("P1_MODEL", "qwen2.5:0.5b-instruct")
    k = int(os.environ.get("LEAN_K", "4"))
    rows = []
    print(f"[lean-headroom] model={model} K={k} n={len(TASKS)} (ungameable oracle, headroom tasks)")
    for t in TASKS:
        single = _arm_single(t, model)
        repair = _arm_repair(t, model, k)
        bestn = _arm_bestn(t, model, k)
        rows.append((t.difficulty, single, repair, bestn))
        print(
            f"  [{t.difficulty:8s}] {t.name:12s} single={int(single)} repair={int(repair)} bestN={int(bestn)}"
        )
    hr = [r for r in rows if r[0] == "headroom"]
    out = {
        "model": model,
        "K": k,
        "n_tasks": len(rows),
        "n_headroom": len(hr),
        "all": {
            "single": sum(r[1] for r in rows),
            "repair": sum(r[2] for r in rows),
            "bestN": sum(r[3] for r in rows),
            "of": len(rows),
        },
        "headroom_only": {
            "single": sum(r[1] for r in hr),
            "repair": sum(r[2] for r in hr),
            "bestN": sum(r[3] for r in hr),
            "of": len(hr),
        },
        "repair_beats_single_on_headroom": sum(r[2] for r in hr) > sum(r[1] for r in hr),
        "bestN_beats_single_on_headroom": sum(r[3] for r in hr) > sum(r[1] for r in hr),
    }
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
