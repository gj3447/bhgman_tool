"""Shared pytest fixtures for SYMPOSIUM-absorbed tests.

KG: rs-mcp-symposium-tests-conftest-2026-05-14
Provenance: SYMPOSIUM/tests/conftest.py (absorbed Wave 7 P2-A)
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Walk up to bhgman_tool repo root: 4 parents up from this file
# (.../bhgman_tool/engine/mcp_server/tests/symposium/conftest.py → bhgman_tool/)
BHGMAN_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="session")
def bhgman_root() -> Path:
    """Repo root of bhgman_tool (replaces SYMPOSIUM_ROOT in the original tests)."""
    return BHGMAN_ROOT


@pytest.fixture(scope="session")
def symposium_root(bhgman_root: Path) -> Path:
    """Backwards-compat alias for ported SYMPOSIUM tests."""
    return bhgman_root


@pytest.fixture(scope="session")
def skills_dir(bhgman_root: Path) -> Path:
    """SKILL.md root. bhgman_tool uses lowercase skills/."""
    return bhgman_root / "skills"


@pytest.fixture
def mock_kg(monkeypatch):
    """Replace _ssh_cypher with an in-memory mock for fail-closed-free tests.

    Targets engine.mcp_server.tools.symposium._ssh_cypher (not top-level server).
    """
    calls: list[dict] = []

    def fake_ssh_cypher(cypher: str, params=None, timeout_s: float = 5.0):
        calls.append({"cypher": cypher, "params": params or {}, "timeout_s": timeout_s})
        return {"ok": True, "stdout": "label  count\nFoo  1", "stderr": "", "returncode": 0}

    from engine.mcp_server.tools import symposium

    monkeypatch.setattr(symposium, "_ssh_cypher", fake_ssh_cypher)
    return calls
