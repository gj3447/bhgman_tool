"""external_grounding_ratio 런타임 배선 (RED artifact, test-first).

compute_external_grounding_ratio + update_grounding 은 이미 존재하지만(test_external_grounding_
ratio.py) **legion 경로에서 죽어 있었다**: _run_acquire 의 acquired dict 에 citation_urls 가
없고 _measure_prometheus 가 grounding 을 계산하지 않아 ratio 가 생성자 기본 1.0 에 고정 —
Goodhart 컨트롤(<0.3 → self-recurse)이 런타임에서 원리적으로 발화 불가(항상 1.0 < 0.3 = False).

이 파일이 배선을 고정한다:
  1. 결정론 acquire 브랜치는 실 findings 의 citation_url 목록을 acquired["citation_urls"] 로
     노출한다 (빈 KG = 빈 목록, 키는 실재).
  2. _measure_prometheus 는 그 목록에서 ratio 를 실계산한다 (키 부재 시 정직 기본 유지 —
     LLM 브랜치는 citations 를 노출하지 않음을 공시).
  3. (NOVEL) 전부 비접지 citations → <0.3 self-recurse dispatch 가 *실제로 발화* —
     runtime-dead 시절엔 불가능했던 사건.

# Direct regression: prometheus_grounding_wire
# KG: prometheus-grounding-2026-05-05
"""

from __future__ import annotations

from engine.kg_local.runner import make_local_runner
from engine.kg_local.store import LocalKgStore
from engine.legion.commanders import _measure_prometheus, _run_acquire


def test_deterministic_acquire_exposes_citation_urls(tmp_path):
    """배선 1: acquired dict 가 citation_urls 를 노출 (빈 KG → 빈 목록, 키 실재)."""
    rc = make_local_runner(LocalKgStore(tmp_path / "e.json"), autosave=False)
    out = _run_acquire({"run_cypher": rc, "cycle_id": "gw-expose"})
    acquired = out["acquired"]
    assert acquired["mode"] == "kg-deterministic"
    assert "citation_urls" in acquired, "결정론 브랜치는 실 findings 의 citation_url 을 노출해야"
    assert acquired["citation_urls"] == []


def test_measure_computes_ratio_from_real_citations():
    """배선 2: _measure_prometheus 가 citation_urls 에서 ratio 실계산 (혼합 → 0.5)."""
    m = _measure_prometheus(
        {"acquired": {"findings": 2, "citation_urls": ["http://phys.test/koide", ""]}}
    )
    assert m.measure()["external_grounding_ratio"] == 0.5


def test_measure_without_citations_is_unmeasured():
    """LLM 브랜치 공시 v2 (seam-integrity 20260708): citation_urls 미노출 = 미측정(키 부재) —
    v1 의 '기본 1.0 유지'는 측정 없이 완전-접지를 위장하는 영구 불-발화 상수였다."""
    m = _measure_prometheus({"acquired": {"findings": 3, "mode": "llm"}})
    assert "external_grounding_ratio" not in m.measure()


def test_self_recurse_fires_on_all_ungrounded():
    """NOVEL 축: 전부 비접지 → ratio 0.0 < 0.3 → prometheus→prometheus self-recurse dispatch
    실제 발화 — runtime-dead(고정 1.0) 시절엔 구조적으로 불가능했던 사건."""
    m = _measure_prometheus({"acquired": {"findings": 2, "citation_urls": ["", "not a url"]}})
    decisions = m.decide_dispatch(cycle_id="gw-fire")
    fired = [d for d in decisions if d.metric_name == "external_grounding_ratio"]
    assert fired, f"<0.3 self-recurse 가 발화해야 한다; got {decisions}"
    assert fired[0].target_commander == "prometheus"


def test_grounded_citations_do_not_fire_self_recurse():
    """판별 반대쪽: 전부 실 http 접지 → ratio 1.0 → self-recurse 미발화 (항상-발화 장식 아님)."""
    m = _measure_prometheus(
        {"acquired": {"findings": 2, "citation_urls": ["http://a.test/x", "https://b.test/y"]}}
    )
    fired = [
        d
        for d in m.decide_dispatch(cycle_id="gw-nofire")
        if d.metric_name == "external_grounding_ratio"
    ]
    assert not fired
