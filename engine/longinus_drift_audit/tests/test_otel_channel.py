"""Tests for OTel GenAI-semconv dispatch trace channel.

Pure mapping helpers (span_name / span_attributes) run WITHOUT the OpenTelemetry
SDK installed. Full span-emission is verified via an in-memory exporter, skipped
gracefully when ``[otel]`` is absent so the pre-commit ratchet never breaks.

# KG: finding-aidev-otel-dispatch-tracing-2026-05-25
"""

from __future__ import annotations

import pytest

from otel_channel import (
    BHGMAN_CARDINALITY_MATCH,
    BHGMAN_INTENT_N,
    GEN_AI_AGENT_NAME,
    GEN_AI_OPERATION_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_USAGE_INPUT_TOKENS,
    DispatchSpanRecord,
    dispatch_span,
    emit_dispatch,
    otel_available,
    span_attributes,
    span_name,
)


def _rec(
    *, intent_n: int = 16, actual_n: int = 16, model: str | None = "claude-haiku-4-5"
) -> DispatchSpanRecord:
    return DispatchSpanRecord(
        cycle_id="prom16-ai-dev-tools-2026-05-25",
        wave_index=0,
        agent_name="prom-research",
        intent_n=intent_n,
        actual_n=actual_n,
        model=model,
        input_tokens=1200,
    )


# ─── pure mapping (always runs, no SDK needed) ───────────────────────────


def test_span_name_genai_convention() -> None:
    assert span_name(_rec()) == "invoke_agent prom-research"


def test_span_attributes_genai_semconv_keys() -> None:
    attrs = span_attributes(_rec())
    assert attrs[GEN_AI_OPERATION_NAME] == "invoke_agent"
    assert attrs[GEN_AI_AGENT_NAME] == "prom-research"
    assert attrs[GEN_AI_REQUEST_MODEL] == "claude-haiku-4-5"
    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 1200
    assert attrs[BHGMAN_INTENT_N] == 16
    assert attrs[BHGMAN_CARDINALITY_MATCH] is True


def test_cardinality_mismatch_flag() -> None:
    attrs = span_attributes(_rec(intent_n=16, actual_n=14))
    assert attrs[BHGMAN_CARDINALITY_MATCH] is False


def test_optional_fields_omitted_when_none() -> None:
    attrs = span_attributes(_rec(model=None))
    assert GEN_AI_REQUEST_MODEL not in attrs  # null omitted, not emitted


def test_record_validation() -> None:
    with pytest.raises(Exception):
        DispatchSpanRecord(cycle_id="", wave_index=0, agent_name="x", intent_n=1, actual_n=1)
    with pytest.raises(Exception):
        DispatchSpanRecord(cycle_id="c", wave_index=-1, agent_name="x", intent_n=1, actual_n=1)


def test_otel_available_returns_bool() -> None:
    assert isinstance(otel_available(), bool)


# ─── graceful no-op when SDK absent ──────────────────────────────────────


@pytest.mark.skipif(otel_available(), reason="SDK present; no-op path not exercised")
def test_dispatch_span_noop_without_sdk() -> None:
    with dispatch_span(_rec()) as span:
        assert span is None  # body still runs, span is null
    assert emit_dispatch(_rec()) is False


# ─── full emission via in-memory exporter (skip if [otel] absent) ─────────


def _in_memory_tracer():
    sdk_trace = pytest.importorskip("opentelemetry.sdk.trace")
    export = pytest.importorskip("opentelemetry.sdk.trace.export")
    in_memory = pytest.importorskip("opentelemetry.sdk.trace.export.in_memory_span_exporter")

    provider = sdk_trace.TracerProvider()
    exporter = in_memory.InMemorySpanExporter()
    provider.add_span_processor(export.SimpleSpanProcessor(exporter))
    return provider.get_tracer("test"), exporter


def test_dispatch_span_emits_genai_span() -> None:
    tracer, exporter = _in_memory_tracer()
    with dispatch_span(_rec(), tracer=tracer) as span:
        assert span is not None
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    s = spans[0]
    assert s.name == "invoke_agent prom-research"
    assert s.attributes[GEN_AI_OPERATION_NAME] == "invoke_agent"
    assert s.attributes[BHGMAN_CARDINALITY_MATCH] is True


def test_dispatch_span_drift_event_on_mismatch() -> None:
    tracer, exporter = _in_memory_tracer()
    with dispatch_span(_rec(intent_n=16, actual_n=14), tracer=tracer):
        pass
    s = exporter.get_finished_spans()[0]
    assert s.attributes[BHGMAN_CARDINALITY_MATCH] is False
    event_names = [e.name for e in s.events]
    assert "gen_ai.dispatch.drift" in event_names


def test_emit_dispatch_one_shot() -> None:
    tracer, exporter = _in_memory_tracer()
    assert emit_dispatch(_rec(), tracer=tracer) is True
    assert len(exporter.get_finished_spans()) == 1
