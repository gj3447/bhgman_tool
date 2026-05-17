"""OPA client integration tests (PROM 16 A6 — sidecar pattern).

Absorbed from SYMPOSIUM/THEORY/APT/gate_endpoint_prototype/tests/test_opa_client.py
(Wave 7 P3-H, 2026-05-14).

Tests use httpx.MockTransport — no actual OPA process required.
Production deployment would use subprocess OPA fixture with policies/.
"""

from __future__ import annotations
import json
import pytest

httpx = pytest.importorskip("httpx")


@pytest.fixture
def mock_opa_transport():
    """Return an httpx.MockTransport that simulates OPA Data API responses."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, text="OK")
        if request.url.path.startswith("/v1/data/"):
            body = json.loads(request.content) if request.content else {}
            input_doc = body.get("input", {})
            allow = input_doc.get("expected_count") == input_doc.get("actual_count")
            return httpx.Response(200, json={"result": {"allow": allow, "deny": []}})
        if request.url.path == "/v1/policies/reload":
            return httpx.Response(200, text="reloaded")
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_opa_client_health_ok(mock_opa_transport):
    from engine.gate.opa_client import OPAClient

    opa = OPAClient(base_url="http://opa-mock")
    opa._client = httpx.AsyncClient(transport=mock_opa_transport, base_url="http://opa-mock")
    try:
        assert await opa.health() is True
    finally:
        await opa._client.aclose()


@pytest.mark.asyncio
async def test_opa_eval_pass(mock_opa_transport):
    from engine.gate.opa_client import OPAClient

    opa = OPAClient(base_url="http://opa-mock")
    opa._client = httpx.AsyncClient(transport=mock_opa_transport, base_url="http://opa-mock")
    try:
        r = await opa.eval("apt.gate_check.G3.5", {"expected_count": 16, "actual_count": 16})
        assert r["result"]["allow"] is True
    finally:
        await opa._client.aclose()


@pytest.mark.asyncio
async def test_opa_eval_deny_on_mismatch(mock_opa_transport):
    from engine.gate.opa_client import OPAClient

    opa = OPAClient(base_url="http://opa-mock")
    opa._client = httpx.AsyncClient(transport=mock_opa_transport, base_url="http://opa-mock")
    try:
        r = await opa.eval("apt.gate_check.G3.5", {"expected_count": 16, "actual_count": 12})
        assert r["result"]["allow"] is False
    finally:
        await opa._client.aclose()


@pytest.mark.asyncio
async def test_opa_reload_bundle(mock_opa_transport):
    from engine.gate.opa_client import OPAClient

    opa = OPAClient(base_url="http://opa-mock")
    opa._client = httpx.AsyncClient(transport=mock_opa_transport, base_url="http://opa-mock")
    try:
        assert await opa.reload_bundle() is True
    finally:
        await opa._client.aclose()
