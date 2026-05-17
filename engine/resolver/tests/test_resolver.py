"""APT resolver — unit tests.

Absorbed from SYMPOSIUM/THEORY/APT/resolver_prototype/tests/test_resolver.py (Wave 7 P3-H).
KG 의존 부분은 mock (CypherKGClient stub). 실제 Neo4j 연결 테스트는 integration suite.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from engine.resolver import resolver
from engine.resolver.cypher_kg_client import CypherKGClient, MissingConfigError
from engine.resolver.jinja_env import UnresolvedMarkerError, build_env


# ─── fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def mock_kg(tmp_path: Path):
    """5 core field 모두 채워진 mock KG client."""
    client = MagicMock()
    client.health_check.return_value = True
    client.fetch_methodology_config.return_value = {
        "vibe_coding_sweet_min": 200,
        "vibe_coding_sweet_max": 500,
        "lens_count_constitutional": 9,
        "contract_default_fields": 7,
        "st_decision_areas": 8,
    }
    client.verify_core_magic_present.return_value = None
    return client


@pytest.fixture
def example_skill_path() -> Path:
    return Path(__file__).parent.parent / "example_skill.md"


# ─── render path ─────────────────────────────────────────────────────────


def test_resolve_replaces_all_markers(mock_kg, example_skill_path):
    result = resolver.resolve(example_skill_path, mock_kg)
    assert "{{cfg." not in result.rendered_body, "All markers must resolve"
    assert "200" in result.rendered_body
    assert "500" in result.rendered_body
    assert "9" in result.rendered_body
    assert len(result.used_markers) == 5


def test_resolve_raises_on_missing_marker(mock_kg, tmp_path):
    skill = tmp_path / "broken.md"
    skill.write_text("---\nname: broken\n---\n\nValue: {{cfg.nonexistent_field}}\n")
    mock_kg.fetch_methodology_config.return_value = {"some_other": 1}
    with pytest.raises(SystemExit):
        resolver.resolve(skill, mock_kg)


# ─── validate path ───────────────────────────────────────────────────────


def test_validate_clean_skill_passes(mock_kg, example_skill_path):
    report = resolver.validate(example_skill_path, mock_kg)
    assert report.ok, f"example_skill.md must validate cleanly: {report}"
    assert not report.missing_in_kg
    assert not report.bare_inline_numbers


def test_validate_detects_bare_inline_number(mock_kg, tmp_path):
    skill = tmp_path / "bad.md"
    skill.write_text("---\nname: bad\n---\n\n# 위반\n\nvibe coding sweet 200~500 줄.\n")
    report = resolver.validate(skill, mock_kg)
    assert not report.ok
    nums = [n for _, n in report.bare_inline_numbers]
    assert "200" in nums
    assert "500" in nums


def test_validate_allows_parenthetical_hint(mock_kg, tmp_path):
    skill = tmp_path / "with_hint.md"
    skill.write_text(
        "---\nname: ok\n---\n\n"
        "vibe coding sweet `{{cfg.vibe_coding_sweet_min}}` (현재 200) 줄.\n"
    )
    report = resolver.validate(skill, mock_kg)
    assert not report.bare_inline_numbers, "괄호 안 reader-facing 안내는 위반 X"


def test_validate_detects_orphan_cfg_field(mock_kg, tmp_path):
    """KG에는 있는데 SKILL.md 어디서도 참조 안 됨 → orphan WARN."""
    skill = tmp_path / "partial.md"
    skill.write_text("---\nname: partial\n---\n\nOnly: {{cfg.vibe_coding_sweet_min}}\n")
    report = resolver.validate(skill, mock_kg)
    # 4 fields(max/lens/contract/st) 모두 orphan
    assert "vibe_coding_sweet_max" in report.orphan_kg_fields
    assert "lens_count_constitutional" in report.orphan_kg_fields


# ─── boot path ───────────────────────────────────────────────────────────


def test_boot_fails_on_missing_core_field():
    """5 core field 중 누락 시 startup 즉시 실패 (Composition Root)."""
    incomplete = MagicMock()
    incomplete.health_check.return_value = True
    incomplete.fetch_methodology_config.return_value = {
        "vibe_coding_sweet_min": 200,
        # 나머지 4 누락
    }

    # verify_core_magic_present 직접 호출 (우회 mock)
    real_method = CypherKGClient.verify_core_magic_present.__get__(incomplete)
    with pytest.raises(MissingConfigError):
        real_method()


# ─── jinja sandbox ───────────────────────────────────────────────────────


def test_sandboxed_env_blocks_attr_access():
    env = build_env()
    template = env.from_string("{{ cfg.__class__ }}")
    with pytest.raises((UnresolvedMarkerError, Exception)):
        template.render(cfg={"vibe_coding_sweet_min": 200})


def test_strict_undefined_raises_on_missing():
    env = build_env()
    template = env.from_string("{{ cfg.never_defined }}")
    with pytest.raises(UnresolvedMarkerError):
        template.render(cfg={"only_this": 1})
