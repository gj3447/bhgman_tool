"""Project adapters for Harness Console architecture analysis.

Adapters produce domain DTOs only. They do not write KG, call FastAPI, or decide
human verdicts.

# KG: task-harness-console-project-adapters-2026-06-24
# KG: task-harness-console-architecture-graph-2026-06-24
# KG: plan-harness-console-live-verdict-2026-06-24
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from engine.harness_console.models import (
    ArchitectureEdge,
    ArchitectureGraph,
    ArchitectureNode,
    ArchitectureRole,
    ProjectKind,
    ProjectSnapshot,
    ProjectTarget,
    utc_now,
)


class ProjectAdapter(Protocol):
    name: str

    def supports(self, target: ProjectTarget) -> bool: ...

    def snapshot(self, target: ProjectTarget) -> ProjectSnapshot: ...

    def architecture(self, snapshot: ProjectSnapshot) -> ArchitectureGraph: ...


class PythonRepoAdapter:
    name = "python_repo"

    def supports(self, target: ProjectTarget) -> bool:
        root = Path(target.root_path)
        return target.kind is ProjectKind.PYTHON_REPO or (root / "pyproject.toml").exists()

    def snapshot(self, target: ProjectTarget) -> ProjectSnapshot:
        root = Path(target.root_path)
        py_files = sorted(p for p in root.rglob("*.py") if _is_project_file(p))
        return ProjectSnapshot(
            id=f"{target.id}:snapshot:{self.name}",
            target_id=target.id,
            root_path=str(root),
            adapter=self.name,
            summary={"python_files": len(py_files)},
            created_at=utc_now(),
        )

    def architecture(self, snapshot: ProjectSnapshot) -> ArchitectureGraph:
        root = Path(snapshot.root_path)
        nodes: list[ArchitectureNode] = []
        edges: list[ArchitectureEdge] = []
        for path in sorted(p for p in root.rglob("*.py") if _is_project_file(p)):
            rel = path.relative_to(root).as_posix()
            role = _python_role(rel)
            node_id = f"file:{rel}"
            nodes.append(
                ArchitectureNode(
                    id=node_id,
                    label=path.name,
                    path=rel,
                    role=role,
                    metadata={"suffix": path.suffix},
                )
            )
            parent = _parent_module_node(rel)
            if parent is not None:
                edges.append(ArchitectureEdge(source=parent, target=node_id, relation="CONTAINS"))
        return ArchitectureGraph(
            project_id=snapshot.target_id,
            adapter=self.name,
            nodes=nodes,
            edges=[edge for edge in edges if any(node.id == edge.source for node in nodes)],
            warnings=[],
        )


class NodeViteAdapter:
    name = "node_vite"

    def supports(self, target: ProjectTarget) -> bool:
        root = Path(target.root_path)
        if target.kind is ProjectKind.NODE_VITE:
            return True
        package_json = root / "package.json"
        if not package_json.exists():
            return False
        try:
            data = json.loads(package_json.read_text())
        except json.JSONDecodeError:
            return False
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        return "vite" in deps

    def snapshot(self, target: ProjectTarget) -> ProjectSnapshot:
        root = Path(target.root_path)
        source_files = sorted(
            p for p in root.rglob("*") if p.suffix in {".ts", ".tsx", ".js", ".jsx"}
        )
        return ProjectSnapshot(
            id=f"{target.id}:snapshot:{self.name}",
            target_id=target.id,
            root_path=str(root),
            adapter=self.name,
            summary={"source_files": len(source_files)},
            created_at=utc_now(),
        )

    def architecture(self, snapshot: ProjectSnapshot) -> ArchitectureGraph:
        root = Path(snapshot.root_path)
        nodes: list[ArchitectureNode] = []
        warnings: list[str] = []
        for path in sorted(
            p for p in root.rglob("*") if p.suffix in {".ts", ".tsx", ".js", ".jsx", ".json"}
        ):
            if "node_modules" in path.parts:
                continue
            rel = path.relative_to(root).as_posix()
            nodes.append(
                ArchitectureNode(
                    id=f"file:{rel}",
                    label=path.name,
                    path=rel,
                    role=_node_role(rel),
                    metadata={"suffix": path.suffix},
                )
            )
        if not (root / "src").exists():
            warnings.append("src directory not found")
        return ArchitectureGraph(
            project_id=snapshot.target_id,
            adapter=self.name,
            nodes=nodes,
            edges=[],
            warnings=warnings,
        )


class ThreeDProjectAdapter:
    name = "three_d"

    def supports(self, target: ProjectTarget) -> bool:
        root = Path(target.root_path)
        if target.kind is ProjectKind.THREE_D:
            return True
        return any(
            p.suffix.lower() in {".glb", ".gltf", ".obj", ".fbx", ".vert", ".frag", ".glsl"}
            for p in root.rglob("*")
            if _is_project_file(p)
        )

    def snapshot(self, target: ProjectTarget) -> ProjectSnapshot:
        root = Path(target.root_path)
        assets = sorted(
            p
            for p in root.rglob("*")
            if _is_project_file(p)
            and p.suffix.lower() in {".glb", ".gltf", ".obj", ".fbx", ".vert", ".frag", ".glsl"}
        )
        return ProjectSnapshot(
            id=f"{target.id}:snapshot:{self.name}",
            target_id=target.id,
            root_path=str(root),
            adapter=self.name,
            summary={"three_d_assets": len(assets)},
            created_at=utc_now(),
        )

    def architecture(self, snapshot: ProjectSnapshot) -> ArchitectureGraph:
        root = Path(snapshot.root_path)
        nodes: list[ArchitectureNode] = []
        for path in sorted(p for p in root.rglob("*") if p.is_file() and _is_project_file(p)):
            rel = path.relative_to(root).as_posix()
            role = _three_d_role(rel)
            if role is ArchitectureRole.UNKNOWN:
                continue
            nodes.append(
                ArchitectureNode(
                    id=f"file:{rel}",
                    label=path.name,
                    path=rel,
                    role=role,
                    metadata={"suffix": path.suffix.lower()},
                )
            )
        return ArchitectureGraph(
            project_id=snapshot.target_id,
            adapter=self.name,
            nodes=nodes,
            edges=[],
            warnings=[],
        )


class BeadProjectAdapter:
    name = "bead"

    def supports(self, target: ProjectTarget) -> bool:
        return target.kind is ProjectKind.BEAD

    def snapshot(self, target: ProjectTarget) -> ProjectSnapshot:
        root = Path(target.root_path)
        files = sorted(p for p in root.rglob("*") if p.is_file() and _is_project_file(p))
        return ProjectSnapshot(
            id=f"{target.id}:snapshot:{self.name}",
            target_id=target.id,
            root_path=str(root),
            adapter=self.name,
            summary={"files": len(files), "schema_status": "reserved_extension_slot"},
            created_at=utc_now(),
        )

    def architecture(self, snapshot: ProjectSnapshot) -> ArchitectureGraph:
        return ArchitectureGraph(
            project_id=snapshot.target_id,
            adapter=self.name,
            nodes=[],
            edges=[],
            warnings=["bead project schema is reserved; no canonical bead corpus was provided"],
        )


class GenericFileAdapter:
    name = "generic_files"

    def supports(self, target: ProjectTarget) -> bool:
        return target.kind is ProjectKind.GENERIC_FILES or Path(target.root_path).exists()

    def snapshot(self, target: ProjectTarget) -> ProjectSnapshot:
        root = Path(target.root_path)
        files = sorted(p for p in root.rglob("*") if p.is_file() and _is_project_file(p))
        return ProjectSnapshot(
            id=f"{target.id}:snapshot:{self.name}",
            target_id=target.id,
            root_path=str(root),
            adapter=self.name,
            summary={"files": len(files)},
            created_at=utc_now(),
        )

    def architecture(self, snapshot: ProjectSnapshot) -> ArchitectureGraph:
        root = Path(snapshot.root_path)
        nodes: list[ArchitectureNode] = []
        for path in sorted(p for p in root.rglob("*") if p.is_file() and _is_project_file(p)):
            rel = path.relative_to(root).as_posix()
            role = _generic_role(rel)
            nodes.append(
                ArchitectureNode(
                    id=f"file:{rel}",
                    label=path.name,
                    path=rel,
                    role=role,
                    metadata={"suffix": path.suffix.lower()},
                )
            )
        return ArchitectureGraph(
            project_id=snapshot.target_id,
            adapter=self.name,
            nodes=nodes,
            edges=[],
            warnings=["generic adapter preserves files but cannot infer full architecture"],
        )


def select_adapter(
    target: ProjectTarget, adapters: list[ProjectAdapter] | None = None
) -> ProjectAdapter:
    candidates = adapters or [
        PythonRepoAdapter(),
        NodeViteAdapter(),
        ThreeDProjectAdapter(),
        BeadProjectAdapter(),
        GenericFileAdapter(),
    ]
    for adapter in candidates:
        if adapter.supports(target):
            return adapter
    raise ValueError(f"no project adapter supports {target.root_path}")


def _is_project_file(path: Path) -> bool:
    return not any(part in {".git", ".venv", "__pycache__", ".pytest_cache"} for part in path.parts)


def _python_role(rel: str) -> ArchitectureRole:
    parts = rel.split("/")
    name = parts[-1]
    stem = name.removesuffix(".py")
    if name in {"main.py", "__main__.py"} or "/cli/" in f"/{rel}":
        return ArchitectureRole.ENTRYPOINT
    if stem.endswith("_engine") or stem == "commander_engine":
        return ArchitectureRole.ENGINE
    if "mcp_server" in parts or "server" in stem:
        return ArchitectureRole.TRANSPORT
    if stem.endswith("_adapter") or "adapter" in stem:
        return ArchitectureRole.ADAPTER
    if stem in {"models", "occam_models", "schemas"} or stem.endswith("_models"):
        return ArchitectureRole.DTO
    if "store" in stem or "kg" in stem:
        return ArchitectureRole.STORAGE
    if "test" in stem or "tests" in parts:
        return ArchitectureRole.TEST
    return ArchitectureRole.UNKNOWN


def _node_role(rel: str) -> ArchitectureRole:
    name = rel.rsplit("/", 1)[-1]
    if name in {"main.ts", "main.tsx", "index.ts", "index.tsx"}:
        return ArchitectureRole.ENTRYPOINT
    if name.endswith((".tsx", ".jsx")):
        return ArchitectureRole.UI
    if name == "package.json":
        return ArchitectureRole.DTO
    return ArchitectureRole.UNKNOWN


def _three_d_role(rel: str) -> ArchitectureRole:
    suffix = Path(rel).suffix.lower()
    if suffix in {".vert", ".frag", ".glsl"}:
        return ArchitectureRole.SHADER
    if suffix in {".glb", ".gltf", ".obj", ".fbx"}:
        return ArchitectureRole.ASSET
    name = rel.rsplit("/", 1)[-1].lower()
    if "scene" in name:
        return ArchitectureRole.SCENE
    return ArchitectureRole.UNKNOWN


def _generic_role(rel: str) -> ArchitectureRole:
    suffix = Path(rel).suffix.lower()
    name = rel.rsplit("/", 1)[-1].lower()
    if suffix in {".md", ".rst", ".txt", ".adoc"}:
        return ArchitectureRole.DOC
    if name in {"package.json", "pyproject.toml", "uv.lock"}:
        return ArchitectureRole.DTO
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".glb", ".gltf"}:
        return ArchitectureRole.ASSET
    return ArchitectureRole.UNKNOWN


def _parent_module_node(rel: str) -> str | None:
    parent = Path(rel).parent
    if parent == Path("."):
        return None
    init = parent / "__init__.py"
    return f"file:{init.as_posix()}"


__all__ = [
    "BeadProjectAdapter",
    "GenericFileAdapter",
    "NodeViteAdapter",
    "ProjectAdapter",
    "PythonRepoAdapter",
    "ThreeDProjectAdapter",
    "select_adapter",
]
