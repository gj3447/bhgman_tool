"""Resolver E2E golden tests (PROM 16 A5 scaffold).

Absorbed from SYMPOSIUM/THEORY/APT/resolver_prototype/tests/test_resolver_e2e_golden.py
(Wave 7 P3-H, 2026-05-14).

Approach: write SKILL.md fixture to tmp_path → resolver.resolve(path, client) →
inspect ResolveResult.body for substituted markers.

Real resolver API (engine/resolver/resolver.py):
    resolve(skill_path: Path, client: CypherKGClient) -> ResolveResult
"""

from __future__ import annotations
import pathlib
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_cfg_kg():
    """Mock CypherKGClient — returns known cfg dict from fetch_methodology_config()."""
    client = MagicMock()
    client.health_check.return_value = True
    client.fetch_methodology_config.return_value = {
        "vibe_coding_sweet_min": 200,
        "vibe_coding_sweet_max": 500,
        "lens_count_constitutional": 9,
        "contract_default_fields": 7,
        "st_decision_areas": 8,
        "fulfillment_gate_checks": 7,
    }
    client.verify_core_magic_present.return_value = None
    client.close = MagicMock()
    return client


def _write(tmp_path, content: str) -> pathlib.Path:
    p = tmp_path / "test.md"
    p.write_text(content, encoding="utf-8")
    return p


def test_e2e_minimal_2_markers_resolved(tmp_path, sample_skill_md_minimal, mock_cfg_kg):
    """Minimal SKILL.md with 2 markers → resolver replaces both."""
    from engine.resolver.resolver import resolve

    p = _write(tmp_path, sample_skill_md_minimal)
    result = resolve(p, mock_cfg_kg)
    assert "{{cfg." not in result.rendered_body, "All markers should be resolved"
    assert "200" in result.rendered_body and "500" in result.rendered_body


def test_e2e_full_6_markers_resolved(tmp_path, sample_skill_md_full, mock_cfg_kg):
    """Realistic SKILL.md with 6 markers → all resolved."""
    from engine.resolver.resolver import resolve

    p = _write(tmp_path, sample_skill_md_full)
    result = resolve(p, mock_cfg_kg)
    assert "{{cfg." not in result.rendered_body
    for v in ["200", "500", "9", "7", "8"]:
        assert v in result.rendered_body


def test_e2e_orphan_bare_number_detected(tmp_path, sample_skill_md_orphan, mock_cfg_kg):
    """SKILL.md with bare inline number (no marker) → validate.bare_inline_numbers flags."""
    from engine.resolver.resolver import validate

    p = _write(tmp_path, sample_skill_md_orphan)
    report = validate(p, mock_cfg_kg)
    # ValidateReport.bare_inline_numbers: tuple[(lineno, num)]
    bare = report.bare_inline_numbers
    # PARENTHETICAL_HINT_RE removes "(currently 200)" patterns,
    # so the bare "200" inline (not in parens) should remain flagged.
    assert any("200" in str(b[1]) for b in bare), (
        f"Expected bare 200 flag in non-paren context, got bare={bare}"
    )


def test_e2e_real_skill_md_apt_sp(mock_cfg_kg):
    """Resolve real apt-sp/SKILL.md from filesystem (3 unique markers)."""
    # bhgman_tool layout: skills/apt-sp/SKILL.md
    candidates = [
        pathlib.Path(__file__).resolve().parents[3] / "skills" / "apt-sp" / "SKILL.md",
        pathlib.Path("/Users/lagyeongjun/CD/SYMPOSIUM/SKILLS/apt-sp/SKILL.md"),
        pathlib.Path("/home/metahumotonic27/symposium/SKILLS/apt-sp/SKILL.md"),
    ]
    real_path = next((c for c in candidates if c.exists()), None)
    if real_path is None:
        pytest.skip(f"SKILL.md not found at any of: {[str(c) for c in candidates]}")
    from engine.resolver.resolver import resolve

    result = resolve(real_path, mock_cfg_kg)
    assert "{{cfg.vibe_coding_sweet_min}}" not in result.rendered_body
    assert "{{cfg.vibe_coding_sweet_max}}" not in result.rendered_body
    assert "{{cfg.lens_count_constitutional}}" not in result.rendered_body
    assert (
        "200" in result.rendered_body
        and "500" in result.rendered_body
        and "9" in result.rendered_body
    )
