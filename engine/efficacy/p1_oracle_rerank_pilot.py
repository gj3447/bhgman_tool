"""P1 — oracle-reranked best-of-N: bhgman의 첫 *cognitive lift* 실증 시도 (pilot).

PROM_16_COGNITIVE_LIFT_REPORT 의 권장 첫 실험. 가설(bitter-lesson 반증):
  base-LLM을 *동일 토큰 예산*에서 이기려면 oracle을 종료 GATE가 아니라 search 신호로
  써야 한다. 코드 도메인은 oracle(실행)이 완벽·공짜라 verifier가 병목이 아니다.

4 arm (전부 같은 N 샘플 = 같은 토큰; 차이는 *어느 샘플을 고르나*):
  · base@1            — 첫 샘플 (1× 토큰, 비교 anchor)
  · self_consistency  — N 중 *모달 코드* (합의, oracle 미사용)
  · oracle_rerank     — N 중 *public test 최다 통과* (실행 oracle = ~0 토큰)  ← bhgman arm
  · pass@N            — N 중 하나라도 hidden 전부 통과 (천장)

정직성 (falsifier):
  · rerank 신호 = PUBLIC tests / 평가 = HIDDEN tests (분리 → 비순환, LEVER/AlphaCode).
  · lift = oracle_rerank − self_consistency  (동일 토큰. pass@1만 이기면 그냥 compute 더 쓴 것).
  · bootstrap CI(lift) 가 0 제외해야 주장. 난이도 medium band에서만 기대 (Snell/D3).
  · ablation: real-oracle(public tests) vs LLM-judge 같은 N → A≫judge면 lift는 oracle에서.

실행: dgx ollama (qwen2.5:0.5b/1.5b = 약한 base). 샌드박스 subprocess 격리 실행.

# KG: lesson-bhgman-cognitive-lift-requires-oracle-guided-search-2026-06-02,
#     efficacy-measurement-line-2026-06-01, project_bhgman_ab_falsifier_2026_05_30
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from collections import Counter
from dataclasses import dataclass

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/v1/chat/completions")
MODEL = os.environ.get("P1_MODEL", "qwen2.5:0.5b-instruct")
N = int(os.environ.get("P1_N", "8"))
TEMP = float(os.environ.get("P1_TEMP", "0.8"))
SEED_BASE = int(os.environ.get("P1_SEED", "1000"))
MAX_TOK = int(os.environ.get("P1_MAX_TOKENS", "700"))  # raise for reasoning models (qwen3 <think>)


@dataclass
class Task:
    name: str
    difficulty: str  # easy | medium | hard
    prompt: str  # function spec
    public_tests: list[str]  # rerank signal (visible)
    hidden_tests: list[str]  # evaluation (held out)


@dataclass
class SampleRun:
    code: str
    public_pass: int
    public_total: int
    hidden_ok: bool
    tokens: int


@dataclass
class TaskResult:
    task: str
    difficulty: str
    base1: bool
    self_consistency: bool
    oracle_rerank: bool
    judge_rerank: bool  # LLM-judge picks best-of-N (ablation: judge vs oracle)
    passN: bool
    n_tokens_total: int
    n_judge_tokens: int
    n_valid: int


# --------------------------------------------------------------------------- LLM


def _ollama(messages: list[dict], seed: int) -> tuple[str, int]:
    body = json.dumps(
        {
            "model": MODEL,
            "messages": messages,
            "temperature": TEMP,
            "seed": seed,
            "max_tokens": MAX_TOK,
        }
    ).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    text = d["choices"][0]["message"]["content"]
    toks = int(d.get("usage", {}).get("total_tokens", 0))
    return text, toks


def _extract_code(text: str) -> str:
    m = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return max(m, key=len).strip()
    return text.strip()


def _llm_judge(task: "Task", codes: list[str]) -> tuple[int, int]:
    """Ablation arm: an LLM (not the oracle) picks the best-of-N. Returns
    (index, judge_tokens). If oracle_rerank >> judge_rerank, the lift is
    attributable to the *execution oracle*, not to having a reranker."""
    listing = "\n\n".join(f"### Candidate {i}\n```python\n{c}\n```" for i, c in enumerate(codes))
    msg = [
        {
            "role": "system",
            "content": "You judge Python solutions. Reply with ONLY the integer index of the candidate most likely to be correct.",
        },
        {
            "role": "user",
            "content": f"Task:\n{task.prompt}\n\n{listing}\n\nWhich candidate index is most likely correct? Reply with only the number.",
        },
    ]
    try:
        text, toks = _ollama(msg, seed=SEED_BASE)
        m = re.search(r"\d+", text)
        idx = int(m.group()) if m else 0
        return (idx if 0 <= idx < len(codes) else 0), toks
    except Exception:
        return 0, 0


# ----------------------------------------------------------------------- sandbox


def _run_tests(code: str, tests: list[str]) -> int:
    """격리 subprocess 에서 code + tests 실행, 통과한 assert 수 반환."""
    passed = 0
    for t in tests:
        script = code + "\n\n" + t + "\nprint('OK')\n"
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(script)
            path = f.name
        try:
            p = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=8)
            if p.returncode == 0 and "OK" in p.stdout:
                passed += 1
        except Exception:
            pass
        finally:
            os.unlink(path)
    return passed


# ------------------------------------------------------------------------- arms


def run_task(task: Task) -> TaskResult:
    sys_msg = {
        "role": "system",
        "content": "You are a Python expert. Return ONLY a single ```python code block with the requested function. No explanation.",
    }
    user = {"role": "user", "content": task.prompt}

    samples: list[SampleRun] = []
    total_tokens = 0
    for i in range(N):
        try:
            text, toks = _ollama([sys_msg, user], seed=SEED_BASE + i)
        except Exception as e:
            print(f"    [warn] gen fail {task.name} s{i}: {e}", file=sys.stderr)
            continue
        code = _extract_code(text)
        total_tokens += toks
        pub = _run_tests(code, task.public_tests)
        hid = _run_tests(code, task.hidden_tests)
        samples.append(
            SampleRun(code, pub, len(task.public_tests), hid == len(task.hidden_tests), toks)
        )

    if not samples:
        return TaskResult(
            task.name, task.difficulty, False, False, False, False, False, total_tokens, 0, 0
        )

    # base@1 — 첫 샘플
    base1 = samples[0].hidden_ok

    # self_consistency — 모달 코드(정규화 source 최빈), 그 대표의 hidden
    norm = [re.sub(r"\s+", " ", s.code.strip()) for s in samples]
    modal = Counter(norm).most_common(1)[0][0]
    sc_rep = next(s for s, n in zip(samples, norm) if n == modal)
    self_consistency = sc_rep.hidden_ok

    # oracle_rerank — public 최다통과(동률시 모달클러스터 큰쪽), 그 대표의 hidden
    best_pub = max(s.public_pass for s in samples)
    cands = [s for s in samples if s.public_pass == best_pub]
    if len(cands) > 1:
        cand_norm = Counter(re.sub(r"\s+", " ", c.code.strip()) for c in cands)
        cands.sort(key=lambda c: cand_norm[re.sub(r"\s+", " ", c.code.strip())], reverse=True)
    oracle_rerank = cands[0].hidden_ok

    # judge_rerank — LLM-judge ablation (costs extra tokens; oracle costs ~0)
    judge_idx, judge_tokens = _llm_judge(task, [s.code for s in samples])
    judge_rerank = samples[judge_idx].hidden_ok

    passN = any(s.hidden_ok for s in samples)

    return TaskResult(
        task.name,
        task.difficulty,
        base1,
        self_consistency,
        oracle_rerank,
        judge_rerank,
        passN,
        total_tokens,
        judge_tokens,
        len(samples),
    )


# -------------------------------------------------------------------- bootstrap


def _bootstrap_ci(deltas: list[int], iters: int = 10000) -> tuple[float, float, float]:
    """paired delta(=oracle_rerank − self_consistency, per task ∈ {-1,0,1}) 의 평균 + 95% CI.
    결정론 LCG(시드 고정)로 외부 의존 없이."""
    n = len(deltas)
    if n == 0:
        return 0.0, 0.0, 0.0
    mean = sum(deltas) / n
    state = 0x2545F4914F6CDD1D
    means = []
    for _ in range(iters):
        s = 0
        for _ in range(n):
            state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
            # HIGH bits: LCG low bits are periodic (period <= n) → every "resample" drew a fixed
            # cyclic index pattern → degenerate lo==hi CI = FALSE POSITIVE on sparse small-n deltas
            # (funsearch n=8 [8,0×7] reported realized=True spuriously). Verified vs true-random 2026-06-03.
            s += deltas[(state >> 33) % n]
        means.append(s / n)
    means.sort()
    return mean, means[int(0.025 * iters)], means[int(0.975 * iters)]


# ------------------------------------------------------------------------- main


def summarize(results: list[TaskResult]) -> dict:
    arms = ["base1", "self_consistency", "judge_rerank", "oracle_rerank", "passN"]
    out = {}
    for band in ["all", "easy", "medium", "hard"]:
        rs = results if band == "all" else [r for r in results if r.difficulty == band]
        if not rs:
            continue
        out[band] = {a: round(sum(getattr(r, a) for r in rs) / len(rs), 3) for a in arms}
        out[band]["n"] = len(rs)
        # primary lift: oracle-rerank vs self-consistency (same N = same gen tokens)
        d_sc = [int(r.oracle_rerank) - int(r.self_consistency) for r in rs]
        m, lo, hi = _bootstrap_ci(d_sc)
        out[band]["lift_vs_sc"] = round(m, 3)
        out[band]["lift_vs_sc_ci95"] = [round(lo, 3), round(hi, 3)]
        out[band]["lift_vs_sc_excludes_0"] = lo > 0 or hi < 0
        # ablation: oracle-rerank vs LLM-judge-rerank (attributes lift to the oracle)
        d_j = [int(r.oracle_rerank) - int(r.judge_rerank) for r in rs]
        mj, loj, hij = _bootstrap_ci(d_j)
        out[band]["lift_vs_judge"] = round(mj, 3)
        out[band]["lift_vs_judge_ci95"] = [round(loj, 3), round(hij, 3)]
        out[band]["lift_vs_judge_excludes_0"] = loj > 0 or hij < 0
        out[band]["gen_tokens"] = sum(r.n_tokens_total for r in rs)
        out[band]["judge_tokens"] = sum(r.n_judge_tokens for r in rs)  # oracle costs ~0 of these
    return out


def main(tasks: list[Task]) -> None:
    print(
        f"P1 oracle-rerank pilot — model={MODEL} N={N} temp={TEMP} tasks={len(tasks)}",
        file=sys.stderr,
    )
    results = []
    for i, t in enumerate(tasks):
        r = run_task(t)
        results.append(r)
        print(
            f"  [{i+1}/{len(tasks)}] {t.name:24} ({t.difficulty:6}) "
            f"base={int(r.base1)} sc={int(r.self_consistency)} "
            f"rerank={int(r.oracle_rerank)} passN={int(r.passN)} tok={r.n_tokens_total}",
            file=sys.stderr,
        )
    summary = summarize(results)
    print(
        json.dumps(
            {"model": MODEL, "N": N, "summary": summary, "tasks": [r.__dict__ for r in results]},
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    from engine.efficacy.p1_tasks import TASKS  # noqa: E402

    main(TASKS)
