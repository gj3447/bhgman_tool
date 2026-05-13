"""Tests for Longinus drift detection daemon (skeleton).

Pattern absorbed from code-review-graph (tirth8205) crg-daemon (2026-05-13).
KG: longinus-drift-daemon-pattern-2026-05-13 (:DaemonPattern:Canonical)
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from daemon import RepoEntry, WatchConfig, safe_read_hash


class TestWatchConfigTomlParse:
    """Minimal TOML parse — no external dep, supports our specific schema."""

    def test_empty(self):
        config = WatchConfig.parse_toml("")
        assert config.repos == ()

    def test_single_repo_no_alias(self):
        toml = """
[[repos]]
path = "/tmp/proj-a"
"""
        config = WatchConfig.parse_toml(toml)
        assert len(config.repos) == 1
        repo = config.repos[0]
        # path is resolved — macOS turns /tmp into /private/tmp; just compare basename
        assert repo.path.name == "proj-a"
        assert repo.alias is None
        assert repo.display_name == "proj-a"  # falls back to dirname

    def test_single_repo_with_alias(self):
        toml = """
[[repos]]
path = "/tmp/anything"
alias = "my-proj"
"""
        config = WatchConfig.parse_toml(toml)
        assert config.repos[0].alias == "my-proj"
        assert config.repos[0].display_name == "my-proj"

    def test_multiple_repos(self):
        toml = """
[[repos]]
path = "/tmp/a"
alias = "alpha"

[[repos]]
path = "/tmp/b"

[[repos]]
path = "/tmp/c"
alias = "charlie"
"""
        config = WatchConfig.parse_toml(toml)
        assert len(config.repos) == 3
        assert config.repos[0].alias == "alpha"
        assert config.repos[1].alias is None
        assert config.repos[2].alias == "charlie"

    def test_comments_skipped(self):
        toml = """
# this is a comment
[[repos]]
# repo 1
path = "/tmp/proj-x"
alias = "x"
"""
        config = WatchConfig.parse_toml(toml)
        assert len(config.repos) == 1
        assert config.repos[0].alias == "x"

    def test_default_intervals(self):
        config = WatchConfig.parse_toml("")
        assert config.health_check_interval == 30.0
        assert config.config_reload_interval == 5.0


class TestSafeReadHash:
    """TOCTOU-safe read-hash: bytes read once, used for hash + downstream."""

    def test_basic(self, tmp_path: Path):
        f = tmp_path / "hello.txt"
        content = b"hello world"
        f.write_bytes(content)

        bytes_data, sha = safe_read_hash(f)

        assert bytes_data == content
        assert sha == hashlib.sha256(content).hexdigest()

    def test_empty_file(self, tmp_path: Path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")

        bytes_data, sha = safe_read_hash(f)

        assert bytes_data == b""
        assert sha == hashlib.sha256(b"").hexdigest()

    def test_binary_content(self, tmp_path: Path):
        f = tmp_path / "bin.dat"
        content = bytes(range(256))
        f.write_bytes(content)

        bytes_data, sha = safe_read_hash(f)

        assert bytes_data == content
        assert sha == hashlib.sha256(content).hexdigest()

    def test_returns_same_bytes_used_for_hash(self, tmp_path: Path):
        """Critical invariant: TOCTOU-safety.

        The bytes returned must be the *same* bytes that were hashed.
        Otherwise a caller could parse different bytes than what was hashed,
        defeating drift detection.
        """
        f = tmp_path / "race.txt"
        f.write_bytes(b"original")

        bytes_data, sha = safe_read_hash(f)

        # Even if the file changes after this call, our returned bytes_data
        # is what we hashed — guaranteed by `read_bytes` returning bytes once.
        f.write_bytes(b"modified")

        recomputed = hashlib.sha256(bytes_data).hexdigest()
        assert recomputed == sha
        # And our bytes_data is the *original*, not the modified
        assert bytes_data == b"original"


class TestRepoEntry:
    def test_alias_takes_precedence_over_path_name(self):
        repo = RepoEntry(path=Path("/some/long/path/project-x"), alias="px")
        assert repo.display_name == "px"

    def test_path_name_when_no_alias(self):
        repo = RepoEntry(path=Path("/some/long/path/project-x"))
        assert repo.display_name == "project-x"

    def test_frozen(self):
        repo = RepoEntry(path=Path("/tmp/x"))
        with pytest.raises(dc_frozen_error()):
            repo.alias = "new-alias"  # type: ignore[misc]


def dc_frozen_error():
    """Compat: dataclasses.FrozenInstanceError under different Python versions."""
    import dataclasses
    return dataclasses.FrozenInstanceError
