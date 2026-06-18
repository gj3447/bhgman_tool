"""gap-detect — KG의 빈 곳(OpenQuestion / VerdictPending) 결정론 scan.

이 단계가 "무엇을 찾을지"를 LLM 없이 결정한다: KG가 이미 뭐가 빠졌는지 안다.

# KG: project-legion-unification-kg-engine-2026-06-01
"""

from __future__ import annotations

from collections.abc import Callable

from engine.prometheus.models import Gap

CypherRunner = Callable[[str, dict], list[dict]]

# 답이 안 채워진 열린 질문/미결 verdict = 지식 gap.
_GAP_CYPHER = (
    "MATCH (q) WHERE q:OpenQuestion OR q:VerdictPending "
    "RETURN coalesce(q.name, q.id, toString(id(q))) AS id, "
    "coalesce(q.question, q.description, q.name, '') AS question, "
    "head(labels(q)) AS kind "
    "LIMIT $limit"
)


def scan_gaps(run_cypher: CypherRunner, *, limit: int = 50) -> list[Gap]:
    # KG: ATOM_Skill_prometheus
    """gap 노드 → Gap 리스트. 백엔드가 임의 MATCH 미지원(local 등)이면 [] (graceful)."""
    try:
        rows = run_cypher(_GAP_CYPHER, {"limit": limit})
    except Exception:  # noqa: BLE001 — backend가 쿼리 미지원 → gap 없음으로 degrade (covenant)
        return []
    gaps: list[Gap] = []
    for r in rows:
        gid = str(r.get("id") or "").strip()
        if not gid:
            continue
        gaps.append(
            Gap(
                id=gid,
                question=str(r.get("question") or "").strip(),
                kind=str(r.get("kind") or "OpenQuestion"),
            )
        )
    return gaps


__all__ = ["scan_gaps"]
