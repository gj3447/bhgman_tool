from engine.eureka.quality_gate import (
    FCA_STABILITY_MIN,
    GOODHART_CAP,
    MODULARITY_MIN,
    SILHOUETTE_MIN,
    evaluate,
)


def test_silhouette_below_threshold_fails():
    r = evaluate(silhouette=0.40)
    assert not r.passed
    assert any("silhouette" in reason for reason in r.reasons)


def test_modularity_below_threshold_fails():
    r = evaluate(modularity=0.20)
    assert not r.passed
    assert any("modularity" in reason for reason in r.reasons)


def test_both_above_threshold_passes():
    r = evaluate(silhouette=0.60, modularity=0.40)
    assert r.passed
    assert r.reasons == ()


def test_goodhart_cap_rejects_too_high():
    r = evaluate(silhouette=0.98)
    assert not r.passed
    assert any("Goodhart" in reason for reason in r.reasons)


def test_all_none_fails():
    r = evaluate()
    assert not r.passed


def test_fca_stability_path():
    assert evaluate(fca_stability=FCA_STABILITY_MIN + 0.01).passed
    assert not evaluate(fca_stability=FCA_STABILITY_MIN - 0.01).passed


def test_fca_stability_perfect_cohesion_passes():
    """W1-E: a fully-cohesive formal concept legitimately scores 1.0 — it is EXEMPT from
    the Goodhart cap (which still rejects silhouette/modularity/AMI ≈ 1.0 as gamed)."""
    assert evaluate(fca_stability=1.0).passed  # was rejected: 1.0 > 0.95 cap
    assert not evaluate(silhouette=0.99).passed  # other metrics still capped
    assert not evaluate(modularity=0.99).passed
    assert not evaluate(ami=0.99).passed


def test_threshold_constants():
    assert SILHOUETTE_MIN == 0.50
    assert MODULARITY_MIN == 0.30
    assert GOODHART_CAP == 0.95
