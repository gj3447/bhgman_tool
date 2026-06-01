"""A/B falsifier — llm_decompose vs 결정론 decompose 구조 비교 (PROM 16 P4/C6).

dispatch가 falsifier상 인지기여 0이었던 전례 → "LLM decompose가 kg/static보다 나은가"를
가정 말고 *측정*. 이 harness는 같은 goal·같은 max_depth로 두 분해 전략의 계획 트리를 만들어
구조 발산(node 수/depth/jaccard/arm-only)을 raw로 보고한다.

Goodhart 가드: **단일 품질 점수 없음**. 가독성≠정확성 착각 차단 — 발산 raw만 찍고 판단은 외부
oracle/사용자. 공정성: 두 arm 동일 max_depth, 동일 goal. 실 falsification은 arm_a에 실 LLM
(도구예산 통제) 주입 + 외부 oracle 채점 — 본 파일 default는 fake-LLM 데모(harness 검증용).

# KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01 (C6), finding-jbm-eng-D3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from engine.jaebaeman.ab_compare import compare_decompose  # noqa: E402
from engine.jaebaeman.jaebaeman_models import Goal  # noqa: E402
from engine.jaebaeman.llm_decompose import from_agent_client, llm_decompose  # noqa: E402
from engine.jaebaeman.planner import DecomposeFn, static_decompose  # noqa: E402


def _naive_baseline_arm(root: str) -> DecomposeFn:
    """결정론 dumb baseline — 어떤 목표든 design/implement/verify 3단계 고정 (LLM 없는 대조군)."""

    def dec(node):
        if node.name != root:
            return []
        return [
            Goal(name=f"{root}::design", objective="design"),
            Goal(name=f"{root}::implement", objective="implement"),
            Goal(name=f"{root}::verify", objective="verify"),
        ]

    return dec


def _real_llm_arm(model: str) -> DecomposeFn:
    """실 LLM arm — AgentClient(openai-compat/anthropic). web off(공정 예산). runtime 불가 시 raise."""
    from engine.agents.client import AgentClient  # noqa: PLC0415

    return llm_decompose(from_agent_client(AgentClient(), model=model))


def _fake_llm_arm() -> DecomposeFn:
    """데모용 결정론 fake-LLM — goal당 고정 JSON 반환. (실 LLM은 --llm로 주입)"""
    canned = {
        "ship-feature": '[{"name":"design","objective":"design"},{"name":"impl","objective":"impl"},{"name":"test","objective":"test"}]',
        "impl": '[{"name":"impl.core","objective":"core"},{"name":"impl.glue","objective":"glue"}]',
    }
    return llm_decompose(lambda prompt: next((v for k, v in canned.items() if k in prompt), "[]"))


def _baseline_arm() -> DecomposeFn:
    """결정론 baseline (static/kg 대역) — fake-LLM과 다른 분해 → 발산 시연."""
    return static_decompose(
        {
            "ship-feature": [
                Goal(name="design", objective="design"),
                Goal(name="build", objective="build"),  # impl 대신 build (의도적 발산)
            ],
            "build": [Goal(name="build.core", objective="core")],
        }
    )


def main() -> int:
    import os  # noqa: PLC0415

    parser = argparse.ArgumentParser(prog="bench_decompose_ab")
    parser.add_argument("--goal", default="ship-feature", help="비교할 goal name.")
    parser.add_argument("--depth", type=int, default=3, help="max_depth (양 arm 공통).")
    parser.add_argument(
        "--llm", action="store_true", help="arm_a를 실 LLM로 (AgentClient). 없으면 fake-llm 데모."
    )
    args = parser.parse_args()

    if args.llm:
        model = os.environ.get("BHGMAN_LLM_MODEL", "claude-haiku-4-5-20251001")
        arm_a, arm_a_kind, arm_b = (
            _real_llm_arm(model),
            f"real-llm:{model}",
            _naive_baseline_arm(args.goal),
        )
        arm_b_kind = "naive-3phase-baseline"
    else:
        arm_a, arm_a_kind, arm_b, arm_b_kind = (
            _fake_llm_arm(),
            "fake-llm",
            _baseline_arm(),
            "static-baseline",
        )

    result = compare_decompose(
        Goal(name=args.goal, objective="(A/B falsifier)"), arm_a, arm_b, max_depth=args.depth
    )
    print(json.dumps({"arm_a_kind": arm_a_kind, "arm_b_kind": arm_b_kind, **result}, indent=2))
    print(
        "\n# C6: raw 발산만. '나음'은 외부 oracle 판단 (가독성≠정확성 Goodhart 가드).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
