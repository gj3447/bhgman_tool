"""Forward binding materializer — the missing creation step.

The audit (audit_runner) only *detects* reverse orphans (code symbols with no
`# KG:` comment); it never *creates* the ReferenceSite that a `# KG:` comment
implies. This module closes that gap: it scans the code-root, and for every
``# KG: <node>`` comment MERGEs a ReferenceSite bound to the cited KG node
(BINDS_TO / REALIZED_BY) — so commander concept nodes stop floating.

Granularity = **module + public API** (user verdict 2026-06-01):
  - module-level `# KG:` refs (comment not attached to any symbol) → bound (module)
  - public function/class symbols (name not starting with ``_``) with refs → bound
  - private helpers (name starts ``_``) → skipped

Node-centric: one ReferenceSite per *distinct* cited node (sourceId = node name,
first citation wins as representative), so signature_baseline / drift_detector —
which key by ``sourceId`` == ref name — match, and the shared KG is not flooded
with a site per (node × file). A cited node that does not exist is reported as an
orphan `# KG:` comment and skipped (never auto-created).

# KG: lesson-concept-nodes-created-without-longinus-binding-float-2026-05-29
# KG: project_eureka_word_creation_search_compression_2026_05_30
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from engine.longinus_drift_audit import code_scanner
from engine.longinus_drift_audit.kg_client import KgClient
from engine.longinus_drift_audit.models import ReferenceLayer, ReferenceSite


@dataclass
class MaterializeResult:
    # KG: ATOM_Skill_longinus
    bound: int = 0
    modules: int = 0
    public_api: int = 0
    skipped_private: int = 0
    orphan_refs: list[tuple[str, str]] = field(default_factory=list)  # (ref, where)


def _file_sha256(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    line_count = data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1)
    return hashlib.sha256(data).hexdigest(), max(line_count, 1)


def _path_of(source_path: str) -> Path:
    """Strip the ``:line`` suffix from a ``file:line`` sourcePath."""
    return Path(source_path.rsplit(":", 1)[0])


def _file_citations(fp: Path) -> tuple[list[tuple[str, str, str | None, str]], int]:
    """One file → ([(ref, sourcePath, signature, kind), ...], skipped_private).

    Public function/class symbols and module-level comments are emitted; private
    helpers (name starts ``_``) are counted but not emitted (granularity filter).
    """
    out: list[tuple[str, str, str | None, str]] = []
    skipped_private = 0
    symbol_refs: set[str] = set()
    for s in code_scanner.scan_python_symbols(fp):
        is_private = s.name.startswith("_")
        for ref in s.kg_refs:
            symbol_refs.add(ref)
            if is_private:
                skipped_private += 1
            else:
                out.append((ref, s.sourcePath, s.signature, "public_api"))
    rel = str(fp)
    for line_no, refs in code_scanner.scan_kg_refs(fp):
        for ref in refs:
            if ref not in symbol_refs:  # module-level (not attached to any symbol)
                out.append((ref, f"{rel}:{line_no}", None, "module"))
    return out, skipped_private


def collect_candidates(code_root: Path) -> tuple[dict[str, tuple[str, str | None, str]], int]:
    # KG: ATOM_Skill_longinus
    """ref → (sourcePath, signature, kind) for module + public-API citations.

    First citation of a ref wins (node-centric). Returns (candidates, skipped_private).
    """
    candidates: dict[str, tuple[str, str | None, str]] = {}
    skipped_private = 0
    for fp in code_scanner.iter_files(code_root):
        if any(part in {"tests", "bench"} for part in fp.parts):
            continue  # tests are not domain bindings
        citations, skipped = _file_citations(fp)
        skipped_private += skipped
        for ref, source_path, signature, kind in citations:
            candidates.setdefault(ref, (source_path, signature, kind))
    return candidates, skipped_private


def materialize(kg: KgClient, code_root: Path, *, repo_tag: str = "bhgman") -> MaterializeResult:
    # KG: ATOM_Skill_longinus
    """Scan code-root and MERGE a bound ReferenceSite per module/public-API `# KG:` ref."""
    code_root = Path(code_root).resolve()
    candidates, skipped_private = collect_candidates(code_root)
    result = MaterializeResult(skipped_private=skipped_private)
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    for ref, (source_path, signature, kind) in candidates.items():
        if not kg.has_node(ref):
            result.orphan_refs.append((ref, source_path))
            continue
        fpath = _path_of(source_path)
        if not fpath.is_file():
            result.orphan_refs.append((ref, f"{source_path} (file missing)"))
            continue
        sha, line_count = _file_sha256(fpath)
        site = ReferenceSite(
            sourceId=ref,
            sourcePath=source_path,
            sha256=sha,
            sha256_baseline=sha,
            kg_anchor=ref,
            layer=ReferenceLayer.L4_SEMIOTIC,
            repo_tag=repo_tag,
            signature_baseline=signature,
            last_validated=now,
        )
        if kg.merge_forward_binding(site, line_count=line_count):
            result.bound += 1
            if kind == "module":
                result.modules += 1
            else:
                result.public_api += 1
        else:
            result.orphan_refs.append((ref, source_path))
    return result


__all__ = ["materialize", "collect_candidates", "MaterializeResult"]
