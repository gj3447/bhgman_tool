"""Tests for L4 in-toto attestation chain integrity gate.

Binary semantics: warn iff unsigned in recent window, halt iff broken
chain or policy violation. No graded thresholds — PROM 16 A4S4 explicit.

# KG: CONTRACT_IntotoChannel_v1_2026-05-19, sa-longinus-v3.4-L4-intoto-2026-05-19
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from engine.longinus_drift_audit.intoto_channel import (
    AttestationChainResult,
    IntotoAttestation,
    verify_chain,
)


SLSA_PRED = "https://slsa.dev/provenance/v1"
ALT_PRED = "https://in-toto.io/Statement/v1"
NOW = datetime(2026, 5, 19, 0, 0, 0)


def _att(
    subject: str,
    *,
    signed: bool = True,
    signer: str = "alice@example.com",
    predicate_type: str = SLSA_PRED,
    offset_min: int = 0,
) -> IntotoAttestation:
    return IntotoAttestation(
        subject=subject,
        predicate_type=predicate_type,
        predicate={"buildType": "test"},
        signer=signer,
        signature="sig_" + subject if signed else "",
        signed_at=NOW + timedelta(minutes=offset_min),
    )


def test_empty_chain_perfect():
    """No attestations, no expected subjects → PERFECT (degenerate clean case)."""
    r = verify_chain(attestations=[], expected_subjects=[])
    assert r.total_mutations == 0
    assert r.signed_count == 0
    assert r.unsigned_count == 0
    assert r.unsigned_ratio == 0.0
    assert not r.warn
    assert not r.halt
    assert r.severity == "PERFECT"
    assert r.broken_links == []
    assert r.policy_violations == []


def test_identity_all_signed_policy_match():
    """All subjects signed + predicate within policy → PERFECT, no warn/halt."""
    subjects = ["mut_001", "mut_002", "mut_003"]
    atts = [_att(s) for s in subjects]
    policy = {"allowed_predicate_types": [SLSA_PRED]}
    r = verify_chain(attestations=atts, expected_subjects=subjects, policy=policy)
    assert r.total_mutations == 3
    assert r.signed_count == 3
    assert r.unsigned_count == 0
    assert not r.warn
    assert not r.halt
    assert r.severity == "PERFECT"


def test_one_unsigned_in_recent_window_warns():
    """1 unsigned in last 100 → warn=True, halt=False."""
    subjects = ["mut_a", "mut_b", "mut_c"]
    atts = [
        _att("mut_a"),
        _att("mut_b", signed=False),  # unsigned
        _att("mut_c"),
    ]
    r = verify_chain(attestations=atts, expected_subjects=subjects)
    assert r.unsigned_count == 1
    assert r.warn is True
    assert r.halt is False
    assert r.severity == "WARN_UNSIGNED"


def test_broken_link_subject_missing_halts():
    """Expected subject without matching attestation → halt."""
    expected = ["mut_a", "mut_b", "mut_MISSING"]
    atts = [_att("mut_a"), _att("mut_b")]
    r = verify_chain(attestations=atts, expected_subjects=expected)
    assert r.halt is True
    assert any("missing_attestation:mut_MISSING" in b for b in r.broken_links)
    assert r.severity == "HALT_BROKEN_CHAIN"


def test_broken_link_unknown_subject_halts():
    """Attestation for a subject not in expected set → halt."""
    expected = ["mut_a"]
    atts = [_att("mut_a"), _att("mut_ROGUE")]
    r = verify_chain(attestations=atts, expected_subjects=expected)
    assert r.halt is True
    assert any("unknown_subject:mut_ROGUE" in b for b in r.broken_links)


def test_policy_violation_predicate_type_halts():
    """predicate_type outside allowed set → halt with policy violation."""
    subjects = ["mut_a", "mut_b"]
    atts = [
        _att("mut_a", predicate_type=SLSA_PRED),
        _att("mut_b", predicate_type=ALT_PRED),
    ]
    policy = {"allowed_predicate_types": [SLSA_PRED]}
    r = verify_chain(attestations=atts, expected_subjects=subjects, policy=policy)
    assert r.halt is True
    assert any("predicate_type_not_allowed:mut_b" in v for v in r.policy_violations)
    assert r.severity == "HALT_POLICY_VIOLATION"


def test_mock_signer_rejection_halts():
    """signature_verifier returns False → halt via policy_violations."""
    subjects = ["mut_a", "mut_b"]
    atts = [_att("mut_a"), _att("mut_b")]

    def reject_all(payload: bytes, sig: str, signer: str) -> bool:
        return False

    r = verify_chain(
        attestations=atts,
        expected_subjects=subjects,
        signature_verifier=reject_all,
    )
    assert r.halt is True
    assert all("signature_rejected" in v for v in r.policy_violations)
    assert r.severity == "HALT_POLICY_VIOLATION"


def test_key_rotation_signer_change_does_not_halt_alone():
    """Different signer mid-chain should NOT halt unless verifier rejects."""
    subjects = ["mut_a", "mut_b", "mut_c"]
    atts = [
        _att("mut_a", signer="alice@example.com"),
        _att("mut_b", signer="bob@example.com"),  # key rotation
        _att("mut_c", signer="bob@example.com"),
    ]

    def accept_known_signers(payload: bytes, sig: str, signer: str) -> bool:
        return signer in {"alice@example.com", "bob@example.com"}

    r = verify_chain(
        attestations=atts,
        expected_subjects=subjects,
        signature_verifier=accept_known_signers,
    )
    assert not r.halt
    assert r.signed_count == 3
    assert r.severity == "PERFECT"


def test_recent_window_size_negative_raises():
    with pytest.raises(ValueError, match="recent_window_size"):
        verify_chain(attestations=[], expected_subjects=[], recent_window_size=-1)


def test_recent_window_excludes_old_unsigned():
    """Old unsigned attestation outside window should NOT trigger warn."""
    # 5 attestations, only the *first* is unsigned; window=2 → window is
    # last 2, both signed → warn=False even though unsigned_count > 0.
    subjects = ["m1", "m2", "m3", "m4", "m5"]
    atts = [
        _att("m1", signed=False, offset_min=0),
        _att("m2", offset_min=1),
        _att("m3", offset_min=2),
        _att("m4", offset_min=3),
        _att("m5", offset_min=4),
    ]
    r = verify_chain(attestations=atts, expected_subjects=subjects, recent_window_size=2)
    assert r.unsigned_count == 1
    assert r.warn is False  # unsigned is outside window
    assert r.halt is False
    assert r.severity == "PERFECT"


def test_pydantic_serialization_roundtrip():
    """IntotoAttestation + AttestationChainResult both serialise cleanly."""
    att = _att("mut_x")
    payload = att.model_dump_json()
    rebuilt = IntotoAttestation.model_validate_json(payload)
    assert rebuilt.subject == "mut_x"
    assert rebuilt.signer == "alice@example.com"

    r = verify_chain(attestations=[att], expected_subjects=["mut_x"])
    d = r.model_dump()
    assert d["total_mutations"] == 1
    assert d["severity"] == "PERFECT"
    rebuilt_r = AttestationChainResult.model_validate(d)
    assert rebuilt_r.severity == "PERFECT"
