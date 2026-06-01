"""프로메테우스 결정론 엔진 — 경계축 ingest (외부 지식 → KG).

획득(프로메테우스)의 본질은 LLM이 아니라 *외부→KG ingest*다 (bhgman A/B falsifier:
LLM 인지기여 0 → 본질은 경계 넘기 = 결정론 I/O). 이 엔진이 그 본질을 결정론으로 실현한다:

  gap-detect → query-derive → fetch(주입식 boundary I/O) → parse → :ResearchFinding ingest

5단계 전부 결정론 (fetcher 주입 시 fetch까지 결정론). LLM은 `engine.agents.prometheus`에
별도로 남는 *선택적 enrichment* — 이 엔진은 키 없이 동작하는 floor.

covenant: ingest는 PROPOSE/dry-run 기본 (eureka/하데스/오캄과 동일) — planned MERGE cypher
반환, `apply=True` + write_cypher 있을 때만 write.

# KG: bihaenggiman-legioncommanders-2026-05-26 (프로메테우스=획득),
#     project-legion-unification-kg-engine-2026-06-01 (경계축 reframe)
"""

from __future__ import annotations

from engine.prometheus.models import (
    AcquireReport,
    FetchedDoc,
    Finding,
    Gap,
    Query,
)
from engine.prometheus.fetcher import CallableFetcher, Fetcher, StaticFetcher
from engine.prometheus.pipeline import run_acquire
from engine.prometheus.web import WebSearchFetcher

__all__ = [
    "AcquireReport",
    "CallableFetcher",
    "FetchedDoc",
    "Fetcher",
    "Finding",
    "Gap",
    "Query",
    "StaticFetcher",
    "WebSearchFetcher",
    "run_acquire",
]
