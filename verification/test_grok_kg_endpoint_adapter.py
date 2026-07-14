"""Deterministic safety tests for the opt-in Grok KG live-probe adapter.

Every transport seam is replaced with a fake.  These tests must never contact a live endpoint.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from types import SimpleNamespace
from typing import Any

import pytest

from ooptdd import grok_kg_endpoint_adapter as adapter


class FakeBackend:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def ship(self, events: list[dict[str, Any]]) -> None:
        self.events.extend(events)


class FakeProcess:
    stdout = None

    def __init__(self) -> None:
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: int = 0) -> int:  # noqa: ARG002
        return 0

    def kill(self) -> None:
        self.killed = True


class FakeStream:
    def __init__(self, process: FakeProcess | None = None) -> None:
        self.process = process or FakeProcess()


def _tool_text(text: str) -> dict[str, Any]:
    return {
        "result": {
            "content": [{"type": "text", "text": text}],
            "isError": False,
        }
    }


def _forbid_transport(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("disabled probe touched a transport seam")


def test_probe_is_disabled_without_exact_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(adapter._ENABLE_ENV, raising=False)
    monkeypatch.delenv(adapter._URL_ENV, raising=False)
    monkeypatch.setattr(adapter, "_check_no_downgrade", _forbid_transport)
    monkeypatch.setattr(adapter, "_open_sse_stream", _forbid_transport)
    backend = FakeBackend()

    result = adapter.run_grok_kg_probe(backend, "disabled")

    assert result["live_probe_enabled"] is False
    assert adapter._ENABLE_ENV in result["error"]
    assert backend.events == []


def test_enabled_probe_requires_secret_https_url() -> None:
    url, error = adapter._configured_sse_url({adapter._ENABLE_ENV: "1"})
    assert url is None and adapter._URL_ENV in error

    url, error = adapter._configured_sse_url(
        {adapter._ENABLE_ENV: "1", adapter._URL_ENV: "http://kg.example/cap/"}
    )
    assert url is None and "must use https" in error

    secret = "https://kg.example/runtime-secret/"
    url, error = adapter._configured_sse_url({adapter._ENABLE_ENV: "1", adapter._URL_ENV: secret})
    assert (url, error) == (secret, None)
    assert "runtime-secret" not in adapter._redact_url(secret)


@pytest.mark.parametrize(
    "advertised",
    [
        "http://kg.example/messages/session",
        "https://other.example/messages/session",
    ],
)
def test_messages_endpoint_cannot_downgrade_or_cross_origin(advertised: str) -> None:
    with pytest.raises(ValueError, match="configured HTTPS origin"):
        adapter._same_origin_post_url("https://kg.example/runtime-secret/", advertised)


def test_downgrade_diagnostic_never_echoes_redirect_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = subprocess.CompletedProcess(
        args=["curl"],
        returncode=0,
        stdout="307 https://kg.example/runtime-secret/",
        stderr="",
    )
    monkeypatch.setattr(adapter, "_curl", lambda *_args, **_kwargs: completed)

    ok, detail = adapter._check_no_downgrade("https://kg.example/runtime-secret/")

    assert ok is False
    assert detail == "code=307 redirect_scheme=https"
    assert "runtime-secret" not in detail


def test_https_check_accepts_expected_sse_stream_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = subprocess.CompletedProcess(
        args=["curl"],
        returncode=28,
        stdout="200 ",
        stderr="curl: (28) operation timed out",
    )
    monkeypatch.setattr(adapter, "_curl", lambda *_args, **_kwargs: completed)

    ok, detail = adapter._check_no_downgrade("https://kg.example/runtime-secret/")

    assert ok is True
    assert detail == "code=200 redirect_scheme=-"


def test_https_check_rejects_other_transport_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = subprocess.CompletedProcess(
        args=["curl"],
        returncode=7,
        stdout="200 ",
        stderr="connection failed",
    )
    monkeypatch.setattr(adapter, "_curl", lambda *_args, **_kwargs: completed)

    ok, detail = adapter._check_no_downgrade("https://kg.example/runtime-secret/")

    assert ok is False
    assert detail == "curl_exit=7"


def test_curl_receives_secret_url_only_over_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "https://kg.example/runtime-secret/"
    monkeypatch.setenv(adapter._URL_ENV, secret)
    observed: dict[str, Any] = {}

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        observed["args"] = args
        observed.update(kwargs)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(adapter.subprocess, "run", fake_run)

    adapter._curl(["-o", "/dev/null"], url=secret, timeout=1)

    assert all(secret not in arg for arg in observed["args"])
    assert adapter._URL_ENV not in observed["env"]
    assert all(secret not in value for value in observed["env"].values())
    assert observed["input"] == adapter._curl_config(secret)
    assert observed["args"][-2:] == ["-o", "/dev/null"]


def test_sse_process_receives_capability_only_over_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "https://kg.example/runtime-secret/"
    monkeypatch.setenv(adapter._URL_ENV, secret)
    observed: dict[str, Any] = {}

    class RecordingStdin:
        def __init__(self) -> None:
            self.data = bytearray()
            self.closed = False

        def write(self, data: bytes) -> int:
            self.data.extend(data)
            return len(data)

        def close(self) -> None:
            self.closed = True

    class CapturingProcess(FakeProcess):
        def __init__(self) -> None:
            super().__init__()
            self.stdin = RecordingStdin()
            self.stdout = object()

    process = CapturingProcess()

    def fake_popen(args: list[str], **kwargs: Any) -> CapturingProcess:
        observed["args"] = args
        observed.update(kwargs)
        return process

    class OpenedStream:
        def __init__(self, opened_process: CapturingProcess) -> None:
            self.process = opened_process

        def readline_until(self, _deadline: float) -> str:
            return "data: /messages/session-secret\n"

    monkeypatch.setattr(adapter.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(adapter, "_SseStream", OpenedStream)

    stream, post_url = adapter._open_sse_stream(secret)

    assert stream.process is process
    assert post_url == "https://kg.example/messages/session-secret"
    assert all(secret not in arg for arg in observed["args"])
    assert adapter._URL_ENV not in observed["env"]
    assert all(secret not in value for value in observed["env"].values())
    assert bytes(process.stdin.data).decode() == adapter._curl_config(secret)
    assert process.stdin.closed is True


def test_sse_reader_honors_deadline_without_waiting_for_output() -> None:
    read_fd, write_fd = os.pipe()
    reader = os.fdopen(read_fd, "rb", buffering=0)
    try:
        stream = adapter._SseStream(SimpleNamespace(stdout=reader))
        started = time.monotonic()

        line = stream.readline_until(started + 0.02)

        assert line is None
        assert time.monotonic() - started < 0.25
    finally:
        os.close(write_fd)
        reader.close()


def test_sse_reader_rejects_oversize_line_without_newline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = SimpleNamespace(fileno=lambda: 123)
    stream = adapter._SseStream(SimpleNamespace(stdout=stdout))
    monkeypatch.setattr(adapter.select, "select", lambda *_args: ([stdout], [], []))
    monkeypatch.setattr(adapter.os, "read", lambda *_args: b"x" * (adapter._MAX_SSE_LINE_BYTES + 1))

    with pytest.raises(RuntimeError, match="size limit"):
        stream.readline_until(time.monotonic() + 1)

    assert stream._buffer == bytearray()


def test_failed_https_check_stops_before_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(adapter._ENABLE_ENV, "1")
    monkeypatch.setenv(adapter._URL_ENV, "https://kg.example/runtime-secret/")
    monkeypatch.setattr(
        adapter,
        "_check_no_downgrade",
        lambda _url: (False, "code=307 redirect_scheme=http"),
    )
    monkeypatch.setattr(adapter, "_open_sse_stream", _forbid_transport)
    backend = FakeBackend()

    result = adapter.run_grok_kg_probe(backend, "downgrade")

    assert result["error"] == "HTTPS capability check failed"
    assert backend.events == []


def test_unverified_live_read_stops_before_write(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(adapter._ENABLE_ENV, "1")
    monkeypatch.setenv(adapter._URL_ENV, "https://kg.example/runtime-secret/")
    monkeypatch.setattr(adapter, "_check_no_downgrade", lambda _url: (True, "code=200"))
    process = FakeProcess()
    stream = FakeStream(process)
    monkeypatch.setattr(
        adapter,
        "_open_sse_stream",
        lambda _url: (stream, "https://kg.example/messages/session"),
    )
    monkeypatch.setattr(adapter, "_post", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(adapter, "_write_roundtrip", _forbid_transport)

    def fake_rpc(
        _proc: Any,
        _post_url: str,
        request_id: int,
        _method: str,
        _params: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            1: {"result": {"serverInfo": {"name": "fake"}}},
            2: {
                "result": {
                    "tools": [
                        {"name": "read_neo4j_cypher"},
                        {"name": "write_neo4j_cypher"},
                    ]
                }
            },
            3: _tool_text('[{"nodes":0}]'),
        }[request_id]

    monkeypatch.setattr(adapter, "_rpc", fake_rpc)

    result = adapter.run_grok_kg_probe(FakeBackend(), "empty")

    assert result["error"] == "live KG read did not return a positive node count"
    assert process.terminated is True


def test_write_roundtrip_uses_parameters_and_verifies_zero_residue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, dict[str, Any]]] = []

    def fake_rpc(
        _proc: Any,
        _post_url: str,
        request_id: int,
        _method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        calls.append((request_id, params))
        return {
            4: _tool_text('{"nodes_created":1}'),
            5: _tool_text('[{"c":1}]'),
            6: _tool_text('{"nodes_deleted":1}'),
            7: _tool_text('[{"c":0}]'),
        }[request_id]

    monkeypatch.setattr(adapter, "_rpc", fake_rpc)
    probe_id = "quoted-'cid}-must-not-enter-query"

    result = adapter._write_roundtrip(FakeStream(), "https://kg.example/messages/1", probe_id)

    assert result == {
        "created": True,
        "readback": 1,
        "cleanup_attempted": True,
        "deleted": True,
        "residual": 0,
        "ok": True,
    }
    assert [request_id for request_id, _ in calls] == [4, 5, 6, 7]
    for _request_id, rpc_params in calls:
        arguments = rpc_params["arguments"]
        assert "$cid" in arguments["query"]
        assert probe_id not in arguments["query"]
        assert arguments["params"] == {"cid": probe_id}


def test_intermediate_failure_still_deletes_and_checks_residue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[int] = []

    def fake_rpc(
        _proc: Any,
        _post_url: str,
        request_id: int,
        _method: str,
        _params: dict[str, Any],
    ) -> dict[str, Any]:
        seen.append(request_id)
        if request_id == 5:
            raise RuntimeError("simulated read failure")
        return {
            4: _tool_text('{"nodes_created":1}'),
            6: _tool_text('{"nodes_deleted":1}'),
            7: _tool_text('[{"c":0}]'),
        }[request_id]

    monkeypatch.setattr(adapter, "_rpc", fake_rpc)

    result = adapter._write_roundtrip(FakeStream(), "https://kg.example/messages/1", "probe")

    assert seen == [4, 5, 6, 7]
    assert result["cleanup_attempted"] is True
    assert result["deleted"] is True and result["residual"] == 0
    assert result["error"] == "RuntimeError"
    assert result["ok"] is False


def test_nonzero_residue_never_earns_roundtrip_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_rpc(
        _proc: Any,
        _post_url: str,
        request_id: int,
        _method: str,
        _params: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            4: _tool_text('{"nodes_created":1}'),
            5: _tool_text('[{"c":1}]'),
            6: _tool_text('{"nodes_deleted":1}'),
            7: _tool_text('[{"c":1}]'),
        }[request_id]

    monkeypatch.setattr(adapter, "_rpc", fake_rpc)

    result = adapter._write_roundtrip(FakeStream(), "https://kg.example/messages/1", "probe")

    assert result["residual"] == 1
    assert result["ok"] is False


@pytest.mark.parametrize(
    ("created_text", "deleted_text", "expected_created", "expected_deleted"),
    [
        ('{"nodes_created":0}', '{"nodes_deleted":1}', False, True),
        ("mentions nodes_created but is not JSON", '{"nodes_deleted":1}', False, True),
        ('{"nodes_created":1}', '{"nodes_deleted":0}', True, False),
        ('{"nodes_created":1}', "mentions nodes_deleted but is not JSON", True, False),
    ],
)
def test_write_stats_must_be_exactly_one(
    monkeypatch: pytest.MonkeyPatch,
    created_text: str,
    deleted_text: str,
    expected_created: bool,
    expected_deleted: bool,
) -> None:
    def fake_rpc(
        _stream: Any,
        _post_url: str,
        request_id: int,
        _method: str,
        _params: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            4: _tool_text(created_text),
            5: _tool_text('[{"c":1}]'),
            6: _tool_text(deleted_text),
            7: _tool_text('[{"c":0}]'),
        }[request_id]

    monkeypatch.setattr(adapter, "_rpc", fake_rpc)

    result = adapter._write_roundtrip(FakeStream(), "https://kg.example/messages/1", "probe")

    assert result["ok"] is False
    assert result["created"] is expected_created
    assert result["deleted"] is expected_deleted


def test_enabled_flow_is_fully_fake_and_redacts_runtime_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capability_url = "https://kg.example/runtime-secret/"
    post_url = "https://kg.example/messages/session-secret"
    monkeypatch.setenv(adapter._ENABLE_ENV, "1")
    monkeypatch.setenv(adapter._URL_ENV, capability_url)
    monkeypatch.setattr(adapter, "_check_no_downgrade", lambda _url: (True, "code=200"))
    process = FakeProcess()
    stream = FakeStream(process)
    monkeypatch.setattr(adapter, "_open_sse_stream", lambda _url: (stream, post_url))
    monkeypatch.setattr(adapter.uuid, "uuid4", lambda: SimpleNamespace(hex="fixed"))
    notifications: list[dict[str, Any]] = []
    monkeypatch.setattr(adapter, "_post", lambda _url, payload: notifications.append(payload))
    calls: list[tuple[int, dict[str, Any]]] = []

    def fake_rpc(
        _proc: Any,
        _post_url: str,
        request_id: int,
        _method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        calls.append((request_id, params))
        return {
            1: {"result": {"serverInfo": {"name": "fake", "version": "1"}}},
            2: {
                "result": {
                    "tools": [
                        {"name": "read_neo4j_cypher"},
                        {"name": "write_neo4j_cypher"},
                    ]
                }
            },
            3: _tool_text('[{"nodes":2}]'),
            4: _tool_text('{"nodes_created":1}'),
            5: _tool_text('[{"c":1}]'),
            6: _tool_text('{"nodes_deleted":1}'),
            7: _tool_text('[{"c":0}]'),
        }[request_id]

    monkeypatch.setattr(adapter, "_rpc", fake_rpc)
    backend = FakeBackend()

    result = adapter.run_grok_kg_probe(backend, "cycle")

    assert result["live_probe_enabled"] is True
    assert result["write_roundtrip"]["ok"] is True
    assert process.terminated is True
    assert notifications == [
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
    ]
    assert [event["event"] for event in backend.events] == [
        "grok_https_no_downgrade",
        "grok_sse_initialized",
        "grok_tools_readwrite",
        "grok_kg_read_ok",
        "grok_kg_write_roundtrip",
    ]
    assert [request_id for request_id, _params in calls] == [1, 2, 3, 4, 5, 6, 7]
    assert calls[3][1]["arguments"]["params"] == {"cid": "fixed"}
    serialized = json.dumps(result)
    assert "runtime-secret" not in serialized
    assert "session-secret" not in serialized
