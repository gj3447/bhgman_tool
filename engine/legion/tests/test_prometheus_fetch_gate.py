"""prometheus fetched 실행 게이트 — 주입≠실행 (광역 측정 재배선 2026-07-10, slice 1 이중가드).

적대검증 정정 3(설계 2026-07-09): run_acquire 는 ``gaps==()`` 면 fetcher 가 주입돼
있어도 fetch 루프를 돌지 않는다(pipeline.py) — 그러므로 "fetch 가 실행됐다"의 정직
게이트는 fetcher 주입 여부가 아니라 ``bool(gaps) and fetcher`` 다.

guard_defect(결함 재현, 음성 오라클): fetch 가 실행되지 않은 획득(=fetcher 부재,
또는 gap 0건)에서 research_finding_count 가 '측정된 0건'으로 위장 노출되던 결함 —
경계 I/O 가 없었으면 미측정(키 부재)이어야 한다.

guard_mechanism(메커니즘 실재, 양성 오라클): fetch 가 실제 실행되면(gap>0 ∧ fetcher)
finding_count 는 len(findings) 실측(0건도 측정된 영)으로 등장하고, >16 발화 규칙이
살아 있다.

# KG: bhgman-measurement-rewire-design-20260709 (정정 3: fetched=주입≠실행)
# KG: ATOM_Skill_prometheus
"""

from __future__ import annotations

from engine.legion.commanders import _measure_prometheus, _run_acquire
from engine.prometheus.models import FetchedDoc
from engine.prometheus.pipeline import run_acquire


class _StubFetcher:
    """경계 I/O 스텁 — 쿼리당 doc 1개 (substantive 문장 1개 → finding 1개)."""

    def __init__(self, n_docs: int = 1) -> None:
        self.calls = 0
        self._n = n_docs

    def fetch(self, query) -> list[FetchedDoc]:
        self.calls += 1
        return [
            FetchedDoc(
                url=f"http://ext.test/{self.calls}/{i}",
                text=(
                    "This is a sufficiently long substantive sentence about the gap topic "
                    "that passes the extractor minimum length filter."
                ),
            )
            for i in range(self._n)
        ]


def _gap_rc(n_gaps: int):
    """scan_gaps 모양의 gap row 를 돌려주는 run_cypher 스텁."""

    def rc(cypher: str, params: dict) -> list[dict]:
        if "OpenQuestion" in cypher:
            return [
                {"id": f"q{i}", "question": f"open question {i}?", "kind": "OpenQuestion"}
                for i in range(n_gaps)
            ]
        return []

    return rc


# ── guard_defect: fetch 미실행 → finding_count 미측정 ─────────────────────────


def test_no_fetcher_means_unmeasured_finding_count():
    """fetcher 부재(infra 기아, MCP/기본 루프와 동형): gap 이 있어도 fetch 는 안 돌았다 —
    research_finding_count 는 '측정된 0'이 아니라 미측정(키 부재)이어야 한다."""
    out = _run_acquire({"run_cypher": _gap_rc(3), "cycle_id": "fg-nofetcher"})
    acquired = out["acquired"]
    assert acquired["fetched"] is False, "fetcher 부재 = fetch 미실행 공시"
    m = _measure_prometheus({"acquired": acquired})
    assert "research_finding_count" not in m.measure(), (
        "경계 I/O 가 없었는데 '측정된 0건'을 위장하면 안 된다"
    )


def test_fetcher_injected_but_no_gaps_is_not_executed():
    """정정 3의 머리: gaps==() 면 fetcher 가 주입돼 있어도 fetch 루프는 안 돈다 —
    '주입됨'을 '실행됨'으로 보고하면 거짓이다."""
    fetcher = _StubFetcher()
    report = run_acquire(_gap_rc(0), fetcher=fetcher, cycle_id="fg-nogap")
    assert fetcher.calls == 0, "전제: gap 0건이면 fetch 호출 자체가 없다"
    assert report.fetch_executed is False
    out = _run_acquire({"run_cypher": _gap_rc(0), "fetcher": fetcher, "cycle_id": "fg-nogap2"})
    assert out["acquired"]["fetched"] is False
    m = _measure_prometheus({"acquired": out["acquired"]})
    assert "research_finding_count" not in m.measure()


def test_llm_branch_exposes_no_fabricated_zero():
    """LLM 브랜치(citations/findings 미노출)도 미측정 — 옛 int(get('findings', 0)) 은
    fetch 개념이 없는 브랜치에서 '측정된 0건'을 날조했다."""
    m = _measure_prometheus({"acquired": {"mode": "llm", "summary": "s", "grounded_facts": 2}})
    assert m.measure() == {}


# ── guard_mechanism: 실행된 fetch 는 실측으로 등장 + 발화 보존 ────────────────


def test_executed_fetch_measures_finding_count():
    """gap>0 ∧ fetcher → fetch 실행 → finding_count = len(findings) 실측."""
    fetcher = _StubFetcher()
    out = _run_acquire({"run_cypher": _gap_rc(2), "fetcher": fetcher, "cycle_id": "fg-exec"})
    acquired = out["acquired"]
    assert acquired["fetched"] is True
    assert fetcher.calls == 2
    assert acquired["findings"] == 2  # doc 1개 × substantive 문장 1개 × gap 2개
    m = _measure_prometheus({"acquired": acquired})
    assert m.measure()["research_finding_count"] == 2.0


def test_executed_fetch_with_zero_findings_is_measured_zero():
    """실행됐는데 0건 = '측정된 영'(키 실재, 값 0.0) — 미측정과 구분된다.
    (3-상태의 셋째 상태가 실제로 존재함을 핀: None ≠ 0.0)"""

    class _EmptyFetcher:
        def fetch(self, query):
            return []

    out = _run_acquire(
        {"run_cypher": _gap_rc(2), "fetcher": _EmptyFetcher(), "cycle_id": "fg-zero"}
    )
    acquired = out["acquired"]
    assert acquired["fetched"] is True
    m = _measure_prometheus({"acquired": acquired})
    assert m.measure()["research_finding_count"] == 0.0


def test_many_findings_still_fire_naesengmoon():
    """>16 findings → naesengmoon 발화 규칙이 fetched 게이트 이후에도 산다 (monotone)."""
    m = _measure_prometheus({"acquired": {"fetched": True, "findings": 20}})
    assert any(
        d.target_commander == "naesengmoon"
        for d in m.decide_dispatch(cycle_id="fg-fire")
        if d.metric_name == "research_finding_count"
    )
