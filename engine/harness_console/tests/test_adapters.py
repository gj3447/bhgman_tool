from __future__ import annotations

from engine.harness_console.adapters import NodeViteAdapter, PythonRepoAdapter, select_adapter
from engine.harness_console.models import ArchitectureRole, ProjectKind, ProjectTarget


def test_python_repo_adapter_detects_roles(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    engine_dir = tmp_path / "engine"
    engine_dir.mkdir()
    (engine_dir / "__init__.py").write_text("")
    (engine_dir / "commander_engine.py").write_text("class CommanderEngine: ...\n")
    (engine_dir / "foo_adapter.py").write_text("")
    tests_dir = engine_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_foo.py").write_text("")

    target = ProjectTarget(id="p", root_path=str(tmp_path), kind=ProjectKind.PYTHON_REPO)
    adapter = PythonRepoAdapter()
    graph = adapter.architecture(adapter.snapshot(target))

    roles = {node.path: node.role for node in graph.nodes}
    assert roles["engine/commander_engine.py"] is ArchitectureRole.ENGINE
    assert roles["engine/foo_adapter.py"] is ArchitectureRole.ADAPTER
    assert roles["engine/tests/test_foo.py"] is ArchitectureRole.TEST
    assert any(edge.relation == "CONTAINS" for edge in graph.edges)


def test_node_vite_adapter_detects_entrypoint_and_ui(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"dependencies": {}, "devDependencies": {"vite": "^5.0.0"}}'
    )
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.ts").write_text("console.log('x')\n")
    (src / "App.tsx").write_text("export function App() { return null }\n")

    target = ProjectTarget(id="web", root_path=str(tmp_path))
    adapter = select_adapter(target, [NodeViteAdapter()])
    graph = adapter.architecture(adapter.snapshot(target))

    roles = {node.path: node.role for node in graph.nodes}
    assert roles["src/main.ts"] is ArchitectureRole.ENTRYPOINT
    assert roles["src/App.tsx"] is ArchitectureRole.UI


def test_select_adapter_rejects_unknown_project(tmp_path):
    target = ProjectTarget(id="unknown", root_path=str(tmp_path))

    try:
        select_adapter(target, [PythonRepoAdapter(), NodeViteAdapter()])
    except ValueError as exc:
        assert "no project adapter" in str(exc)
    else:
        raise AssertionError("expected ValueError")
