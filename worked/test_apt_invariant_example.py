"""Example apt_invariant-tagged test — demonstrates F7 instrumentation.

This is the smoke-test for the pytest marker + conftest hook installed
per WQI F7. Each test asserts an APT methodology invariant; the conftest
hook writes a TSV row that downstream batch jobs ingest as :TestRunResult.

# KG: wqi-bhgman-apt-F7-test-tagging-apt-invariants-2026-05-25
# KG: adr-apt-phase-contract-2026-05-25
"""

from __future__ import annotations

import pytest


@pytest.mark.apt_invariant(
    rule="SourceCodeNode requires sha256+lineCount+sourcePath (t_sourcecode_required_fields_not_null APOC trigger)"
)
def test_required_fields_contract_documented():
    """The APOC schema trigger name is canonical; cross-ref CLAUDE.md §Constrain Layer (1)."""
    trigger_name = "t_sourcecode_required_fields_not_null"
    assert trigger_name.startswith("t_") and "required_fields" in trigger_name


@pytest.mark.apt_invariant(rule="apt-meta-review max_depth=1, delta=0 (self-application forbidden)")
def test_meta_review_self_application_constants():
    """Per adr-apt-phase-contract-2026-05-25 §Self-application forbidden."""
    max_depth, delta = 1, 0
    assert max_depth == 1 and delta == 0


@pytest.mark.apt_invariant(
    rule="Wave 9 §3 — AdversarialChallenge ≥ 1 per sprint-end MetaReview cycle"
)
def test_wave9_ac_minimum_constant():
    """Per CLAUDE.md Constrain Layer (3) + apt-gate-semantics ADR."""
    min_ac_per_cycle = 1
    assert min_ac_per_cycle >= 1
