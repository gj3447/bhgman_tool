"""Ladder rung runner: qwen3:32b with an EXPLICIT think toggle (ollama NATIVE API).

Why this module exists (2026-07-19): the ladder rung `pred-ladder-qwen3-32b-2026-07-19`
(LakatoTree BhgmanCeilingPierce) must run qwen3:32b in NO_THINK mode to match the dead
qwen3.6-27b condition (mode-matched size/family discrimination), but ollama's openai-compat
`/v1` path IGNORES both the `/no_think` soft switch (thinking silently eats the token budget →
empty content, measured 114s/0 chars) and a `think:false` extra field (126s/0 chars). Only the
NATIVE `/api/chat` honors `think:false` (measured 1s, correct content). So this runner injects a
native-API `complete` into the FROZEN harness's `_run_once` — zero changes to
`lean_headroom_run.py` (band sha 4a73146e discipline preserved).

Defaults mirror the frozen harness: temperature 0.8 (LEAN_TEMP), num_predict 3072
(LEAN_MAX_TOKENS), seed threaded per attempt.

Run (NO_THINK rung): uv run python -m engine.efficacy.ladder_qwen3_run \
    --model qwen3:32b --think false --k 4 --replications 5 --out-dir <dir>

# KG: project_ultimate_ai_tool_halo_loop_2026_07_19, Q-floor-mechanism-decomposition-2026-07-19
# KG: pred-ladder-qwen3-32b-2026-07-19 (prereg 125b6ab; this runner is the ladder harness)
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

from engine.efficacy.lean_headroom_run import _run_id, _run_once, lean_available


def make_native_complete(model: str, *, think: bool, base_url: str = "http://localhost:11435"):
    """(messages, seed) -> text via ollama NATIVE /api/chat with an honored think toggle."""
    temp = float(os.environ.get("LEAN_TEMP") or os.environ.get("P1_TEMP", "0.8"))
    num_predict = int(os.environ.get("LEAN_MAX_TOKENS", "3072"))
    timeout = int(os.environ.get("BHGMAN_LLM_TIMEOUT", "600"))

    def complete(messages, seed):
        body = json.dumps({
            "model": model, "think": think, "stream": False, "messages": list(messages),
            "options": {"temperature": temp, "num_predict": num_predict, "seed": int(seed)},
        }).encode()
        req = urllib.request.Request(
            f"{base_url}/api/chat", body, {"Content-Type": "application/json"})
        data = json.load(urllib.request.urlopen(req, timeout=timeout))
        complete.last_usage = (
            int(data.get("prompt_eval_count", 0)), int(data.get("eval_count", 0)))
        return data.get("message", {}).get("content", "")

    complete.last_usage = (0, 0)
    return complete


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="qwen3 ladder rung with explicit think toggle.")
    p.add_argument("--model", default="qwen3:32b")
    p.add_argument("--think", choices=["true", "false"], required=True)
    p.add_argument("--base-url", default=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11435"))
    p.add_argument("--k", type=int, default=int(os.environ.get("LEAN_K", "4")))
    p.add_argument("--replications", type=int, default=int(os.environ.get("LEAN_REPLICATIONS", "1")))
    p.add_argument("--seed-offset", type=int, default=0)
    p.add_argument("--seed-step", type=int, default=10)
    p.add_argument("--out-dir", default=os.environ.get("LEAN_OUT_DIR"))
    args = p.parse_args(argv)
    if not lean_available():
        print("[ladder] lean toolchain not on PATH — cannot run.")
        return 2
    think = args.think == "true"
    complete = make_native_complete(args.model, think=think, base_url=args.base_url)
    backend = f"ollama-native:{args.model}:think={str(think).lower()}"
    out_dir = Path(args.out_dir) if args.out_dir else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
    for rep in range(args.replications):
        seed_offset = args.seed_offset + rep * args.seed_step
        rid = _run_id(seed_offset)
        if out_dir is None:
            _run_once(complete, backend, k=args.k, seed_offset=seed_offset)
            continue
        with (out_dir / f"seed_{seed_offset}.jsonl").open("w", encoding="utf-8") as log:
            print(f"[ladder] raw_jsonl={out_dir / f'seed_{seed_offset}.jsonl'}")
            _run_once(complete, backend, k=args.k, seed_offset=seed_offset, log=log, run_id=rid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
