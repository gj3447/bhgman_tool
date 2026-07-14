"""Opt-in ooptdd-loop probe for a live Grok KG MCP SSE endpoint.

The capability URL is operational secret material.  It is never stored in source and
the live write probe is disabled unless an operator supplies both environment variables::

    BHGMAN_GROK_KG_LIVE_WRITE_PROBE=1
    BHGMAN_GROK_KG_MCP_SSE_URL=https://host.example/<capability>/

Importing this module or running the normal test suite performs no network or KG work.
When explicitly enabled, ``run_grok_kg_probe`` opens the SSE stream, discovers a same-origin
HTTPS messages endpoint, initializes MCP, checks the read/write tool surface, and performs one
parameterized CREATE/read/DELETE/residue-check round trip.  Cleanup and residue verification run
from a ``finally`` block, so an intermediate read failure cannot silently strand the probe node.

Each trace event is shipped only after the corresponding observed behavior.  The event-name
literals below remain in ``run_grok_kg_probe`` because the ooptdd Longinus gate binds them to that
symbol.

# KG: finding-grok-kg-mcp-endpoint-ooptdd-20260713
# KG: reference_grok_kg_mcp_endpoint_2026_07_13
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

_ENABLE_ENV = "BHGMAN_GROK_KG_LIVE_WRITE_PROBE"
_URL_ENV = "BHGMAN_GROK_KG_MCP_SSE_URL"
_KG_ANCHOR = "finding-grok-kg-mcp-endpoint-ooptdd-20260713"
_PROBE_LABEL = "GrokOoptddProbeTemp"
_MAX_SSE_LINE_BYTES = 1024 * 1024


def _ev(cid: str, event: str, **attrs: Any) -> dict[str, Any]:
    return {
        "cid": cid,
        "correlation_id": cid,
        "cycle_id": cid,
        "service": "grok-kg-endpoint",
        "event": event,
        **attrs,
    }


def _validate_sse_url(raw: str) -> str:
    """Accept only an absolute HTTPS capability URL without userinfo or a fragment."""
    if raw != raw.strip() or not raw:
        raise ValueError("SSE URL must be a non-empty value without surrounding whitespace")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in raw):
        raise ValueError("SSE URL must not contain control characters")
    try:
        parts = urlsplit(raw)
        _ = parts.port
    except ValueError as exc:
        raise ValueError("SSE URL is malformed") from exc
    if parts.scheme != "https":
        raise ValueError("SSE URL must use https")
    if not parts.hostname or parts.username is not None or parts.password is not None:
        raise ValueError("SSE URL must have a host and must not contain userinfo")
    if parts.fragment:
        raise ValueError("SSE URL must not contain a fragment")
    return raw


def _configured_sse_url(
    environ: Mapping[str, str] | None = None,
) -> tuple[str | None, str | None]:
    """Resolve explicit live-probe configuration without exposing the configured URL."""
    env = os.environ if environ is None else environ
    if env.get(_ENABLE_ENV) != "1":
        return None, f"live probe disabled; set {_ENABLE_ENV}=1 explicitly"
    raw = env.get(_URL_ENV)
    if not raw:
        return None, f"{_URL_ENV} is required when the live write probe is enabled"
    try:
        return _validate_sse_url(raw), None
    except ValueError as exc:
        return None, f"invalid {_URL_ENV}: {exc}"


def _redact_url(url: str) -> str:
    """Retain only origin metadata for summaries; capability/session paths stay secret."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "/<redacted>", "", ""))


def _same_origin_post_url(sse_url: str, advertised: str) -> str:
    """Resolve an SSE-advertised messages URL without accepting downgrade or cross-origin hops."""
    candidate = urljoin(sse_url, advertised)
    base = urlsplit(sse_url)
    post = urlsplit(candidate)

    def origin(parts: Any) -> tuple[str | None, int]:
        return parts.hostname, parts.port or 443

    if post.scheme != "https" or origin(post) != origin(base):
        raise ValueError("SSE messages endpoint must stay on the configured HTTPS origin")
    if post.username is not None or post.password is not None or post.fragment:
        raise ValueError("SSE messages endpoint contains forbidden URL components")
    return candidate


