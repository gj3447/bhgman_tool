"""scale_curve 테스트 — longinus flat / base-LLM 컨텍스트 벽."""

from __future__ import annotations

from engine.efficacy.scale_curve import run_curve, scale_point


def test_longinus_flat_accuracy_across_scale():
    pts = run_curve((100, 1000, 10000))
    accs = {p.longinus_classification for p in pts}
    assert len(accs) == 1  # 모든 N에서 동일 (결정론, flat)


def test_base_llm_tokens_grow_and_overflow():
    small = scale_point(100)
    huge = scale_point(100000)
    assert huge.base_llm_prompt_tokens > small.base_llm_prompt_tokens * 100
    assert huge.base_llm_context_overflow is True  # 100k 노드 = 컨텍스트 초과
    assert small.base_llm_context_overflow is False


def test_cost_scales_linearly_ish():
    p = scale_point(10000)
    assert p.base_llm_cost_usd > 0
    assert p.longinus_seconds < 1.0  # longinus는 1만 노드도 1초 미만
