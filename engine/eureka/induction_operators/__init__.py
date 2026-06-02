"""Induction operators for L8 abstract class generation.

4-way bake-off candidates (per seed-prom16lag-conflict-induction-primary-2026-05-20):
- FCA (Ganter-Wille 1999) — Galois lattice extent/intent, idempotent
- AMIE 3 (Lajus-Galárraga-Suchanek 2020) — typed Horn rule mining with PCA confidence
- Leiden-LLM (Edge 2024 GraphRAG) — offline CNM modularity (Leiden *family*) + summary
- Leiden-True (Traag-Waltman-vanEck 2019) — genuine Leiden via leidenalg+igraph (opt-in dep)
"""
# KG: eureka-canonical-2026-05-26

from engine.eureka.induction_operators.fca import FcaResult, induce_fca
from engine.eureka.induction_operators.leiden_llm import induce_leiden_llm
from engine.eureka.induction_operators.leiden_true import induce_leiden_true

__all__ = ["FcaResult", "induce_fca", "induce_leiden_llm", "induce_leiden_true"]
