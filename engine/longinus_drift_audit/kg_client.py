"""KgClient — Mock + Neo4j (DIP).

Wave 6 (2026-05-14) extensions:
    - merge_reference_site_state(site)   : write Wave 6 7-tuple fields
    - emit_drift_event(event)            : :SourceCodeDriftEvent PROV trail
    - list_knowledge_hubs()              : forward orphan scan target
    - set_knowledge_hub_path(name, path) : forward orphan resolution write

# KG: lesson-longinus-wave6-full-symposium-binding-2026-05-14
"""

from __future__ import annotations

import json
import re
import warnings
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable

from engine.longinus_drift_audit.models import (
    KgRefRecord,
    KnowledgeHubRecord,
    ReferenceLayer,
    ReferenceSite,
    Sha256Status,
    SourceCodeDriftEvent,
)


def _coerce_enum(value, enum_cls):
    """Return value iff it is a valid member of enum_cls, else None.

    KG stores free-form layer values + non-enum sha256 statuses
    (OK/PENDING_COMPUTE/…); this degrades unrecognized values to the field
    default instead of rejecting the whole ReferenceSite row.
    """
    if value is None:
        return None
    try:
        enum_cls(value)
    except ValueError:
        return None
    return value


class KgClient(ABC):
    @abstractmethod
    # KG: ATOM_Skill_longinus
    def list_reference_sites(self, repo_tag: str | None = None) -> list[KgRefRecord]: ...

    @abstractmethod
    def has_node(self, name: str) -> bool: ...

    @abstractmethod
    def merge_reference_site(self, record: KgRefRecord) -> None: ...

    # ── Wave 6 (2026-05-14) ───────────────────────────────────────────────

    @abstractmethod
    def list_reference_site_states(self, repo_tag: str | None = None) -> list[ReferenceSite]:
        """Return full :ReferenceSite nodes (Wave 6 7-tuple shape).

        repo_tag (2026-06-01): when set, return only sites with that repo_tag
        (shared-KG scope). None = all sites (backward compat).
        """
        ...

    @abstractmethod
    def merge_reference_site_state(self, site: ReferenceSite) -> None:
        """Upsert sha256 / sha256_baseline / sha256_status / kg_anchor / layer / last_validated."""
        ...

    # ── 2026-06-01 forward binding materializer ───────────────────────────

    def merge_forward_binding(self, site: ReferenceSite, *, line_count: int) -> bool:
        """Materialize a `# KG:` comment into a bound ReferenceSite.

        Upserts the ReferenceSite (``sourceId`` = the cited KG node name) + a
        :SourceCodeNode for ``sourcePath`` + a ``BINDS_TO``/``REALIZED_BY`` edge
        pair to the cited KG node — but ONLY when that node already exists
        (``has_node``). Returns True when bound, False when the cited node is
        absent (caller treats as an orphan `# KG:` comment; never auto-creates
        the node). Default impl = merge site + record SourceCodeNode shadow;
        Neo4j overrides with the real edge writes.
        """
        if not self.has_node(site.kg_anchor or site.sourceId):
            return False
        self.merge_reference_site_state(site)
        return True

    @abstractmethod
    def emit_drift_event(self, event: SourceCodeDriftEvent) -> None:
        """MERGE :SourceCodeDriftEvent + (:SourceCodeDriftEvent)-[:DRIFTED_FROM]->(:ReferenceSite)."""
        ...

    @abstractmethod
    def list_knowledge_hubs(self) -> list[KnowledgeHubRecord]:
        """Return all :KnowledgeHub nodes for forward orphan scan."""
        ...

    @abstractmethod
    def set_knowledge_hub_path(
        self,
        *,
        name: str,
        package_path: str,
        source_file: str | None = None,
        ruflo_grade: str | None = None,
    ) -> None:
        """Resolve a forward orphan by writing package_path/source_file/ruflo_grade."""
        ...

    def run(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        """Execute a raw read query, returning rows as dicts.

        Generic escape hatch used by audits that need ad-hoc Cypher (e.g.
        DispatchAuditor cardinality drift). Default raises; concrete clients
        override. Non-abstract so existing subclasses stay valid.
        """
        raise NotImplementedError("run() not supported by this KgClient")

    def merge_drift_check(self, record: dict[str, Any], *, reinduction: bool = False) -> None:
        """MERGE a :DriftCheck node (the nightly L8 GED drift record); when ``reinduction``
        also MERGE a :ReinductionTrigger for the next /prom 16 cycle. Default raises;
        Mock/Neo4j override. Non-abstract so existing subclasses stay valid."""
        raise NotImplementedError("merge_drift_check() not supported by this KgClient")

    def count_recent_reinduction_triggers(self, within_days: int = 7) -> int:
        """Count :ReinductionTrigger nodes created within the last ``within_days`` — the
        rolling window the Goodhart cap (MAX_REINDUCTION_PER_WEEK) is enforced against.
        Default raises; Mock/Neo4j override. Non-abstract so existing subclasses stay valid."""
        raise NotImplementedError(
            "count_recent_reinduction_triggers() not supported by this KgClient"
        )


class MockKgClient(KgClient):
    # KG: ATOM_Skill_longinus
    def __init__(
        self,
        *,
        refs: Iterable[KgRefRecord] | None = None,
        sites: Iterable[ReferenceSite] | None = None,
        hubs: Iterable[KnowledgeHubRecord] | None = None,
    ) -> None:
        self.refs: dict[str, KgRefRecord] = {}
        if refs:
            for r in refs:
                self.refs[r.sourceId] = r
        self.sites: dict[str, ReferenceSite] = {}
        if sites:
            for s in sites:
                self.sites[s.sourceId] = s
        self.hubs: dict[str, KnowledgeHubRecord] = {}
        if hubs:
            for h in hubs:
                self.hubs[h.name] = h
        self.drift_events: list[SourceCodeDriftEvent] = []
        self.drift_checks: list[dict[str, Any]] = []
        self.reinduction_triggers: list[
            dict[str, Any]
        ] = []  # {name, createdAt} for the Goodhart window
        self.other_nodes: set[str] = set()
        self.run_rows: list[dict[str, Any]] = []

    def run(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        """Return injected fake rows (tests set ``self.run_rows``)."""
        return list(self.run_rows)

    def list_reference_sites(self, repo_tag: str | None = None) -> list[KgRefRecord]:
        # KgRefRecord carries no repo_tag; filter via the ReferenceSite shadow.
        if repo_tag is None:
            return list(self.refs.values())
        keep = {sid for sid, s in self.sites.items() if s.repo_tag == repo_tag}
        return [r for sid, r in self.refs.items() if sid in keep]

    def has_node(self, name: str) -> bool:
        return (
            name in self.refs or name in self.sites or name in self.hubs or name in self.other_nodes
        )

    def merge_reference_site(self, record: KgRefRecord) -> None:
        self.refs[record.sourceId] = record

    # ── Wave 6 ────────────────────────────────────────────────────────────

    def list_reference_site_states(self, repo_tag: str | None = None) -> list[ReferenceSite]:
        if repo_tag is None:
            return list(self.sites.values())
        return [s for s in self.sites.values() if s.repo_tag == repo_tag]

    def merge_reference_site_state(self, site: ReferenceSite) -> None:
        self.sites[site.sourceId] = site
        # Keep KgRefRecord shadow up to date for legacy paths
        self.refs[site.sourceId] = KgRefRecord(
            sourceId=site.sourceId,
            sourcePath=site.sourcePath,
            expected_signature=site.signature_baseline,
        )

    def emit_drift_event(self, event: SourceCodeDriftEvent) -> None:
        self.drift_events.append(event)

    def merge_drift_check(self, record: dict[str, Any], *, reinduction: bool = False) -> None:
        self.drift_checks.append(dict(record))
        if reinduction:
            # carry createdAt so count_recent_reinduction_triggers can enforce the rolling
            # Goodhart window (was a bare name string → no timestamp to rate-limit against).
            self.reinduction_triggers.append(
                {"name": record.get("name", ""), "createdAt": record.get("createdAt")}
            )

    def count_recent_reinduction_triggers(self, within_days: int = 7) -> int:
        import datetime as _dt  # noqa: PLC0415

        cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=within_days)
        n = 0
        for t in self.reinduction_triggers:
            created = t.get("createdAt") if isinstance(t, dict) else None
            if created is None:  # no timestamp → treat as current (count it)
                n += 1
                continue
            try:
                if _dt.datetime.fromisoformat(created) >= cutoff:
                    n += 1
            except ValueError:
                n += 1
        return n

    def list_knowledge_hubs(self) -> list[KnowledgeHubRecord]:
        return list(self.hubs.values())

    def set_knowledge_hub_path(
        self,
        *,
        name: str,
        package_path: str,
        source_file: str | None = None,
        ruflo_grade: str | None = None,
    ) -> None:
        existing = self.hubs.get(name) or KnowledgeHubRecord(name=name)
        self.hubs[name] = existing.model_copy(
            update={
                "package_path": package_path,
                "source_file": source_file or existing.source_file,
                "ruflo_grade": ruflo_grade or existing.ruflo_grade,
            }
        )


class Neo4jKgClient(KgClient):  # pragma: no cover
    # KG: ATOM_Skill_longinus
    def __init__(self, uri: str, auth: tuple[str, str]):
        from neo4j import GraphDatabase  # type: ignore

        # Any: the McpKgClient subclass swaps in a duck-typed _McpDriver (session()/close()).
        self._driver: Any = GraphDatabase.driver(uri, auth=auth)

    def close(self) -> None:
        self._driver.close()

    def run(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        with self._driver.session() as s:
            return [dict(r) for r in s.run(cypher, **params)]

    def list_reference_sites(self, repo_tag: str | None = None) -> list[KgRefRecord]:
        # Filter null sourceId/sourcePath in Cypher: such nodes carry no usable
        # drift-comparison key, and KgRefRecord requires both to be str. (Live
        # audit smoke 2026-05-25 surfaced real null-sourcePath ReferenceSites
        # that crashed this previously-uncovered path — Naesengmoon ensemble
        # finding ac-bhgman-5f5a905-goodhart-self-audit-mock-zero-drift.)
        # repo_tag (2026-06-01): shared-KG scope — $repo_tag IS NULL = all.
        with self._driver.session() as s:
            rows = s.run(
                "MATCH (n:ReferenceSite) "
                "WHERE n.sourceId IS NOT NULL AND n.sourcePath IS NOT NULL "
                "AND ($repo_tag IS NULL OR n.repo_tag = $repo_tag) "
                "RETURN n.sourceId AS sourceId, n.sourcePath AS sourcePath, "
                "n.label AS label, n.signature_baseline AS signature_baseline",
                repo_tag=repo_tag,
            )
            return [
                KgRefRecord(
                    sourceId=r["sourceId"],
                    sourcePath=r["sourcePath"],
                    label=r.get("label"),
                    expected_signature=r.get("signature_baseline"),
                )
                for r in rows
            ]

    def has_node(self, name: str) -> bool:
        with self._driver.session() as s:
            row = s.run(
                "MATCH (n) WHERE n.name = $name OR n.sourceId = $name RETURN count(n) AS c",
                name=name,
            ).single()
            return bool(row and row["c"] > 0)

    def merge_reference_site(self, record: KgRefRecord) -> None:
        with self._driver.session() as s:
            s.run(
                """
                MERGE (n:ReferenceSite {sourceId: $sourceId})
                SET n.sourcePath = $sourcePath, n.label = $label
                """,
                sourceId=record.sourceId,
                sourcePath=record.sourcePath,
                label=record.label,
            )

    # ── Wave 6 ────────────────────────────────────────────────────────────

    def list_reference_site_states(self, repo_tag: str | None = None) -> list[ReferenceSite]:
        # Mirrors list_reference_sites: null-key sites (no sourceId/sourcePath =
        # no usable sha256-verify key) are excluded at the Cypher level rather
        # than swallowed by a bare except, and remaining reconstruction failures
        # are COUNTED + surfaced (no silent drop). sha256_status + layer are
        # carried through so the BX GetPut roundtrip is faithful — DIRECTORY_SKIP
        # sites stay skipped instead of false-flagging FILE_MISSING. Naesengmoon
        # re-validation v2 findings: ...-sibling-list_reference_site_states
        # -goodhart (HIGH) + ...-drops-status-layer (MED).
        # repo_tag (2026-06-01): shared-KG scope — $repo_tag IS NULL = all.
        with self._driver.session() as s:
            rows = s.run(
                "MATCH (n:ReferenceSite) "
                "WHERE n.sourceId IS NOT NULL AND n.sourcePath IS NOT NULL "
                "AND ($repo_tag IS NULL OR n.repo_tag = $repo_tag) "
                "RETURN n.sourceId AS sourceId, n.sourcePath AS sourcePath, "
                "n.sha256 AS sha256, n.sha256_baseline AS sha256_baseline, "
                "n.sha256_status AS sha256_status, n.kg_anchor AS kg_anchor, "
                "n.layer AS layer, n.last_validated AS last_validated, "
                "n.repo_tag AS repo_tag, n.repo_id AS repo_id, "
                "n.repo_relpath AS repo_relpath, n.commit AS commit, "
                "n.blob_oid AS blob_oid, n.blob_oid_baseline AS blob_oid_baseline",
                repo_tag=repo_tag,
            )
            out: list[ReferenceSite] = []
            skipped = 0
            for r in rows:
                kwargs = dict(
                    sourceId=r["sourceId"],
                    sourcePath=r["sourcePath"],
                    sha256=r.get("sha256"),
                    sha256_baseline=r.get("sha256_baseline"),
                    kg_anchor=r.get("kg_anchor"),
                    last_validated=r.get("last_validated"),
                    repo_tag=r.get("repo_tag"),
                    repo_id=r.get("repo_id"),
                    repo_relpath=r.get("repo_relpath"),
                    commit=r.get("commit"),
                    blob_oid=r.get("blob_oid"),
                    blob_oid_baseline=r.get("blob_oid_baseline"),
                )
                # Carry sha256_status/layer ONLY when the stored value is a valid
                # enum member (so DIRECTORY_SKIP etc. survive the roundtrip), else
                # let the field default apply — never drop the whole row over a
                # free-form layer string or a non-enum status.
                st = _coerce_enum(r.get("sha256_status"), Sha256Status)
                if st is not None:
                    kwargs["sha256_status"] = st
                ly = _coerce_enum(r.get("layer"), ReferenceLayer)
                if ly is not None:
                    kwargs["layer"] = ly
                try:
                    out.append(ReferenceSite(**kwargs))
                except Exception:  # noqa: BLE001 — genuinely broken row; count, never silently swallow
                    skipped += 1
            if skipped:
                warnings.warn(
                    f"list_reference_site_states: {skipped} ReferenceSite row(s) skipped "
                    "(malformed despite non-null key); sha256 verify is incomplete for those.",
                    stacklevel=2,
                )
            return out

    def merge_reference_site_state(self, site: ReferenceSite) -> None:
        with self._driver.session() as s:
            s.run(
                """
                MERGE (n:ReferenceSite {sourceId: $sourceId})
                SET n.sourcePath = $sourcePath,
                    n.sha256 = $sha256,
                    n.sha256_baseline = $sha256_baseline,
                    n.sha256_status = $sha256_status,
                    n.kg_anchor = $kg_anchor,
                    n.layer = $layer,
                    n.last_validated = $last_validated,
                    n.drift_score = $drift_score,
                    n.drift_detected_at = $drift_detected_at,
                    n.signature_baseline = $signature_baseline,
                    n.repo_tag = coalesce($repo_tag, n.repo_tag),
                    n.repo_id = coalesce($repo_id, n.repo_id),
                    n.repo_relpath = coalesce($repo_relpath, n.repo_relpath),
                    n.commit = $commit,
                    n.blob_oid = $blob_oid,
                    n.blob_oid_baseline = coalesce(n.blob_oid_baseline, $blob_oid_baseline)
                """,
                sourceId=site.sourceId,
                sourcePath=site.sourcePath,
                sha256=site.sha256,
                sha256_baseline=site.sha256_baseline,
                sha256_status=site.sha256_status.value if site.sha256_status else None,
                kg_anchor=site.kg_anchor,
                layer=site.layer.value if site.layer else None,
                last_validated=site.last_validated,
                drift_score=site.drift_score,
                drift_detected_at=site.drift_detected_at,
                signature_baseline=site.signature_baseline,
                repo_tag=site.repo_tag,
                repo_id=site.repo_id,
                repo_relpath=site.repo_relpath,
                commit=site.commit,
                blob_oid=site.blob_oid,
                blob_oid_baseline=site.blob_oid_baseline,
            )

    def merge_forward_binding(self, site: ReferenceSite, *, line_count: int) -> bool:
        kg_ref = site.kg_anchor or site.sourceId
        src_name = site.sourcePath.rsplit("/", 1)[-1]
        with self._driver.session() as s:
            row = s.run(
                """
                OPTIONAL MATCH (kg {name: $kg_ref})
                WITH kg LIMIT 1
                WITH kg WHERE kg IS NOT NULL
                MERGE (rs:ReferenceSite {sourceId: $sourceId, sourcePath: $sourcePath})
                  SET rs.sha256 = $sha256,
                      rs.sha256_baseline = $sha256_baseline,
                      rs.kg_anchor = $kg_ref,
                      rs.layer = $layer,
                      rs.repo_tag = $repo_tag,
                      rs.signature_baseline = $signature_baseline,
                      rs.last_validated = $last_validated
                MERGE (scn:SourceCodeNode {sourcePath: $sourcePath})
                  SET scn.sha256 = $sha256, scn.lineCount = $line_count, scn.name = $src_name
                MERGE (rs)-[:BINDS_TO]->(kg)
                MERGE (kg)-[:REALIZED_BY]->(rs)
                MERGE (rs)-[:LOCATED_IN]->(scn)
                RETURN count(rs) AS bound
                """,
                kg_ref=kg_ref,
                sourceId=site.sourceId,
                sourcePath=site.sourcePath,
                sha256=site.sha256,
                sha256_baseline=site.sha256_baseline,
                layer=site.layer.value if site.layer else None,
                repo_tag=site.repo_tag,
                signature_baseline=site.signature_baseline,
                last_validated=site.last_validated,
                line_count=line_count,
                src_name=src_name,
            ).single()
            return bool(row and row["bound"] > 0)

    def emit_drift_event(self, event: SourceCodeDriftEvent) -> None:
        with self._driver.session() as s:
            s.run(
                """
                MERGE (e:SourceCodeDriftEvent {name: $name})
                ON CREATE SET e.created_at = $created_at,
                              e.detected_by = $detected_by,
                              e.ref_site = $ref_site,
                              e.path = $path,
                              e.baseline_sha256 = $baseline_sha256,
                              e.current_sha256 = $current_sha256,
                              e.kind = $kind,
                              e.resolved = $resolved
                WITH e
                MATCH (rs:ReferenceSite {sourceId: $ref_site})
                MERGE (e)-[:DRIFTED_FROM]->(rs)
                """,
                name=event.name,
                created_at=event.created_at,
                detected_by=event.detected_by,
                ref_site=event.ref_site,
                path=event.path,
                baseline_sha256=event.baseline_sha256,
                current_sha256=event.current_sha256,
                kind=event.kind,
                resolved=event.resolved,
            )

    def merge_drift_check(self, record: dict[str, Any], *, reinduction: bool = False) -> None:
        with self._driver.session() as s:
            s.run(
                """
                MERGE (d:DriftCheck {name: $name})
                SET d += $props
                """,
                name=record.get("name"),
                props=record,
            )
            if reinduction:
                s.run(
                    """
                    MATCH (d:DriftCheck {name: $name})
                    MERGE (t:ReinductionTrigger {name: $trigger_name})
                    ON CREATE SET t.created_at = $created_at, t.source_drift_check = $name
                    MERGE (d)-[:TRIGGERS]->(t)
                    """,
                    name=record.get("name"),
                    trigger_name=f"reinduction-{record.get('name')}",
                    created_at=record.get("createdAt"),
                )

    def count_recent_reinduction_triggers(self, within_days: int = 7) -> int:
        import datetime as _dt  # noqa: PLC0415

        cutoff = (
            _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=within_days)
        ).isoformat()  # created_at stored as ISO 8601 → lexical >= is chronological
        with self._driver.session() as s:
            row = s.run(
                "MATCH (t:ReinductionTrigger) WHERE t.created_at >= $cutoff RETURN count(t) AS n",
                cutoff=cutoff,
            ).single()
            return int(row["n"]) if row else 0

    def list_knowledge_hubs(self) -> list[KnowledgeHubRecord]:
        with self._driver.session() as s:
            rows = s.run(
                "MATCH (h:KnowledgeHub) "
                "RETURN h.name AS name, h.package_path AS package_path, "
                "h.source_file AS source_file, h.ruflo_grade AS ruflo_grade"
            )
            # ruflo_grade is a free-form tag in KG (sometimes stored as bool
            # True/False, int, or str) but KnowledgeHubRecord types it as str —
            # coerce non-null values so live data variance doesn't crash the
            # previously-uncovered path. (Live smoke 2026-05-25, same finding.)
            return [
                KnowledgeHubRecord(
                    name=r["name"],
                    package_path=r.get("package_path"),
                    source_file=r.get("source_file"),
                    ruflo_grade=None if r.get("ruflo_grade") is None else str(r.get("ruflo_grade")),
                )
                for r in rows
            ]

    def set_knowledge_hub_path(
        self,
        *,
        name: str,
        package_path: str,
        source_file: str | None = None,
        ruflo_grade: str | None = None,
    ) -> None:
        with self._driver.session() as s:
            s.run(
                """
                MERGE (h:KnowledgeHub {name: $name})
                SET h.package_path = $package_path,
                    h.source_file = coalesce($source_file, h.source_file),
                    h.ruflo_grade = coalesce($ruflo_grade, h.ruflo_grade)
                """,
                name=name,
                package_path=package_path,
                source_file=source_file,
                ruflo_grade=ruflo_grade,
            )


class _McpResult:
    """neo4j-Result-like wrapper over a list[dict] returned by the MCP gateway."""

    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)

    def single(self):
        return self._rows[0] if self._rows else None

    def data(self):
        return self._rows


