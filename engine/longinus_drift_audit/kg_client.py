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
    def list_reference_sites(self) -> list[KgRefRecord]: ...

    @abstractmethod
    def has_node(self, name: str) -> bool: ...

    @abstractmethod
    def merge_reference_site(self, record: KgRefRecord) -> None: ...

    # ── Wave 6 (2026-05-14) ───────────────────────────────────────────────

    @abstractmethod
    def list_reference_site_states(self) -> list[ReferenceSite]:
        """Return full :ReferenceSite nodes (Wave 6 7-tuple shape)."""
        ...

    @abstractmethod
    def merge_reference_site_state(self, site: ReferenceSite) -> None:
        """Upsert sha256 / sha256_baseline / sha256_status / kg_anchor / layer / last_validated."""
        ...

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


class MockKgClient(KgClient):
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
        self.other_nodes: set[str] = set()
        self.run_rows: list[dict[str, Any]] = []

    def run(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        """Return injected fake rows (tests set ``self.run_rows``)."""
        return list(self.run_rows)

    def list_reference_sites(self) -> list[KgRefRecord]:
        return list(self.refs.values())

    def has_node(self, name: str) -> bool:
        return (
            name in self.refs or name in self.sites or name in self.hubs or name in self.other_nodes
        )

    def merge_reference_site(self, record: KgRefRecord) -> None:
        self.refs[record.sourceId] = record

    # ── Wave 6 ────────────────────────────────────────────────────────────

    def list_reference_site_states(self) -> list[ReferenceSite]:
        return list(self.sites.values())

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
    def __init__(self, uri: str, auth: tuple[str, str]):
        from neo4j import GraphDatabase  # type: ignore

        self._driver = GraphDatabase.driver(uri, auth=auth)

    def close(self) -> None:
        self._driver.close()

    def run(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        with self._driver.session() as s:
            return [dict(r) for r in s.run(cypher, **params)]

    def list_reference_sites(self) -> list[KgRefRecord]:
        # Filter null sourceId/sourcePath in Cypher: such nodes carry no usable
        # drift-comparison key, and KgRefRecord requires both to be str. (Live
        # audit smoke 2026-05-25 surfaced real null-sourcePath ReferenceSites
        # that crashed this previously-uncovered path — Naesengmoon ensemble
        # finding ac-bhgman-5f5a905-goodhart-self-audit-mock-zero-drift.)
        with self._driver.session() as s:
            rows = s.run(
                "MATCH (n:ReferenceSite) "
                "WHERE n.sourceId IS NOT NULL AND n.sourcePath IS NOT NULL "
                "RETURN n.sourceId AS sourceId, n.sourcePath AS sourcePath, "
                "n.label AS label, n.signature_baseline AS signature_baseline"
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

    def list_reference_site_states(self) -> list[ReferenceSite]:
        # Mirrors list_reference_sites: null-key sites (no sourceId/sourcePath =
        # no usable sha256-verify key) are excluded at the Cypher level rather
        # than swallowed by a bare except, and remaining reconstruction failures
        # are COUNTED + surfaced (no silent drop). sha256_status + layer are
        # carried through so the BX GetPut roundtrip is faithful — DIRECTORY_SKIP
        # sites stay skipped instead of false-flagging FILE_MISSING. Naesengmoon
        # re-validation v2 findings: ...-sibling-list_reference_site_states
        # -goodhart (HIGH) + ...-drops-status-layer (MED).
        with self._driver.session() as s:
            rows = s.run(
                "MATCH (n:ReferenceSite) "
                "WHERE n.sourceId IS NOT NULL AND n.sourcePath IS NOT NULL "
                "RETURN n.sourceId AS sourceId, n.sourcePath AS sourcePath, "
                "n.sha256 AS sha256, n.sha256_baseline AS sha256_baseline, "
                "n.sha256_status AS sha256_status, n.kg_anchor AS kg_anchor, "
                "n.layer AS layer, n.last_validated AS last_validated"
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
                    n.signature_baseline = $signature_baseline
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
            )

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


class JsonFileKgClient(MockKgClient):
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
