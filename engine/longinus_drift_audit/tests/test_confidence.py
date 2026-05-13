"""Confidence schema tests (graphify absorbed 2026-05-13).

Python mirrors of Lean theorems in
  MIND/lean_formalization/Longinus_ConfidenceSchema_GraphifyAbsorbed.lean
  - T1 ambiguous_unique_human_gate
  - T3 trust_strict_order
  - T6 ambiguous_in_list_forces_preliminary

KG: longinus-confidence-schema-3tier-2026-05-13 (:ConfidenceSchema:Canonical)
"""
from __future__ import annotations

import pytest

from models import (
    Confidence,
    ReferenceSite,
    any_ambiguous,
    requires_human_verdict,
    trust_level,
)


class TestConfidenceEnum:
    def test_three_values_exist(self):
        assert Confidence.EXTRACTED.value == "EXTRACTED"
        assert Confidence.INFERRED.value == "INFERRED"
        assert Confidence.AMBIGUOUS.value == "AMBIGUOUS"

    def test_enum_is_string_serializable(self):
        """str(Enum) round-trip — needed for KG Cypher property write."""
        for c in Confidence:
            assert Confidence(c.value) == c


class TestT1AmbiguousUniqueHumanGate:
    """Lean T1: AMBIGUOUS is the unique tier requiring human verdict."""

    def test_ambiguous_requires_human(self):
        assert requires_human_verdict(Confidence.AMBIGUOUS) is True

    def test_extracted_does_not_require_human(self):
        assert requires_human_verdict(Confidence.EXTRACTED) is False

    def test_inferred_does_not_require_human(self):
        assert requires_human_verdict(Confidence.INFERRED) is False

    @pytest.mark.parametrize("c", list(Confidence))
    def test_iff_ambiguous(self, c):
        """Bidirectional: requires_human_verdict(c) ↔ c == AMBIGUOUS."""
        assert requires_human_verdict(c) == (c == Confidence.AMBIGUOUS)


class TestT3TrustStrictOrder:
    """Lean T3: trust_level induces strict order EXTRACTED > INFERRED > AMBIGUOUS."""

    def test_extracted_highest(self):
        assert trust_level(Confidence.EXTRACTED) == 2

    def test_inferred_middle(self):
        assert trust_level(Confidence.INFERRED) == 1

    def test_ambiguous_lowest(self):
        assert trust_level(Confidence.AMBIGUOUS) == 0

    def test_strict_descending(self):
        assert (
            trust_level(Confidence.EXTRACTED)
            > trust_level(Confidence.INFERRED)
            > trust_level(Confidence.AMBIGUOUS)
        )


class TestT6AmbiguousContagion:
    """Lean T6: AMBIGUOUS in list forces aggregate :PRELIMINARY label."""

    def test_empty_list_not_ambiguous(self):
        assert any_ambiguous([]) is False

    def test_all_extracted_not_ambiguous(self):
        sites = [
            ReferenceSite(sourceId=f"lesson-x-{i}", sourcePath=f"src/a.py:{i}",
                          confidence=Confidence.EXTRACTED)
            for i in range(3)
        ]
        assert any_ambiguous(sites) is False

    def test_single_ambiguous_contaminates(self):
        sites = [
            ReferenceSite(sourceId="lesson-a", sourcePath="src/a.py:1",
                          confidence=Confidence.EXTRACTED),
            ReferenceSite(sourceId="lesson-b", sourcePath="src/b.py:2",
                          confidence=Confidence.AMBIGUOUS),
            ReferenceSite(sourceId="lesson-c", sourcePath="src/c.py:3",
                          confidence=Confidence.INFERRED),
        ]
        assert any_ambiguous(sites) is True

    def test_ambiguous_at_tail(self):
        sites = [
            ReferenceSite(sourceId="lesson-x", sourcePath="src/x.py:1",
                          confidence=Confidence.EXTRACTED),
            ReferenceSite(sourceId="lesson-y", sourcePath="src/y.py:99",
                          confidence=Confidence.AMBIGUOUS),
        ]
        assert any_ambiguous(sites) is True


class TestReferenceSiteConfidenceField:
    """BC + new field round-trip."""

    def test_default_is_extracted(self):
        """Backward compatibility: existing call sites without confidence get EXTRACTED."""
        rs = ReferenceSite(sourceId="lesson-foo-2026", sourcePath="src/foo.py:42")
        assert rs.confidence == Confidence.EXTRACTED

    def test_explicit_ambiguous(self):
        rs = ReferenceSite(
            sourceId="lesson-bar",
            sourcePath="src/bar.py:10",
            confidence=Confidence.AMBIGUOUS,
        )
        assert rs.confidence == Confidence.AMBIGUOUS
        assert requires_human_verdict(rs.confidence) is True

    def test_pydantic_serialization_round_trip(self):
        rs = ReferenceSite(
            sourceId="lesson-baz",
            sourcePath="src/baz.py:7",
            confidence=Confidence.INFERRED,
        )
        data = rs.model_dump()
        assert data["confidence"] == "INFERRED"
        rs2 = ReferenceSite.model_validate(data)
        assert rs2.confidence == Confidence.INFERRED
