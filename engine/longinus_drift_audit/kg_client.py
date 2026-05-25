"""KgClient — Mock + Neo4j (DIP).

Wave 6 (2026-05-14) extensions:
    - merge_reference_site_state(site)   : write Wave 6 7-tuple fields
    - emit_drift_event(event)            : :SourceCodeDriftEvent PROV trail
    - list_knowledge_hubs()              : forward orphan scan target
    - set_knowledge_hub_path(name, path) : forward orphan resolution write

# KG: lesson-longinus-wave6-full-symposium-binding-2026-05-14
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from models import (
    KgRefRecord,
    KnowledgeHubRecord,
    ReferenceSite,
    SourceCodeDriftEvent,
)


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
                "n.label AS label"
            )
            return [
                KgRefRecord(
                    sourceId=r["sourceId"],
                    sourcePath=r["sourcePath"],
                    label=r.get("label"),
                )
                for r in rows
            ]

    def has_node(self, name: str) -> bool:
        with self._driver.session() as s:
            row = s.run(
                "MATCH (n) WHERE n.name = $name OR n.sourceId = $name " "RETURN count(n) AS c",
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
        with self._driver.session() as s:
            rows = s.run(
                "MATCH (n:ReferenceSite) "
                "RETURN n.sourceId AS sourceId, n.sourcePath AS sourcePath, "
                "n.sha256 AS sha256, n.sha256_baseline AS sha256_baseline, "
                "n.sha256_status AS sha256_status, n.kg_anchor AS kg_anchor, "
                "n.layer AS layer, n.last_validated AS last_validated"
            )
            out: list[ReferenceSite] = []
            for r in rows:
                # Build via constructor; Pydantic enums tolerate missing/None.
                try:
                    out.append(
                        ReferenceSite(
                            sourceId=r["sourceId"],
                            sourcePath=r["sourcePath"],
                            sha256=r.get("sha256"),
                            sha256_baseline=r.get("sha256_baseline"),
                            kg_anchor=r.get("kg_anchor"),
                            last_validated=r.get("last_validated"),
                        )
                    )
                except Exception:
                    continue
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
                    n.drift_detected_at = $drift_detected_at
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


# KG: lesson-longinus-wave6-full-symposium-binding-2026-05-14
# KG: span-bhgman-longinus-wave6-absorb-2026-05-14
