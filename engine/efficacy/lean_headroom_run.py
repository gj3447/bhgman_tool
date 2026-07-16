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

import argparse
import functools
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

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
        # seed/temperature MUST be threaded on the frontier/openai-compat path too, or best-of-N's K
        # "independent" draws collapse to one greedy proof (the 2026-06-03 confound) — unfair on exactly
        # the reachable dgx-LAN/cloud path. The local ollama path already threads seed; this one silently
        # dropped it. temp default 0.8 (LEAN_HEADROOM_FAIRTEST); temp=0.0 would be greedy and ignore seed.
        temp = float(os.environ.get("LEAN_TEMP") or os.environ.get("P1_TEMP", "0.8"))

        def _frontier_complete(messages, seed):
            system = next((m["content"] for m in messages if m["role"] == "system"), "")
            user = next((m["content"] for m in messages if m["role"] == "user"), "")
            c = client.complete(
                system=system, user=user, model=model, max_tokens=mx, temperature=temp, seed=seed
            )
            # non-breaking token accounting (prereg P4): callers read dynamic
            # attributes after each call. The callable contract remains unchanged.
            setattr(
                _frontier_complete,
                "last_usage",
                (
                    int(getattr(c, "input_tokens", 0) or 0),
                    int(getattr(c, "output_tokens", 0) or 0),
                ),
            )
            setattr(
                _frontier_complete,
                "last_response_model",
                str(getattr(c, "model", "") or ""),
            )
            setattr(
                _frontier_complete,
                "last_response_model_observed",
                bool(getattr(c, "model_observed", False)),
            )
            return c.text

        setattr(_frontier_complete, "last_usage", (0, 0))
        setattr(_frontier_complete, "last_response_model", "")
        setattr(_frontier_complete, "last_response_model_observed", False)
        return _frontier_complete, f"frontier:{model}"

    def _local_complete(messages, seed):
        text, _ = _ollama(messages, seed)
        # local ollama does not surface per-call token usage here.
        setattr(_local_complete, "last_usage", (0, 0))
        setattr(
            _local_complete,
            "last_response_model",
            os.environ.get("P1_MODEL", "qwen2.5:0.5b-instruct"),
        )
        setattr(_local_complete, "last_response_model_observed", False)
        return text

    setattr(_local_complete, "last_usage", (0, 0))
    setattr(_local_complete, "last_response_model", "")
    setattr(_local_complete, "last_response_model_observed", False)
    return _local_complete, (
        f"local-ollama:{os.environ.get('P1_MODEL', 'qwen2.5:0.5b-instruct')}"
    )


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


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _log_record(log: TextIO | None, record: dict[str, Any]) -> None:
    if log is None:
        return
    log.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    log.flush()


def _eval_attempt(
    task,
    proof: str,
    *,
    arm: str,
    attempt: int,
    seed: int,
    log: TextIO | None,
    run_meta: dict[str, Any] | None,
    prior_proof: str | None = None,
    used_feedback: bool = False,
    in_tok: int = 0,
    out_tok: int = 0,
):
    if run_meta is None:
        run_meta = {
            "run_id": f"lean-headroom-ad-hoc-seed-{seed}",
            "backend": "ad-hoc",
            "K": None,
            "seed_offset": seed,
        }
    v = evaluate(task.name, task.signature, proof, preamble=task.preamble)
    record = {
        "record_type": "attempt",
        "run_id": run_meta["run_id"],
        "backend": run_meta["backend"],
        "K": run_meta["K"],
        "seed_offset": run_meta["seed_offset"],
        "task": task.name,
        "difficulty": task.difficulty,
        "arm": arm,
        "attempt": attempt,
        "seed": seed,
        "used_feedback": used_feedback,
        "proof": proof,
        "proof_sha256": _sha256(proof),
        "compiles": v.compiles,
        "proven": v.proven,
        "sorry_tainted": v.sorry_tainted,
        "graded_score": v.graded_score,
        "error_tail": v.error_tail,
        "error_tail_sha256": _sha256(v.error_tail),
        "input_tokens": in_tok,  # prereg P4 token-parity accounting (0 when the backend hides usage)
        "output_tokens": out_tok,
        "model_calls": 1,
    }
    if prior_proof is not None:
        record["prior_proof_sha256"] = _sha256(prior_proof)
    _log_record(log, record)
    return v