# word-boundary write detection after stripping string literals — substring matching
# (`"MERGE" in up`) misrouted legitimate READS to the write tool whenever a property
# (n.createdAt), label (:MergedPR), or literal value contained a write keyword (W3-L).
_MCP_WRITE_RE = re.compile(
    r"\b(CREATE|MERGE|DELETE|REMOVE|SET|DROP|FOREACH|DETACH|LOAD\s+CSV)\b", re.IGNORECASE
)
_MCP_STRING_LIT = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", re.DOTALL)


def _is_write_cypher(cypher: str) -> bool:
    return bool(_MCP_WRITE_RE.search(_MCP_STRING_LIT.sub("''", cypher)))


def _mcp_exec(url: str, cypher: str, params: dict) -> list[dict]:
    """POST one cypher to a streamable-HTTP mcp-neo4j-cypher gateway (stateless).

    Classifies read vs write by keyword (the gateway exposes separate
    read_neo4j_cypher / write_neo4j_cypher tools), parses the SSE `data:` frame,
    and unwraps result.content[0].text (a JSON array of rows).
    KG: bhgman-engine-mcp-kg-backend.
    """
    import json as _json
    import urllib.request as _ur

    tool = "write_neo4j_cypher" if _is_write_cypher(cypher) else "read_neo4j_cypher"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": {"query": cypher, "params": params or {}}},
    }
    req = _ur.Request(
        url,
        data=_json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    with _ur.urlopen(req, timeout=120) as resp:  # noqa: S310 — fixed scheme, op env
        body = resp.read().decode()
    data = body
    for line in body.splitlines():
        if line.startswith("data:"):
            data = line[5:].strip()
    obj = _json.loads(data)
    if "error" in obj:
        raise RuntimeError(f"MCP error: {obj['error']}")
    result = obj["result"]
    if result.get("isError"):
        raise RuntimeError(f"cypher error: {result['content'][0]['text']}")
    text = result["content"][0]["text"] if result.get("content") else ""
    parsed = _json.loads(text) if text else []
    return parsed if isinstance(parsed, list) else [parsed]


class _McpSession:
    def __init__(self, url: str):
        self._url = url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, cypher: str, **params: Any) -> _McpResult:
        return _McpResult(_mcp_exec(self._url, cypher, params))

    def close(self) -> None:
        pass


