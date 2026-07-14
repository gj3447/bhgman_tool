"""Cryptographic head anchor shared by durable effect-queue journals.

The mutable lease/usage projections and the append-only journal are not enough
to expose a coordinated tail truncation.  Each lease therefore has a separate
transactional head row whose digest commits to every preceding journal entry.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from engine.apt_runtime.domain.canonical import MAX_SIGNED_64, canonical_sha256


GENESIS_JOURNAL_HASH = "0" * 64
_CHAIN_FORMAT = "apt-effect-journal-chain-v1"
JournalChainEntry: TypeAlias = tuple[int, str, str, str]


@dataclass(frozen=True, slots=True)
class JournalHead:
    """Expected durable head for one lease journal."""

    position: int
    digest: str


def _digest_text(name: str, value: object) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    if any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _entry_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError(f"journal {name} must be a non-empty string")
    return value


def advance_journal_head(
    previous: JournalHead,
    *,
    lease_token: str,
    action: str,
    occurred_at: str,
    detail_hash: str,
) -> JournalHead:
    """Commit one typed journal envelope to the preceding chain head."""

    if previous.position >= MAX_SIGNED_64:
        raise ValueError("effect journal position exceeds signed 64-bit range")
    position = previous.position + 1
    digest = canonical_sha256(
        {
            "action": _entry_text("action", action),
            "chain_format": _CHAIN_FORMAT,
            "detail_hash": _digest_text("detail_hash", detail_hash),
            "journal_position": position,
            "lease_token": _entry_text("lease_token", lease_token),
            "occurred_at": _entry_text("occurred_at", occurred_at),
            "previous_hash": _digest_text("previous_hash", previous.digest),
        }
    )
    return JournalHead(position=position, digest=digest)


def replay_journal_head(lease_token: str, entries: tuple[JournalChainEntry, ...]) -> JournalHead:
    """Recompute an exact contiguous head from durable journal envelopes."""

    checkpoints = replay_journal_checkpoints(lease_token, entries)
    if checkpoints:
        return checkpoints[-1]
    return JournalHead(position=0, digest=GENESIS_JOURNAL_HASH)


def replay_journal_checkpoints(
    lease_token: str, entries: tuple[JournalChainEntry, ...]
) -> tuple[JournalHead, ...]:
    """Recompute every immutable prefix checkpoint for one journal."""

    head = JournalHead(position=0, digest=GENESIS_JOURNAL_HASH)
    checkpoints: list[JournalHead] = []
    for expected, entry in enumerate(entries, start=1):
        position, action, occurred_at, detail_hash = entry
        if isinstance(position, bool) or position != expected:
            raise ValueError("journal positions are not contiguous from one")
        head = advance_journal_head(
            head,
            lease_token=lease_token,
            action=action,
            occurred_at=occurred_at,
            detail_hash=detail_hash,
        )
        checkpoints.append(head)
    return tuple(checkpoints)


__all__ = [
    "GENESIS_JOURNAL_HASH",
    "JournalChainEntry",
    "JournalHead",
    "advance_journal_head",
    "replay_journal_checkpoints",
    "replay_journal_head",
]
