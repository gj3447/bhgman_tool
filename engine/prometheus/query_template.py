"""query-derive — gap → 검색어, 결정론 템플릿 (LLM 아님).

gap의 kind별 고정 템플릿. "창의적 쿼리 생성"이 아니라 KG가 명시한 질문의 결정론적 변환.

# KG: project-legion-unification-kg-engine-2026-06-01
"""

from __future__ import annotations

from engine.prometheus.models import Gap, Query

# kind → 쿼리 템플릿. {q} = gap.question(없으면 gap.id). 새 kind는 기본 "{q}".
_TEMPLATES: dict[str, str] = {
    "OpenQuestion": "{q}",
    "VerdictPending": "{q} evidence resolution",
}


def derive_query(gap: Gap) -> Query:
    # KG: ATOM_Skill_prometheus
    q = gap.question or gap.id
    tmpl = _TEMPLATES.get(gap.kind, "{q}")
    return Query(gap_id=gap.id, text=tmpl.format(q=q).strip())


__all__ = ["derive_query"]
