"""Claude 모델 ID 단일 출처 (claude-api skill 정본, 2026-05-28).

병렬 서브에이전트 = Haiku (싸고 빠름), 합성/판단 = Opus (가장 유능).
모델 ID는 정확 문자열만 — 날짜 suffix 금지 (claude-api skill).
"""

from __future__ import annotations

OPUS = "claude-opus-4-7"  # 합성/판단 (가장 유능, adaptive thinking, effort 지원)
SONNET = "claude-sonnet-4-6"  # 속도-지능 균형 (effort 지원)
HAIKU = "claude-haiku-4-5"  # 싸고 빠름 — 병렬 서브에이전트용 (effort 미지원)

# 역할별 default
SUBAGENT_MODEL = HAIKU  # N개 병렬 fan-out
SYNTHESIS_MODEL = OPUS  # 수확분 합성 / 판단 렌즈

# effort는 Opus/Sonnet 4.6+ 만 (Haiku 4.5에 주면 400). 이 집합으로 가드.
EFFORT_CAPABLE = frozenset({OPUS, SONNET, "claude-opus-4-6", "claude-opus-4-5"})

__all__ = [
    "EFFORT_CAPABLE",
    "HAIKU",
    "OPUS",
    "SONNET",
    "SUBAGENT_MODEL",
    "SYNTHESIS_MODEL",
]
