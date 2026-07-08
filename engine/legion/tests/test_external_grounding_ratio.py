"""external_grounding_ratio — compute the REAL grounding fraction so the <0.3 self-recurse
(Goodhart mitigation) can actually fire. The Red artifact (test-first):

Today PrometheusMeasurement.external_grounding_ratio is hardcoded 1.0 and never computed from
real findings, so 1.0 < 0.3 is always False and the Goodhart-mitigation control is DEAD. These
tests pin the computed ratio and the dispatch firing — RED until compute_external_grounding_ratio
+ PrometheusMeasurement.update_grounding exist.

# KG: prometheus-grounding-2026-05-05
"""

from __future__ import annotations

from engine.legion.measurement import (
    PrometheusMeasurement,
    compute_external_grounding_ratio,
)


def test_ratio_is_fraction_with_real_external_citation():
    # mixed: one real http url + one empty url => 0.5 (the value-pinned RED).
    assert compute_external_grounding_ratio(["http://phys.test/koide", ""]) == 0.5


def test_all_grounded_is_one():
    assert compute_external_grounding_ratio(["http://a.test/x", "https://b.test/y"]) == 1.0


def test_none_grounded_is_zero():
    # empty / non-http scheme / host-less => NOT external grounding.
    assert compute_external_grounding_ratio(["", "ftp://x", "not a url", "http://"]) == 0.0


def test_empty_findings_is_unmeasured_not_a_constant():
    # v2 (seam-integrity 2026-07-08): no findings => UNMEASURED (None) — 상수 0.0 은 vacuous 1.0
    # 의 거울상이었다: infra-0/MCP 경로(fetcher 부재 → findings 구조적 0)에서 self-recurse 가
    # 매 run 무조건 발화 = 정보량 0 의 죽은 컨트롤. 미측정은 measure() 키 부재로 흐른다.
    assert compute_external_grounding_ratio([]) is None


def test_unmeasured_default_exposes_no_ratio_key():
    # 생성자 기본(측정 이전) = 미측정 — measure() 가 어떤 상수도 위장 노출하지 않는다.
    m = PrometheusMeasurement()
    assert "external_grounding_ratio" not in m.measure()
    assert "external_grounding_ratio" not in [d.metric_name for d in m.decide_dispatch()]


def test_low_grounding_fires_self_recurse():
    # all-ungrounded findings => ratio 0.0 => <0.3 => the self-recurse decision FIRES (was dead).
    m = PrometheusMeasurement()
    m.update_grounding(["", ""])
    assert m.measure()["external_grounding_ratio"] == 0.0
    assert "external_grounding_ratio" in [d.metric_name for d in m.decide_dispatch()]


def test_high_grounding_does_not_fire_self_recurse():
    m = PrometheusMeasurement()
    m.update_grounding(["http://a.test/x", "https://b.test/y"])
    assert m.measure()["external_grounding_ratio"] == 1.0
    assert "external_grounding_ratio" not in [d.metric_name for d in m.decide_dispatch()]
