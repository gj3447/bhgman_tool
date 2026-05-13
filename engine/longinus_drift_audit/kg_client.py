"""KgClient — Mock + Neo4j (DIP)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from models import KgRefRecord


class KgClient(ABC):
    @abstractmethod
    def list_reference_sites(self) -> list[KgRefRecord]: ...

    @abstractmethod
    def has_node(self, name: str) -> bool: ...

    @abstractmethod
    def merge_reference_site(self, record: KgRefRecord) -> None: ...


class MockKgClient(KgClient):
    def __init__(self, *, refs: Iterable[KgRefRecord] | None = None) -> None:
        self.refs: dict[str, KgRefRecord] = {}
        if refs:
            for r in refs:
                self.refs[r.sourceId] = r
        self.other_nodes: set[str] = set()  # 다른 KG 노드 (lesson, finding 등)

    def list_reference_sites(self) -> list[KgRefRecord]:
        return list(self.refs.values())

    def has_node(self, name: str) -> bool:
        return name in self.refs or name in self.other_nodes

    def merge_reference_site(self, record: KgRefRecord) -> None:
        self.refs[record.sourceId] = record


class Neo4jKgClient(KgClient):  # pragma: no cover
    def __init__(self, uri: str, auth: tuple[str, str]):
        from neo4j import GraphDatabase  # type: ignore

        self._driver = GraphDatabase.driver(uri, auth=auth)

    def close(self) -> None:
        self._driver.close()

    def list_reference_sites(self) -> list[KgRefRecord]:
        with self._driver.session() as s:
            rows = s.run(
                "MATCH (n:ReferenceSite) "
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
                "MATCH (n) WHERE n.name = $name OR n.sourceId = $name "
                "RETURN count(n) AS c",
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