def _sanitized_env() -> dict[str, str]:
    """Keep the capability URL out of child-process environments and diagnostics."""
    env = dict(os.environ)
    env.pop(_URL_ENV, None)
    return env


def _curl_config(url: str) -> str:
    """Pass a URL to curl over stdin instead of exposing it in process arguments."""
    return f"url = {json.dumps(url)}\n"


def _curl(args: list[str], *, url: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["curl", "-sS", "--max-time", str(timeout), "--config", "-", *args],
        capture_output=True,
        env=_sanitized_env(),
        input=_curl_config(url),
        text=True,
        timeout=timeout + 5,
    )


def _check_no_downgrade(sse_url: str) -> tuple[bool, str]:
    """Probe the slash-less capability path without following redirects."""
    result = _curl(
        [
            "-o",
            "/dev/null",
            "--no-location",
            "-w",
            "%{http_code} %{redirect_url}",
        ],
        url=sse_url.rstrip("/"),
        timeout=12,
    )
    # A healthy SSE response stays open, so curl commonly reaches --max-time and exits 28
    # after already reporting HTTP 200.  No other transport failure is acceptable.
    if result.returncode not in {0, 28}:
        return False, f"curl_exit={result.returncode}"
    code, _, redirect = result.stdout.strip().partition(" ")
    downgraded = redirect.startswith("http://")
    redirect_scheme = urlsplit(redirect).scheme if redirect else "-"
    return (
        code == "200" and not downgraded,
        f"code={code} redirect_scheme={redirect_scheme}",
    )


def _stop_process(proc: subprocess.Popen[Any]) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


@dataclass
class _SseStream:
    """Deadline-aware reader for a binary curl SSE subprocess."""

    process: subprocess.Popen[bytes]
    _buffer: bytearray = field(default_factory=bytearray)

    def readline_until(self, deadline: float) -> str | None:
        """Return one line, an empty string at EOF, or ``None`` at the deadline."""
        stdout = self.process.stdout
        if stdout is None:
            raise RuntimeError("SSE process stdout is unavailable")

        while True:
            newline = self._buffer.find(b"\n")
            if newline >= 0:
                raw = bytes(self._buffer[: newline + 1])
                del self._buffer[: newline + 1]
                return raw.decode("utf-8", errors="replace")

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            readable, _, _ = select.select([stdout], [], [], remaining)
            if not readable:
                return None

            chunk = os.read(stdout.fileno(), 4096)
            if chunk:
                self._buffer.extend(chunk)
                newline = self._buffer.find(b"\n")
                line_size = newline + 1 if newline >= 0 else len(self._buffer)
                if line_size > _MAX_SSE_LINE_BYTES:
                    self._buffer.clear()
                    raise RuntimeError("SSE line exceeded the configured size limit")
                continue
            if self._buffer:
                raw = bytes(self._buffer)
                self._buffer.clear()
                return raw.decode("utf-8", errors="replace")
            return ""


