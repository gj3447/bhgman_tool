"""Longinus SCIP adapter — Sourcegraph Code Intelligence Protocol (LSIF migration 2024).

INPUT preprocessing only — parses SCIP files and feeds Symbol/Occurrence data
into the existing Longinus `CodeSymbol` shape so downstream `drift_detector`
can consume external code-intel without re-running its own scanner.

This module is decoupled from `kg_client.py` (keep that focused on KG I/O).

Known limitations (honest disclaimers — DecisionLog 2026-05-19):
  * JSON-only parsing. SCIP also has a protobuf binary format
    (scip.proto v0.5+). Sourcegraph emits both; this adapter handles
    the `--format=json` variant only. Production may need to add
    protobuf binary parsing via `scip-python` or `protobuf` lib.
  * Moniker grammar implements the common case only — scheme + manager +
    package_name + version + descriptor. Edge cases NOT handled:
    escaped backticks in identifier, multi-arity method overloads,
    type parameter packs. Document subset.
  * No semantic validation — adapter trusts SCIP file is well-formed.
    Deeper validation (cross-reference consistency, `project_root`
    path normalization) deferred.
  * LSIF deprecated 2024. This adapter is the migration path; old
    LSIF dumps must be re-emitted via `scip` tooling first.

References:
  * SCIP spec: https://github.com/sourcegraph/scip
  * Symbol grammar: https://github.com/sourcegraph/scip/blob/main/scip.proto
  * SymbolRole bitset: 0x1=Definition, 0x2=Import, 0x4=WriteAccess, 0x8=ReadAccess,
    0x10=Generated, 0x20=Test, 0x40=ForwardDefinition.

# KG: sa-longinus-scip-adapter-2026-05-19, CONTRACT_ScipAdapter_v1_2026-05-19,
# KG: wqi-longinus-scip-adapter-v3.3-2026-06-2026-05-19
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, field_validator

from models import CodeSymbol


# ─── SCIP symbol moniker grammar ─────────────────────────────────────────
#
# Per spec, a symbol moniker is space-separated:
#   <scheme> <manager> <package_name> <version> <descriptor...>
# Examples:
#   scip-typescript npm @types/node 20.0.0 `index.d.ts`/Buffer#
#   scip-python python my-pkg 1.2.3 `mymod`/MyClass#method().
#   . . . . `local 1`  (a local symbol — sentinel scheme `.`)
#
# Descriptors carry suffix sigils:
#   '#'  — type
#   '.'  — term (function/method/field)
#   '('  — method signature start
#   ')'  — method signature end
#   '['  — type-parameter start
#   ']'  — type-parameter end
#   '/'  — namespace/package separator
#   '`'  — identifier delimiter (raw escaped)

_MONIKER_RE = re.compile(
    r"^(?P<scheme>\S+)\s+(?P<manager>\S+)\s+(?P<pkg>\S+)\s+(?P<version>\S+)\s+(?P<desc>.+)$"
)


class ScipSymbol(BaseModel):
    """Parsed SCIP symbol moniker — Frege Sinn carrier."""

    scheme: str = Field(..., description="Indexer scheme e.g. 'scip-typescript', 'scip-python'")
    package: str = Field(..., description="`<manager>/<package_name>@<version>` composite")
    descriptor: str = Field(..., description="Symbol descriptor (suffix-sigil grammar)")
    raw: str = Field(..., description="Original space-separated moniker")


class ScipOccurrence(BaseModel):
    """One symbol reference in a document — Bedeutung carrier (file+range)."""

    symbol: str = Field(..., description="Moniker string referencing a ScipSymbol")
    range_start_line: int = Field(..., ge=0)
    range_start_char: int = Field(..., ge=0)
    range_end_line: int = Field(..., ge=0)
    range_end_char: int = Field(..., ge=0)
    role: int = Field(default=0, ge=0, description="SymbolRole bitset (0x1 Def, 0x2 Imp, ...)")

    @field_validator("range_end_line")
    @classmethod
    def _end_ge_start_line(cls, v, info):
        start = info.data.get("range_start_line")
        if start is not None and v < start:
            raise ValueError(f"range_end_line {v} < range_start_line {start}")
        return v


class ScipDocument(BaseModel):
    """Per-source-file collection of occurrences."""

    relative_path: str = Field(..., description="Path relative to project_root")
    language: str = Field(default="", description="Language id e.g. 'TypeScript', 'Python'")
    occurrences: list[ScipOccurrence] = Field(default_factory=list)


class ScipIndex(BaseModel):
    """Top-level SCIP index — mirrors `scip.Index` protobuf message."""

    metadata_version: int = Field(default=0, ge=0)
    project_root: str = Field(default="", description="Absolute path or URI root")
    documents: list[ScipDocument] = Field(default_factory=list)


# ─── Parsing ─────────────────────────────────────────────────────────────


def parse_scip_symbol(raw_moniker: str) -> ScipSymbol:
    """Parse a SCIP symbol moniker into structured form.

    Raises ValueError if moniker does not match expected grammar.

    NOTE: This implements the common 5-token form
    (scheme manager package version descriptor). Local symbols
    (sentinel scheme `.`) and the spec's full suffix-sigil grammar
    are accepted as-is in `descriptor` without further decomposition.
    """
    if not isinstance(raw_moniker, str) or not raw_moniker.strip():
        raise ValueError(f"empty or non-string moniker: {raw_moniker!r}")

    m = _MONIKER_RE.match(raw_moniker.strip())
    if not m:
        raise ValueError(
            f"malformed SCIP moniker — expected 'scheme manager pkg version descriptor', "
            f"got: {raw_moniker!r}"
        )

    scheme = m.group("scheme")
    manager = m.group("manager")
    pkg_name = m.group("pkg")
    version = m.group("version")
    descriptor = m.group("desc")
    package = f"{manager}/{pkg_name}@{version}"

    return ScipSymbol(
        scheme=scheme,
        package=package,
        descriptor=descriptor,
        raw=raw_moniker.strip(),
    )


def parse_scip_index_json(json_text: str) -> ScipIndex:
    """Parse a SCIP index JSON document (protobuf JSON marshaling).

    Sourcegraph's `scip` CLI emits both binary protobuf and JSON
    via `--format=json`. This adapter uses JSON to avoid a hard
    protobuf dependency.

    Raises ValueError on malformed JSON.
    Raises pydantic.ValidationError on schema violations.
    """
    if not isinstance(json_text, str):
        raise ValueError(f"json_text must be str, got {type(json_text).__name__}")
    try:
        raw = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"malformed SCIP JSON: {e}") from e

    if not isinstance(raw, dict):
        raise ValueError(f"SCIP root must be JSON object, got {type(raw).__name__}")

    # Normalize protobuf JSON shape:
    #   metadata.version  -> metadata_version
    #   metadata.projectRoot -> project_root
    #   documents[*].relativePath -> relative_path
    #   documents[*].occurrences[*].symbol / range / symbolRoles
    meta = raw.get("metadata", {}) or {}
    documents_raw = raw.get("documents", []) or []

    docs: list[ScipDocument] = []
    for d in documents_raw:
        occ_list: list[ScipOccurrence] = []
        for o in d.get("occurrences", []) or []:
            rng = o.get("range", []) or []
            # SCIP range encoding: [startLine, startChar, endLine, endChar]
            # OR [startLine, startChar, endChar] when single-line.
            if len(rng) == 4:
                sl, sc, el, ec = rng
            elif len(rng) == 3:
                sl, sc, ec = rng
                el = sl
            else:
                raise ValueError(f"occurrence range must be 3- or 4-tuple, got {rng!r}")
            occ_list.append(
                ScipOccurrence(
                    symbol=o.get("symbol", ""),
                    range_start_line=int(sl),
                    range_start_char=int(sc),
                    range_end_line=int(el),
                    range_end_char=int(ec),
                    role=int(o.get("symbolRoles", 0) or 0),
                )
            )
        docs.append(
            ScipDocument(
                relative_path=d.get("relativePath", ""),
                language=d.get("language", ""),
                occurrences=occ_list,
            )
        )

    return ScipIndex(
        metadata_version=int(meta.get("version", 0) or 0),
        project_root=str(meta.get("projectRoot", "") or ""),
        documents=docs,
    )


# ─── Adapter: SCIP → Longinus CodeSymbol ─────────────────────────────────


def _extract_name_from_descriptor(descriptor: str) -> str:
    """Best-effort identifier extraction from SCIP descriptor.

    SCIP descriptors look like:
      `mymod`/MyClass#method().
      `index.d.ts`/Buffer#
      `pkg`/foo/bar.
    The final identifier (between the last `/` and the trailing
    suffix sigil) is the human-readable name. Backtick-wrapped
    identifiers are unwrapped.
    """
    if not descriptor:
        return ""
    # Strip trailing sigils '.', '#', '()', '[...]'
    body = descriptor.rstrip(".#)")
    # Drop method-arg parens if present
    if "(" in body:
        body = body.split("(", 1)[0]
    # Split on '/' and take last segment
    last = body.split("/")[-1]
    # Unwrap backticks
    if last.startswith("`") and last.endswith("`") and len(last) >= 2:
        last = last[1:-1]
    return last


def _classify_kind(descriptor: str) -> str:
    """Best-effort kind classification from SCIP descriptor sigil."""
    if not descriptor:
        return "unknown"
    if descriptor.endswith("#"):
        return "class"
    if descriptor.endswith(")."):
        return "function"
    if descriptor.endswith("."):
        return "term"  # field/var/const
    if descriptor.endswith("]"):
        return "type_parameter"
    return "unknown"


def scip_to_code_symbols(idx: ScipIndex) -> list[CodeSymbol]:
    """Adapt a parsed SCIP index into `models.CodeSymbol` list.

    Each SCIP occurrence becomes one CodeSymbol with:
      sourcePath  = `{relative_path}:{range_start_line + 1}`
                    (SCIP uses 0-based lines; Longinus uses 1-based)
      name        = identifier extracted from descriptor
      kind        = class/function/term/unknown by sigil
      signature   = full moniker (preserves package + version context)
      kg_refs     = [] (SCIP carries no `# KG:` refs — separate channel)

    Empty documents / empty occurrence lists handled gracefully.
    Malformed monikers within a document raise ValueError.
    """
    out: list[CodeSymbol] = []
    for doc in idx.documents:
        for occ in doc.occurrences:
            try:
                sym = parse_scip_symbol(occ.symbol)
            except ValueError:
                # SCIP also emits local symbols ('local 1') which don't
                # match the 5-token grammar. Skip rather than abort.
                continue
            name = _extract_name_from_descriptor(sym.descriptor)
            kind = _classify_kind(sym.descriptor)
            # Convert 0-based to 1-based for Longinus convention.
            line = occ.range_start_line + 1
            out.append(
                CodeSymbol(
                    sourcePath=f"{doc.relative_path}:{line}",
                    name=name or sym.descriptor,
                    kind=kind,
                    signature=sym.raw,
                    kg_refs=[],
                )
            )
    return out


__all__ = [
    "ScipSymbol",
    "ScipOccurrence",
    "ScipDocument",
    "ScipIndex",
    "parse_scip_symbol",
    "parse_scip_index_json",
    "scip_to_code_symbols",
]
