# Lean headroom re-pin — qwen2.5:32b (2026-06-18) — DEFERRED (dgx down)

Reproducibility re-pin of **the one positive efficacy signal** in the whole project.

## The claim being re-pinned

`engine/efficacy/VERDICT.md` §3 + `engine/efficacy/LEAN_HEADROOM_FAIRTEST_2026-06-05.md`:

> At the **qwen2.5:32b** tier, an oracle-guided **repair loop** (feed the Lean compiler error
> back and re-attempt) **BEATS best-of-N** (K independent draws) on boundary *headroom* Lean
> proving tasks, at equal K=4. Powered Run B: repair ≥ best-of-N in **10/10** seed replications,
> strict win **7/10**, never loses, **sign-test two-sided p = 0.016**.

The mechanism: the model gets *close*, the Lean error names the defect, repair converges where
independent resampling can't (e.g. `dbl_ge` best-of-N 0/10 vs repair 5/10).

## Why a re-pin is needed (the blocker on the *evidence*, not the run)

The historical Run B was executed on `qwen2.5:32b` (via dgx **ollama**, since disabled) but its
**raw per-attempt JSONL was never committed** → it is **not independently regenerable**, so the
2026-06-14 hardening audit (H2) demoted the `p=0.016` headline to *historical, not authoritative*.

A committed re-pin on a **weaker** model — `verification/lean_headroom_repin_7b_2026-06-14/`
(`qwen2.5:7b`, n=10) — is a **NULL**: repair 13 = best-of-N 13, sign-test 2 wins / 2 losses /
6 ties, two-sided **p = 1.00**. (Verified here: `uv run python -m engine.efficacy.analyze_lean_headroom
verification/lean_headroom_repin_7b_2026-06-14` reproduces exactly that.) The 7b null is a *lower*
operating point and does **not** by itself refute the 32b claim — but the 32b result stays
**unreproduced with committed logs**. This directory exists to fix that: re-run on dgx-local
qwen2.5:32b **and commit the raw JSONL**.

## The exact command

```bash
bash verification/lean_headroom_repin_32b_2026-06-18/run_repin.sh
```

It is idempotent. It:
1. **Preflights** dgx reachability (`curl http://100.64.0.3:8000/v1/models`); on `http_code=000`
   it aborts cleanly with exit 3 and prints what to restore (it does **not** fabricate results).
2. Pins `BHGMAN_LLM_MODEL=qwen2.5:32b` (overriding `env.vllm.sh`'s default `qwen3.6-27b`; on the
   openai-compat backend `client.py` uses `BHGMAN_LLM_MODEL` as the authoritative served-model id).
   Override with `BHGMAN_LLM_MODEL_32B=<id>` if dgx serves the 32b under a different name.
3. Runs the **exact powered Run-B config**: `--k 4 --replications 10 --seed-step 10`, raw JSONL
   written into **this committed directory** (`seed_0.jsonl` … `seed_90.jsonl`, mirroring the 7b dir).
4. Runs `analyze_lean_headroom` on this dir → recomputes the sign-test + per-task counts from the
   raw logs (not from any markdown table).

## The blocker — dgx is DOWN

`http://100.64.0.3:8000/v1` returns **http_code=000** (curl exit 28, timeout) as of 2026-06-18.
The live experiment **cannot run** until the dgx backend is restored. Two things must come back
(per `reference_dgx_vllm_gb10_setup`):

- **`vllm-relay.service`** on the dgx host (systemd, root) — the `nsenter`+`socat` relay that
  exposes the k8s pod's `:8000` on the host `:8000` so Mac can reach it at `100.64.0.3:8000`.
- **a backend actually serving `qwen2.5:32b`.** The current vLLM k8s pod serves `qwen3.6-27b`,
  not the 32b. For an apples-to-apples re-pin of the *32b* claim, either:
  - **(a)** re-enable ollama on dgx (`systemctl enable --now ollama` + `ollama pull qwen2.5:32b`)
    and expose `:11434` as the `/v1` endpoint — this matches the historical Run B serving path; or
  - **(b)** serve `Qwen2.5-32B-Instruct` via vLLM and point `BHGMAN_LLM_BASE_URL` at it.

Until then this directory holds only the runner + this README; `seed_*.jsonl` are populated by the
real run (deferred — **no fabricated logs**).

## Pass / fail criterion

Recomputed by `analyze_lean_headroom` over the committed `seed_*.jsonl`:

- **PASS (CONFIRMS the historical 32b p=0.016):** headroom **repair ≥ best-of-N in every run**,
  strict-win majority, and **sign-test two-sided p < 0.05**.
- **FAIL (REFUTES / does not reproduce):** `p ≥ 0.05`, or any run where best-of-N strictly beats
  repair on headroom. Record the outcome honestly here and propagate to `VERDICT.md` /
  `LEAN_HEADROOM_FAIRTEST_2026-06-05.md` (which currently mark the 32b result *unreproduced*).

This is the test that turns the project's single positive signal from *historical anecdote* into
either a **committed, regenerable result** or an **honest retraction**.

# KG: efficacy-measurement-line-2026-06-01, project_bhgman_efficacy_verdict_operational_substrate_2026_06_02
