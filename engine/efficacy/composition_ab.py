"""engine/efficacy 4th gate — Verification-Grounded Composition A/B (loop-realization falsifier).

prom16-bhgman-ci-design §5. evolve_loop(read-back 루프)가 equal-compute 에서 *진짜* 이득을
내는지 판정하는 게이트. 3 arm, **동일 총 생성-토큰 예산 T**(동일 N 아님 — 루프는 재생성하므로
토큰 동수가 정직한 통제). 평가 = HIDDEN test 만, read-back/oracle 신호 = PUBLIC test 만
(비순환 분리, LEVER/AlphaCode).

  ARM1 best-of-N   — blind: T 토큰까지 독립 샘플, public 최다통과 pick, hidden 평가. (read-back 無)
  ARM2 evolve-loop — read-back: ProgramDatabase best-K 를 프롬프트로 되먹임, T 까지 반복. (루프 그 자체)
  ARM3 oracle-gate — public 전부 통과한 샘플만 keep, 하나 pick, hidden 평가. (oracle, 루프·judge 無)

realized = ARM2 가 ARM1 AND ARM3 *둘 다* 이김 (paired bootstrap CI lower bound > 0).
  ARM2<=ARM1 → "그냥 compute 더 씀"; ARM2<=ARM3 → "oracle 가 한 것, 루프는 장식".

이 모듈은 evolve_loop.ProgramDatabase + ScalarOracle 를 *실제* pytest oracle 에 배선한다 —
"unwired island" gap(critic verdict 2026-06-02)을 닫는다. test_composition_ab.py 는 주입식
fake LLM 으로 게이트가 *발화 가능*함을 결정론적으로 증명(planted: 반복이 도움 → realized /
반복 무용 → unrealized). 게이트 로직은 offline falsifiable, ollama run 은 그 위 경험 층.

# KG: prom16-bhgman-ci-design-2026-06-02, lesson-bhgman-cognitive-lift-requires-oracle-guided-search-2026-06-02,
#     efficacy-measurement-line-2026-06-01, project_bhgman_ab_falsifier_2026_05_30
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from engine.efficacy.p1_oracle_rerank_pilot import (
    Task,
    _bootstrap_ci,
    _extract_code,
    _ollama,
    _run_tests,
)
from engine.legion.evolve_loop import ProgramDatabase
from engine.naesengmoon.oracle_lens import ScalarOracle

# complete(messages, seed) -> (text, tokens). p1._ollama 와 동형 (테스트는 fake 주입).
CompleteFn = Callable[[list[dict], int], "tuple[str, int]"]

_SYS = {
    "role": "system",
    "content": "You are a Python expert. Return ONLY a single ```python code block "
    "with the requested function. No explanation.",
}


def _public_oracle(task: Task) -> ScalarOracle:
    """외부 결정론 fitness = PUBLIC test 통과 수 (실행 oracle, ~0 토큰). 높을수록 좋음."""
    return ScalarOracle(
        name="pytest-public",
        kind="pytest-ratio",
        score=lambda code: float(_run_tests(code, task.public_tests)),
    )


def _gen(
    task: Task, complete: CompleteFn, seed: int, prior: list[str] | None = None
) -> tuple[str, int]:
    """1회 생성. prior(이전 best-K 코드)가 있으면 read-back 프롬프트(개선 지시)."""
    if prior:
        listing = "\n\n".join(f"# prior attempt {i}:\n{c}" for i, c in enumerate(prior))
        user = {
            "role": "user",
            "content": f"{task.prompt}\n\nIMPROVE on these prior attempts "
            f"(fix what fails, keep what works):\n{listing}",
        }
    else:
        user = {"role": "user", "content": task.prompt}
    text, toks = complete([_SYS, user], seed)
    return _extract_code(text), toks


def _hidden_ok(code: str, task: Task) -> bool:
    return _run_tests(code, task.hidden_tests) == len(task.hidden_tests)


def _arm_best_of_n(task: Task, complete: CompleteFn, budget: int, seed0: int) -> tuple[bool, int]:
    """ARM1 — T 토큰까지 독립 샘플, public 최다통과 pick (read-back 無)."""
    oracle = _public_oracle(task)
    db = ProgramDatabase()
    tok = 0
    i = 0
    while tok < budget:
        code, t = _gen(task, complete, seed0 + i)
        tok += t
        i += 1
        db.add(payload=code, score=oracle.evaluate(code).value, generation=0, parent=None)
    best = db.best()
    return (_hidden_ok(best.payload, task) if best else False), tok


def _arm_evolve(task: Task, complete: CompleteFn, budget: int, seed0: int) -> tuple[bool, int]:
    """ARM2 — read-back 루프: best-K 를 프롬프트로 되먹여 T 까지 반복 (evolve_loop primitive 배선)."""
    oracle = _public_oracle(task)
    db = ProgramDatabase()
    tok = 0
    i = 0
    gen = 0
    seed_code, t = _gen(task, complete, seed0)  # gen 0 (read-back 無)
    tok += t
    db.add(payload=seed_code, score=oracle.evaluate(seed_code).value, generation=0, parent=None)
    while tok < budget:
        gen += 1
        i += 1
        parents = db.best_k(2)
        code, t = _gen(task, complete, seed0 + i, prior=[c.payload for c in parents])
        tok += t
        parent_idx = parents[0].index if parents else None
        db.add(payload=code, score=oracle.evaluate(code).value, generation=gen, parent=parent_idx)
    best = db.best()
    return (_hidden_ok(best.payload, task) if best else False), tok


def _arm_oracle_gate(task: Task, complete: CompleteFn, budget: int, seed0: int) -> tuple[bool, int]:
    """ARM3 — public 전부 통과(hard gate)한 샘플만 keep, 하나 pick (루프·judge 無)."""
    oracle = _public_oracle(task)
    full = float(len(task.public_tests))
    db = ProgramDatabase()
    gated: list[str] = []
    tok = 0
    i = 0
    while tok < budget:
        code, t = _gen(task, complete, seed0 + i)
        tok += t
        i += 1
        score = oracle.evaluate(code).value
        db.add(payload=code, score=score, generation=0, parent=None)
        if score >= full:
            gated.append(code)
    if gated:
        return _hidden_ok(gated[0], task), tok
    best = db.best()  # gate 통과 0 → fallback best public
    return (_hidden_ok(best.payload, task) if best else False), tok


@dataclass
class CompositionVerdict:
    """3-arm 게이트 판정. realized = 루프 구조가 real (ARM2 가 ARM1·ARM3 둘 다 이김)."""

    realized: bool
    arm2_beats_arm1: bool
    arm2_beats_arm3: bool
    rates: dict = field(default_factory=dict)  # arm -> hidden pass rate
    lift_vs_arm1: tuple = (0.0, 0.0, 0.0)  # (mean, lo95, hi95)
    lift_vs_arm3: tuple = (0.0, 0.0, 0.0)
    gen_tokens: dict = field(default_factory=dict)
    n_tasks: int = 0
    reason: str = ""


def run_gate(
    tasks: list[Task],
    complete: CompleteFn = _ollama,
    *,
    budget_tokens: int,
    seed0: int = 1000,
) -> CompositionVerdict:
    """3 arm 을 동일 토큰 예산 T 로 실행 → CompositionVerdict."""
    a1: list[bool] = []
    a2: list[bool] = []
    a3: list[bool] = []
    tk = {"best_of_n": 0, "evolve": 0, "oracle_gate": 0}
    for task in tasks:
        ok1, t1 = _arm_best_of_n(task, complete, budget_tokens, seed0)
        ok2, t2 = _arm_evolve(task, complete, budget_tokens, seed0)
        ok3, t3 = _arm_oracle_gate(task, complete, budget_tokens, seed0)
        a1.append(ok1)
        a2.append(ok2)
        a3.append(ok3)
        tk["best_of_n"] += t1
        tk["evolve"] += t2
        tk["oracle_gate"] += t3

    d1 = [int(x2) - int(x1) for x2, x1 in zip(a2, a1)]
    d3 = [int(x2) - int(x3) for x2, x3 in zip(a2, a3)]
    lift1 = _bootstrap_ci(d1)
    lift3 = _bootstrap_ci(d3)
    beats1 = lift1[1] > 0  # lower 95% CI bound > 0 → ARM2 strictly above ARM1
    beats3 = lift3[1] > 0
    realized = beats1 and beats3
    n = len(tasks) or 1
    return CompositionVerdict(
        realized=realized,
        arm2_beats_arm1=beats1,
        arm2_beats_arm3=beats3,
        rates={
            "best_of_n": round(sum(a1) / n, 3),
            "evolve": round(sum(a2) / n, 3),
            "oracle_gate": round(sum(a3) / n, 3),
        },
        lift_vs_arm1=tuple(round(x, 3) for x in lift1),
        lift_vs_arm3=tuple(round(x, 3) for x in lift3),
        gen_tokens=tk,
        n_tasks=len(tasks),
        reason=(
            "REALIZED: read-back loop beats both best-of-N and oracle-gating at token parity"
            if realized
            else (
                "UNREALIZED: "
                + ("loop <= best-of-N (just more compute); " if not beats1 else "")
                + (
                    "loop <= oracle-gate (the oracle did it, loop is decoration); "
                    if not beats3
                    else ""
                )
            ).strip("; ")
        ),
    )


def main(tasks: list[Task], budget_tokens: int) -> None:
    print(
        f"composition 4th gate — budget_tokens={budget_tokens} tasks={len(tasks)}", file=sys.stderr
    )
    verdict = run_gate(tasks, budget_tokens=budget_tokens)
    print(json.dumps(verdict.__dict__, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    import os

    from engine.efficacy.p1_tasks import TASKS

    band = os.environ.get("CAB_BAND", "medium")
    budget = int(os.environ.get("CAB_BUDGET", "4000"))
    sel = TASKS if band == "all" else [t for t in TASKS if t.difficulty == band]
    main(sel, budget)
