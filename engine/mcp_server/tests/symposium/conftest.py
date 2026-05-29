"""Shared pytest fixtures for SYMPOSIUM-absorbed tests.

KG: rs-mcp-symposium-tests-conftest-2026-05-14
Provenance: SYMPOSIUM/tests/conftest.py (absorbed Wave 7 P2-A)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Walk up to bhgman_tool repo root: 4 parents up from this file
# (.../bhgman_tool/engine/mcp_server/tests/symposium/conftest.py → bhgman_tool/)
BHGMAN_ROOT = Path(__file__).resolve().parents[4]

# These tests import `from engine.mcp_server.tools.symposium import ...` (repo-root
# absolute), but the CI mcp_server suite runs from working-directory engine/mcp_server
# where only the flat `mcp_server` package is installed — so the `engine` namespace
# package is not importable. Bridge repo root onto sys.path at collection time
# (project sys.path-bridge pattern; see root pyproject E402 per-file-ignore note).
if str(BHGMAN_ROOT) not in sys.path:
    sys.path.insert(0, str(BHGMAN_ROOT))


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
