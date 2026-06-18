#!/usr/bin/env bash
# Reproducibility re-pin of the ONE positive efficacy signal (engine/efficacy/VERDICT.md §3):
#   "oracle-guided repair loop BEATS best-of-N on boundary headroom Lean tasks, sign-test p=0.016
#    on qwen2.5:32b" — but the original Run B raw JSONL was NEVER committed → historical, not
#   authoritative. This script RE-RUNS that exact powered Run-B config on dgx-hosted qwen2.5:32b
#   AND writes the raw per-attempt JSONL into THIS committed directory, then recomputes the
#   sign-test from those logs. One command, idempotent, with a hard dgx-reachability preflight.
#
# Mirrors the committed 7b re-pin layout (verification/lean_headroom_repin_7b_2026-06-14/, which
# is a NULL at the lower 7b operating point). This 32b run is what CONFIRMS or REFUTES the
# historical p=0.016.
#
# Run B config (engine/efficacy/LEAN_HEADROOM_FAIRTEST_2026-06-05.md "Reproduction hardening"):
#   model qwen2.5:32b · K=4 · 10 seed replications (offset 0..90, step 10) · graded oracle.
#   The headroom band (10 headroom tasks, 5 live) is fixed in engine/efficacy/lean_tasks.py.
#
# Usage:  bash verification/lean_headroom_repin_32b_2026-06-18/run_repin.sh
# Pass criterion: repair >= best-of-N on headroom in every run, strict-win majority, sign-test p<0.05.
#
# # KG: efficacy-measurement-line-2026-06-01, project_bhgman_efficacy_verdict_operational_substrate_2026_06_02
set -euo pipefail

# ── resolve repo root (this script lives in verification/lean_headroom_repin_32b_2026-06-18/) ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_DIR="${SCRIPT_DIR}"   # raw JSONL is committed alongside this script (mirror of the 7b dir)
cd "${REPO_ROOT}"

# ── dgx vLLM backend (openai-compat). MODEL pinned to qwen2.5:32b for the 32b re-pin. ──
# env.vllm.sh serves qwen3.6-27b by default; we OVERRIDE BHGMAN_LLM_MODEL because client.py's
# openai-compat path uses os.environ["BHGMAN_LLM_MODEL"] as the AUTHORITATIVE served-model name
# (the model string the runner passes is ignored on this backend — see engine/agents/client.py).
export BHGMAN_LLM_BASE_URL="${BHGMAN_LLM_BASE_URL:-http://100.64.0.3:8000/v1}"
export BHGMAN_LLM_MODEL="${BHGMAN_LLM_MODEL_32B:-qwen2.5:32b}"   # historical Run B id: qwen2.5:32b(-instruct)
export BHGMAN_LLM_API_KEY="${BHGMAN_LLM_API_KEY:-EMPTY}"
export BHGMAN_LLM_TIMEOUT="${BHGMAN_LLM_TIMEOUT:-300}"   # 32b on dgx is slow per call
# P1_MODEL/P1_TEMP for the runner's prompt/seed path (fairness: temp>0 → independent draws).
export P1_MODEL="${BHGMAN_LLM_MODEL}"
export P1_TEMP="${P1_TEMP:-0.8}"
# NB: do NOT set BHGMAN_LLM_NO_THINK here — qwen2.5:32b is a non-reasoning instruct model.

# Run-B powered config (do not change without re-pinning the claim):
K="${LEAN_K:-4}"
REPLICATIONS="${LEAN_REPLICATIONS:-10}"
SEED_STEP="${LEAN_SEED_STEP:-10}"
SEED_OFFSET="${SEED_OFFSET:-0}"

echo "=== lean-headroom 32b re-pin (Run-B powered config) ==="
echo "  model       : ${BHGMAN_LLM_MODEL}  @ ${BHGMAN_LLM_BASE_URL}"
echo "  K           : ${K}"
echo "  replications: ${REPLICATIONS} (seed_offset ${SEED_OFFSET}..$((SEED_OFFSET + (REPLICATIONS-1)*SEED_STEP)) step ${SEED_STEP})"
echo "  out-dir     : ${OUT_DIR}  (raw JSONL committed here)"
echo

