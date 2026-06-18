"""Signature baseline — the SigMismatch counterpart of the sha256 baseline.

`detect_sig_mismatch` only fires its real (structural ast) path when a
ReferenceSite carries a recorded baseline signature. This module records that
baseline: it takes the live code symbols (with canonical signatures from the
ast scanner) and writes each bound symbol's signature onto its ReferenceSite as
``signature_baseline``. A later audit then detects parameter/annotation/return
drift against the frozen baseline.

Lifecycle mirrors sha256_baseline (init → drift on mismatch):
    1. record_signature_baselines(kg, symbols)   # freeze current signatures
    2. ... code changes ...
    3. audit → KgRefRecord.expected_signature = signature_baseline → SigMismatch

# KG: drift_detector.detect_sig_mismatch, longinus-sha256-daemon-canonical-2026-05-06 (baseline pattern)
"""

from __future__ import annotations

from engine.longinus_drift_audit.kg_client import KgClient
from engine.longinus_drift_audit.models import CodeSymbol


def signatures_by_ref(symbols: list[CodeSymbol]) -> dict[str, str]:
    # KG: ATOM_Skill_longinus
    """sourceId → live canonical signature, from each symbol's `# KG:` refs.

    First symbol wins per ref (refs are normally 1:1 with the symbol they anchor).
    Symbols without a signature (e.g. a class with no bases) are skipped.
    """
    out: dict[str, str] = {}
    for s in symbols:
        if s.signature is None:
            continue
        for ref in s.kg_refs:
            out.setdefault(ref, s.signature)
    return out


def record_signature_baselines(
    kg: KgClient, symbols: list[CodeSymbol], repo_tag: str | None = None
) -> int:
    # KG: ATOM_Skill_longinus
    """Freeze each bound symbol's current signature onto its ReferenceSite.

    Returns the number of sites whose baseline was (re)written. Idempotent — a
    baseline already equal to the live signature is left untouched, so re-running
    on unchanged code writes nothing.

    repo_tag (2026-06-01): scope to one repo's sites (shared dgx KG). Matching is
    by ``site.sourceId`` == a `# KG:` ref name (signatures_by_ref is keyed by ref),
    so sites must be materialized with ``sourceId = kg_ref`` for this to fire.
    """
    live = signatures_by_ref(symbols)
    updated = 0
    for site in kg.list_reference_site_states(repo_tag):
        sig = live.get(site.sourceId)
        if sig is not None and site.signature_baseline != sig:
            kg.merge_reference_site_state(site.model_copy(update={"signature_baseline": sig}))
            updated += 1
    return updated


__all__ = ["record_signature_baselines", "signatures_by_ref"]