def _usage(complete) -> tuple[int, int]:
    """(input_tokens, output_tokens) of the last `complete` call — 0/0 if the backend hides usage
    (prereg P4). Read immediately after `_gen`, which makes exactly one `complete` call."""
    return getattr(complete, "last_usage", (0, 0))


def _arm_single(task, complete, off=0, *, log: TextIO | None = None, run_meta=None):
    proof = _gen(task, complete, off)
    ti, to = _usage(complete)
    v = _eval_attempt(
        task,
        proof,
        arm="single",
        attempt=1,
        seed=off,
        log=log,
        run_meta=run_meta,
        in_tok=ti,
        out_tok=to,
    )
    return v.proven, v.graded_score


def _arm_repair(task, complete, k, off=0, *, log: TextIO | None = None, run_meta=None):
    prior, err, best = None, None, 0.0
    for i in range(k):
        proof = _gen(task, complete, off + i, prior, err)  # varied seed + error feedback
        ti, to = _usage(complete)
        v = _eval_attempt(
            task,
            proof,
            arm="repair",
            attempt=i + 1,
            seed=off + i,
            log=log,
            run_meta=run_meta,
            prior_proof=prior,
            used_feedback=prior is not None,
            in_tok=ti,
            out_tok=to,
        )
        best = max(best, v.graded_score)
        if v.proven:
            return True, 1.0
        prior, err = proof, v.error_tail
    return False, best


def _arm_bestn(task, complete, k, off=0, *, log: TextIO | None = None, run_meta=None):
    best = 0.0
    for i in range(k):  # varied seed → genuinely independent attempts (no oracle feedback)
        proof = _gen(task, complete, off + i)
        ti, to = _usage(complete)
        v = _eval_attempt(
            task,
            proof,
            arm="bestN",
            attempt=i + 1,
            seed=off + i,
            log=log,
            run_meta=run_meta,
            in_tok=ti,
            out_tok=to,
        )
        best = max(best, v.graded_score)
        if v.proven:
            return True, 1.0
    return False, best


@functools.lru_cache(maxsize=None)
def _decoy_error_for(task_name: str) -> str:
    """A well-formed-but-WRONG Lean error for `task_name`: evaluate a DIFFERENT task's reference proof
    against THIS task's statement → a real Lean type/identifier error that gives NO valid guidance for
    this task. Constant per task (seed-independent, cached). This is the decoy arm's placebo signal —
    the same input-context volume as repair's real error, with the oracle SIGNAL removed."""
    idx = next(i for i, t in enumerate(TASKS) if t.name == task_name)
    task = TASKS[idx]
    other = TASKS[(idx + 1) % len(TASKS)]
    other_proof = getattr(other, "reference_proof", None)
    if not other_proof:  # synthetic task with no reference proof → fixed placeholder decoy
        return "unsolved goals\n"
    v = evaluate(task.name, task.signature, other_proof, preamble=getattr(task, "preamble", ""))
    return v.error_tail or "unsolved goals\n"  # fallback if the mismatched proof happens to compile


def _arm_decoy(task, complete, k, off=0, *, log: TextIO | None = None, run_meta=None):
    """Placebo control for _arm_repair (prereg P2). Identical K-loop + varied seed + prior-proof context
    threading, but rounds 2+ feed a FIXED bogus error from a different task (_decoy_error_for), never
    this task's real oracle error. repair>decoy AND decoy≈bestN ⇒ the win is oracle-CONTENT, not
    input-context VOLUME. round 1 has no feedback (mirrors repair's first round exactly)."""
    decoy = _decoy_error_for(task.name)
    prior, best = None, 0.0
    for i in range(k):
        err = (
            decoy if prior is not None else None
        )  # bogus feedback from round 2 (mirror repair's shape)
        proof = _gen(
            task, complete, off + i, prior, err
        )  # varied seed; DECOY error, not the oracle
        ti, to = _usage(complete)
        v = _eval_attempt(
            task,
            proof,
            arm="decoy",
            attempt=i + 1,
            seed=off + i,
            log=log,
            run_meta=run_meta,
            prior_proof=prior,
            used_feedback=prior is not None,
            in_tok=ti,
            out_tok=to,
        )
        best = max(best, v.graded_score)
        if v.proven:
            return True, 1.0
        prior = proof  # context volume matched to repair; the error is bogus
    return False, best


