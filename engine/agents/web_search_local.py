"""로컬 SearXNG self-host 웹검색 — vLLM agent(ReAct)용. API 키 0, 무의존(stdlib).

Anthropic server-side web_search(`web_search_20260209`, 걔네 서버가 검색+종합)와 달리,
검색을 *우리 인프라*(dgx SearXNG)가 실행한다 → 결과를 어떤 로컬 모델(vLLM Qwen 등)에도
주입할 수 있다. client.py 의 openai-compat ReAct 루프(`_complete_openai` web_search=True)가 호출.

  Mac/agent → BHGMAN_SEARXNG_URL(예 http://100.64.0.3:8888) → SearXNG /search?format=json

# KG: bhgman-local-web-search-searxng-2026-06-16
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

DEFAULT_N = 5
DEFAULT_TIMEOUT = 15.0


def searxng_url() -> str | None:
    """BHGMAN_SEARXNG_URL (없으면 None → 호출자가 검색 비활성)."""
    return os.environ.get("BHGMAN_SEARXNG_URL")


def searxng_search(
    query: str,
    n: int = DEFAULT_N,
    *,
    base: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict]:
    """SearXNG JSON API 검색 → [{title, url, snippet}] 상위 n개. stdlib urllib only."""
    base = (base or searxng_url() or "").rstrip("/")
    if not base:
        raise RuntimeError("BHGMAN_SEARXNG_URL 미설정 — 로컬 웹검색 불가")
    qs = urllib.parse.urlencode({"q": query, "format": "json"})
    req = urllib.request.Request(  # noqa: S310 — 신뢰된 내부 SearXNG endpoint
        f"{base}/search?{qs}", headers={"User-Agent": "bhgman-agent/1.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    out: list[dict] = []
    for r in (data.get("results") or [])[:n]:
        out.append(
            {
                "title": (r.get("title") or "").strip(),
                "url": (r.get("url") or "").strip(),
                "snippet": (r.get("content") or "").strip(),
            }
        )
    return out


def format_results(results: list[dict]) -> str:
    """검색 결과를 모델 주입용 텍스트로. snippet 은 과길이 방지 truncation."""
    if not results:
        return "(검색 결과 없음)"
    lines = []
    for i, r in enumerate(results, 1):
        snip = r["snippet"][:300]
        lines.append(f"[{i}] {r['title']}\n    {r['url']}\n    {snip}")
    return "\n".join(lines)


__all__ = ["DEFAULT_N", "format_results", "searxng_search", "searxng_url"]
