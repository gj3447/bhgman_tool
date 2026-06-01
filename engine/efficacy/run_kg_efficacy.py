"""실 KG 효능 측정 진입점 — occam을 독립 oracle(디스크 실존)로 end-to-end 측정.

부채 #1(invocation_count) + #2(순환성 깬 oracle=disk_present) 백필 후 실행.
occam σ 엔진의 실제 출력(SupersessionScore.sigma)이 *디스크에서 사라진 노드(stale)*를
*살아있는 노드*보다 높게 매기는지 = 3-falsifier 게이트 통과한 진짜 효능 측정.

oracle 독립성: disk_present 는 파일시스템이 결정 (occam status 라벨과 무관) → 순환성 ~0.

# KG: efficacy-measurement-line-2026-06-01, efficacy-occam-sigma-ab-2026-06-01
"""

from __future__ import annotations

import sys

from engine.efficacy.harness import run_efficacy
from engine.efficacy.models import CommanderEfficacySpec, Direction, LabeledItem
from engine.efficacy.scoring_bridge import sigma_from_row

# 디스크 oracle 기반 occam spec — 라벨 provenance가 occam이 아니라 파일시스템.
OCCAM_DISK_SPEC = CommanderEfficacySpec(
    commander="occam",
    verb="정리",
    task="σ 엔진이 디스크-stale 노드를 live보다 높게 점수 (독립 oracle)",
    metric="AUC(σ; disk-absent vs disk-present)",
    oracle_source="disk_present (파일시스템 — occam 라벨과 무관, 순환성 없음)",
    required_signal="σ = redundancy·staleness·deadness·guard (invocation 백필 후)",
    expected_direction=Direction.HIGHER,  # stale → σ 높아야
    circularity_keywords=("occam", "dup", "supersed", "moved"),
    label_cypher=None,  # run_kg_efficacy 가 직접 fetch (twin self-join 포함)
    known_falsifier="disk oracle로 순환성 제거. signal=invocation 백필로 확보.",
)

# disk_present + invocation_count 있는 bhgman_tool 노드 + sha-twin 수 + age(created_at).
_FETCH = """
MATCH (s:SourceCodeNode)
WHERE s.disk_present IS NOT NULL AND s.invocation_count IS NOT NULL
  AND s.sourcePath CONTAINS 'bhgman_tool/'
OPTIONAL MATCH (t:SourceCodeNode) WHERE t.sha256 = s.sha256 AND t <> s
WITH s, count(t) AS twins
RETURN s.name AS name, s.disk_present AS disk_present,
       s.invocation_count AS invocation_count, twins AS twins,
       s.created_at AS created_at,
       coalesce(s.supersededReason, s.occam_archive_reason, '') AS provenance
"""


def rows_to_items(rows: list[dict]) -> list[LabeledItem]:
    """KG row → LabeledItem. signal=σ(score_node), positive=디스크에서 사라짐(stale)."""
    items: list[LabeledItem] = []
    for r in rows:
        sigma = sigma_from_row(r)
        items.append(
            LabeledItem(
                item_id=str(r["name"]),
                is_positive=not bool(r["disk_present"]),
                signal=sigma,
                provenance=str(r.get("provenance") or ""),
            )
        )
    return items


def main() -> int:  # pragma: no cover — IO 진입점
    from engine.cli.runtime import make_kg_runners  # noqa: PLC0415

    runners = make_kg_runners()
    if runners is None:
        print("neo4j 미연결 (NEO4J_PASSWORD?)", file=sys.stderr)
        return 2
    run_cypher, _write, close = runners
    try:
        rows = run_cypher(_FETCH, {})
        items = rows_to_items(rows)
        result = run_efficacy(OCCAM_DISK_SPEC, items)
        print(result.summary)
        if result.preflight:
            p = result.preflight
            print(
                f"  preflight: circularity={p.circularity_ratio:.3f} "
                f"availability={p.signal_availability:.3f} raw_auc={p.raw_auc}"
            )
        return 0
    finally:
        close()


__all__ = ["OCCAM_DISK_SPEC", "rows_to_items"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
