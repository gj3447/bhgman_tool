"""Canonical JSON primitives for deterministic APT event and state hashes.

KG: apt-tpa-legion-engine-canon-2026-06-12
KG: user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from enum import Enum
from types import MappingProxyType
from typing import TypeAlias, cast


class CanonicalEncodingError(ValueError):
    """Raised when a value cannot be represented by apt-canonical-json-v1."""


CanonicalScalar: TypeAlias = None | bool | int | str
CanonicalValue: TypeAlias = (
    CanonicalScalar | tuple["CanonicalValue", ...] | Mapping[str, "CanonicalValue"]
)


def normalize_text(value: str) -> str:
    """Return the NFC form used by every canonical runtime identity."""

    return unicodedata.normalize("NFC", value)


def deep_freeze(value: object) -> CanonicalValue:
    """Return a deeply immutable, NFC-normalized canonical value.

    Mappings become read-only mapping proxies and sequences become tuples.  The
    accepted scalar domain deliberately excludes floats: canonical JSON v1 only
    permits integer numbers (with JSON booleans handled separately).
    """

    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise CanonicalEncodingError("apt-canonical-json-v1 permits integers only")
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, Enum):
        return deep_freeze(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        return deep_freeze({field.name: getattr(value, field.name) for field in fields(value)})
    if isinstance(value, Mapping):
        normalized: dict[str, CanonicalValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalEncodingError("canonical mapping keys must be strings")
            normal_key = normalize_text(key)
            if normal_key in normalized:
                raise CanonicalEncodingError(
                    f"mapping contains duplicate key after NFC normalization: {normal_key!r}"
                )
            normalized[normal_key] = deep_freeze(item)
        return MappingProxyType(dict(sorted(normalized.items())))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(deep_freeze(item) for item in value)
    raise CanonicalEncodingError(f"unsupported canonical JSON value: {type(value).__name__}")


def _json_value(value: object) -> object:
    frozen = deep_freeze(value)
    if isinstance(frozen, Mapping):
        return {key: _json_value(item) for key, item in frozen.items()}
    if isinstance(frozen, tuple):
        return [_json_value(item) for item in frozen]
    return frozen


def canonical_json_bytes(value: object) -> bytes:
    """Encode *value* using apt-canonical-json-v1."""

    try:
        document = json.dumps(
            _json_value(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return document.encode("utf-8")
    except CanonicalEncodingError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise CanonicalEncodingError(f"canonical JSON encoding failed: {exc}") from exc


def canonical_sha256(value: object) -> str:
    """Return the lowercase SHA-256 digest of canonical JSON bytes."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def as_mapping(value: CanonicalValue) -> Mapping[str, CanonicalValue]:
    """Narrow a frozen canonical value to a mapping or fail clearly."""

    if not isinstance(value, Mapping):
        raise CanonicalEncodingError("expected a canonical mapping")
    return cast(Mapping[str, CanonicalValue], value)
