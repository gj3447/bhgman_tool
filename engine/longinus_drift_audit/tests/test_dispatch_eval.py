"""Tests for deterministic dispatch-output eval.

Pure / offline — no KG, no network. Encodes the project's own contracts
(FullFindingRecord + citation covenant + WRITE_DEFERRED + cardinality).

# KG: finding-aidev-dispatch-eval-2026-05-25
"""

from __future__ import annotations

from engine.longinus_drift_audit.dispatch_eval import (
    DispatchEvalReport,
    evaluate_dispatch,
    evaluate_finding,
)


def _good(**over) -> dict:
    rec = {
        "findingId": "finding_x",
        "oneLineSummary": "a real one-line summary",
        "citation_url": "https://arxiv.org/abs/2209.10652",
        "confidence": "HIGH",
        "agentId": "agent-1",
    }
    rec.update(over)
    return rec


# ─── per-finding checks ──────────────────────────────────────────────────


def test_clean_finding_passes() -> None:
    assert evaluate_finding(_good()).passed is True


def test_missing_citation_fails() -> None:
    res = evaluate_finding(_good(citation_url=None))
    assert "has_citation" in res.failures


def test_references_only_satisfies_citation() -> None:
    res = evaluate_finding(_good(citation_url=None, references=["Author 2024, Title"]))
    assert "has_citation" not in res.failures


def test_no_external_citation_waiver_ok() -> None:
    res = evaluate_finding(
        _good(citation_url=None, no_external_citation_reason="internal experiment")
    )
    assert "has_citation" not in res.failures


def test_self_write_claim_flag_field() -> None:
    res = evaluate_finding(_good(kg_writes_done=True))
    assert "no_self_write_claim" in res.failures


def test_self_write_claim_phrase() -> None:
    res = evaluate_finding(_good(recommendation="30개 노드 생성 완료, write 성공"))
    assert "no_self_write_claim" in res.failures


def test_invalid_confidence_fails() -> None:
    assert "valid_confidence" in evaluate_finding(_good(confidence="VERY_SURE")).failures


def test_empty_summary_fails() -> None:
    assert "has_summary" in evaluate_finding(_good(oneLineSummary="   ")).failures


# ─── batch / verdict ─────────────────────────────────────────────────────


def test_all_clean_batch_passes() -> None:
    rep = evaluate_dispatch([_good(findingId=f"f{i}") for i in range(4)])
    assert isinstance(rep, DispatchEvalReport)
    assert rep.verdict == "PASS"
    assert rep.pass_rate == 1.0


def test_cardinality_miss_forces_fail() -> None:
    rep = evaluate_dispatch([_good(), _good()], intent_n=4)
    assert rep.verdict == "FAIL"
    assert "cardinality_match" in rep.failed_check_counts


def test_self_write_claim_forces_fail() -> None:
    rep = evaluate_dispatch([_good(), _good(kg_writes_done=True)])
    assert rep.verdict == "FAIL"


def test_soft_shortfall_warns() -> None:
    # one finding missing citation (soft check) → pass_rate 0.5 < 0.90 → WARN (no hard breach)
    rep = evaluate_dispatch([_good(), _good(citation_url=None)])
    assert rep.verdict == "WARN"


def test_empty_batch_passes_vacuously() -> None:
    rep = evaluate_dispatch([])
    assert rep.verdict == "PASS"
    assert rep.total == 0