# ── PREFLIGHT 1: dgx vLLM reachability. curl-fail / http_code=000 → dgx DOWN → abort cleanly. ──
# Use curl's own exit status (28=timeout, 7=refused) as the authoritative "unreachable" signal;
# http_code is only meaningful when curl itself succeeded. (No ||echo fallback — that concatenates.)
echo "[preflight] probing ${BHGMAN_LLM_BASE_URL}/models ..."
HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "${BHGMAN_LLM_BASE_URL}/models" 2>/dev/null)" && CURL_RC=0 || CURL_RC=$?
if [ "${CURL_RC}" -ne 0 ] || [ -z "${HTTP_CODE}" ] || [ "${HTTP_CODE}" = "000" ]; then
  echo "[preflight] FAIL: dgx unreachable (curl_rc=${CURL_RC} http_code='${HTTP_CODE:-none}') — vLLM/ollama backend is DOWN."
  echo "[preflight] This re-pin is DEFERRED. Restore the dgx backend, then re-run this script."
  echo "[preflight] What to restore (per reference_dgx_vllm_gb10_setup):"
  echo "             - dgx host systemd 'vllm-relay.service' (pod IP -> host :8000 socat relay), AND"
  echo "             - a backend actually serving qwen2.5:32b. The current vLLM pod serves"
  echo "               qwen3.6-27b; for the 32b re-pin either (a) re-enable ollama on dgx"
  echo "               ('systemctl enable --now ollama' + 'ollama pull qwen2.5:32b', expose :11434"
  echo "               as :8000/v1), or (b) serve Qwen2.5-32B via vLLM. Then set BHGMAN_LLM_BASE_URL"
  echo "               to the endpoint that serves it (default http://100.64.0.3:8000/v1)."
  exit 3
fi
echo "[preflight] dgx reachable (http_code=${HTTP_CODE})."

# ── PREFLIGHT 2: served model id sanity. Warn (don't abort) if 32b not in /v1/models. ──
MODELS_JSON="$(curl -s --max-time 8 "${BHGMAN_LLM_BASE_URL}/models" 2>/dev/null || echo '{}')"
if ! printf '%s' "${MODELS_JSON}" | grep -qi 'qwen2.5:32b\|qwen2.5-32b'; then
  echo "[preflight] WARN: '${BHGMAN_LLM_MODEL}' not visibly listed in /v1/models response."
  echo "[preflight]       Listed ids: $(printf '%s' "${MODELS_JSON}" | grep -o '"id":"[^"]*"' | head -8 | tr '\n' ' ')"
  echo "[preflight]       If dgx serves the 32b under a different id, set BHGMAN_LLM_MODEL_32B=<id> and re-run."
  echo "[preflight]       Continuing — the openai-compat backend will pass '${BHGMAN_LLM_MODEL}' through."
fi

# ── PREFLIGHT 3: local lean toolchain (the ungameable oracle runs on THIS machine). ──
if ! command -v lean >/dev/null 2>&1; then
  echo "[preflight] FAIL: 'lean' not on PATH — the ungameable Lean oracle cannot run locally."
  echo "[preflight] Install elan/lean (Lean 4 core; no Mathlib needed) and re-run."
  exit 4
fi
echo "[preflight] lean toolchain present: $(lean --version 2>/dev/null | head -1)"
echo

# ── RUN: write raw JSONL into the committed dir (idempotent: --out-dir overwrites seed_*.jsonl) ──
echo "[run] executing powered Run-B sweep (this is slow on dgx 32b — expect tens of minutes)..."
uv run python -m engine.efficacy.lean_headroom_run \
  --k "${K}" \
  --replications "${REPLICATIONS}" \
  --seed-offset "${SEED_OFFSET}" \
  --seed-step "${SEED_STEP}" \
  --out-dir "${OUT_DIR}"

echo
echo "[analyze] recomputing sign-test + per-task counts from committed raw JSONL ..."
uv run python -m engine.efficacy.analyze_lean_headroom "${OUT_DIR}"

echo
echo "=== done. Raw JSONL written to ${OUT_DIR}/seed_*.jsonl ==="
echo "Pass criterion: headroom repair >= best-of-N every run + strict-win majority + sign-test p<0.05."
echo "  p<0.05 & repair>=bestN  => CONFIRMS historical 32b p=0.016."
echo "  p>=0.05 or a reversal    => REFUTES / fails to reproduce it (record honestly in README.md)."
