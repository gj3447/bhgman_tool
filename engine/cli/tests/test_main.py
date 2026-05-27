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


# ─── occam verb (KG dedup engine) ──────────────────────────────────────────
# KG: occam-kam-canonical-2026-05-26, occam-pass-kg-wide-2026-05-27


def test_parser_has_occam_subcommand():
    parser = build_parser()
    actions = [a for a in parser._actions if a.dest == "cmd"]
    choices = set(actions[0].choices.keys())
    assert "occam" in choices


def test_occam_parser_defaults_dry_run():
    args = build_parser().parse_args(["occam"])
    assert args.apply is False  # covenant: dry-run default
    assert args.scope is None


class _FakeRunner:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def __call__(self, cypher, params):
        self.calls.append((cypher, params))
        return self.rows


_DUP_ROWS = [
    {"name": "old", "source_path": "bhgman_tool/x.py", "sha256": "o", "line_count": 10},
    {"name": "new", "source_path": "bhgman_tool/x.py", "sha256": "n", "line_count": 99},
]


def _patch_runners(monkeypatch, read_rows):
    read, write = _FakeRunner(read_rows), _FakeRunner()
    monkeypatch.setattr("engine.cli.main.make_kg_runners", lambda: (read, write, lambda: None))
    return read, write


def test_occam_dry_run_default_does_not_write(monkeypatch, capsys):
    _read, write = _patch_runners(monkeypatch, _DUP_ROWS)
    rc = cli(["occam"])
    out = capsys.readouterr().out
    assert rc == 0
    assert write.calls == []  # covenant: dry-run never writes
    assert "DRY-RUN" in out
    assert "supersede old → new" in out


def test_occam_apply_writes_supersession(monkeypatch, capsys):
    _read, write = _patch_runners(monkeypatch, _DUP_ROWS)
    rc = cli(["occam", "--apply"])
    out = capsys.readouterr().out
    assert rc == 0
    assert len(write.calls) == 1  # one supersession written
    assert "APPLIED 1" in out


def test_occam_degrades_when_no_neo4j(monkeypatch, capsys):
    monkeypatch.setattr("engine.cli.main.make_kg_runners", lambda: None)
    rc = cli(["occam", "--scope", "engine/occam"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "neo4j unavailable" in err
