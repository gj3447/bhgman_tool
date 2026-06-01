"""fetch — boundary I/O 주입식 seam (외부 경계 넘기).

경계 넘기는 결정론 I/O(주어진 쿼리→문서)지 LLM이 아니다. 실제 web search/HTTP는
*주입*(CallableFetcher로 parent WebSearch 등 plug). 엔진은 fetcher만 알고, 그 안의
I/O는 caller 책임 — longinus가 KgClient 주입받는 것과 동일 철학(DIP).

# KG: project-legion-unification-kg-engine-2026-06-01
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from engine.prometheus.models import FetchedDoc, Query


@runtime_checkable
class Fetcher(Protocol):
    """쿼리 → 외부 문서들. 구현이 boundary I/O를 담당."""

    def fetch(self, query: Query) -> list[FetchedDoc]: ...


class StaticFetcher:
    """오프라인/결정론 fetcher — corpus {query_text: [FetchedDoc]} backed. 테스트/무네트워크."""

    def __init__(self, corpus: dict[str, list[FetchedDoc]]) -> None:
        self._corpus = corpus

    def fetch(self, query: Query) -> list[FetchedDoc]:
        return list(self._corpus.get(query.text, []))


class CallableFetcher:
    """임의 `query→list[FetchedDoc]` 콜러블 wrap — production web search/HTTP plug-in 지점."""

    def __init__(self, fn: Callable[[Query], list[FetchedDoc]]) -> None:
        self._fn = fn

    def fetch(self, query: Query) -> list[FetchedDoc]:
        return list(self._fn(query))


__all__ = ["CallableFetcher", "Fetcher", "StaticFetcher"]
