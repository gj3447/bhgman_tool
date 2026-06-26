"""naesengmoon kg-corroboration oracle — a separate-SOURCE verdict leg.

The verify ensemble's existing critics (lean-goals / pytest-ratio / drift-recount /
occam-twins) all measure code / proof / KG-self-state — NONE probe whether a *claim*
contradicts persisted canon. So 3/5 verdict legs were derived-self (frontier OQ
q-naesengmoon-single-authority): the ensemble had no external/separate-source check.

This deterministic, dep-free oracle corroborates a claim against the KG's CANONICAL facts
(via the existing :class:`GroundingSource` contract — zero neo4j/LLM/torch). If a high-overlap
canonical fact (label in ``_CANON_LABELS``) carries the OPPOSITE polarity to the claim (one
negated, the other not), the claim is contradicted by canon → not corroborated. It is an
ORACLE leg (substrate-disjoint from the LLM judges), so a contradiction VETOES the ensemble
(:func:`decorrelation.aggregate`).

Honest scope: this is a lexical overlap + polarity heuristic, not full NLI — it catches a
claim that directly negates (or is directly negated by) a high-overlap canonical fact, which
is the single-authority gap that mattered. It abstains (passed=True) when canon is silent.

# KG: q-naesengmoon-single-authority, naesengmoon-canonical-2026-05-19
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from engine.agents.grounding import _CANON_LABELS, _node_blob, _props_of, _terms
from engine.naesengmoon.decorrelation import CriticKind, CriticVerdict

_LENS = "kg-corroborate"

# negation markers — word-based for English (avoids 'another'→'not' false positives),
# substring for Korean.
_NEG_WORDS = frozenset(
    {
        "not",
        "never",
        "no",
        "nor",
        "false",
        "incorrect",
        "wrong",
        "cannot",
        "isn't",
        "aren't",
        "doesn't",
        "don't",
        "wasn't",
        "weren't",
    }
)
_NEG_KO = ("아님", "아니", "없", "거짓", "틀린", "반증")


def _has_negation(text: str) -> bool:
    low = text.lower()
    if set(re.findall(r"[a-z']+", low)) & _NEG_WORDS:
        return True
    return any(k in low for k in _NEG_KO)


def _is_canonical(node: dict) -> bool:
    return any(lbl in _CANON_LABELS for lbl in node.get("labels", []))


def _node_text(node: dict) -> str:
    # reuse the SAME text the GroundingSource indexes (grounding._TEXT_PROPS), so overlap +
    # polarity are computed on exactly what search matched on.
    return _node_blob(_props_of(node))


def _overlap(claim_terms: list[str], text: str) -> float:
    if not claim_terms:
        return 0.0
    low = text.lower()
    return sum(1 for t in claim_terms if t in low) / len(claim_terms)


@dataclass(frozen=True)
class KgCorroborationOracle:
    """A separate-source critic: corroborate a claim against canonical KG facts."""

    source: Any  # GroundingSource (LocalGroundingSource / Neo4jGroundingSource)
    overlap_threshold: float = 0.5
    limit: int = 8

    def evaluate(self, claim: str) -> CriticVerdict:
        terms = _terms(claim)
        claim_negated = _has_negation(claim)
        passed = True
        for node in self.source.search(terms, self.limit):
            if not _is_canonical(node):
                continue
            text = _node_text(node)
            if _overlap(terms, text) < self.overlap_threshold:
                continue
            # high-overlap canonical fact with OPPOSITE polarity → it contradicts the claim
            if _has_negation(text) != claim_negated:
                passed = False
                break
        return CriticVerdict(
            lens=_LENS, kind=CriticKind.ORACLE, passed=passed, model_family="deterministic"
        )


def kg_corroboration_oracle(source: Any) -> KgCorroborationOracle:
    """Build the separate-source corroboration oracle over a :class:`GroundingSource`."""
    return KgCorroborationOracle(source=source)


__all__ = ["KgCorroborationOracle", "kg_corroboration_oracle"]
