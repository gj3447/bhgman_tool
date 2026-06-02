"""prometheus(획득) faithfulness oracle — novelty 0.933의 *precision*을 깎는다.

novelty(prometheus_novelty.py)는 "base 회상 밖"(recall-delta 상한)이라 검증불가 주장이
섞여있다. precision = "가져온 claim이 *인용한 그 소스에 실제로 있나*"(RAG faithfulness/
attribution 표준). 인용한 외부 페이지(arxiv/wiki/html)가 prometheus의 oracle — prometheus가
안 만든 외부 텍스트가 ground truth → 비순환. 시간 축적 0(지금 가능).

**2중 컨트롤**(2026-06-02 정정): (1) positive control — *심은* (claim, page) 쌍(claim이
page의 실제 문장 → FAITHFUL 나와야 / 명백 무관 → UNSUPPORTED 나와야)으로 judge가 faithful을
*탐지할 능력*이 있나 검증. (2) shuffled — claim_i ↔ 다른 page로 거짓양성("아무거나 FAITHFUL")
통제. 1차 버전은 (2)만 있어 matched가 진짜 낮을 때 INCONCLUSIVE에 갇혔다(거짓음성 미통제,
root cause=positive control 부재). control_acc≥0.8이어야 matched_rate 신뢰.

정직 라벨: matched_rate = **extractive** faithfulness(claim이 인용 page에 글자그대로 뒷받침).
낮다 = prometheus가 *합성/해석형 획득*(citation=pointer지 quote 아님)이지 *거짓*이 아님 —
합성의 *가치·정확성*은 이 oracle이 답 못 함(별개·더 어려운 질문). LLM noisy+page 앞 5k자+PDF 제외.

순수(parse_faithful/FaithReport) + IO(fetch/judge) 분리.

# KG: efficacy-prometheus-2026-06-01, efficacy-measurement-line-2026-06-01,
#     project_bhgman_self_critique_2026_05_28
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from html import unescape

_BASE_URL = os.environ.get("BHGMAN_LLM_BASE_URL", "http://localhost:11434")
_MODEL = os.environ.get("BHGMAN_LLM_MODEL", "qwen2.5:32b-instruct")
_UA = "bhgman-efficacy-faithfulness/1.0 (research citation check)"

_PROMPT = (
    "You check whether a web passage SUPPORTS a research claim that cites it. "
    "Judge only from the passage; do not use outside knowledge.\n"
    "PASSAGE:\n{page}\n\nCLAIM: {claim}\n\n"
    "Answer ONE word: FAITHFUL (the passage supports / contains the claim) or "
    "UNSUPPORTED (the passage does not support it)."
)

# positive control — judge가 faithful을 *탐지할 능력*이 있나(거짓음성 통제). (page, claim, expected).
_CONTROL_PAGE = (
    "The Leiden algorithm improves on Louvain by guaranteeing well-connected communities. "
    "It was introduced by Traag, Waltman, and van Eck in 2019. "
    "Quicksort has average-case O(n log n) time complexity."
)
_CONTROLS: tuple[tuple[str, str, str], ...] = (
    (
        _CONTROL_PAGE,
        "Leiden guarantees well-connected communities, improving on Louvain.",
        "FAITHFUL",
    ),
    (_CONTROL_PAGE, "Quicksort has average-case O(n log n) complexity.", "FAITHFUL"),
    (_CONTROL_PAGE, "Leiden was introduced by Traag, Waltman, and van Eck in 2019.", "FAITHFUL"),
    (_CONTROL_PAGE, "The Zorblax constant equals 3.77 in flux manifolds.", "UNSUPPORTED"),
    (_CONTROL_PAGE, "TCP uses a three-way handshake with SYN/SYN-ACK/ACK.", "UNSUPPORTED"),
)

_TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_ANYTAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def parse_faithful(text: str) -> str:
    """LLM 응답 → 'FAITHFUL'/'UNSUPPORTED'/'?' (robust)."""
    up = text.strip().upper()
    first = up.split()[0] if up.split() else ""
    if first.startswith("FAITH") or (up.startswith("FAITHFUL")):
        return "FAITHFUL"
    if first.startswith("UNSUP") or up.startswith("UNSUPPORTED"):
        return "UNSUPPORTED"
    has_f, has_u = "FAITHFUL" in up, "UNSUPPORTED" in up
    if has_f and not has_u:
        return "FAITHFUL"
    if has_u and not has_f:
        return "UNSUPPORTED"
    return "?"


def strip_html(raw: str, limit: int = 5000) -> str:
    """HTML → 본문 텍스트 앞 limit자 (script/style 제거, 태그 제거, 공백 정규화)."""
    no_scripts = _TAG.sub(" ", raw)
    text = unescape(_ANYTAG.sub(" ", no_scripts))
    return _WS.sub(" ", text).strip()[:limit]


def control_accuracy(verdicts: list[tuple[str, str]]) -> float:
    """[(expected, got)] → positive control 정확도. judge의 faithful 탐지능력 (순수)."""
    if not verdicts:
        return 0.0
    return sum(1 for exp, got in verdicts if exp == got) / len(verdicts)


@dataclass(frozen=True)
class FaithReport:
    n_accessible: int
    matched_faithful: int
    shuffled_faithful: int
    control_acc: float = 1.0  # positive control 정확도 (judge 탐지능력)

    @property
    def matched_rate(self) -> float:
        return self.matched_faithful / self.n_accessible if self.n_accessible else 0.0

    @property
    def shuffled_rate(self) -> float:
        return self.shuffled_faithful / self.n_accessible if self.n_accessible else 0.0

    @property
    def delta(self) -> float:
        return self.matched_rate - self.shuffled_rate

    @property
    def instrument_valid(self) -> bool:
        """positive control이 faithful 탐지능력 입증 + 거짓양성(shuffled) 통제."""
        return self.control_acc >= 0.8 and self.shuffled_rate <= self.matched_rate

    def summary(self) -> str:
        verdict = "MEASURED" if self.instrument_valid else "INCONCLUSIVE"
        return (
            f"prometheus faithfulness oracle [{verdict}]: extractive_faithfulness="
            f"{self.matched_rate:.3f} (control_acc={self.control_acc:.2f}, "
            f"shuffled={self.shuffled_rate:.3f}) · n_accessible={self.n_accessible}"
        )


def _norm_url(url: str) -> str:
    """arxiv /pdf/ID → /abs/ID (HTML abstract 페이지)."""
    m = re.search(r"arxiv\.org/pdf/([\w.]+?)(?:v\d+)?(?:\.pdf)?$", url)
    return f"https://arxiv.org/abs/{m.group(1)}" if m else url


def _fetch_page(url: str) -> str | None:  # pragma: no cover — network IO
    """citation 페이지 본문 텍스트. PDF/실패는 None."""
    try:
        req = urllib.request.Request(_norm_url(url), headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 — public citation GET
            raw = r.read(400_000)
        if raw[:5] == b"%PDF-":
            return None
        return strip_html(raw.decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001 — 어떤 fetch 실패도 inaccessible 처리
        return None


def _judge(page: str, claim: str) -> str:  # pragma: no cover — network IO
    body = json.dumps(
        {
            "model": _MODEL,
            "prompt": _PROMPT.format(page=page, claim=claim),
            "stream": False,
            "options": {"temperature": 0},
        }
    ).encode()
    req = urllib.request.Request(
        f"{_BASE_URL}/api/generate", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310 — local trusted base_url
        return parse_faithful(json.load(r)["response"])


_FETCH = (
    "MATCH (f:ResearchFinding) WHERE f.citation_url =~ '(?i)^https?://.*' "
    "AND NOT f.citation_url CONTAINS '.pdf' "
    "AND f.oneLineSummary IS NOT NULL AND size(f.oneLineSummary) > 50 "
    "AND NOT (f.domain CONTAINS 'bhgman' OR f.oneLineSummary CONTAINS 'PROM 16' "
    "OR f.oneLineSummary CONTAINS 'bhgman') "
    "RETURN f.oneLineSummary AS claim, f.citation_url AS url "
    "ORDER BY f.researchedAt DESC LIMIT $n"
)


def _measure(pairs: list[tuple[str, str]]) -> FaithReport:  # pragma: no cover — IO orchestration
    """positive control + [(claim, page)] matched vs shuffled judge."""
    n = len(pairs)
    ctrl = [(exp, _judge(page, claim)) for page, claim, exp in _CONTROLS]
    cacc = control_accuracy(ctrl)
    matched = sum(1 for claim, page in pairs if _judge(page, claim) == "FAITHFUL")
    # shuffled: claim_i ↔ page_{(i+1)%n} (거짓양성 통제).
    shuffled = sum(1 for i in range(n) if _judge(pairs[(i + 1) % n][1], pairs[i][0]) == "FAITHFUL")
    return FaithReport(
        n_accessible=n, matched_faithful=matched, shuffled_faithful=shuffled, control_acc=cacc
    )


def main() -> int:  # pragma: no cover — IO 진입점
    from engine.cli.runtime import make_kg_runners  # noqa: PLC0415

    n = int(os.environ.get("PROM_FAITH_N", "24"))
    runners = make_kg_runners()
    if runners is None:
        print("neo4j 미연결 — bolt 직결 필요", file=sys.stderr)
        return 2
    run_cypher, _w, close = runners
    try:
        rows = run_cypher(_FETCH, {"n": n})
    finally:
        close()

    pairs: list[tuple[str, str]] = []
    for r in rows:
        page = _fetch_page(r["url"])
        if page and len(page) > 200:
            pairs.append((r["claim"], page))
    if len(pairs) < 4:
        print(f"accessible page {len(pairs)}개 — 표본 부족, INCONCLUSIVE", file=sys.stderr)
        return 1
    try:
        rep = _measure(pairs)
    except OSError as e:
        print(f"ollama 미연결 — ssh -L 11434 dgx 필요: {e}", file=sys.stderr)
        return 2

    print(rep.summary())
    print(
        "  읽기: control_acc≥0.8 = judge가 faithful 탐지능력 입증(거짓음성 통제). 그때 "
        "extractive_faithfulness 낮음 = prometheus가 *합성/해석형 획득*(citation=pointer지 quote 아님)."
    )
    print(
        "  주의: '낮은 faithfulness ≠ 거짓' — 합성의 가치·정확성은 별개 질문. LLM noisy+page 앞 5k자+PDF 제외+n 작음."
    )
    return 0 if rep.instrument_valid else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