def _open_sse_stream(sse_url: str) -> tuple[_SseStream, str | None]:
    """Open the configured SSE stream and resolve its advertised messages endpoint."""
    proc = subprocess.Popen(
        [
            "curl",
            "-sS",
            "-N",
            "--max-time",
            "180",
            "--config",
            "-",
            "-H",
            "Accept: text/event-stream",
        ],
        env=_sanitized_env(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.stdin is None or proc.stdout is None:
        _stop_process(proc)
        raise RuntimeError("SSE process did not expose required pipes")

    try:
        proc.stdin.write(_curl_config(sse_url).encode())
        proc.stdin.close()
        stream = _SseStream(proc)
        deadline = time.monotonic() + 15
        while True:
            line = stream.readline_until(deadline)
            if line is None or not line:
                break
            line = line.strip()
            if line.startswith("data:") and "/messages/" in line:
                advertised = line.split(":", 1)[1].strip()
                return stream, _same_origin_post_url(sse_url, advertised)
    except Exception:
        _stop_process(proc)
        raise
    return stream, None


def _post(post_url: str, obj: dict[str, Any]) -> None:
    result = _curl(
        [
            "-H",
            "Content-Type: application/json",
            "--data-binary",
            json.dumps(obj, separators=(",", ":")),
        ],
        url=post_url,
        timeout=12,
    )
    if result.returncode != 0:
        raise RuntimeError(f"MCP POST failed with curl exit {result.returncode}")


def _drain(stream: _SseStream, want_ids: set[int], timeout: int = 18) -> dict[int, dict[str, Any]]:
    """Read JSON-RPC responses off the SSE stream until every requested ID is seen."""
    out: dict[int, dict[str, Any]] = {}
    deadline = time.monotonic() + timeout
    while want_ids - set(out):
        line = stream.readline_until(deadline)
        if line is None or not line:
            break
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line.split(":", 1)[1].strip()
        if not payload.startswith("{"):
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        request_id = obj.get("id") if isinstance(obj, dict) else None
        if isinstance(request_id, int):
            out[request_id] = obj
    return out


def _rpc(
    stream: _SseStream,
    post_url: str,
    request_id: int,
    method: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    _post(
        post_url,
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
    )
    response = _drain(stream, {request_id}).get(request_id)
    if response is None:
        raise RuntimeError(f"MCP response {request_id} was not observed")
    if "error" in response:
        raise RuntimeError(f"MCP response {request_id} returned a JSON-RPC error")
    result = response.get("result")
    if isinstance(result, dict) and result.get("isError"):
        raise RuntimeError(f"MCP tool response {request_id} reported an error")
    return response


def _tool_call(
    stream: _SseStream,
    post_url: str,
    request_id: int,
    tool_name: str,
    query: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _rpc(
        stream,
        post_url,
        request_id,
        "tools/call",
        {
            "name": tool_name,
            "arguments": {"query": query, "params": params or {}},
        },
    )


def _text_result(response: dict[str, Any]) -> str:
    try:
        return response["result"]["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return ""


def _count_result(response: dict[str, Any], key: str) -> int | None:
    try:
        rows = json.loads(_text_result(response))
        value = rows[0][key]
    except (json.JSONDecodeError, IndexError, KeyError, TypeError):
        return None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _stat_result(response: dict[str, Any], key: str) -> int | None:
    """Extract one exact integer write statistic from a structured tool result."""
    try:
        parsed = json.loads(_text_result(response))
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, list) and len(parsed) == 1:
        parsed = parsed[0]
    if not isinstance(parsed, dict):
        return None
    value = parsed.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _error_name(exc: Exception) -> str:
    """Return a non-secret diagnostic; exception text may contain a configured URL."""
    return type(exc).__name__


def _write_roundtrip(stream: _SseStream, post_url: str, probe_id: str) -> dict[str, Any]:
    """Run one parameterized write probe and always attempt cleanup plus residue verification."""
    result: dict[str, Any] = {
        "created": False,
        "readback": None,
        "cleanup_attempted": False,
        "deleted": False,
        "residual": None,
    }
    params = {"cid": probe_id}
    try:
        created = _tool_call(
            stream,
            post_url,
            4,
            "write_neo4j_cypher",
            f"CREATE (x:{_PROBE_LABEL} {{cid:$cid}}) RETURN x",
            params,
        )
        result["created"] = _stat_result(created, "nodes_created") == 1
        readback = _tool_call(
            stream,
            post_url,
            5,
            "read_neo4j_cypher",
            f"MATCH (x:{_PROBE_LABEL} {{cid:$cid}}) RETURN count(x) AS c",
            params,
        )
        result["readback"] = _count_result(readback, "c")
    except Exception as exc:
        result["error"] = _error_name(exc)
    finally:
        result["cleanup_attempted"] = True
        try:
            deleted = _tool_call(
                stream,
                post_url,
                6,
                "write_neo4j_cypher",
                f"MATCH (x:{_PROBE_LABEL} {{cid:$cid}}) DELETE x",
                params,
            )
            result["deleted"] = _stat_result(deleted, "nodes_deleted") == 1
        except Exception as exc:
            result["cleanup_error"] = _error_name(exc)
        try:
            residue = _tool_call(
                stream,
                post_url,
                7,
                "read_neo4j_cypher",
                f"MATCH (x:{_PROBE_LABEL} {{cid:$cid}}) RETURN count(x) AS c",
                params,
            )
            result["residual"] = _count_result(residue, "c")
        except Exception as exc:
            result["cleanup_verify_error"] = _error_name(exc)

    result["ok"] = bool(
        result["created"]
        and result["readback"] == 1
        and result["deleted"]
        and result["residual"] == 0
        and "error" not in result
        and "cleanup_error" not in result
        and "cleanup_verify_error" not in result
    )
    return result


def run_grok_kg_probe(backend: Any, cid: str) -> dict[str, Any]:
    """Run the explicitly enabled live probe and ship only observed, residue-free evidence."""
    sse_url, config_error = _configured_sse_url()
    summary: dict[str, Any] = {"live_probe_enabled": sse_url is not None}
    if config_error or sse_url is None:
        summary["error"] = config_error
        return summary
    summary["endpoint"] = _redact_url(sse_url)

    try:
        ok, detail = _check_no_downgrade(sse_url)
    except Exception as exc:
        summary["error"] = _error_name(exc)
        return summary
    summary["https_check"] = detail
    if ok:
        backend.ship([_ev(cid, "grok_https_no_downgrade", detail=detail)])
    else:
        summary["error"] = "HTTPS capability check failed"
        return summary

    stream: _SseStream | None = None
    try:
        stream, post_url = _open_sse_stream(sse_url)
        summary["post_url"] = _redact_url(post_url) if post_url else None
        if not post_url:
            summary["error"] = "no endpoint event from SSE stream"
            return summary

        initialized = _rpc(
            stream,
            post_url,
            1,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "ooptdd-grok-probe", "version": "1"},
            },
        )
        _post(
            post_url,
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        )
        server = (initialized.get("result") or {}).get("serverInfo") or {}
        summary["serverInfo"] = server
        if server.get("name"):
            backend.ship(
                [
                    _ev(
                        cid,
                        "grok_sse_initialized",
                        server_name=server.get("name"),
                        server_version=server.get("version"),
                    )
                ]
            )

        listed = _rpc(stream, post_url, 2, "tools/list", {})
        tools = [
            tool.get("name")
            for tool in ((listed.get("result") or {}).get("tools") or [])
            if isinstance(tool, dict)
        ]
        summary["tools"] = tools
        has_tools = "read_neo4j_cypher" in tools and "write_neo4j_cypher" in tools
        if has_tools:
            backend.ship([_ev(cid, "grok_tools_readwrite", tools=tools)])
        else:
            summary["error"] = "required KG tools are absent"
            return summary

        read = _tool_call(
            stream,
            post_url,
            3,
            "read_neo4j_cypher",
            "MATCH (n) RETURN count(n) AS nodes",
        )
        node_count = _count_result(read, "nodes")
        summary["node_count"] = node_count
        if node_count is not None and node_count > 0:
            backend.ship([_ev(cid, "grok_kg_read_ok", node_count=node_count)])
        else:
            summary["error"] = "live KG read did not return a positive node count"
            return summary

        # The caller CID remains trace metadata only.  A random probe key prevents an
        # untrusted/oversized CID from entering even the parameter payload sent to the KG.
        probe_id = uuid.uuid4().hex
        roundtrip = _write_roundtrip(stream, post_url, probe_id)
        summary["write_roundtrip"] = roundtrip
        if roundtrip["ok"]:
            backend.ship(
                [
                    _ev(
                        cid,
                        "grok_kg_write_roundtrip",
                        created=True,
                        readback=1,
                        deleted=True,
                        residual=0,
                    )
                ]
            )
    except Exception as exc:
        summary["error"] = _error_name(exc)
    finally:
        if stream is not None:
            _stop_process(stream.process)

    return summary


__all__ = ["run_grok_kg_probe"]
