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


def _clear_status_env(monkeypatch):
    for name in (
        "BHGMAN_STATUS_NEO4J_URI",
        "BHGMAN_STATUS_NEO4J_USER",
        "BHGMAN_STATUS_NEO4J_PASSWORD",
        "BHGMAN_STATUS_K8S_NAMESPACE",
        "BHGMAN_STATUS_NEO4J_POD",
        "BHGMAN_K8S_NAMESPACE",
        "BHGMAN_NEO4J_POD",
        "NEO4J_URI",
        "NEO4J_USER",
        "NEO4J_PASSWORD",
        "SYMPOSIUM_KG_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)


def test_status_prefers_direct_cypher_shell(monkeypatch, capsys):
    _clear_status_env(monkeypatch)
    monkeypatch.setenv("BHGMAN_STATUS_NEO4J_URI", "bolt://example:7687")
    monkeypatch.setenv("BHGMAN_STATUS_NEO4J_PASSWORD", "pw")
    monkeypatch.setattr("engine.cli.commands.shutil.which", lambda name: f"/bin/{name}")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, stdout="label, count\n", stderr="")

    monkeypatch.setattr("engine.cli.commands.subprocess.run", fake_run)
    rc = cli(["status"])
    captured = capsys.readouterr()
    assert rc == 0
    assert calls[0][0][:3] == ["/bin/cypher-shell", "-a", "bolt://example:7687"]
    assert "-p" not in calls[0][0]  # W4: password not on argv (ps-visible)
    assert calls[0][1]["env"]["NEO4J_PASSWORD"] == "pw"  # passed via env instead
    assert "cypher-shell bolt://example:7687" in captured.err
    assert "label, count" in captured.out


def test_status_falls_back_to_dgx_data_namespace(monkeypatch, capsys):
    _clear_status_env(monkeypatch)
    monkeypatch.setenv("BHGMAN_STATUS_NEO4J_PASSWORD", "pw")
    monkeypatch.setattr("engine.cli.commands.shutil.which", lambda _name: None)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("engine.cli.commands.subprocess.run", fake_run)
    rc = cli(["status"])
    captured = capsys.readouterr()
    assert rc == 0
    assert calls[0][0][0] == "ssh"
    assert "kubectl exec -n data neo4j-0" in calls[0][0][2]
    assert "cypher-shell -u neo4j -p pw" in calls[0][0][2]
    assert "cypher-shell not found" in captured.err


