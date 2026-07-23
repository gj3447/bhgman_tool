"""오캄 verdict 수확 — KG ValidationResult → decision_log 라벨 자동 회수 (PROM 6 C6 폐합).

σ 보정 루프의 마지막 배선: 크리틱(나생문/워크플로 적대검증자)이 supersession 판정을
`:ValidationResult` 로 KG에 남기면, 이 모듈이 그것을 수확해 decision_log 의 열린
`verdict_label` 슬롯에 채운다. 이후 `calibration.calibrate` 가 (σ, label) 페어로 Platt fit.

수확 소스 2종 (UNION):
  1. 엣지형 — ``(v:ValidationResult)-[]->(s:SourceCodeNode)``: subject = s.name.
  2. 프로퍼티형 — ``v.subject`` 문자열 (nameless stale 은 name 이 없어 엣지형으로 못 잡음 →
     크리틱이 match_key(``normalized_path:sha12``)를 subject 프로퍼티로 직접 기록).

read-only 수확 + 파일 원자 백필 (verdict_feedback.apply_verdicts). None-only fill 이라
재수확은 멱등 — 이미 라벨된 레코드는 절대 덮어쓰지 않는다.

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A5-2026-07-19,
#     occam-kam-canonical-2026-05-26
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from engine.occam.verdict_feedback import FeedbackReport, apply_verdicts, vr_to_verdicts

CypherRunner = Callable[[str, "dict"], "list[dict]"]

# 엣지형(subject=노드 name) UNION 프로퍼티형(subject=v.subject 문자열).
# ORDER BY 결정론: 같은 subject 에 VR 다수면 나중 이름(사전순 최후)이 이김 —
# vr_to_verdicts 의 later-row-wins 계약에 맡긴다.
HARVEST_CYPHER = (
    "MATCH (v:ValidationResult)-[]->(s:SourceCodeNode) "
    "WHERE v.verdict IS NOT NULL AND s.name IS NOT NULL "
    "RETURN s.name AS subject, v.verdict AS verdict, v.name AS vr "
    "UNION "
    "MATCH (v:ValidationResult) "
    "WHERE v.verdict IS NOT NULL AND v.subject IS NOT NULL "
    "RETURN v.subject AS subject, v.verdict AS verdict, v.name AS vr "
    "ORDER BY vr, subject"
)


def harvest_rows(run_cypher: CypherRunner) -> list[dict]:
    """KG에서 (subject, verdict) 행 수확 (read-only)."""
    return run_cypher(HARVEST_CYPHER, {})


def harvest_and_apply(run_cypher: CypherRunner, log_path: str | Path) -> FeedbackReport:
    """KG verdict 수확 → decision_log 라벨 백필. 멱등(None-only fill).

    unmatched_keys 는 '이 로그와 무관한 VR 주제' — 오류 아님(KG 전체 VR 을 수확하므로
    다른 대상의 판정이 다수 섞인다). updated 만 이 로그에 실제로 착지한 라벨 수.
    """
    verdicts = vr_to_verdicts(harvest_rows(run_cypher))
    return apply_verdicts(log_path, verdicts)


__all__ = ["HARVEST_CYPHER", "harvest_and_apply", "harvest_rows"]