class _McpDriver:
    def __init__(self, url: str):
        self._url = url

    def session(self) -> _McpSession:
        return _McpSession(self._url)

    def close(self) -> None:
        pass


class McpKgClient(Neo4jKgClient):  # pragma: no cover
    # KG: ATOM_Skill_longinus
    """KgClient over the mcp-neo4j-cypher HTTP gateway (bolt-firewalled KG).

    Reuses every Neo4jKgClient method verbatim by swapping the bolt driver for an
    MCP shim whose .session().run() POSTs cypher to the gateway. Lets the longinus
    audit/materialize reach a KG that only exposes its MCP endpoint (e.g.
    airobotics-1 over Tailscale; bolt 7687 firewalled, MCP open on :55013).
    """

    def __init__(self, url: str):
        self._url = url
        self._driver = _McpDriver(url)

    def merge_forward_binding(self, site: ReferenceSite, *, line_count: int) -> bool:
        """Override: the gateway's write tool returns counters, not the RETURN row,
        so the parent's `row["bound"]` read is unavailable. Confirm the kg anchor
        exists via a read (matches the parent's `WITH kg WHERE kg IS NOT NULL` skip —
        no dangling binding), then run the MERGE as a write."""
        kg_ref = site.kg_anchor or site.sourceId
        if not self.has_node(kg_ref):
            return False
        src_name = site.sourcePath.rsplit("/", 1)[-1]
        self._driver.session().run(
            """
            MATCH (kg {name: $kg_ref}) WITH kg LIMIT 1
            MERGE (rs:ReferenceSite {sourceId: $sourceId, sourcePath: $sourcePath})
              SET rs.sha256 = $sha256, rs.sha256_baseline = $sha256_baseline,
                  rs.kg_anchor = $kg_ref, rs.layer = $layer, rs.repo_tag = $repo_tag,
                  rs.signature_baseline = $signature_baseline, rs.last_validated = $last_validated
            MERGE (scn:SourceCodeNode {sourcePath: $sourcePath})
              SET scn.sha256 = $sha256, scn.lineCount = $line_count, scn.name = $src_name
            MERGE (rs)-[:BINDS_TO]->(kg)
            MERGE (kg)-[:REALIZED_BY]->(rs)
            MERGE (rs)-[:LOCATED_IN]->(scn)
            """,
            kg_ref=kg_ref,
            sourceId=site.sourceId,
            sourcePath=site.sourcePath,
            sha256=site.sha256,
            sha256_baseline=site.sha256_baseline,
            layer=site.layer.value if site.layer else None,
            repo_tag=site.repo_tag,
            signature_baseline=site.signature_baseline,
            last_validated=site.last_validated,
            line_count=line_count,
            src_name=src_name,
        )
        return True


