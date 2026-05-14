"""APT resolver — Neo4j KG client.

`MethodologyConfig_default_v27` 노드 + `LensSet` + `ContractSchema` slot resolve.
60s TTL cache. Composition Root 시 health check + 5 core field 존재 검증.

KG ref: rfc-apt-v26-A6-resolver-path-A-pre-prompt-hook-2026-04-30
Absorbed from SYMPOSIUM/THEORY/APT/resolver_prototype/cypher_kg_client.py (Wave 7 P3-H).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from neo4j import GraphDatabase, Driver


# 5 core magic — Sprint 2b 변환 대상 (외부화 정전)
CORE_MAGIC_FIELDS: tuple[str, ...] = (
    "vibe_coding_sweet_min",
    "vibe_coding_sweet_max",
    "lens_count_constitutional",
    "contract_default_fields",
    "st_decision_areas",
)

CONFIG_NODE_NAME = "MethodologyConfig_default_v27"


@dataclass(frozen=True, slots=True)
class KGConfig:
    uri: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "KGConfig":
        return cls(
            uri=os.environ["NEO4J_URI"],
            user=os.environ.get("NEO4J_USER", "neo4j"),
            password=os.environ["NEO4J_PASSWORD"],
        )


class CypherKGClient:
    """KG client with 60s TTL cache + Composition Root validation."""

    _CACHE_TTL = 60.0  # seconds

    def __init__(self, cfg: KGConfig) -> None:
        self._driver: Driver = GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password))
        self._cache: dict[str, tuple[float, Any]] = {}

    def close(self) -> None:
        self._driver.close()

    # ─── Composition Root validation ────────────────────────────────────

    def health_check(self) -> bool:
        with self._driver.session() as s:
            r = s.run("RETURN 1 AS ok").single()
            return bool(r and r["ok"] == 1)

    def verify_core_magic_present(self) -> None:
        """5 core field 모두 존재 검증. 누락 시 MissingConfigError."""
        cfg = self.fetch_methodology_config()
        missing = [f for f in CORE_MAGIC_FIELDS if f not in cfg]
        if missing:
            raise MissingConfigError(
                f"5 core magic fields missing in KG {CONFIG_NODE_NAME}: {missing}. "
                f"RFC A6.1 ACCEPTED인데 KG seeding 누락."
            )

    # ─── KG fetch (cached) ───────────────────────────────────────────────

    def fetch_methodology_config(self) -> dict[str, Any]:
        return self._cached("methodology_config", self._fetch_methodology_config)

    def fetch_lens_set(self, name: str) -> dict[str, Any]:
        return self._cached(f"lensset:{name}", lambda: self._fetch_lens_set(name))

    def fetch_contract_schema(self) -> dict[str, Any]:
        return self._cached("contract_schema", self._fetch_contract_schema)

    # ─── private ─────────────────────────────────────────────────────────

    def _cached(self, key: str, loader):
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached and (now - cached[0]) < self._CACHE_TTL:
            return cached[1]
        value = loader()
        self._cache[key] = (now, value)
        return value

    def _fetch_methodology_config(self) -> dict[str, Any]:
        q = """
        MATCH (cfg:MethodologyConfig {name: $name})
        RETURN properties(cfg) AS props
        """
        with self._driver.session() as s:
            r = s.run(q, name=CONFIG_NODE_NAME).single()
        if not r:
            raise MissingConfigError(f"KG node not found: {CONFIG_NODE_NAME}")
        return dict(r["props"])

    def _fetch_lens_set(self, name: str) -> dict[str, Any]:
        q = """
        MATCH (ls:LensSet {name: $name})
        WHERE ls.deprecated <> true
        RETURN ls.lensCount AS lensCount, ls.minCritics AS minCritics
        """
        with self._driver.session() as s:
            r = s.run(q, name=name).single()
        if not r:
            raise MissingConfigError(f"LensSet not found or deprecated: {name}")
        return dict(r)

    def _fetch_contract_schema(self) -> dict[str, Any]:
        q = """
        MATCH (slot:MethodologySlot {name:'ContractSchema'})-[:RESOLVES_TO]->(schema)
        RETURN properties(schema) AS props
        """
        with self._driver.session() as s:
            r = s.run(q).single()
        if not r:
            raise MissingConfigError("ContractSchema slot unresolved")
        return dict(r["props"])


class MissingConfigError(KeyError):
    """KG에 cfg field 없음 — Composition Root에서 startup 실패."""
