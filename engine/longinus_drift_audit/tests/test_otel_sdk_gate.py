"""OTel availability must reflect the SDK, not just the API package.

``otel_available()`` documents itself as "True iff opentelemetry-{api,sdk} is
importable", and the whole module promises a *graceful no-op* when ``[otel]`` is
absent: ``emit_dispatch`` returns ``False``, ``dispatch_span`` yields ``None``.

But the import guard set ``_OTEL_AVAILABLE = True`` on ``from opentelemetry import
trace`` (the **API** package) alone. With the API present but the SDK absent — the
default state of this .venv — the global tracer hands back a ``NonRecordingSpan``
(``is_recording() == False``) that silently drops every attribute. So
``otel_available()`` returned True, ``emit_dispatch`` returned True (claiming a span
was emitted) and ``dispatch_span`` yielded a live-looking span — while NOTHING was
recorded. A silent observability lie, and the no-op contract test was skipped under a
false 'SDK present' reason.

# KG: finding-otel-availability-api-only-false-positive-2026-06-26
"""

from __future__ import annotations

import importlib.util

from engine.longinus_drift_audit.otel_channel import (
    DispatchSpanRecord,
    dispatch_span,
    emit_dispatch,
    otel_available,
)


def _sdk_importable() -> bool:
    return importlib.util.find_spec("opentelemetry.sdk") is not None


def _rec() -> DispatchSpanRecord:
    return DispatchSpanRecord(
        cycle_id="c1", wave_index=0, agent_name="scout", intent_n=1, actual_n=1
    )


def test_otel_available_reflects_sdk_presence_not_just_api() -> None:
    # otel_available() must track the SDK, not the API package alone — otherwise it
    # advertises a tracing capability that can only emit NonRecordingSpans.
    assert otel_available() is _sdk_importable()


def test_emit_dispatch_is_honest_noop_when_sdk_absent() -> None:
    # When the SDK is absent the only spans obtainable are non-recording, so emit_dispatch
    # must report the no-op truthfully (False), not claim success.
    if _sdk_importable():
        import pytest

        pytest.skip("SDK present — real emission path, not the no-op contract under test")
    assert emit_dispatch(_rec()) is False


def test_dispatch_span_yields_none_when_sdk_absent() -> None:
    # The documented no-op: dispatch_span yields None (null context) when [otel] is absent —
    # NOT a NonRecordingSpan that looks live but drops every set_attribute.
    if _sdk_importable():
        import pytest

        pytest.skip("SDK present — dispatch_span yields a real span")
    with dispatch_span(_rec()) as span:
        assert span is None
