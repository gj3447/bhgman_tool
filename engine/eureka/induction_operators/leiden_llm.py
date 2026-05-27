"""Leiden + LLM summarization induction stub.

Edge et al. 2024 GraphRAG (arXiv 2404.16130). Hierarchical Leiden (Traag-Waltman-vanEck
2019) at γ ∈ {0.5, 1.0, 2.0} → per-community Haiku summary via 재배맨 SOP →
:AbstractClass.

Status: STUB — pending bake-off implementation. Requires:
- gds 2.6+ on Neo4j VM
- Haiku model dispatch via 재배맨 SubagentTaskSpec
- Embedding channel for community-summary RRF retrieval (stage 6)

NOT IMPLEMENTED. Calling induce_leiden_llm raises NotImplementedError.
"""

from __future__ import annotations


def induce_leiden_llm(*args, **kwargs):
    raise NotImplementedError(
        "Leiden-LLM induction is a stub. Implementation pending bake-off — see "
        "plan-prom16lag-l8-induction-2026-05-20 + "
        "seed-prom16lag-cons-gamma-sweep-hierarchical-2026-05-20."
    )


__all__ = ["induce_leiden_llm"]
