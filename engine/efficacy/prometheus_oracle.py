"""부채 — prometheus(획득) 독립 oracle: ResearchFinding citation verifiability.

prometheus 동사 = "획득"(외부 지식 ingest). 효능 주장 = "base-LLM 회상보다 새롭고
정확한 외부 사실을 가져온다." 이를 막던 건 self-citation loop 비판
([[project_bhgman_self_critique_2026_05_28]]) — 도구가 자기 KG를 인용하면 "획득"이 아님.

이 oracle은 *결정론·비순환*으로 **citation verifiability**를 잰다: finding의 citation_url이
(a) 실제 외부 URL 구조인가 (b) self/internal(file://·kg://·localhost) 아닌가 (c) 텍스트-only
인가. URL 구조 판정은 prometheus가 만든 게 아니다(urlparse=표준) → 순환성 0. citation_url
필드는 prometheus가 쓰지만, 그 *내용이 외부 실재 URL인지*는 독립 구조 속성.

두 층으로 보고(둘 다 정직):
  1. sourcing_rate     = 인용 가진 finding / 전체 (획득이 출처를 남기는 비율)
  2. verifiability     = 외부-유효 URL / 인용가진 (남긴 출처가 진짜 외부인 비율)
  + self_citation_rate = self/internal 인용 / 인용가진 (loop 비판의 직접 정량)

정직 라벨: 이건 **groundedness/verifiability**(precision 하한)이지 *novelty*가 아니다.
진짜 cognitive 효능(base-LLM이 모르는 걸 가져왔나)은 base-LLM recall delta가 필요 —
결정론 baseline 없음(외부 지식 정확성=본질적 외부 검증). novelty 층은 OPEN(아래 설계).
liveness(HTTP 200) 미체크 — dead-link은 외부 요청 회피 위해 안 잼; verifiability는 *상한*.

순수(classify_citation/aggregate) + IO(KG fetch) 분리.

# KG: efficacy-prometheus-2026-06-01, efficacy-measurement-line-2026-06-01,
#     prometheus-grounding-2026-05-05, project_bhgman_self_critique_2026_05_28
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from urllib.parse import urlparse

_SELF_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0")
_SELF_SCHEMES = ("file", "kg")


def classify_citation(url: str | None) -> str:
    """citation_url → {'external','self','text','empty'} (결정론·prometheus 무관)."""
    if not url or not url.strip():
        return "empty"
    u = url.strip()
    parsed = urlparse(u)
    scheme = parsed.scheme.lower()
    if scheme in _SELF_SCHEMES:
        return "self"
    if scheme in ("http", "https"):
        host = (parsed.netloc or "").lower()
        if not host:
            return "text"
        if any(h in host for h in _SELF_HOSTS):
            return "self"
        return "external"
    return "text"  # scheme 없음 = 자유 텍스트 인용(검증불가 URL 아님)


@dataclass(frozen=True)
class PrometheusGroundedness:
    """획득 효능 oracle 결과 — 두 층 + self-citation 정량."""

    total: int
    sourced: int
    external: int
    self_cited: int
    text_only: int

    @property
    def sourcing_rate(self) -> float:
        return self.sourced / self.total if self.total else 0.0

    @property
    def verifiability(self) -> float:
        return self.external / self.sourced if self.sourced else 0.0

    @property
    def self_citation_rate(self) -> float:
        return self.self_cited / self.sourced if self.sourced else 0.0

    def summary(self) -> str:
        return (
            f"prometheus groundedness oracle: sourcing_rate={self.sourcing_rate:.4f} "
            f"({self.sourced}/{self.total}) · verifiability={self.verifiability:.3f} "
            f"({self.external}/{self.sourced} 외부URL) · self_citation={self.self_citation_rate:.4f} "
            f"({self.self_cited}/{self.sourced}) · text_only={self.text_only}"
        )


def aggregate(total: int, urls: list[str | None]) -> PrometheusGroundedness:
    """전체 finding 수 + 인용 URL 리스트 → groundedness (순수)."""
    kinds = [classify_citation(u) for u in urls]
    external = sum(1 for k in kinds if k == "external")
    self_cited = sum(1 for k in kinds if k == "self")
    text_only = sum(1 for k in kinds if k == "text")
    sourced = external + self_cited + text_only  # 'empty'는 비-sourced
    return PrometheusGroundedness(
        total=total,
        sourced=sourced,
        external=external,
        self_cited=self_cited,
        text_only=text_only,
    )


_TOTAL_CYPHER = "MATCH (f:ResearchFinding) RETURN count(f) AS total"
_URL_CYPHER = (
    "MATCH (f:ResearchFinding) WHERE f.citation_url IS NOT NULL AND f.citation_url <> '' "
    "RETURN f.citation_url AS url"
)


def main() -> int:  # pragma: no cover — IO 진입점
    from engine.cli.runtime import make_kg_runners  # noqa: PLC0415

    runners = make_kg_runners()
    if runners is None:
        print("neo4j 미연결 (NEO4J_PASSWORD?) — bolt 직결 필요", file=sys.stderr)
        return 2
    run_cypher, _w, close = runners
    try:
        total = int(run_cypher(_TOTAL_CYPHER, {})[0]["total"])
        urls = [r["url"] for r in run_cypher(_URL_CYPHER, {})]
    finally:
        close()

    res = aggregate(total, urls)
    print(res.summary())
    print(
        "  읽기: 획득의 *진짜* 한계는 self-citation이 아니라(self "
        f"{res.self_cited}/{res.sourced}) **무출처**({res.total - res.sourced}/{res.total}, "
        f"{1 - res.sourcing_rate:.1%}). 남긴 출처는 {res.verifiability:.0%}가 외부 실URL."
    )
    print(
        "  주의: verifiability(groundedness 상한, precision 하한) — novelty 아님. "
        "진짜 cognitive 효능=base-LLM recall delta(dgx local) 필요 = OPEN. liveness 미체크."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
