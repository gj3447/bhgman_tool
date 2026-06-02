"""composition 4th gate TDD — 주입식 fake LLM 으로 게이트 발화 가능성을 결정론적으로 증명.

핵심: 게이트가 *양방향*으로 발화함을 보여야 신뢰할 수 있다 —
(1) read-back 가 도움되는 planted 조건 → realized=True,
(2) read-back 가 무용한 planted 조건 → realized=False.
+ 토큰 동수(equal-compute 통제) 검증. ollama 실행 없이 (DI fake LLM).

# KG: prom16-bhgman-ci-design-2026-06-02 §5, lesson-bhgman-cognitive-lift-requires-oracle-guided-search-2026-06-02
"""

from __future__ import annotations

from engine.efficacy.composition_ab import run_gate
from engine.efficacy.p1_oracle_rerank_pilot import Task

# planted task: GOOD=solve(x)->x+1 가 public+hidden 통과, BAD=solve(x)->x 는 실패.
_GOOD = "def solve(x):\n    return x + 1"
_BAD = "def solve(x):\n    return x"


def _task(name: str) -> Task:
    return Task(
        name=name,
        difficulty="medium",
        prompt="Write def solve(x): returning x+1.",
        public_tests=["assert solve(1) == 2"],
        hidden_tests=["assert solve(5) == 6", "assert solve(0) == 1"],
    )


_PLANTED = [_task("p1"), _task("p2"), _task("p3")]


def _fake_readback_helps(messages, seed):
    """read-back(prior attempt)이 프롬프트에 있으면 GOOD, 아니면 BAD → 반복이 도움되는 조건."""
    text = " ".join(m["content"] for m in messages)
    code = _GOOD if "prior attempt" in text else _BAD
    return f"```python\n{code}\n```", 100


def _fake_always_good(messages, seed):
    """read-back 유무 무관 항상 GOOD → 1-shot 이 이미 풂, 반복 무용 조건."""
    return f"```python\n{_GOOD}\n```", 100


def test_gate_fires_realized_when_readback_helps():
    v = run_gate(_PLANTED, _fake_readback_helps, budget_tokens=300, seed0=1)
    assert v.realized is True
    assert v.arm2_beats_arm1 is True
    assert v.arm2_beats_arm3 is True
    assert v.rates["evolve"] == 1.0  # read-back 으로 GOOD 도달
    assert v.rates["best_of_n"] == 0.0  # blind 는 BAD 만
    assert v.rates["oracle_gate"] == 0.0  # gate 통과 0 → BAD fallback
    assert v.lift_vs_arm1[1] > 0  # lower CI bound > 0


def test_gate_emits_unrealized_when_readback_useless():
    v = run_gate(_PLANTED, _fake_always_good, budget_tokens=300, seed0=1)
    assert v.realized is False  # 모든 arm 동일(1.0) → 루프 이득 없음
    assert v.rates["evolve"] == 1.0
    assert v.rates["best_of_n"] == 1.0
    assert v.lift_vs_arm1 == (0.0, 0.0, 0.0)
    assert "UNREALIZED" in v.reason


def test_token_parity_across_arms():
    """equal-compute 통제: 세 arm 의 총 생성 토큰이 동수여야 (정직한 비교 전제)."""
    v = run_gate(_PLANTED, _fake_readback_helps, budget_tokens=300, seed0=1)
    toks = set(v.gen_tokens.values())
    assert len(toks) == 1  # best_of_n == evolve == oracle_gate
    assert v.gen_tokens["evolve"] == 300 * len(_PLANTED)  # 3 calls/task × 100 tok


def test_verdict_reason_names_failure_mode():
    """ARM2<=ARM1 → 'just more compute', ARM2<=ARM3 → 'oracle did it' 을 reason 이 명시."""
    v = run_gate(_PLANTED, _fake_always_good, budget_tokens=300, seed0=1)
    assert ("more compute" in v.reason) or ("oracle did it" in v.reason)
