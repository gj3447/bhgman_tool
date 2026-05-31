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


# ─── hades verb (materialize ACCEPTED abstractions) ─────────────────────────
# KG: hades-canonical-2026-05-27


def test_parser_has_hades_subcommand():
    choices = set([a for a in build_parser()._actions if a.dest == "cmd"][0].choices.keys())
    assert "hades" in choices


def test_hades_parser_defaults_dry_run():
    args = build_parser().parse_args(["hades"])
    assert args.apply is False  # c6 danger: dry-run default
    assert args.concept is None


_ACCEPTED_ROWS = [
    {"concept": "ac_x", "verdict": "ACCEPTED", "members": ["a", "b", "c"]},
]


def test_hades_dry_run_default_does_not_write(monkeypatch, capsys):
    read, write = _FakeRunner(_ACCEPTED_ROWS), _FakeRunner()
    monkeypatch.setattr("engine.cli.main.make_kg_runners", lambda: (read, write, lambda: None))
    rc = cli(["hades"])
    out = capsys.readouterr().out
    assert rc == 0
    assert write.calls == []  # dry-run never materializes
    assert "DRY-RUN" in out


def test_hades_apply_materializes(monkeypatch, capsys):
    read, write = _FakeRunner(_ACCEPTED_ROWS), _FakeRunner()
    monkeypatch.setattr("engine.cli.main.make_kg_runners", lambda: (read, write, lambda: None))
    rc = cli(["hades", "--apply"])
    out = capsys.readouterr().out
    assert rc == 0
    assert len(write.calls) >= 1
    assert "APPLIED" in out


# ─── eureka verb (induce abstractions, PROPOSE only) ────────────────────────
# KG: eureka-canonical-2026-05-26


def test_parser_has_eureka_subcommand():
    choices = set([a for a in build_parser()._actions if a.dest == "cmd"][0].choices.keys())
    assert "eureka" in choices


def test_eureka_degrades_when_no_neo4j(monkeypatch, capsys):
    monkeypatch.setattr("engine.cli.main.make_kg_runners", lambda: None)
    rc = cli(["eureka"])
    assert rc == 2
    assert "neo4j unavailable" in capsys.readouterr().err


_EUREKA_ROWS = [
    {"object": o, "attributes": ["ALIGNS_WITH_AXIS:Math", "USES_ABSTRACT_DOMAIN:Algebra"]}
    for o in ("Topology", "Group Theory", "Abstract Algebra", "Spectral Sequences")
]


def test_eureka_runs_pipeline_even_after_occam_oracle_lens_cached(monkeypatch, capsys):
    """oracle_lens 충돌 회귀 가드: occam oracle_lens가 먼저 캐시돼도 eureka가 동작."""
    import sys as _sys
    from pathlib import Path

    # occam oracle_lens를 먼저 sys.modules에 캐시 (충돌 조건 재현)
    _sys.path.insert(0, str(Path(_repo_root()) / "engine" / "occam"))
    import oracle_lens as _occ  # noqa: F401  # occam's — lacks kg_oracle_gate

    read = _FakeRunner(_EUREKA_ROWS)
    monkeypatch.setattr("engine.cli.main.make_kg_runners", lambda: (read, read, lambda: None))
    rc = cli(["eureka"])  # _load_engine_module이 oracle_lens를 evict해야 동작
    out = capsys.readouterr().out
    assert rc == 0
    assert "PROPOSE only" in out
    assert "kg-extract" in out.lower() or "induce" in out.lower()


def test_hades_extract_superclass_finds_duplicate(tmp_path, capsys):
    """hades --extract-superclass scans code (no neo4j) and reports a real candidate."""
    (tmp_path / "dup.py").write_text(
        "class Dog:\n    def speak(self):\n        return 'woof'\n    def legs(self):\n        return 4\n"
        "class Cat:\n    def speak(self):\n        return 'woof'\n    def meow(self):\n        return 'm'\n",
        encoding="utf-8",
    )
    rc = cli(["hades", "--extract-superclass", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "1 candidate" in out
    assert "Dog" in out and "Cat" in out and "speak" in out  # pair printed sorted (Cat ~ Dog)
    assert "PLAN only" in out  # covenant: dry-run, no in-place rewrite


def test_hades_extract_superclass_none_when_no_dup(tmp_path, capsys):
    (tmp_path / "x.py").write_text(
        "class A:\n    def f(self): return 1\nclass B:\n    def g(self): return 2\n",
        encoding="utf-8",
    )
    rc = cli(["hades", "--extract-superclass", str(tmp_path)])
    assert rc == 0
    assert "0 candidate" in capsys.readouterr().out


def test_hades_extract_superclass_missing_path(capsys):
    rc = cli(["hades", "--extract-superclass", "/no/such/path/zzz"])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_hades_apply_gate_pass_applies(tmp_path, capsys):
    """hades --extract-superclass FILE --apply: keep refactor when test-cmd passes."""
    f = tmp_path / "m.py"
    f.write_text(
        "class Dog:\n    def speak(self):\n        return 'woof'\n    def legs(self):\n        return 4\n"
        "class Cat:\n    def speak(self):\n        return 'woof'\n    def meow(self):\n        return 'm'\n",
        encoding="utf-8",
    )
    check = (
        f'{sys.executable} -c "import sys; sys.path.insert(0,{str(tmp_path)!r}); '
        "import m; assert m.Dog().speak()=='woof'\""
    )
    rc = cli(["hades", "--extract-superclass", str(f), "--apply", "--test-cmd", check])
    out = capsys.readouterr().out
    assert rc == 0 and "APPLIED" in out
    assert "Base" in f.read_text(encoding="utf-8")  # base class inserted, file changed


def test_hades_apply_gate_fail_reverts(tmp_path, capsys):
    f = tmp_path / "m.py"
    original = (
        "class Dog:\n    def speak(self):\n        return 'woof'\n"
        "class Cat:\n    def speak(self):\n        return 'woof'\n"
    )
    f.write_text(original, encoding="utf-8")
    rc = cli(
        [
            "hades",
            "--extract-superclass",
            str(f),
            "--apply",
            "--test-cmd",
            f'{sys.executable} -c "import sys; sys.exit(1)"',
        ]
    )
    out = capsys.readouterr().out
    assert rc == 1 and "REVERTED" in out
    assert f.read_text(encoding="utf-8") == original  # reverted byte-for-byte


def test_hades_apply_requires_test_cmd(tmp_path, capsys):
    f = tmp_path / "m.py"
    f.write_text("class A:\n    def f(self): return 1\n", encoding="utf-8")
    rc = cli(["hades", "--extract-superclass", str(f), "--apply"])
    assert rc == 2
    assert "test-cmd" in capsys.readouterr().err
