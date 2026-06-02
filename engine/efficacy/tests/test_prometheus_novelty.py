"""prometheus novelty oracle 순수 함수 테스트 — verdict 파싱 / control / report 수식.

라이브 LLM 호출(_ollama_judge/main)은 IO이므로 테스트 안 함 — 순수 로직만.
"""

from __future__ import annotations

from engine.efficacy.prometheus_novelty import (
    NoveltyReport,
    control_accuracy,
    parse_verdict,
)


# ── parse_verdict ────────────────────────────────────────────────────────────────
def test_parse_clean_words():
    assert parse_verdict("KNOWN") == "KNOWN"
    assert parse_verdict("NOVEL") == "NOVEL"
    assert parse_verdict("known") == "KNOWN"


def test_parse_with_noise():
    assert parse_verdict("NOVEL. This is specialized.") == "NOVEL"
    assert parse_verdict("Answer: KNOWN") == "KNOWN"  # first word fail → fallback scan
    assert parse_verdict("It is either KNOWN or NOVEL") == "?"  # 둘 다 등장 → 모호


def test_parse_unparseable():
    assert parse_verdict("maybe") == "?"
    assert parse_verdict("") == "?"


# ── control_accuracy ─────────────────────────────────────────────────────────────
def test_control_accuracy_perfect_and_partial():
    perfect = [("KNOWN", "KNOWN"), ("NOVEL", "NOVEL")]
    assert control_accuracy(perfect) == 1.0
    half = [("KNOWN", "KNOWN"), ("NOVEL", "KNOWN")]
    assert control_accuracy(half) == 0.5
    assert control_accuracy([]) == 0.0


# ── NoveltyReport ────────────────────────────────────────────────────────────────
def test_report_rate_and_instrument_gate():
    ok = NoveltyReport(n=15, novel=14, known=1, unparsed=0, control_acc=1.0)
    assert ok.novelty_rate == 14 / 15
    assert ok.instrument_valid is True
    assert "MEASURED" in ok.summary()


def test_report_inconclusive_when_control_fails():
    bad = NoveltyReport(n=10, novel=9, known=1, unparsed=0, control_acc=0.4)
    assert bad.instrument_valid is False  # < 0.8 → 신뢰불가
    assert "INCONCLUSIVE" in bad.summary()


def test_report_rate_ignores_unparsed():
    r = NoveltyReport(n=10, novel=6, known=2, unparsed=2, control_acc=1.0)
    assert r.novelty_rate == 6 / 8  # decided=novel+known, unparsed 제외
