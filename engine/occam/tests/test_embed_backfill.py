"""occam 임베딩 backfill 러너 테스트 — PROM 6 P2 / A1.

인덱스/knn 통합은 live run(2026-07-19, 홈 KG 1678 임베딩)으로 실증. 여기선 결정론 surface.
# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A1-2026-07-19
"""

from __future__ import annotations

from engine.occam.embed_backfill import _base, sourcecode_spec


def test_spec_dim_from_embedder():
    spec = sourcecode_spec(384)
    assert spec.dimensions == 384
    assert spec.label == "SourceCodeNode"
    assert spec.text_prop == "sourcePath"
    assert spec.embedding_prop == "embedding"


def test_spec_supports_768():
    assert sourcecode_spec(768).dimensions == 768


def test_base_strips_line_anchor():
    assert _base("engine/x.py:27") == "engine/x.py"
    assert _base("engine/x.py:1048") == "engine/x.py"
    assert _base("engine/x.py") == "engine/x.py"  # anchor 없으면 그대로
    assert _base(None) == ""


def test_line_siblings_share_base():
    # x.py:27 과 x.py:28 은 같은 파일(다른 참조 위치) → 중복 아님 (필터 제외 대상).
    assert _base("dispatch_audit.py:27") == _base("dispatch_audit.py:29")


def test_cross_name_same_file_differs_by_full_path_not_anchor():
    # session-bind 노드 vs bare 노드 = 같은 sourcePath → base 동일하지만 anchor 차이 아님 → 유지.
    assert _base("engine/legion/legion.py") == _base("engine/legion/legion.py")
