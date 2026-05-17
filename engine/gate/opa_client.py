"""OPA HTTP client integration (PROM 16 A6 finding scaffold).

Absorbed from SYMPOSIUM/THEORY/APT/gate_endpoint_prototype/opa_client.py
(Wave 7 P3-H, 2026-05-14).

Architecture: OPA sidecar pattern (≤10ms p99) on localhost:8181.
Policy bundles loaded from engine/gate/policies/ (apt_phase_gates / harness / taliban).

Usage:
    from engine.gate import OPAClient
    opa = OPAClient(base_url="http://localhost:8181")
    decision = await opa.eval("apt/phase_gates/sa_to_sp/allow", input_doc)

KG ref: PROM_16_A6_opa-gate-http-integration-2026-05-11
Reference: SYMPOSIUM/THEORY/APT/rfc/rfc-apt-v27-A9-opa-rego-full-2026-05-11.md
"""

from __future__ import annotations
import os
from typing import Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


OPA_DEFAULT_URL = os.environ.get("OPA_URL", "http://localhost:8181")
OPA_TIMEOUT_MS = int(os.environ.get("OPA_TIMEOUT_MS", "500"))


class OPAClient:
    """Async OPA Data API client with circuit-breaker semantics."""

    def __init__(self, base_url: str = OPA_DEFAULT_URL, timeout_ms: int = OPA_TIMEOUT_MS):
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_ms / 1000.0)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.05, max=0.5))
    async def eval(self, policy_path: str, input_doc: dict[str, Any]) -> dict[str, Any]:
        """
        Evaluate Rego policy.

        policy_path: e.g. "apt/phase_gates/sa_to_sp/allow" → POST /v1/data/apt/phase_gates/sa_to_sp/allow
        input_doc: input data injected into Rego eval (becomes `input` symbol)

        Returns: {"result": <decision>}  OR raises httpx.HTTPError
        """
        assert self._client is not None, "use within async context (`async with OPAClient(...)`)"
        path = policy_path.replace(".", "/")
        url = f"/v1/data/{path}"
        resp = await self._client.post(url, json={"input": input_doc})
        resp.raise_for_status()
        return resp.json()

    async def health(self) -> bool:
        """Returns True if OPA /health endpoint responds 200."""
        try:
            assert self._client is not None
            resp = await self._client.get("/health", timeout=httpx.Timeout(0.2))
            return resp.status_code == 200
        except Exception:
            return False

    async def reload_bundle(self) -> bool:
        """Trigger OPA to reload its policy bundle (hot-reload). No restart needed."""
        try:
            assert self._client is not None
            resp = await self._client.post("/v1/policies/reload")
            return resp.status_code == 200
        except Exception:
            return False


# Convenience: standalone factory for FastAPI lifespan injection
def build_opa_client(app=None) -> OPAClient:
    """Construct OPAClient (call within FastAPI lifespan or test fixture)."""
    return OPAClient()
