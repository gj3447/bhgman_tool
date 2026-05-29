"""code_to_kg — tree-sitter source → KG symbol ingestion (POC 2).

Implements the tree-sitter primary pipeline recommended by PROM 16
(`prom16-code-to-kg-2026-05-28`, Consensus C1/C4): parse Python source with
tree-sitter, extract function/class/import/call symbols, and MERGE them into
Neo4j as an *isolated* `:CodeSymbol` family that weaves into the existing
`:SourceCodeNode` schema via `sourcePath` (DERIVED_FROM edge).

Design invariants (PROM 16 권고):
    - tree-sitter primary parse layer (C1).
    - code→KG UNIDIRECTIONAL + sha256 baseline drift (C4 / Longinus L1).
    - isolated label `:CodeSymbol` so the whole POC graph is one removable set
      (KG pollution guard — sibling Cognee/Joern NOT mixed).
    - graceful import: missing tree-sitter degrades to a documented stub.

# KG: lesson-prom16-code-to-kg-tools-2026-05-28, cycle prom16-code-to-kg-2026-05-28,
      ATOM_Skill_longinus (sha256 baseline L1), family-expansion-pattern-canonical-2026-04-30
"""

from __future__ import annotations

from .ts_extractor import (
    CodeGraph,
    SymbolNode,
    SymbolEdge,
    extract_python_file,
    extract_python_source,
    TREE_SITTER_AVAILABLE,
)

__all__ = [
    "CodeGraph",
    "SymbolNode",
    "SymbolEdge",
    "extract_python_file",
    "extract_python_source",
    "TREE_SITTER_AVAILABLE",
]
