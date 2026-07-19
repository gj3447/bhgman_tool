"""오캄 공유 뷰 — "이 노드는 current(무덤 아님)인가?" 의 단일 진실원.

PROM 6 C1 / rf-occam-adv-A3: canonical 아카이브 마커 = `:ARCHIVED` **라벨**. 소비자는
`NOT x:ARCHIVED` 를 **손으로 쓰지 말고** 이 fragment 를 import 한다. soft-delete
안티패턴의 #1 실패모드 = 필터 누락(각 쿼리가 WHERE 를 잊음) — 단일 정의로 봉쇄.
status 문자열로 게이트하지 말 것(서브타입·대소문자 파편화, 이번 세션 버그의 원인).

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A3-2026-07-19,
#     lesson-occam-refetch-archived-status-exact-match-2026-07-19
"""

from __future__ import annotations

# canonical 아카이브(무덤) 라벨. 이 라벨이 유일 게이트 — status 는 주석일 뿐.
ARCHIVED_LABEL = "ARCHIVED"


def current_only(var: str = "n") -> str:
    """live(비아카이브) 노드만 선택하는 WHERE-절 fragment.

    사용: ``f"MATCH (n:SourceCodeNode) WHERE {current_only('n')} RETURN n"``.
    소비자는 이 함수만 쓰고 ``NOT n:ARCHIVED`` 를 직접 쓰지 않는다(단일 진실원).
    """
    return f"NOT {var}:{ARCHIVED_LABEL}"


def current_match(label: str, var: str = "n") -> str:
    """live 노드 MATCH 전체: ``MATCH (var:label) WHERE NOT var:ARCHIVED``."""
    return f"MATCH ({var}:{label}) WHERE {current_only(var)}"


__all__ = ["ARCHIVED_LABEL", "current_only", "current_match"]