class JsonFileKgClient(MockKgClient):
    # KG: ATOM_Skill_longinus
    """Neo4j-free local backend — MockKgClient persisted to a JSON file.

    Lets `longinus-audit --kg local` record + audit signature/drift baselines
    offline (the SigMismatch counterpart of occam/hades ``--local``). Reuses
    every MockKgClient method; only adds load-on-init + save-after-mutate.
    Default path ``~/.bhgman/longinus_kg.json``.
    """

    DEFAULT_PATH = "~/.bhgman/longinus_kg.json"

    def __init__(self, path: str | Path | None = None) -> None:
        super().__init__()
        self.path = Path(path or self.DEFAULT_PATH).expanduser()
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for r in data.get("refs", []):
            self.refs[r["sourceId"]] = KgRefRecord(**r)
        for s in data.get("sites", []):
            self.sites[s["sourceId"]] = ReferenceSite(**s)
        for h in data.get("hubs", []):
            self.hubs[h["name"]] = KnowledgeHubRecord(**h)
        self.other_nodes = set(data.get("other_nodes", []))

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "refs": [r.model_dump(mode="json") for r in self.refs.values()],
            "sites": [s.model_dump(mode="json") for s in self.sites.values()],
            "hubs": [h.model_dump(mode="json") for h in self.hubs.values()],
            "other_nodes": sorted(self.other_nodes),
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    def merge_reference_site(self, record: KgRefRecord) -> None:
        super().merge_reference_site(record)
        self._save()

    def merge_reference_site_state(self, site: ReferenceSite) -> None:
        super().merge_reference_site_state(site)
        self._save()

    def set_knowledge_hub_path(self, **kwargs: Any) -> None:
        super().set_knowledge_hub_path(**kwargs)
        self._save()


# KG: lesson-longinus-wave6-full-symposium-binding-2026-05-14
# KG: span-bhgman-longinus-wave6-absorb-2026-05-14
