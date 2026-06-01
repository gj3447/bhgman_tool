"""프로메테우스 결정론 엔진 value objects.

# KG: project-legion-unification-kg-engine-2026-06-01
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Gap:
    """KG의 빈 곳 — 답이 안 채워진 OpenQuestion / VerdictPending 노드."""

    id: str
    question: str = ""
    kind: str = "OpenQuestion"
    candidate_urls: tuple[str, ...] = ()


@dataclass(frozen=True)
class Query:
    """gap → 결정론 템플릿으로 도출한 검색어 (LLM 아님)."""

    gap_id: str
    text: str


@dataclass(frozen=True)
class FetchedDoc:
    """fetcher(boundary I/O)가 돌려준 외부 문서."""

    url: str
    text: str


@dataclass(frozen=True)
class Finding:
    """외부에서 ingest한 :ResearchFinding 후보 (정전 필드명 정렬)."""

    finding_id: str
    gap_id: str
    claim: str
    citation_url: str
    content_sha256: str
    cycle_id: str
    researched_at: str = ""

    @staticmethod
    def make(
        gap_id: str,
        claim: str,
        citation_url: str,
        content_sha256: str,
        cycle_id: str,
        researched_at: str = "",
    ) -> "Finding":
        """findingId = sha256(gap|url|claim) → idempotent MERGE 키 (재실행 안전)."""
        raw = f"{gap_id}|{citation_url}|{claim}".encode()
        fid = "rf-" + hashlib.sha256(raw).hexdigest()[:16]
        return Finding(fid, gap_id, claim, citation_url, content_sha256, cycle_id, researched_at)


@dataclass(frozen=True)
class AcquireReport:
    """획득 1회 결과. dry_run=True면 planned cypher만 (PROPOSE)."""

    cycle_id: str
    gaps: tuple[Gap, ...]
    queries: tuple[Query, ...]
    findings: tuple[Finding, ...]
    dry_run: bool
    ingested: int
    planned_cyphers: tuple[str, ...] = ()

    @property
    def summary(self) -> str:
        mode = "dry-run (PROPOSE)" if self.dry_run else f"ingested {self.ingested}"
        return (
            f"prometheus[ingest]: gaps={len(self.gaps)} queries={len(self.queries)} "
            f"findings={len(self.findings)} — {mode}"
        )
