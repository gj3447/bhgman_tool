"""prometheus faithfulness oracle 순수 함수 테스트 — 파싱 / html strip / report 수식.

라이브 fetch·judge(_fetch_page/_judge/_measure/main)는 IO이므로 테스트 안 함.
"""

from __future__ import annotations

from engine.efficacy.prometheus_faithfulness import (
    FaithReport,
    _norm_url,
    control_accuracy,
    parse_faithful,
    strip_html,
)


# ── parse_faithful ───────────────────────────────────────────────────────────────
def test_parse_clean():
    assert parse_faithful("FAITHFUL") == "FAITHFUL"
    assert parse_faithful("UNSUPPORTED") == "UNSUPPORTED"
    assert parse_faithful("faithful") == "FAITHFUL"


def test_parse_noise_and_ambiguous():
    assert parse_faithful("FAITHFUL — the passage states it") == "FAITHFUL"
    assert parse_faithful("Answer: UNSUPPORTED") == "UNSUPPORTED"
    assert parse_faithful("could be FAITHFUL or UNSUPPORTED") == "?"
    assert parse_faithful("dunno") == "?"


# ── strip_html ───────────────────────────────────────────────────────────────────
def test_strip_html_removes_tags_scripts_and_caps():
    raw = "<html><head><style>x{}</style><script>evil()</script></head><body><p>Hello &amp; world</p></body></html>"
    out = strip_html(raw, limit=100)
    assert "Hello & world" in out
    assert "evil" not in out and "x{}" not in out
    assert "<" not in out


def test_strip_html_limit():
    assert len(strip_html("<p>" + "a" * 9000 + "</p>", limit=500)) == 500


# ── _norm_url (arxiv pdf → abs) ──────────────────────────────────────────────────
def test_norm_arxiv_pdf_to_abs():
    assert _norm_url("https://arxiv.org/pdf/2212.12541") == "https://arxiv.org/abs/2212.12541"
    assert _norm_url("https://arxiv.org/pdf/1701.05946v2") == "https://arxiv.org/abs/1701.05946"
    assert _norm_url("https://en.wikipedia.org/wiki/X") == "https://en.wikipedia.org/wiki/X"


# ── control_accuracy (positive control = judge 탐지능력) ─────────────────────────
def test_control_accuracy():
    assert control_accuracy([("FAITHFUL", "FAITHFUL"), ("UNSUPPORTED", "UNSUPPORTED")]) == 1.0
    assert control_accuracy([("FAITHFUL", "UNSUPPORTED"), ("UNSUPPORTED", "UNSUPPORTED")]) == 0.5
    assert control_accuracy([]) == 0.0


# ── FaithReport (positive-control gate + 거짓양성 통제) ──────────────────────────
def test_report_measured_when_control_passes_low_faithful_real():
    # control_acc=1.0 → judge 탐지능력 입증 → 낮은 matched도 *진짜* MEASURED.
    low = FaithReport(n_accessible=22, matched_faithful=1, shuffled_faithful=0, control_acc=1.0)
    assert abs(low.matched_rate - 1 / 22) < 1e-9
    assert low.instrument_valid is True  # control 통과 + shuffled≤matched
    assert "MEASURED" in low.summary()


def test_report_inconclusive_when_control_fails():
    # judge가 faithful 탐지 못 하면(control_acc 낮음) matched 신뢰불가.
    bad = FaithReport(n_accessible=20, matched_faithful=1, shuffled_faithful=0, control_acc=0.4)
    assert bad.instrument_valid is False
    assert "INCONCLUSIVE" in bad.summary()


def test_report_inconclusive_when_shuffled_exceeds_matched():
    # 거짓양성: 섞은 게 맞춘 것보다 더 FAITHFUL이면 무효.
    fp = FaithReport(n_accessible=20, matched_faithful=3, shuffled_faithful=8, control_acc=1.0)
    assert fp.instrument_valid is False


def test_report_empty_safe():
    z = FaithReport(n_accessible=0, matched_faithful=0, shuffled_faithful=0, control_acc=1.0)
    assert z.matched_rate == 0.0 and z.delta == 0.0
