"""Signed YAML/TOML config + HMAC config_hash binding.

PROM 16 P3(e): close A4 vulnerability (silent threshold mutation).
HMAC-SHA256(config_bytes, secret) → config_hash. Anyone who modifies the
threshold file without re-signing produces a hash mismatch.

DispatchDecision can include the config_hash in its HMAC payload so a
decision is bound to the config that produced it (W3C PROV).

# KG: actionplan-threshold-derivation-2026-05-30 P3(e)
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from pathlib import Path


_DEFAULT_SECRET = b"bhgman-dev-secret-2026-05-30"


def _secret() -> bytes:
    raw = os.environ.get("BHGMAN_THRESHOLD_HMAC_SECRET")
    if raw:
        return raw.encode("utf-8")
    return _DEFAULT_SECRET


@dataclass(frozen=True)
class SignedConfigDigest:
    """SHA-256 + HMAC binding of a config file."""

    config_path: str
    sha256: str
    hmac_sha256: str
    size_bytes: int
    method: str = "hmac_sha256_w3c_prov_2026_05_30"

    def to_kg_props(self) -> dict[str, str | int]:
        return {
            "config_path": self.config_path,
            "sha256": self.sha256,
            "hmac_sha256": self.hmac_sha256,
            "size_bytes": self.size_bytes,
            "method": self.method,
        }


def compute_digest(path: Path | str) -> SignedConfigDigest:
    """Compute SHA-256 + HMAC-SHA256 digest of the file at `path`."""
    p = Path(path)
    data = p.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    mac = hmac.new(_secret(), data, hashlib.sha256).hexdigest()
    return SignedConfigDigest(
        config_path=str(p),
        sha256=sha,
        hmac_sha256=mac,
        size_bytes=len(data),
    )


def verify_digest(digest: SignedConfigDigest) -> bool:
    """Verify that the file still matches the digest (HMAC + size + sha)."""
    p = Path(digest.config_path)
    if not p.is_file():
        return False
    data = p.read_bytes()
    if len(data) != digest.size_bytes:
        return False
    sha = hashlib.sha256(data).hexdigest()
    if not hmac.compare_digest(sha, digest.sha256):
        return False
    mac = hmac.new(_secret(), data, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, digest.hmac_sha256)


def bind_to_dispatch_payload(payload: dict, digest: SignedConfigDigest) -> dict:
    """Add config_hash binding to a DispatchDecision HMAC payload."""
    return {
        **payload,
        "config_hmac": digest.hmac_sha256,
        "config_path": digest.config_path,
    }