def _plain_prompt(task, transcript: list[tuple[str, str]]):
    """Generic coding-agent persona (NOT the Lean-4-EXPERT template) for the plain_baseline arm.

    Isolates bhgman-specific scaffolding from the task-fairness info a FAIR generic agent must keep:
    the persona is a plain test-loop coding assistant, but the ask still carries core Lean 4 / NO
    Mathlib, the preamble, the exact theorem statement, and the output-format instruction — dropping
    any of those would strawman the arm (forbidden; the arm is weaker only in scaffolding, never in
    task information). `transcript` = [(proof, error), ...] from prior rounds, rendered as a plain-text
    session log INSIDE one user message: `_make_complete`'s AgentClient path flattens messages to one
    system + one user (`next(role==system)` / `next(role==user)`), so a plain agent's growing context
    lives in the user text, not in multi-turn chat."""
    sys = {
        "role": "system",
        "content": "You are a coding assistant in a test-loop. Write code, read the tool output, and "
        "fix your code until it passes. Output ONLY the code requested — no explanation, no prose.",
    }
    pre = f"Given:\n{task.preamble}\n\n" if task.preamble else ""
    ask = (
        f"Prove a theorem in CORE Lean 4 (NO Mathlib).\n{pre}"
        f"theorem {task.name} {task.signature} := ?\n\n"
        "Output ONLY the proof term that goes after ':=' (no theorem line, no markdown, no prose)."
    )
    for i, (proof, error) in enumerate(transcript, start=1):
        ask += f"\n\n=== your attempt {i} ===\n{proof}\n=== lean output {i} (fix it) ===\n{error}"
    return [sys, {"role": "user", "content": ask}]


def _arm_plain(task, complete, k, off=0, *, log: TextIO | None = None, run_meta=None):
    """Plain agent-with-oracle test-loop baseline (prereg §3 `plain_baseline`, K8). A FAIR generic
    coding agent: same K budget, same ungameable oracle, same task-fairness info, but WITHOUT the
    bhgman-specific scaffolding that `_arm_repair` adds — and NOTHING else changed:
      1. conversation ACCUMULATION — the full transcript of every prior attempt + raw Lean error grows
         inside one user message (a real agent session accumulates), vs repair's structured LAST-proof
         / LAST-error template;
      2. FIXED seed = off every round — a plain session does not jitter seeds mid-loop; its variety
         comes from the grown context, vs repair's per-round varied seed (off+i) diversity injection;
      3. GENERIC persona — a test-loop coding assistant, vs repair's "Lean 4 expert" persona.
    If capable-model `repair <= plain`, the edge is a generic gen-verify-gap ("reading informative
    compiler errors > not", near true-by-construction), NOT a bhgman capability ⇒ operational-only.
    # KG: LakatosTree_BhgmanCeilingPierce_20260712, PIERCE_PREREGISTRATION §3 plain_baseline (K8)"""
    transcript: list[tuple[str, str]] = []
    best = 0.0
    for i in range(k):
        proof = _extract_proof(complete(_plain_prompt(task, transcript), off))  # FIXED seed = off
        ti, to = _usage(complete)
        v = _eval_attempt(
            task,
            proof,
            arm="plain",
            attempt=i + 1,
            seed=off,
            log=log,
            run_meta=run_meta,
            prior_proof=(transcript[-1][0] if transcript else None),
            used_feedback=bool(transcript),
            in_tok=ti,
            out_tok=to,
        )
        best = max(best, v.graded_score)
        if v.proven:
            return True, 1.0
        transcript.append((proof, v.error_tail))  # accumulate — the plain agent's growing context
    return False, best


