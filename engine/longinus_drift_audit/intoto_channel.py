"""L4 in-toto attestation chain integrity gate (v3.4, 2026-05-19).

Per PROM 16 OQ2 ALT6 (A4S4 finding). Cryptographic non-repudiation gate
that complements the *quantitative* drift channels L1 (GED), L2 (URDNA2015
Jaccard), and L3 (W3C PROV). L4 is **binary** (warn / halt only) — there
is no graded "small drift OK" signal. A signed attestation chain is either
intact or it isn't.

Background:
  - in-toto (Torres-Arias et al., USENIX Security 2019) — cryptographic
    attestations binding each supply-chain step to a signer.
  - Sigstore (Newman et al., ACM CCS 2022) — keyless signing via OIDC +
    Rekor transparency log.
  - SLSA v1.0 (https://slsa.dev) — provenance + build integrity framework.

L4 model:
  - Each KG mutation MAY emit an `IntotoAttestation` (subject + predicate
    + signer + signature).
  - `verify_chain` walks a stream of attestations against an expected set
    of subjects (the actual KG mutations observed) and a (optional) policy
    that restricts allowed predicate types.
  - Drift conditions are *categorical*:
      * warn  ← any unsigned attestation in the most recent window.
      * halt  ← broken chain (subject missing or unknown) OR policy
                 violation OR signature_verifier rejects.

Honest disclaimers (also recorded on DecisionLog
``decision-longinus-v3.4-L4-intoto-shipped-2026-05-19``):
  1. **Pluggable signature verifier** — the default
     ``signature_verifier`` is a no-op stub returning ``True``. Production
     deployment MUST inject a real verifier (sigstore-python, cosign,
     ssh-keygen -Y verify, etc.).
  2. **No rekor transparency log query** — ``transparency_log_url`` is a
     metadata field only; this module does not yet query Rekor / CT log.
     Future work: integrate ``rekor-cli`` or sigstore-python.
  3. **Policy DSL minimal** — only ``allowed_predicate_types`` is checked.
     Full SLSA Build L3 verification (provenance.materials, builder.id,
     reproducible build hash, etc.) is deferred.
  4. **Binary semantics intentional** — DO NOT add a graded threshold
     here. L1/L2/L3 already cover continuous drift; L4 is the binary
     integrity gate. PROM 16 A4S4 explicit: "no gradient signal for
     'small drift OK'".

# KG: CONTRACT_IntotoChannel_v1_2026-05-19, sa-longinus-v3.4-L4-intoto-2026-05-19,
#     wqi-longinus-v3.4-L4-intoto-attestation-2026-05-19,
#     finding_A4S4_oq2_2026_05_19, decision-longinus-v3.4-L4-intoto-shipped-2026-05-19
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Iterable, Optional

from pydantic import BaseModel, Field, field_validator


SignatureVerifier = Callable[[bytes, str, str], bool]
"""(payload, signature, signer) -> bool. Production: sigstore/cosign."""


def _default_verifier(payload: bytes, signature: str, signer: str) -> bool:
    """No-op stub. Returns True for any non-empty signature.

    Empty signature still fails (signals 'unsigned' upstream). Real
    deployment MUST override.
    """
    return bool(signature)


class IntotoAttestation(BaseModel):
    # KG: ATOM_Skill_longinus
    """One in-toto-style attestation over a KG mutation.

    Loosely follows the in-toto v1 statement schema
    (https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md)
    but stripped to the fields L4 needs for chain integrity.
    """

    subject: str = Field(..., description="KG node name or mutation id this attests to.")
    predicate_type: str = Field(..., description="e.g. 'https://slsa.dev/provenance/v1'.")
    predicate: dict = Field(default_factory=dict)
    signer: str = Field(..., description="Identity (email / DID / keyid) that signed.")
    signature: str = Field(default="", description="Base64 or hex signature; empty = unsigned.")
    signed_at: datetime
    transparency_log_url: Optional[str] = Field(
        default=None,
        description="Optional Rekor / CT log URL. NOT verified in this module (stub).",
    )


class AttestationChainResult(BaseModel):
    # KG: ATOM_Skill_longinus
    """Output of L4 in-toto attestation chain verification."""

    total_mutations: int = Field(ge=0)
    signed_count: int = Field(ge=0)
    unsigned_count: int = Field(ge=0)
    broken_links: list[str] = Field(default_factory=list)
    policy_violations: list[str] = Field(default_factory=list)
    unsigned_ratio: float = Field(ge=0.0, le=1.0)
    warn: bool
    halt: bool
    severity: str
    recent_window_size: int = Field(ge=0)

    @field_validator("severity")
    @classmethod
    def _severity_valid(cls, v: str) -> str:
        valid = {"PERFECT", "WARN_UNSIGNED", "HALT_BROKEN_CHAIN", "HALT_POLICY_VIOLATION"}
        if v not in valid:
            raise ValueError(f"severity must be one of {valid}")
        return v


def _payload_bytes(att: IntotoAttestation) -> bytes:
    """Canonical bytes for verifier input (deterministic)."""
    return att.model_dump_json(exclude={"signature"}).encode("utf-8")


def _verify_signature_safe(
    verifier: SignatureVerifier,
    att: IntotoAttestation,
) -> tuple[bool, Optional[str]]:
    """Run signature verifier defensively. Returns (ok, violation_msg)."""
    try:
        ok = verifier(_payload_bytes(att), att.signature, att.signer)
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"verifier_exception:{att.subject}:{exc!r}"
    if not ok:
        return False, f"signature_rejected:{att.subject}:{att.signer}"
    return True, None


def _classify_attestation(
    att: IntotoAttestation,
    *,
    expected_set: set[str],
    allowed_preds: Optional[set[str]],
    verifier: SignatureVerifier,
) -> dict:
    """Return per-attestation outcome: subject_known, signed, violations, broken."""
    if att.subject not in expected_set:
        return {
            "broken": f"unknown_subject:{att.subject}",
            "seen": None,
            "violation": None,
            "signed": False,
            "unsigned": False,
        }

    if allowed_preds is not None and att.predicate_type not in allowed_preds:
        pred_violation: Optional[str] = (
            f"predicate_type_not_allowed:{att.subject}:{att.predicate_type}"
        )
    else:
        pred_violation = None

    if not att.signature:
        return {
            "broken": None,
            "seen": att.subject,
            "violation": pred_violation,
            "signed": False,
            "unsigned": True,
        }

    ok, sig_violation = _verify_signature_safe(verifier, att)
    violation = pred_violation or sig_violation
    return {
        "broken": None,
        "seen": att.subject,
        "violation": violation,
        "signed": ok and pred_violation is None,
        "unsigned": False,
    }


def _severity_for_chain(
    *,
    halt: bool,
    warn: bool,
    policy_violations: list[str],
) -> str:
    if halt:
        return "HALT_POLICY_VIOLATION" if policy_violations else "HALT_BROKEN_CHAIN"
    return "WARN_UNSIGNED" if warn else "PERFECT"


def verify_chain(
    attestations: Iterable[IntotoAttestation],
    expected_subjects: Iterable[str],
    policy: Optional[dict] = None,
    recent_window_size: int = 100,
    *,
    signature_verifier: SignatureVerifier = _default_verifier,
) -> AttestationChainResult:
    # KG: ATOM_Skill_longinus
    """Verify a stream of in-toto attestations against expected mutations.

    Args:
        attestations: stream of ``IntotoAttestation`` (insertion order
            preserved; ``recent_window_size`` slices the tail).
        expected_subjects: KG mutation subjects that SHOULD be attested.
            Any expected subject without a matching attestation → broken
            link. Any attestation whose subject is NOT in this set →
            broken link (unknown / orphan).
        policy: optional dict. Recognised keys:
            ``allowed_predicate_types`` (Iterable[str]) — predicate_types
            outside this set count as policy violations.
        recent_window_size: how many trailing attestations to inspect for
            the unsigned-warn flag (default 100). Older unsigned entries
            do not trip ``warn`` (matches "last N ops" semantics).
        signature_verifier: pluggable callable; default = stub that
            accepts any non-empty signature. Production: real crypto.

    Returns:
        ``AttestationChainResult`` with binary warn/halt verdicts.

    Raises:
        ValueError: if ``recent_window_size`` < 0.

    Binary semantics:
      - warn := unsigned_count_in_recent_window > 0
      - halt := broken_links OR policy_violations non-empty
        (signature_verifier rejection also feeds policy_violations).
    """
    if recent_window_size < 0:
        raise ValueError(f"recent_window_size must be >= 0, got {recent_window_size}")

    att_list = list(attestations)
    expected_set = set(expected_subjects)
    allowed_preds: Optional[set[str]] = (
        set(policy["allowed_predicate_types"])
        if policy and "allowed_predicate_types" in policy
        else None
    )

    outcomes = [
        _classify_attestation(
            att,
            expected_set=expected_set,
            allowed_preds=allowed_preds,
            verifier=signature_verifier,
        )
        for att in att_list
    ]
    seen_subjects = {o["seen"] for o in outcomes if o["seen"]}
    broken_links = [o["broken"] for o in outcomes if o["broken"]]
    policy_violations = [o["violation"] for o in outcomes if o["violation"]]
    signed_count = sum(1 for o in outcomes if o["signed"])
    unsigned_count = sum(1 for o in outcomes if o["unsigned"])

    broken_links.extend(f"missing_attestation:{m}" for m in (expected_set - seen_subjects))

    total_mutations = len(att_list)
    unsigned_ratio = unsigned_count / total_mutations if total_mutations else 0.0
    recent = att_list[-recent_window_size:] if recent_window_size > 0 else []
    warn_flag = sum(1 for a in recent if not a.signature) > 0
    halt_flag = bool(broken_links) or bool(policy_violations)

    return AttestationChainResult(
        total_mutations=total_mutations,
        signed_count=signed_count,
        unsigned_count=unsigned_count,
        broken_links=broken_links,
        policy_violations=policy_violations,
        unsigned_ratio=unsigned_ratio,
        warn=warn_flag,
        halt=halt_flag,
        severity=_severity_for_chain(
            halt=halt_flag,
            warn=warn_flag,
            policy_violations=policy_violations,
        ),
        recent_window_size=recent_window_size,
    )
