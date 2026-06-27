"""StuckDetector — dispatch 루프 정체(무진전) 감지. 깊이캡과 직교.

깊이캡(depth cap)은 '얼마나 깊이' 를 막지만 '진전이 있나' 는 못 본다 — 같은 행동·관찰을
무한 반복해도 깊이만 안 넘으면 통과한다. StuckDetector 는 연속 N 라운드가 같은 progress
signature(무진전)면 halt 를 신호해 무진전 루프를 끊는다.

coding-harness-deepdive 교훈: OpenHands 의 StuckDetector(반복 action-observation 패턴 감지)는
'무한루프 방지(한도)' 와 '정체 감지' 가 **별개 메커니즘**임을 보여준다. 재배맨 dispatch 루프에
얹어 깊이캡(한도)과 함께 직교로 건다.

# KG: legion-stuck-detector-2026-06-27 (deepdive §4.2 'stuck인데 안 멈춤' 실패 대응)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StuckDetector:
    """연속 무진전 라운드 카운터. patience 회 연속 같은 signature → stuck(halt 권고)."""

    patience: int = 3
    _last: str | None = field(default=None, repr=False)
    _repeat: int = field(default=0, repr=False)
    history: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.patience < 1:
            raise ValueError("patience must be >= 1")

    def observe(self, signature: str) -> bool:
        """한 라운드의 진전 signature 관찰. 직후 stuck 이면 True.

        signature = 그 라운드에서 '진전' 을 요약하는 안정 문자열(예: 미해결 요구 set 의 해시,
        새로 제공된 키 정렬 join). 같은 값이 patience 회 연속이면 무진전으로 본다.
        """
        self.history.append(signature)
        if signature == self._last:
            self._repeat += 1
        else:
            self._last = signature
            self._repeat = 1
        return self.is_stuck

    @property
    def is_stuck(self) -> bool:
        return self._repeat >= self.patience

    def reset(self) -> None:
        self._last, self._repeat = None, 0


__all__ = ["StuckDetector"]