def _summary(rows: list) -> dict:
    """proven counts + graded partial-progress sums for a subset of rows."""
    return {
        "single": sum(1 for r in rows if r["single"]),
        "repair": sum(1 for r in rows if r["repair"]),
        "bestN": sum(1 for r in rows if r["bestN"]),
        "decoy": sum(1 for r in rows if r.get("decoy")),
        "plain": sum(1 for r in rows if r.get("plain")),
        "graded_single": round(sum(r["graded_single"] for r in rows), 2),
        "graded_repair": round(sum(r["graded_repair"] for r in rows), 2),
        "graded_bestN": round(sum(r["graded_bestN"] for r in rows), 2),
        "graded_decoy": round(sum(r.get("graded_decoy", 0.0) for r in rows), 2),
        "graded_plain": round(sum(r.get("graded_plain", 0.0) for r in rows), 2),
        "of": len(rows),
    }


def _run_id(seed_offset: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"lean-headroom-{stamp}-seed-{seed_offset}"


def _task_record(
    run_meta: dict[str, Any], task, s_p, s_g, r_p, r_g, b_p, b_g, d_p, d_g, p_p, p_g
) -> dict[str, Any]:
    return {
        "record_type": "task_summary",
        "run_id": run_meta["run_id"],
        "backend": run_meta["backend"],
        "K": run_meta["K"],
        "seed_offset": run_meta["seed_offset"],
        "task": task.name,
        "difficulty": task.difficulty,
        "arms": {
            "single": {"proven": s_p, "graded_score": s_g},
            "repair": {"proven": r_p, "graded_score": r_g},
            "bestN": {"proven": b_p, "graded_score": b_g},
            "decoy": {"proven": d_p, "graded_score": d_g},
            "plain": {"proven": p_p, "graded_score": p_g},
        },
    }


def _run_once(
    complete,
    backend: str,
    *,
    k: int,
    seed_offset: int,
    log: TextIO | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    run_meta = {
        "run_id": run_id or _run_id(seed_offset),
        "backend": backend,
        "K": k,
        "seed_offset": seed_offset,
    }
    _log_record(
        log,
        {
            "record_type": "run_start",
            **run_meta,
            "n_tasks": len(TASKS),
            "tasks": [
                {"name": t.name, "difficulty": t.difficulty, "signature": t.signature}
                for t in TASKS
            ],
        },
    )
    rows = []
    print(
        f"[lean-headroom] backend={backend} K={k} seed_offset={seed_offset} n={len(TASKS)} "
        "(ungameable oracle, headroom tasks; graded 0/0.5/1)"
    )
    for t in TASKS:
        s_p, s_g = _arm_single(t, complete, seed_offset, log=log, run_meta=run_meta)
        r_p, r_g = _arm_repair(t, complete, k, seed_offset, log=log, run_meta=run_meta)
        b_p, b_g = _arm_bestn(t, complete, k, seed_offset, log=log, run_meta=run_meta)
        d_p, d_g = _arm_decoy(t, complete, k, seed_offset, log=log, run_meta=run_meta)
        p_p, p_g = _arm_plain(t, complete, k, seed_offset, log=log, run_meta=run_meta)
        rows.append(
            {
                "task": t.name,
                "difficulty": t.difficulty,
                "single": s_p,
                "repair": r_p,
                "bestN": b_p,
                "decoy": d_p,
                "plain": p_p,
                "graded_single": s_g,
                "graded_repair": r_g,
                "graded_bestN": b_g,
                "graded_decoy": d_g,
                "graded_plain": p_g,
            }
        )
        _log_record(
            log, _task_record(run_meta, t, s_p, s_g, r_p, r_g, b_p, b_g, d_p, d_g, p_p, p_g)
        )
        print(
            f"  [{t.difficulty:8s}] {t.name:12s} proven s/r/b/d/p="
            f"{int(s_p)}/{int(r_p)}/{int(b_p)}/{int(d_p)}/{int(p_p)}  "
            f"graded s/r/b/d/p={s_g:.1f}/{r_g:.1f}/{b_g:.1f}/{d_g:.1f}/{p_g:.1f}"
        )
    hr = [r for r in rows if r["difficulty"] == "headroom"]
    out = {
        **run_meta,
        "n_tasks": len(rows),
        "n_headroom": len(hr),
        "all": _summary(rows),
        "headroom_only": _summary(hr),
        "repair_beats_bestN_on_headroom_proven": sum(r["repair"] for r in hr)
        > sum(r["bestN"] for r in hr),
        "repair_beats_bestN_on_headroom_graded": sum(r["graded_repair"] for r in hr)
        > sum(r["graded_bestN"] for r in hr),
        # prereg P2: the win is oracle-CONTENT (not context-VOLUME) only if repair>decoy AND decoy≈bestN.
        "repair_beats_decoy_on_headroom_proven": sum(r["repair"] for r in hr)
        > sum(r.get("decoy", 0) for r in hr),
        "decoy_minus_bestN_on_headroom_proven": sum(r.get("decoy", 0) for r in hr)
        - sum(r["bestN"] for r in hr),
        # prereg P3/K8: the edge is bhgman-specific only if repair > plain agent-with-oracle baseline.
        "repair_beats_plain_on_headroom_proven": sum(r["repair"] for r in hr)
        > sum(r.get("plain", 0) for r in hr),
        "plain_minus_repair_on_headroom_proven": sum(r.get("plain", 0) for r in hr)
        - sum(r["repair"] for r in hr),
    }
    _log_record(log, {"record_type": "run_summary", **out})
    print(json.dumps(out, indent=1))
    return out


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Lean headroom repair-vs-bestN efficacy test."
    )
    parser.add_argument("--k", type=int, default=int(os.environ.get("LEAN_K", "4")))
    parser.add_argument(
        "--seed-offset",
        type=int,
        default=int(os.environ.get("SEED_OFFSET", "0")),
        help="Base seed offset for the first replication.",
    )
    parser.add_argument(
        "--replications",
        type=int,
        default=int(os.environ.get("LEAN_REPLICATIONS", "1")),
        help="Number of seed-offset replications to run.",
    )
    parser.add_argument(
        "--seed-step",
        type=int,
        default=int(os.environ.get("LEAN_SEED_STEP", "10")),
        help="Offset added between replications.",
    )
    parser.add_argument(
        "--out-dir",
        default=os.environ.get("LEAN_OUT_DIR"),
        help="Optional directory for raw JSONL logs, one file per seed offset.",
    )
    return parser.parse_args(argv)


def _batch_summary(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    wins = ties = losses = 0
    for summary in summaries:
        repair = summary["headroom_only"]["repair"]
        bestn = summary["headroom_only"]["bestN"]
        if repair > bestn:
            wins += 1
        elif repair < bestn:
            losses += 1
        else:
            ties += 1
    return {
        "record_type": "batch_summary",
        "replications": len(summaries),
        "repair_gt_bestN": wins,
        "ties": ties,
        "bestN_gt_repair": losses,
        "seed_offsets": [s["seed_offset"] for s in summaries],
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.k < 1:
        print("[lean-headroom] --k must be >= 1.")
        return 2
    if args.replications < 1:
        print("[lean-headroom] --replications must be >= 1.")
        return 2
    if not lean_available():
        print("[lean-headroom] lean toolchain not on PATH — cannot run.")
        return 2
    complete, backend = _make_complete()
    out_dir = Path(args.out_dir) if args.out_dir else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for rep in range(args.replications):
        seed_offset = args.seed_offset + rep * args.seed_step
        rid = _run_id(seed_offset)
        if out_dir is None:
            summaries.append(_run_once(complete, backend, k=args.k, seed_offset=seed_offset))
            continue
        log_path = out_dir / f"seed_{seed_offset}.jsonl"
        with log_path.open("w", encoding="utf-8") as log:
            print(f"[lean-headroom] raw_jsonl={log_path}")
            summaries.append(
                _run_once(
                    complete,
                    backend,
                    k=args.k,
                    seed_offset=seed_offset,
                    log=log,
                    run_id=rid,
                )
            )
    if len(summaries) > 1:
        print(json.dumps(_batch_summary(summaries), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
