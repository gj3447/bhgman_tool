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


def test_empty_findings_is_zero_not_one():
    # the Goodhart fix: no findings => no external grounding witnessed => 0.0 (NOT a vacuous 1.0).
    assert compute_external_grounding_ratio([]) == 0.0


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
