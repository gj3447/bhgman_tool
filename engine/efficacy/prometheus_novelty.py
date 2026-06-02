"""prometheus(획득) novelty oracle — base-LLM recall-delta (the missing counterfactual).

prometheus_oracle.py는 *groundedness*(인용이 외부 실URL인가)만 쟀다. 진짜 *novelty*(가져온
사실이 base-LLM이 회상 못 하는 것인가 = 획득이 더한 게 있나)는 base-LLM에게 직접 물어야 한다.

protocol: 각 ResearchFinding claim을 base-LLM(도구 없이, dgx-local qwen2.5)에게 주고
"훈련 지식만으로 KNOWN(이미 앎)/NOVEL(특수·최신·확인불가)" 판정. novelty_rate = NOVEL/N.
base-LLM 판정은 prometheus 무관 → 비순환.

**계측기 타당성 강제**: 잘 알려진 사실(KNOWN 나와야)+가짜 사실(NOVEL 나와야) CONTROL을
먼저 돌려 변별 정확도를 잰다. control_accuracy < 0.8 이면 계측기 신뢰불가 → INCONCLUSIVE
(수치 날조 금지, feedback_verify_async_results_before_writeup).

정직 라벨: NOVEL = "base 훈련 회상 밖"인데 이는 *진짜 획득한 특수사실* + *검증불가 주장*
둘 다 포함 = novelty의 *상한*(recall-delta)이지 precision 아님. self-project 노트는 사전 제외
(base가 당연히 모름 = trivial novel). noisy estimate, n=N 명시.

# KG: efficacy-prometheus-2026-06-01, efficacy-measurement-line-2026-06-01,
#     project_bhgman_self_critique_2026_05_28, reference_dgx_vllm_gb10_setup
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from dataclasses import dataclass

_BASE_URL = os.environ.get("BHGMAN_LLM_BASE_URL", "http://localhost:11434")
_MODEL = os.environ.get("BHGMAN_LLM_MODEL", "qwen2.5:32b-instruct")

# (label, topic, claim) — 계측기 변별 검증용. KNOWN 3 / NOVEL 2.
_CONTROLS: tuple[tuple[str, str, str], ...] = (
    ("KNOWN", "networking", "The TCP three-way handshake uses SYN, SYN-ACK, then ACK."),
    ("KNOWN", "physics", "Water boils at 100 degrees Celsius at standard atmospheric pressure."),
    ("KNOWN", "CS", "Quicksort has average-case time complexity O(n log n)."),
    ("NOVEL", "physics", "The Zorblax constant equals 3.7714 in quantized flux manifolds."),
    (
        "NOVEL",
        "internal",
        "Internal benchmark shows module X dispatch latency dropped 43% after refactor Y.",
    ),
)

_PROMPT = (
    "You assess whether a research claim is standard knowledge already in your training, "
    "or specialized/novel. Use your training knowledge ALONE — no external tools. "
    "Topic: {topic}. Claim: {claim}\n"
    "Answer with ONE word: KNOWN (widely-documented, you already have it) or "
    "NOVEL (specialized, recent, or you cannot confirm from training)."
)


def parse_verdict(text: str) -> str:
    """LLM 응답 → 'KNOWN'/'NOVEL'/'?' (대소문자·잡음 robust)."""
    up = text.strip().upper()
    first = up.split()[0] if up.split() else ""
    if "KNOWN" in first or up.startswith("KNOWN"):
        return "KNOWN"
    if "NOVEL" in first or up.startswith("NOVEL"):
        return "NOVEL"
    if "KNOWN" in up and "NOVEL" not in up:
        return "KNOWN"
    if "NOVEL" in up and "KNOWN" not in up:
        return "NOVEL"
    return "?"


def control_accuracy(verdicts: list[tuple[str, str]]) -> float:
    """[(expected, got)] → 정확도. 계측기 변별력 (순수)."""
    if not verdicts:
        return 0.0
    hits = sum(1 for exp, got in verdicts if exp == got)
    return hits / len(verdicts)


@dataclass(frozen=True)
class NoveltyReport:
    n: int
    novel: int
    known: int
    unparsed: int
    control_acc: float

    @property
    def novelty_rate(self) -> float:
        decided = self.novel + self.known
        return self.novel / decided if decided else 0.0

    @property
    def instrument_valid(self) -> bool:
        return self.control_acc >= 0.8

    def summary(self) -> str:
        verdict = "MEASURED" if self.instrument_valid else "INCONCLUSIVE"
        return (
            f"prometheus novelty oracle [{verdict}]: control_acc={self.control_acc:.2f} "
            f"({'instrument OK' if self.instrument_valid else 'instrument FAIL → 신뢰불가'}) · "
            f"novelty_rate={self.novelty_rate:.3f} (NOVEL {self.novel}/{self.novel + self.known}, "
            f"unparsed {self.unparsed}, n={self.n})"
        )


def _ollama_judge(topic: str, claim: str) -> str:  # pragma: no cover — IO/network
    body = json.dumps(
        {
            "model": _MODEL,
            "prompt": _PROMPT.format(topic=topic, claim=claim),
            "stream": False,
            "options": {"temperature": 0},
        }
    ).encode()
    req = urllib.request.Request(
        f"{_BASE_URL}/api/generate", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 — local trusted base_url
        return parse_verdict(json.load(r)["response"])


_FETCH = (
    "MATCH (f:ResearchFinding) WHERE f.citation_url =~ '(?i)^https?://.*' "
    "AND f.oneLineSummary IS NOT NULL AND size(f.oneLineSummary) > 50 "
    "AND NOT (f.domain CONTAINS 'bhgman' OR f.oneLineSummary CONTAINS 'PROM 16' "
    "OR f.oneLineSummary CONTAINS 'bhgman') "
    "RETURN f.oneLineSummary AS claim, "
    "coalesce(f.domain,'')+' '+coalesce(f.axisLabel,f.axis,'') AS topic "
    "ORDER BY f.researchedAt DESC LIMIT $n"
)


def main() -> int:  # pragma: no cover — IO 진입점
    from engine.cli.runtime import make_kg_runners  # noqa: PLC0415

    n = int(os.environ.get("PROM_NOVELTY_N", "15"))
    runners = make_kg_runners()
    if runners is None:
        print("neo4j 미연결 — bolt 직결 필요", file=sys.stderr)
        return 2
    run_cypher, _w, close = runners
    try:
        rows = run_cypher(_FETCH, {"n": n})
    finally:
        close()

    try:
        ctrl = [(exp, _ollama_judge(topic, claim)) for exp, topic, claim in _CONTROLS]
        cacc = control_accuracy(ctrl)
        verdicts = [_ollama_judge(r["topic"], r["claim"]) for r in rows]
    except OSError as e:
        print(
            f"ollama 미연결 ({_BASE_URL}) — ssh -L 11434:localhost:11434 dgx 필요: {e}",
            file=sys.stderr,
        )
        return 2

    rep = NoveltyReport(
        n=len(verdicts),
        novel=sum(1 for v in verdicts if v == "NOVEL"),
        known=sum(1 for v in verdicts if v == "KNOWN"),
        unparsed=sum(1 for v in verdicts if v == "?"),
        control_acc=cacc,
    )
    print(rep.summary())
    print(
        "  읽기: NOVEL = base 훈련 회상 밖(recall-delta 상한) — *진짜 획득 특수사실* + *검증불가 주장* "
        "둘 다 포함이라 precision 아님. self-project 노트는 사전 제외. noisy, n 작음."
    )
    return 0 if rep.instrument_valid else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
