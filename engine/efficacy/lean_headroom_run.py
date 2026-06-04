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

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _make_complete():
    """(messages, seed) -> text. FRONTIER (Anthropic / OpenAI-compat via AgentClient) when a key/
    endpoint is set (ANTHROPIC_API_KEY or BHGMAN_LLM_BASE_URL), else LOCAL ollama. Turnkey: export a
    frontier key and the same command runs on the frontier model — widening the headroom band."""
    from engine.cli.runtime import _agent_runtime  # noqa: PLC0415

    agents, reason = _agent_runtime()
    if agents is not None:
        client = agents.AgentClient()
        model = os.environ.get("BHGMAN_LLM_MODEL") or os.environ.get(
            "P1_MODEL", "claude-sonnet-4-6"
        )

        mx = int(os.environ.get("LEAN_MAX_TOKENS", "3072"))  # reasoning models think long

        def complete(messages, _seed):
            system = next((m["content"] for m in messages if m["role"] == "system"), "")
            user = next((m["content"] for m in messages if m["role"] == "user"), "")
            return client.complete(system=system, user=user, model=model, max_tokens=mx).text

        return complete, f"frontier:{model}"

    def complete(messages, seed):
        text, _ = _ollama(messages, seed)
        return text

    return complete, f"local-ollama:{os.environ.get('P1_MODEL', 'qwen2.5:0.5b-instruct')}"


def _extract_proof(text: str) -> str:
    text = _THINK.sub(" ", text)  # reasoning models (qwen3) emit <think>…</think> — drop it
    text = re.sub(r"```", "", text)  # strip code-fence markers (handles unclosed fences too)
    if ":=" in text:  # model echoed the theorem line — take the proof after the first :=
        text = text.split(":=", 1)[1]
    text = text.strip()
    # drop a leading bare language tag (```python without close → "python\nby ...")
    return re.sub(r"^(?:lean4?|python)\b[ \t]*\n?", "", text, flags=re.IGNORECASE).strip()


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


def _gen(task, complete, seed, prior=None, error=None):
    # seed THREADED per attempt — otherwise samples are identical and bestN collapses to single
    # (the confound found 2026-06-03). bestN/repair must vary seed to be a fair K-budget arm.
    return _extract_proof(complete(_prompt(task, prior, error), seed))


def _arm_single(task, complete, off=0):
    v = evaluate(task.name, task.signature, _gen(task, complete, off), preamble=task.preamble)
    return v.proven, v.graded_score


def _arm_repair(task, complete, k, off=0):
    prior, err, best = None, None, 0.0
    for i in range(k):
        proof = _gen(task, complete, off + i, prior, err)  # varied seed + error feedback
        v = evaluate(task.name, task.signature, proof, preamble=task.preamble)
        best = max(best, v.graded_score)
        if v.proven:
            return True, 1.0
        prior, err = proof, v.error_tail
    return False, best


def _arm_bestn(task, complete, k, off=0):
    best = 0.0
    for i in range(k):  # varied seed → genuinely independent attempts (no oracle feedback)
        v = evaluate(
            task.name, task.signature, _gen(task, complete, off + i), preamble=task.preamble
        )
        best = max(best, v.graded_score)
        if v.proven:
            return True, 1.0
    return False, best


def _summary(rows: list) -> dict:
    """proven counts + graded partial-progress sums for a subset of rows."""
    return {
        "single": sum(r[1] for r in rows),
        "repair": sum(r[2] for r in rows),
        "bestN": sum(r[3] for r in rows),
        "graded_single": round(sum(r[4] for r in rows), 2),
        "graded_repair": round(sum(r[5] for r in rows), 2),
        "graded_bestN": round(sum(r[6] for r in rows), 2),
        "of": len(rows),
    }


def main() -> int:
    if not lean_available():
        print("[lean-headroom] lean toolchain not on PATH — cannot run.")
        return 2
    complete, backend = _make_complete()
    k = int(os.environ.get("LEAN_K", "4"))
    off = int(os.environ.get("SEED_OFFSET", "0"))  # replication control (symmetric across arms)
    rows = []
    print(
        f"[lean-headroom] backend={backend} K={k} seed_offset={off} n={len(TASKS)} "
        "(ungameable oracle, headroom tasks; graded 0/0.5/1)"
    )
    for t in TASKS:
        s_p, s_g = _arm_single(t, complete, off)
        r_p, r_g = _arm_repair(t, complete, k, off)
        b_p, b_g = _arm_bestn(t, complete, k, off)
        rows.append((t.difficulty, s_p, r_p, b_p, s_g, r_g, b_g))
        print(
            f"  [{t.difficulty:8s}] {t.name:12s} proven s/r/b={int(s_p)}/{int(r_p)}/{int(b_p)}  "
            f"graded s/r/b={s_g:.1f}/{r_g:.1f}/{b_g:.1f}"
        )
    hr = [r for r in rows if r[0] == "headroom"]
    out = {
        "backend": backend,
        "K": k,
        "seed_offset": off,
        "n_tasks": len(rows),
        "n_headroom": len(hr),
        "all": _summary(rows),
        "headroom_only": _summary(hr),
        "repair_beats_bestN_on_headroom_proven": sum(r[2] for r in hr) > sum(r[3] for r in hr),
        "repair_beats_bestN_on_headroom_graded": sum(r[5] for r in hr) > sum(r[6] for r in hr),
    }
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
