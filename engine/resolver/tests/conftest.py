"""Pytest fixtures for resolver E2E tests (PROM 16 A5).

Absorbed from SYMPOSIUM/THEORY/APT/resolver_prototype/tests/conftest.py (Wave 7 P3-H).

- mock_kg: light Mock for fast unit tests (existing test_resolver.py)
- real_neo4j_container: ephemeral Neo4j via testcontainers for E2E golden tests
- sample_skill_md: 3 SKILL.md fixtures (sample/full/edge_case)
"""

from __future__ import annotations
import pathlib
import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_skill_md_minimal() -> str:
    """Minimal SKILL.md with 2 markers — used for happy-path E2E."""
    return """---
name: test-skill-sample
kg_ref: ATOM_Skill_test_sample
version: "1.0.0"
---

# Test Skill Sample

This is a minimal skill referencing `{{cfg.vibe_coding_sweet_min}}` (currently 200) and
`{{cfg.vibe_coding_sweet_max}}` (currently 500) as cfg-resolved magic numbers.
"""


@pytest.fixture
def sample_skill_md_full() -> str:
    """Full SKILL.md with 6 markers — realistic apt-scw analogue."""
    return """---
name: test-skill-full
kg_ref: ATOM_Skill_test_full
version: "1.0.0"
---

# Test Skill Full

- vibe_coding sweet spot: `{{cfg.vibe_coding_sweet_min}}`-`{{cfg.vibe_coding_sweet_max}}` lines
- Taliban lens count: `{{cfg.lens_count_constitutional}}`
- Contract default fields: `{{cfg.contract_default_fields}}`
- ST decision areas: `{{cfg.st_decision_areas}}`
- FulfillmentGate checks: `{{cfg.fulfillment_gate_checks}}`
"""


@pytest.fixture
def sample_skill_md_orphan() -> str:
    """SKILL.md with bare inline number — should be flagged."""
    return """---
name: test-skill-orphan
kg_ref: ATOM_Skill_test_orphan
version: "1.0.0"
---

# Orphan Test

This skill has bare `200` inline (should be {{cfg.vibe_coding_sweet_min}} marker).
Validator should flag this E-CB1 hardcoded violation.
"""


# Optional: testcontainers-based ephemeral Neo4j fixture (full E2E).
# Skipped by default — enable with `RESOLVER_E2E_REAL_KG=true pytest`
@pytest.fixture(scope="session")
def real_neo4j_container():
    """Ephemeral Neo4j via testcontainers (PROM 16 A5 finding pattern).

    Skipped unless RESOLVER_E2E_REAL_KG=true. Production CI activates this.
    Returns: (uri, user, password) tuple usable by neo4j-driver.
    """
    import os

    if os.environ.get("RESOLVER_E2E_REAL_KG", "false").lower() != "true":
        pytest.skip("RESOLVER_E2E_REAL_KG not set — skipping real KG E2E")
    try:
        from testcontainers.neo4j import Neo4jContainer
    except ImportError:
        pytest.skip("testcontainers-python[neo4j] not installed")
    with Neo4jContainer("neo4j:5.20-community") as neo:
        uri = neo.get_connection_url()
        yield uri, "neo4j", neo.NEO4J_ADMIN_PASSWORD
