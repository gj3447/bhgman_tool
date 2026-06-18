"""parse — 외부 문서 → :ResearchFinding 후보, 결정론 추출.

정직 공시: *얕은* 추출 (HTML strip → 문장 분할 → substantive 문장 N개). LLM 요약 아님 —
stdlib만으로 결정론. 깊은 claim 추출은 fetcher가 구조화 소스를 주거나 LLM enrichment 몫.

# KG: project-legion-unification-kg-engine-2026-06-01
"""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser

from engine.prometheus.models import FetchedDoc, Finding, Gap


class _TextExtractor(HTMLParser):
    """script/style 제외하고 텍스트 노드만 모음."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:  # noqa: ARG002
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self._parts.append(data.strip())

    @property
    def text(self) -> str:
        return " ".join(self._parts)


def html_to_text(s: str) -> str:
    # KG: ATOM_Skill_prometheus
    """HTML/plain → 텍스트. 태그 없으면 원문 그대로."""
    parser = _TextExtractor()
    try:
        parser.feed(s)
    except Exception:  # noqa: BLE001 — malformed HTML → 원문 fallback
        return s
    return parser.text or s


_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def extract_findings(
    gap: Gap,
    docs: list[FetchedDoc],
    cycle_id: str,
    *,
    max_per_doc: int = 2,
    min_len: int = 40,
    researched_at: str = "",
) -> list[Finding]:
    # KG: ATOM_Skill_prometheus
    """문서별 substantive 문장 max_per_doc개 → Finding (citation_url + content sha256)."""
    out: list[Finding] = []
    for doc in docs:
        text = html_to_text(doc.text)
        sha = hashlib.sha256(doc.text.encode("utf-8")).hexdigest()
        claims = [s.strip() for s in _SENTENCE.split(text) if len(s.strip()) >= min_len]
        for claim in claims[:max_per_doc]:
            out.append(Finding.make(gap.id, claim, doc.url, sha, cycle_id, researched_at))
    return out


__all__ = ["extract_findings", "html_to_text"]
