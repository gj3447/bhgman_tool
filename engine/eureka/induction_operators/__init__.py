"""Induction operators for L8 abstract class generation.

3-way bake-off candidates (per seed-prom16lag-conflict-induction-primary-2026-05-20):
- FCA (Ganter-Wille 1999) — Galois lattice extent/intent, idempotent
- AMIE 3 (Lajus-Galárraga-Suchanek 2020) — typed Horn rule mining with PCA confidence
- Leiden-LLM (Edge 2024 GraphRAG) — hierarchical Leiden + per-community LLM summary
"""

from induction_operators.fca import FcaResult, induce_fca
from induction_operators.leiden_llm import induce_leiden_llm

__all__ = ["FcaResult", "induce_fca", "induce_leiden_llm"]
