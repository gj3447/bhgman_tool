"""Canonical command identity for the APT vNext durable kernel.

The command digest is derived from every semantic identity field.  Callers can
provide canonical input, but they cannot substitute an unchecked digest.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from .canonical import (
    CanonicalEncodingError,
    CanonicalValue,
    MAX_SIGNED_64,
    as_mapping,
    canonical_sha256,
    deep_freeze,
    normalize_text,
)
from .events import EventSchemaError, validate_rfc3339_utc_z


class CommandSchemaError(ValueError):
    """A command envelope is incomplete or not canonically representable."""


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise CommandSchemaError(f"{name} must be a non-empty string")
    normalized = normalize_text(value)
    if "\x00" in normalized:
        raise CommandSchemaError(f"{name} cannot contain U+0000")
    return normalized


def _mapping(name: str, value: object) -> Mapping[str, CanonicalValue]:
    try:
        return as_mapping(deep_freeze(value))
    except (CanonicalEncodingError, RecursionError) as exc:
        raise CommandSchemaError(f"{name} must be canonical JSON: {exc}") from exc


@dataclass(frozen=True, slots=True)
class CanonicalCommandEnvelope:
    """Complete, immutable command identity with internally derived hashes."""

    command_id: str
    command_type: str
    schema_version: str
    cycle_id: str
    expected_version: int
    actor: str
    authorization_context: Mapping[str, CanonicalValue]
    correlation_id: str
    causation_id: str
    input: Mapping[str, CanonicalValue]
    issued_at: str
    input_hash: str = field(init=False)
    command_hash: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "command_id",
            "command_type",
            "schema_version",
            "cycle_id",
            "actor",
            "correlation_id",
            "causation_id",
            "issued_at",
        ):
            object.__setattr__(self, name, _text(name, getattr(self, name)))
        if (
            isinstance(self.expected_version, bool)
            or not isinstance(self.expected_version, int)
            or self.expected_version < 0
            or self.expected_version > MAX_SIGNED_64
        ):
            raise CommandSchemaError(
                "expected_version must be a signed 64-bit non-negative integer"
            )
        try:
            validate_rfc3339_utc_z("issued_at", self.issued_at)
        except EventSchemaError as exc:
            raise CommandSchemaError(str(exc)) from exc
        authorization = _mapping("authorization_context", self.authorization_context)
        input_value = _mapping("input", self.input)
        object.__setattr__(self, "authorization_context", authorization)
        object.__setattr__(self, "input", input_value)
        object.__setattr__(self, "input_hash", canonical_sha256(input_value))
        object.__setattr__(
            self,
            "command_hash",
            canonical_sha256(
                {
                    "actor": self.actor,
                    "authorization_context": authorization,
                    "causation_id": self.causation_id,
                    "command_id": self.command_id,
                    "command_type": self.command_type,
                    "correlation_id": self.correlation_id,
                    "cycle_id": self.cycle_id,
                    "expected_version": self.expected_version,
                    "input": input_value,
                    "input_hash": self.input_hash,
                    "issued_at": self.issued_at,
                    "schema_version": self.schema_version,
                }
            ),
        )


__all__ = ["CanonicalCommandEnvelope", "CommandSchemaError"]
