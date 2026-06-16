"""production web fetcher — query → 검색 → 결과 URL fetch (boundary I/O).

경계 넘기는 결정론 I/O다 (주어진 url_open이면 출력 고정). HTTP 레이어는 *주입식*
(`url_open: str -> str`) — 기본은 stdlib urllib(키 불필요), 테스트는 fake 주입(무네트워크).
검색은 DuckDuckGo HTML endpoint(키 불필요) → 결과 링크 결정론 파싱 → top-K fetch.

정직 공시: HTML 스크레이프는 ToS-gray·구조 변화에 취약. 안정적 production은 검색 API를
url_open/search_url로 갈아끼우거나 CallableFetcher로 parent WebSearch를 plug.

# KG: project-legion-unification-kg-engine-2026-06-01
"""

from __future__ import annotations

from collections.abc import Callable
from html.parser import HTMLParser
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

from engine.prometheus.models import FetchedDoc, Query

_DDG_HTML = "https://html.duckduckgo.com/html/?q={q}"
_UA = "bhgman-tool/0.1 (+https://github.com/gj3447/bhgman_tool)"
_ALLOWED_SCHEMES = ("http", "https")


def _is_http_url(url: str) -> bool:
    """Only http(s) — blocks the file:// / ftp:// / gopher:// SSRF + local-file-read
    vectors a DDG `uddg=` redirect could inject once the fetcher is live."""
    try:
        return urlparse(url).scheme.lower() in _ALLOWED_SCHEMES
    except ValueError:
        return False


def _default_url_open(url: str, *, timeout: float = 10.0) -> str:
    """stdlib urllib GET → text. 네트워크 호출(opt-in: WebSearchFetcher 사용 시에만)."""
    if not _is_http_url(url):
        raise ValueError(f"refusing non-http(s) URL (SSRF/file-read guard): {url!r}")
    import urllib.request  # noqa: PLC0415

    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


class _ResultLinkParser(HTMLParser):
    """DuckDuckGo HTML 결과 페이지에서 result 링크(href) 추출 (결정론)."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag != "a":
            return
        a = dict(attrs)
        if "result__a" in (a.get("class") or "") and a.get("href"):
            self.links.append(_unwrap_ddg(str(a["href"])))


def _unwrap_ddg(href: str) -> str:
    """DDG redirect(/l/?uddg=ENCODED) → 실제 URL. 평범한 href면 그대로."""
    parsed = urlparse(href)
    if parsed.path.endswith("/l/"):
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return unquote(target[0])
    return href


def _extract_result_links(html: str, limit: int) -> list[str]:
    parser = _ResultLinkParser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 — malformed → 모은 만큼만
        pass
    seen: list[str] = []
    for link in parser.links:
        if link not in seen:
            seen.append(link)
        if len(seen) >= limit:
            break
    return seen


class WebSearchFetcher:
    """query → DDG 검색 → top-K 결과 fetch → FetchedDoc. HTTP는 url_open 주입(테스트 가능)."""

    def __init__(
        self,
        *,
        url_open: Callable[[str], str] = _default_url_open,
        max_results: int = 3,
    ) -> None:
        self._open = url_open
        self._max = max_results

    def fetch(self, query: Query) -> list[FetchedDoc]:
        try:
            page = self._open(_DDG_HTML.format(q=quote_plus(query.text)))
        except Exception:  # noqa: BLE001 — 검색 실패 → 빈 결과 (graceful, 거짓 결과 금지)
            return []
        docs: list[FetchedDoc] = []
        for url in _extract_result_links(page, self._max):
            if not _is_http_url(url):
                continue  # SSRF/file-read guard — never hand a non-http(s) URL to url_open
            try:
                docs.append(FetchedDoc(url, self._open(url)))
            except Exception:  # noqa: BLE001 — 개별 문서 실패는 skip
                continue
        return docs


class SearXNGFetcher:
    """SearXNG self-host(키 0) 검색 → top-K URL fetch → FetchedDoc.

    DDG HTML 스크래핑(WebSearchFetcher)보다 안정적 — 검색을 우리 인프라(dgx SearXNG)가 실행.
    동일 인터페이스(fetch(query)->list[FetchedDoc])라 legion --web 에 drop-in 교체.
    """

    def __init__(
        self,
        base: str,
        *,
        url_open: Callable[[str], str] = _default_url_open,
        max_results: int = 3,
    ) -> None:
        self._base = base.rstrip("/")
        self._open = url_open
        self._max = max_results

    def fetch(self, query: Query) -> list[FetchedDoc]:
        from engine.agents.web_search_local import searxng_search  # noqa: PLC0415

        try:
            results = searxng_search(query.text, n=self._max, base=self._base)
        except Exception:  # noqa: BLE001 — 검색 실패 → 빈 결과 (거짓 결과 금지)
            return []
        docs: list[FetchedDoc] = []
        for r in results:
            url = r.get("url", "")
            if not _is_http_url(url):
                continue
            try:
                docs.append(FetchedDoc(url, self._open(url)))
            except Exception:  # noqa: BLE001 — 개별 문서 실패는 skip
                continue
        return docs


def make_web_fetcher() -> WebSearchFetcher | SearXNGFetcher:
    """BHGMAN_SEARXNG_URL 있으면 SearXNGFetcher(self-host, 안정), 없으면 DDG WebSearchFetcher."""
    import os  # noqa: PLC0415

    base = os.environ.get("BHGMAN_SEARXNG_URL")
    return SearXNGFetcher(base) if base else WebSearchFetcher()


__all__ = ["SearXNGFetcher", "WebSearchFetcher", "make_web_fetcher"]
