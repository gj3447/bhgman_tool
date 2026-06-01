"""KG row → occam 탐지신호(candidacy) 다리. 순수.

중요 구분: occam σ = candidacy · guard.
  · candidacy = "이 노드가 obsolete한가" (선별/탐지 신호) ← 효능(stale 탐지) 측정엔 이것.
  · guard = "자동 supersede해도 안전한가" (twin-gate; 후속자 없으면 0).
디스크-orphan은 정의상 twin이 없을 수 있어 guard=0 → σ=0 (flag-only, 의도된 동작).
따라서 *탐지 효능*은 candidacy로 측정해야 옳다 (guard로 σ을 0 만들면 탐지력 측정이 아님).

age(created_at)는 bhgman SourceCodeNode에 희소 → staleness=0 (보수적). 신호는 주로
deadness(invocation 백필) + redundancy(sha-twin).

# KG: efficacy-occam-sigma-ab-2026-06-01, efficacy-measurement-line-2026-06-01
"""

from __future__ import annotations

from engine.occam.scoring import ScoringConfig, candidacy, deadness


def sigma_from_row(row: dict, config: ScoringConfig | None = None) -> float:
    """KG row → candidacy ∈ [0,1] (occam 탐지신호).

    row: {invocation_count, twins}. redundancy=sha-twin 유무, deadness=invocation."""
    cfg = config or ScoringConfig()
    redundancy = 1.0 if (row.get("twins") or 0) > 0 else 0.0
    inv = int(row.get("invocation_count") or 0)
    d = deadness(inv, cfg.invocation_scale)
    staleness_v = 0.0  # created_at 희소 → 미사용 (보수적)
    return candidacy(redundancy, staleness_v, d)


__all__ = ["sigma_from_row"]
