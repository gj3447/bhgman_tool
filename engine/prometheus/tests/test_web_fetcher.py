"""WebSearchFetcher — boundary I/O 주입식 검증 (무네트워크).

url_open 주입 시 결정론. 검색 페이지 파싱 → 결과 링크 → 문서 fetch. 실패 graceful.

# KG: project-legion-unification-kg-engine-2026-06-01
"""

from __future__ import annotations

from engine.prometheus import WebSearchFetcher, run_acquire
from engine.prometheus.models import Query
from engine.prometheus.web import _extract_result_links, _unwrap_ddg

_SEARCH_HTML = """
<html><body>
  <a class="result__a" href="/l/?uddg=https%3A%2F%2Fphys.org%2Fkoide">Koide on phys.org</a>
  <a class="result__a" href="https://example.com/direct">Direct link</a>
  <a class="nav" href="/ignore">nav</a>
</body></html>
"""


def _fake_open(corpus):
    def opener(url: str) -> str:
        if "duckduckgo" in url:
            return _SEARCH_HTML
        return corpus.get(
            url, f"<p>{url} content long enough to be a substantive claim sentence.</p>"
        )

    return opener


def test_unwrap_ddg_redirect():
    assert _unwrap_ddg("/l/?uddg=https%3A%2F%2Fphys.org%2Fkoide") == "https://phys.org/koide"
    assert _unwrap_ddg("https://example.com/x") == "https://example.com/x"


def test_extract_result_links_dedup_and_limit():
    links = _extract_result_links(_SEARCH_HTML, limit=3)
    assert links == ["https://phys.org/koide", "https://example.com/direct"]


def test_web_fetcher_fetches_top_results_via_injected_open():
    fetcher = WebSearchFetcher(url_open=_fake_open({}), max_results=2)
    docs = fetcher.fetch(Query("q1", "Koide relation"))
    assert [d.url for d in docs] == ["https://phys.org/koide", "https://example.com/direct"]
    assert all(d.text for d in docs)


def test_web_fetcher_graceful_on_search_failure():
    def boom(_url: str) -> str:
        raise RuntimeError("network down")

    assert WebSearchFetcher(url_open=boom).fetch(Query("q1", "x")) == []


def test_web_fetcher_drives_full_acquire_pipeline():
    def gap_rc(_c, _p):
        return [{"id": "q-koide", "question": "Koide relation", "kind": "OpenQuestion"}]

    fetcher = WebSearchFetcher(url_open=_fake_open({}), max_results=2)
    report = run_acquire(gap_rc, fetcher=fetcher, cycle_id="cyc-web")
    assert len(report.findings) >= 1
    assert report.findings[0].citation_url.startswith("https://")
