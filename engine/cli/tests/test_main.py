"""Tests for engine.cli.main — covers install-skills, verify, version, daemon delegation.

KG: SPAN_bhgman_tool_phase3_CLI (Phase 3 L1 branch A)
"""

from __future__ import annotations

import subprocess
import sys


from engine.cli.main import _repo_root, build_parser, cli


def test_repo_root_resolves():
    root = _repo_root()
    assert (root / "skills").is_dir()
    assert (root / "pyproject.toml").is_file()


def test_parser_has_native_subcommands():
    """Cohort A (native): install-skills / verify / version / daemon must remain."""
    parser = build_parser()
    actions = [a for a in parser._actions if a.dest == "cmd"]
    assert actions, "subparsers action missing"
    choices = set(actions[0].choices.keys())
    native = {"daemon", "install-skills", "verify", "version"}
    assert native.issubset(choices), f"native cohort missing: {native - choices}"


def test_parser_has_symposium_absorbed_subcommands():
    """Cohort B (Wave 7 P2-A absorbed): apt/tpa/prom/tlb/longinus/harness/status."""
    parser = build_parser()
    actions = [a for a in parser._actions if a.dest == "cmd"]
    choices = set(actions[0].choices.keys())
    symposium = {"apt", "tpa", "prom", "tlb", "longinus", "harness", "status"}
    assert symposium.issubset(choices), f"symposium cohort missing: {symposium - choices}"


def test_version_command_writes_to_stdout(capsys):
    rc = cli(["version"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "bhgman-tool" in captured.out
    assert "skills" in captured.out
    assert "engine" in captured.out


def test_install_skills_dry_run(tmp_path, capsys):
    target = tmp_path / "fake-claude-skills"
    rc = cli(["install-skills", "--target", str(target), "--dry-run"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "dry-run" in captured.out
    assert not target.exists(), "dry-run must not create the target dir"


def test_install_skills_writes_files(tmp_path, capsys):
    target = tmp_path / "claude-skills"
    rc = cli(["install-skills", "--target", str(target)])
    captured = capsys.readouterr()
    assert rc == 0
    assert target.is_dir()
    installed = sorted(p.name for p in target.iterdir() if p.is_dir())
    assert installed, "at least one skill dir must be installed"
    assert "INSTALL" in captured.out


def test_install_skills_skip_existing_without_force(tmp_path, capsys):
    target = tmp_path / "claude-skills"
    cli(["install-skills", "--target", str(target)])
    capsys.readouterr()  # discard first run output
    rc = cli(["install-skills", "--target", str(target)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "SKIP" in captured.out


def test_install_skills_force_overwrites(tmp_path, capsys):
    target = tmp_path / "claude-skills"
    cli(["install-skills", "--target", str(target)])
    capsys.readouterr()
    rc = cli(["install-skills", "--target", str(target), "--force"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "OVERWRITE" in captured.out


def test_install_skills_fails_when_source_missing(tmp_path, monkeypatch, capsys):
    fake_root = tmp_path / "not-a-real-repo"
    fake_root.mkdir()
    (fake_root / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    # skills dir intentionally absent
    monkeypatch.setattr("engine.cli.main._repo_root", lambda: fake_root)
    rc = cli(["install-skills", "--target", str(tmp_path / "target")])
    captured = capsys.readouterr()
    assert rc == 2
    assert "FAIL" in captured.err


def test_cli_console_script_callable_via_python_m():
    """The module must be runnable as `python -m engine.cli.main version`."""
    root = _repo_root()
    rc = subprocess.call(
        [sys.executable, "-m", "engine.cli.main", "version"],
        cwd=root,
    )
    assert rc == 0
