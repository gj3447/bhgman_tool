"""오캄 결정 로그 — supersession 결정의 feature-vector + σ + verdict 영속화.

PROM 6 C6 / rf-occam-adv-A5 (최대 unlock, 최저비용): 결정 시점의 raw 신호 + σ + (나중에)
크리틱 verdict 를 per-decision 로깅해야, hand-weighted σ 를 자가보정(Platt/isotonic + 학습
logistic blend + 비용기반 threshold)으로 승격할 수 있다. 현재 병목 = σ 가 KG에 persist 안 됨.
이 모듈이 그 학습셋의 원본 레코드를 만든다.

`verdict_label` 슬롯은 나중에 나생문/롱기누스 크리틱 결과(PASS/FAIL)로 채워진다 = calibration
label. 즉 (feature_vector, verdict_label) 페어가 σ 보정의 training data.

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A5-2026-07-19,
#     occam-kam-canonical-2026-05-26
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.occam.occam_models import NodeRecord, SupersessionCandidate


def _feat(n: NodeRecord) -> dict:
    """노드 하나의 raw 신호 (σ 가 소비하는 것과 동일한 feature 원본)."""
    return {
        "name": n.name,
        "source_path": n.source_path,
        "sha256": n.sha256,
        "line_count": n.line_count,
        "inbound_edges": n.inbound_edges,
        "last_validated": n.last_validated,
        "invocation_count": n.invocation_count,
    }


def build_decision_record(
    cand: SupersessionCandidate, *, decided_at: str, run_id: str | None = None
) -> dict:
    """`SupersessionCandidate` → 직렬화 가능한 결정 레코드 (feature-vector + σ + verdict slot).

    `decided_at` = ISO 타임스탬프(호출자 주입 — 순수성 유지, 여기서 시계 읽지 않음).
    `verdict_label` = None (크리틱이 나중에 채움; calibration label).
    """
    stale, current = cand.stale, cand.current
    return {
        "run_id": run_id,
        "decided_at": decided_at,
        "normalized_path": cand.normalized_path,
        "reason": cand.reason,
        "confidence": getattr(cand.confidence, "value", str(cand.confidence)),
        "sigma": cand.score,  # σ ∈ [0,1] — calibration 입력 신호
        "verdict": cand.verdict,  # occam 자체 판정 (SUPERSEDE/VERIFY/KEEP/...)
        "verdict_label": None,  # 크리틱 정답 (나중에 채움) = calibration label
        "features": {
            # σ 가 쓰는 파생 신호를 명시적으로 노출 → 학습 blend 가 직접 소비
            "line_count_delta": current.line_count - stale.line_count,
            "inbound_delta": (current.inbound_edges or 0) - (stale.inbound_edges or 0),
            "same_sha": stale.sha256 == current.sha256,
            "stale": _feat(stale),
            "current": _feat(current),
        },
    }


def append_decision_records(records: list[dict], path: str | Path) -> int:
    """결정 레코드들을 jsonl로 append (durable, KG 오염 없음). 반환 = 쓴 줄 수.

    KG에 넣지 않고 파일로 두는 이유: (1) 학습셋은 append-only 스트림이 자연스럽고,
    (2) KG 노드로 넣으면 occam 자신의 dedup 대상이 되는 자기참조 오염 위험.
    """
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(records)


__all__ = ["build_decision_record", "append_decision_records"]
