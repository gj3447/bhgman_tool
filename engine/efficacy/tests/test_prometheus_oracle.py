"""prometheus groundedness oracle 순수 함수 테스트 — citation 분류 + 집계."""

from __future__ import annotations

from engine.efficacy.prometheus_oracle import aggregate, classify_citation


# ── classify_citation ───────────────────────────────────────────────────────────
def test_external_http_urls():
    assert classify_citation("https://arxiv.org/pdf/2212.12541") == "external"
    assert classify_citation("http://research.google.com/x.pdf") == "external"
    assert classify_citation("https://doi.org/10.1103/x") == "external"


def test_self_internal():
    assert classify_citation("file:///Users/x/finding.json") == "self"
    assert classify_citation("kg://node/abc") == "self"
    assert classify_citation("http://localhost:7474/browser") == "self"
    assert classify_citation("https://127.0.0.1/x") == "self"


def test_text_citation_not_url():
    assert classify_citation("Adepu 2024 Medium 'Modeling Data in Bigtable'") == "text"
    assert classify_citation("Stonebraker+Pavlo 2024 CACM") == "text"


def test_empty():
    assert classify_citation(None) == "empty"
    assert classify_citation("") == "empty"
    assert classify_citation("   ") == "empty"


# ── aggregate ────────────────────────────────────────────────────────────────────
def test_aggregate_rates_and_self_citation():
    urls = [
        "https://arxiv.org/abs/1",  # external
        "https://en.wikipedia.org/wiki/x",  # external
        "file:///self.json",  # self
        "Smith 2024 text cite",  # text
        None,  # empty (filtered from sourced; but typically URL_CYPHER excludes these)
    ]
    res = aggregate(total=100, urls=urls)
    assert res.external == 2
    assert res.self_cited == 1
    assert res.text_only == 1
    assert res.sourced == 4  # empty 제외
    assert res.sourcing_rate == 4 / 100
    assert res.verifiability == 2 / 4
    assert res.self_citation_rate == 1 / 4


def test_aggregate_empty_safe():
    res = aggregate(total=0, urls=[])
    assert res.sourcing_rate == 0.0
    assert res.verifiability == 0.0
    assert res.self_citation_rate == 0.0
