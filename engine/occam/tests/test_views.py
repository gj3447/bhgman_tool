"""오캄 공유 current-view 테스트 — PROM 6 C1 (라벨-게이트 단일 진실원).

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A3-2026-07-19
"""

from __future__ import annotations

from engine.occam.kg_adapter import _NOT_ALREADY_ARCHIVED
from engine.occam.views import ARCHIVED_LABEL, current_match, current_only


def test_current_only_gates_on_label_not_status():
    frag = current_only("n")
    assert frag == "NOT n:ARCHIVED"
    assert "status" not in frag.lower()  # 라벨만 — status 문자열 게이트 금지


def test_current_only_var_parametric():
    assert current_only("s") == "NOT s:ARCHIVED"
    assert current_only() == "NOT n:ARCHIVED"


def test_current_match_builds_full_clause():
    assert current_match("SourceCodeNode", "s") == "MATCH (s:SourceCodeNode) WHERE NOT s:ARCHIVED"


def test_archived_label_constant():
    assert ARCHIVED_LABEL == "ARCHIVED"


def test_kg_adapter_fetch_uses_shared_view():
    # 단일 진실원: kg_adapter 의 라벨 게이트가 views.current_only 로부터 나와야 한다.
    assert current_only("s") in _NOT_ALREADY_ARCHIVED
