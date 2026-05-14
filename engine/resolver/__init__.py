"""APT v27 A6 path A — Pre-prompt resolver.

Absorbed from SYMPOSIUM/THEORY/APT/resolver_prototype/ (Wave 7 P3-H, 2026-05-14).

Public API:
    boot_kg_client() -> CypherKGClient
    resolve(skill_path, client) -> ResolveResult
    validate(skill_path, client) -> ValidateReport

KG ref: rfc-apt-v26-A6-resolver-path-A-pre-prompt-hook-2026-04-30
"""
from .resolver import (
    ResolveResult,
    ValidateReport,
    boot_kg_client,
    resolve,
    validate,
)
from .cypher_kg_client import (
    CORE_MAGIC_FIELDS,
    CONFIG_NODE_NAME,
    CypherKGClient,
    KGConfig,
    MissingConfigError,
)
from .frontmatter_parser import ParsedSkill, parse as parse_skill, dump as dump_skill
from .jinja_env import StrictUndefined, UnresolvedMarkerError, build_env

__all__ = [
    "ResolveResult",
    "ValidateReport",
    "boot_kg_client",
    "resolve",
    "validate",
    "CORE_MAGIC_FIELDS",
    "CONFIG_NODE_NAME",
    "CypherKGClient",
    "KGConfig",
    "MissingConfigError",
    "ParsedSkill",
    "parse_skill",
    "dump_skill",
    "StrictUndefined",
    "UnresolvedMarkerError",
    "build_env",
]