def test_version_command_writes_to_stdout(capsys):
    rc = cli(["version"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "bhgman-tool" in captured.out
    assert "skills" in captured.out
    assert "engine" in captured.out


def test_version_degrades_gracefully_in_wheel_only_install(monkeypatch, capsys):
    """Wheel-only install has no skills/ → _repo_root raises; version must still
    print the version + a clean note and exit 0, not a RuntimeError traceback."""

    def _no_repo() -> object:
        raise RuntimeError("bhgman_tool repo root not found (wheel-only)")

    monkeypatch.setattr("engine.cli.commands._repo_root", _no_repo)
    rc = cli(["version"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "bhgman-tool" in captured.out  # version line still printed
    assert "wheel-only" in captured.out  # graceful note instead of traceback


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
    monkeypatch.setattr("engine.cli.commands._repo_root", lambda: fake_root)
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


def _patch_runners(monkeypatch, read_rows, write_rows=None):
    # write runner returns a matched supersession row by default so applied_count (now
    # derived from returned rows, W1-G) reflects a real archive. dry-run never calls it.
    read = _FakeRunner(read_rows)
    write = _FakeRunner(
        write_rows if write_rows is not None else [{"superseded": "old", "current": "new"}]
    )
    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", lambda: (read, write, lambda: None))
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


def test_acquire_web_injects_fetcher_and_ingests(monkeypatch, capsys):
    """W2-B: --web wires a real fetcher into the deterministic acquire pipeline so it
    actually fetches+ingests (was structurally dead — fetcher was always None)."""
    import engine.prometheus as prom
    from engine.prometheus import CallableFetcher
    from engine.prometheus.models import FetchedDoc

    read = _FakeRunner([{"id": "q1", "question": "Is X true", "kind": "OpenQuestion"}])
    write = _FakeRunner([{"findingId": "x"}])
    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", lambda: (read, write, lambda: None))
    fake = CallableFetcher(
        lambda _q: [
            FetchedDoc(
                "https://src/y",
                "The claim under study holds to high empirical precision across many trials.",
            )
        ]
    )
    monkeypatch.setattr(prom, "WebSearchFetcher", lambda *a, **k: fake)

    rc = cli(["acquire", "--web", "--apply"])
    assert rc == 0
    assert len(write.calls) >= 1  # ≥1 :ResearchFinding ingested (was always 0)


def test_acquire_apply_without_web_warns_no_fetcher(monkeypatch, capsys):
    """--apply with no fetcher ingests nothing → explicit warning, not a silent no-op."""
    read = _FakeRunner([{"id": "q1", "question": "q", "kind": "OpenQuestion"}])
    write = _FakeRunner()
    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", lambda: (read, write, lambda: None))
    rc = cli(["acquire", "--apply"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "--apply ignored: no fetcher wired" in err
    assert write.calls == []


def test_occam_degrades_when_no_neo4j(monkeypatch, capsys):
    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", lambda: None)
    rc = cli(["occam", "--scope", "engine/occam"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "neo4j unavailable" in err


def _patch_hash_fallback_embedder(monkeypatch):
    from engine.memory.embedder import Embedder

    monkeypatch.setattr(Embedder, "is_real_model", property(lambda self: False))


def test_occam_semantic_apply_refuses_hash_fallback(monkeypatch, capsys):
    """W1-B: superseding on the meaningless hash-fallback embedder would archive nodes at
    random — `--apply` must refuse (non-zero, no write) when the real model is absent."""
    _patch_hash_fallback_embedder(monkeypatch)
    read, write = _FakeRunner([]), _FakeRunner()
    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", lambda: (read, write, lambda: None))
    rc = cli(["occam", "--semantic", "--apply"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "REFUSING --apply" in err
    assert write.calls == []  # nothing archived


def test_occam_semantic_allow_hash_embed_overrides(monkeypatch, capsys):
    """--allow-hash-embed is the explicit opt-in override (no refusal)."""
    _patch_hash_fallback_embedder(monkeypatch)
    read, write = _FakeRunner([]), _FakeRunner()
    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", lambda: (read, write, lambda: None))
    rc = cli(["occam", "--semantic", "--apply", "--allow-hash-embed"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "REFUSING --apply" not in err


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
    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", lambda: (read, write, lambda: None))
    rc = cli(["hades"])
    out = capsys.readouterr().out
    assert rc == 0
    assert write.calls == []  # dry-run never materializes
    assert "DRY-RUN" in out


def test_hades_apply_materializes(monkeypatch, capsys):
    read, write = _FakeRunner(_ACCEPTED_ROWS), _FakeRunner()
    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", lambda: (read, write, lambda: None))
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
    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", lambda: None)
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
    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", lambda: (read, read, lambda: None))
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


def test_legion_run_positional_is_optional_and_equivalent():
    """`legion` and `legion run` both parse; the ergonomic 'run' verb defaults in."""
    p = build_parser()
    assert p.parse_args(["legion"]).verb == "run"
    assert p.parse_args(["legion", "run"]).verb == "run"


def test_make_kg_runners_accepts_neo4j_username_env(monkeypatch):
    """make_kg_runners reads NEO4J_USERNAME (mcp/.mcp.json convention), not only NEO4J_USER."""
    import types

    from engine.cli import runtime

    monkeypatch.delenv("BHGMAN_KG_MCP_URL", raising=False)
    monkeypatch.setenv("NEO4J_PASSWORD", "pw")
    monkeypatch.setenv("NEO4J_USERNAME", "alice")
    monkeypatch.delenv("NEO4J_USER", raising=False)
    captured: dict = {}

    class _FakeDriver:
        @staticmethod
        def driver(uri, auth=None):
            captured["uri"] = uri
            captured["auth"] = auth
            return types.SimpleNamespace(session=lambda: None, close=lambda: None)

    monkeypatch.setattr("neo4j.GraphDatabase", _FakeDriver)
    runners = runtime.make_kg_runners()
    assert runners is not None
    assert captured["auth"] == ("alice", "pw")  # NEO4J_USERNAME won over the default
