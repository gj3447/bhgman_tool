"""프로메테우스 결정론 파이프라인 — gap→query→fetch→parse→ingest 오케스트레이션.

fetcher 주입 시 5단계 전부 결정론. fetcher 없으면 gap+query까지만(무엇을 찾을지 surface).

# KG: project-legion-unification-kg-engine-2026-06-01
"""

from __future__ import annotations

from collections.abc import Callable

from engine.prometheus.extract import extract_findings
from engine.prometheus.fetcher import Fetcher
from engine.prometheus.gap_source import scan_gaps
from engine.prometheus.ingest import ingest_findings
from engine.prometheus.models import AcquireReport, Finding
from engine.prometheus.query_template import derive_query

CypherRunner = Callable[[str, dict], list[dict]]


def run_acquire(
    run_cypher: CypherRunner,
    *,
    fetcher: Fetcher | None = None,
    write_cypher: CypherRunner | None = None,
    cycle_id: str = "legion-run",
    apply: bool = False,
    gap_limit: int = 50,
    researched_at: str = "",
) -> AcquireReport:
    # KG: ATOM_Skill_prometheus
    """경계축 획득 1회. PROPOSE 기본 (apply+write_cypher 일 때만 ingest write)."""
    gaps = tuple(scan_gaps(run_cypher, limit=gap_limit))
    queries = tuple(derive_query(g) for g in gaps)

    findings: list[Finding] = []
    # 정직 실행 게이트 (정정 3, 2026-07-10): '실행됨' = fetcher 주입 ∧ gap 존재.
    # gaps==() 면 아래 루프는 0회 — fetcher 가 있어도 fetch 는 일어나지 않았다.
    fetch_executed = fetcher is not None and bool(gaps)
    if fetcher is not None:
        for gap, query in zip(gaps, queries):
            docs = fetcher.fetch(query)
            findings.extend(extract_findings(gap, docs, cycle_id, researched_at=researched_at))
    found = tuple(findings)

    written, planned = ingest_findings(found, write_cypher=write_cypher, apply=apply)
    return AcquireReport(
        cycle_id=cycle_id,
        gaps=gaps,
        queries=queries,
        findings=found,
        dry_run=not (apply and write_cypher is not None),
        ingested=written,
        planned_cyphers=planned,
        fetch_executed=fetch_executed,
    )


__all__ = ["run_acquire"]
