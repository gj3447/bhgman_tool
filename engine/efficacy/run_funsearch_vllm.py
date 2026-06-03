"""FunSearch gate runner over the dgx vLLM API (Qwen3.6-27B, OpenAI-compatible).

The "dgx api" = k8s `ai/vllm` service serving Qwen3.6-27B. It is a *reasoning* model, so
`enable_thinking=false` is required to get a direct `content` (else output goes to a `reasoning`
field and content is null). Otherwise this is just a stronger generator injected into the
already-gate-validated funsearch_binpack.run_gate (no new gate logic).

Run:  VLLM_URL=http://localhost:8001/v1/chat/completions FS_SEEDS=12 FS_BUDGET=5000 \
      uv run python -m engine.efficacy.run_funsearch_vllm
(tunnel: ssh -fN -L 8001:10.105.11.193:8000 dgx)

# KG: prom16-evolve-loop-revival-2026-06-02, lesson-premature-close-confirmation-toward-closure-2026-06-02
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

from engine.efficacy.funsearch_binpack import run_gate

VLLM_URL = os.environ.get("VLLM_URL", "http://localhost:8001/v1/chat/completions")
MODEL = os.environ.get("VLLM_MODEL", "qwen3.6-27b")
TEMP = float(os.environ.get("VLLM_TEMP", "0.8"))
MAX_TOKENS = int(os.environ.get("VLLM_MAX_TOKENS", "1024"))


def vllm_complete(messages: list[dict], seed: int) -> tuple[str, int]:
    """vLLM OpenAI chat. enable_thinking=false → direct content. (text, total_tokens).

    Resilient: retry on transient timeout/error; persistent failure → empty candidate (scores 0)
    + nominal token cost so the budget loop advances — one slow call never kills the whole run.
    """
    body = json.dumps(
        {
            "model": MODEL,
            "messages": messages,
            "temperature": TEMP,
            "seed": seed,
            "max_tokens": MAX_TOKENS,
            "chat_template_kwargs": {"enable_thinking": False},
        }
    ).encode()
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(  # noqa: S310
                VLLM_URL, data=body, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310
                d = json.load(r)
            text = d["choices"][0]["message"].get("content") or ""
            toks = int(d.get("usage", {}).get("total_tokens", 0))
            return text, toks
        except Exception as e:  # noqa: BLE001 — transient net/timeout; retry then degrade to dud
            last_err = e
            time.sleep(2 * (attempt + 1))
    print(f"[warn] vllm_complete failed after retries: {last_err}", file=sys.stderr)
    return "", 200  # dud candidate (scores 0) + nominal tokens so budget advances


if __name__ == "__main__":
    n_seeds = int(os.environ.get("FS_SEEDS", "12"))
    budget = int(os.environ.get("FS_BUDGET", "5000"))
    islands = int(os.environ.get("FS_ISLANDS", "4"))
    dist = os.environ.get("FS_DIST", "weibull")
    seeds = list(range(1, n_seeds + 1))
    print(
        f"funsearch vLLM ({MODEL}) — seeds={n_seeds} budget={budget} islands={islands} dist={dist}",
        file=sys.stderr,
    )
    v = run_gate(seeds, vllm_complete, budget_tokens=budget, n_islands=islands, dist=dist)
    print(json.dumps(v.__dict__, ensure_ascii=False, indent=1))
