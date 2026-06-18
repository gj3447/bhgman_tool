"""OTel GenAI-semconv dispatch trace channel (Wave 12, 2026-05-25).

Emits subagent dispatch as OpenTelemetry **GenAI semantic-convention** spans so
ephemeral subagent runs become first-class, vendor-neutral traces (OTLP →
Jaeger / Honeycomb / GCP Cloud Trace / Datadog) *in addition to* the KG
``:DispatchHyperedge`` / ``:SourceCodeDriftEvent`` records that
:mod:`dispatch_audit` already writes.

Sibling of :mod:`prov_channel` / :mod:`intoto_channel` / :mod:`urdna2015_channel`:
where those emit provenance to W3C PROV / in-toto / RDF-canonical, this channel
emits to the OpenTelemetry GenAI semantic conventions (the ``gen_ai.*``
attribute family). The KG channel answers "what was the causal graph"; this
channel answers "what was the live latency / token / call topology" for
operational observability backends.

OpenTelemetry GenAI semconv (subset used; see
https://opentelemetry.io/docs/specs/semconv/gen-ai/):
    - ``gen_ai.operation.name``  : "invoke_agent" | "create_agent"
    - ``gen_ai.system``          : provider id (e.g. "anthropic")
    - ``gen_ai.agent.name``      : subagent role / name
    - ``gen_ai.request.model``   : model id (e.g. "claude-haiku-4-5")
    - ``gen_ai.usage.input_tokens`` / ``gen_ai.usage.output_tokens``
    span name convention: ``"{operation} {agent.name}"``
Plus bhgman-native attributes mirroring the :mod:`dispatch_audit` cardinality
invariant (canonical: ``SKILLS/jaebaeman/references/validation.md`` V5,
GH anthropics/claude-code#29181):
    - ``bhgman.cycle_id`` / ``bhgman.wave_index``
    - ``bhgman.intent_n`` / ``bhgman.actual_n`` / ``bhgman.cardinality_match``

**OPTIONAL DEPENDENCY** ``opentelemetry-{api,sdk}`` (install via
``pip install bhgman_tool[otel]``). When absent, every entry point is a graceful
no-op: :func:`dispatch_span` yields ``None`` (null context), :func:`emit_dispatch`
and :func:`record_active_drift_event` return ``False``. Core dispatch is never
coupled to OTel, and the pure mapping helpers (:func:`span_name`,
:func:`span_attributes`) are importable + testable without the SDK installed.

# KG: finding-aidev-otel-dispatch-tracing-2026-05-25 (PROM 16 prom16-ai-dev-tools cycle, lever ①)
# KG: 재배맨-v2-subagent-runtime-protocol (cardinality invariant source)
"""

from __future__ import annotations

import contextlib
from typing import Any, Iterator, Optional

from pydantic import BaseModel, Field

try:  # optional-dependency guard — bhgman_tool[otel]
    from opentelemetry import trace as _otel_trace
    from opentelemetry.trace import Status, StatusCode

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only in non-[otel] envs
    _otel_trace = None  # type: ignore[assignment]
    Status = StatusCode = None  # type: ignore[assignment,misc]
    _OTEL_AVAILABLE = False


# ─── GenAI semantic-convention attribute keys ────────────────────────────

GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_AGENT_NAME = "gen_ai.agent.name"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"

# bhgman-native attributes (cardinality invariant mirror)
BHGMAN_CYCLE_ID = "bhgman.cycle_id"
BHGMAN_WAVE_INDEX = "bhgman.wave_index"
BHGMAN_INTENT_N = "bhgman.intent_n"
BHGMAN_ACTUAL_N = "bhgman.actual_n"
BHGMAN_CARDINALITY_MATCH = "bhgman.cardinality_match"

_DRIFT_EVENT_NAME = "gen_ai.dispatch.drift"
_TRACER_NAME = "bhgman_tool.dispatch"

# Operation names allowed by GenAI semconv for agent spans.
_VALID_OPERATIONS = {"invoke_agent", "create_agent", "execute_tool"}


class DispatchSpanRecord(BaseModel):
    # KG: ATOM_Skill_longinus
    """A finished (or about-to-run) subagent dispatch, projected to GenAI semconv.

    ``intent_n`` / ``actual_n`` mirror :class:`dispatch_audit.DispatchAuditor`
    cardinality (jaebaeman V5). ``cardinality_match`` is derived, not stored.
    """

    cycle_id: str = Field(min_length=1)
    wave_index: int = Field(ge=0)
    agent_name: str = Field(min_length=1)
    operation: str = "invoke_agent"
    system: str = "anthropic"
    model: Optional[str] = None
    intent_n: int = Field(ge=0)
    actual_n: int = Field(ge=0)
    input_tokens: Optional[int] = Field(default=None, ge=0)
    output_tokens: Optional[int] = Field(default=None, ge=0)

    @property
    def cardinality_match(self) -> bool:
        return self.intent_n == self.actual_n


def otel_available() -> bool:
    # KG: ATOM_Skill_longinus
    """True iff ``opentelemetry-{api,sdk}`` is importable (``[otel]`` installed)."""
    return _OTEL_AVAILABLE


def span_name(record: DispatchSpanRecord) -> str:
    # KG: ATOM_Skill_longinus
    """GenAI span-name convention: ``"{operation} {agent.name}"`` (pure)."""
    return f"{record.operation} {record.agent_name}"


def span_attributes(record: DispatchSpanRecord) -> dict[str, Any]:
    # KG: ATOM_Skill_longinus
    """Project a dispatch record to GenAI-semconv + bhgman attributes (pure).

    None-valued optional fields (model, token usage) are omitted rather than
    emitted as null, per OTel attribute conventions. Importable and testable
    without the OpenTelemetry SDK installed.
    """
    attrs: dict[str, Any] = {
        GEN_AI_OPERATION_NAME: record.operation,
        GEN_AI_SYSTEM: record.system,
        GEN_AI_AGENT_NAME: record.agent_name,
        BHGMAN_CYCLE_ID: record.cycle_id,
        BHGMAN_WAVE_INDEX: record.wave_index,
        BHGMAN_INTENT_N: record.intent_n,
        BHGMAN_ACTUAL_N: record.actual_n,
        BHGMAN_CARDINALITY_MATCH: record.cardinality_match,
    }
    if record.model is not None:
        attrs[GEN_AI_REQUEST_MODEL] = record.model
    if record.input_tokens is not None:
        attrs[GEN_AI_USAGE_INPUT_TOKENS] = record.input_tokens
    if record.output_tokens is not None:
        attrs[GEN_AI_USAGE_OUTPUT_TOKENS] = record.output_tokens
    return attrs


def get_tracer(name: str = _TRACER_NAME):  # type: ignore[no-untyped-def]
    # KG: ATOM_Skill_longinus
    """Return the OpenTelemetry tracer, or ``None`` when ``[otel]`` is absent.

    Uses the globally-configured TracerProvider (the host application is
    responsible for wiring an OTLP exporter, e.g. via
    ``OTEL_EXPORTER_OTLP_ENDPOINT`` + ``opentelemetry-sdk``). No global state
    is mutated here.
    """
    if not _OTEL_AVAILABLE:
        return None
    return _otel_trace.get_tracer(name)


@contextlib.contextmanager
def dispatch_span(
    record: DispatchSpanRecord,
    *,
    tracer=None,  # type: ignore[no-untyped-def]
) -> Iterator[Optional[Any]]:
    # KG: ATOM_Skill_longinus
    """Context manager wrapping a live dispatch as a GenAI span.

    Usage (in the orchestration / runtime layer)::

        with dispatch_span(rec) as span:
            result = run_subagent(...)   # span times the real work

    When ``[otel]`` is absent, yields ``None`` (the body still runs). On a
    cardinality mismatch the span is tagged with a ``gen_ai.dispatch.drift``
    event and ERROR status, mirroring :meth:`dispatch_audit.DispatchAuditor.record_drift`.
    """
    tr = tracer if tracer is not None else get_tracer()
    if tr is None:
        yield None
        return
    with tr.start_as_current_span(span_name(record)) as span:
        for key, value in span_attributes(record).items():
            span.set_attribute(key, value)
        if not record.cardinality_match:
            _add_drift_event(span, record)
            span.set_status(Status(StatusCode.ERROR, "dispatch cardinality mismatch"))
        else:
            span.set_status(Status(StatusCode.OK))
        yield span


def emit_dispatch(
    record: DispatchSpanRecord,
    *,
    tracer=None,  # type: ignore[no-untyped-def]
) -> bool:
    # KG: ATOM_Skill_longinus
    """Emit a one-shot span for an already-finished dispatch (post-hoc).

    Returns ``True`` if a span was emitted, ``False`` on graceful no-op
    (``[otel]`` absent). Suitable for ``audit_runner`` to call after a wave
    completes when live wrapping via :func:`dispatch_span` was not used.
    """
    tr = tracer if tracer is not None else get_tracer()
    if tr is None:
        return False
    span = tr.start_span(span_name(record))
    try:
        for key, value in span_attributes(record).items():
            span.set_attribute(key, value)
        if not record.cardinality_match:
            _add_drift_event(span, record)
            span.set_status(Status(StatusCode.ERROR, "dispatch cardinality mismatch"))
        else:
            span.set_status(Status(StatusCode.OK))
    finally:
        span.end()
    return True


def record_active_drift_event(
    *,
    cycle_id: str,
    wave_index: int,
    intent_n: int,
    actual_n: int,
    severity: str,
    note: Optional[str] = None,
) -> bool:
    # KG: ATOM_Skill_longinus
    """Attach a ``gen_ai.dispatch.drift`` event to the *currently-active* span.

    Called from :meth:`dispatch_audit.DispatchAuditor.record_drift` so that drift
    surfaces in the trace whenever a span is active. Returns ``False`` (no-op)
    when ``[otel]`` is absent or no recording span is in context.
    """
    if not _OTEL_AVAILABLE:
        return False
    span = _otel_trace.get_current_span()
    if span is None or not span.is_recording():
        return False
    attrs: dict[str, Any] = {
        BHGMAN_CYCLE_ID: cycle_id,
        BHGMAN_WAVE_INDEX: wave_index,
        BHGMAN_INTENT_N: intent_n,
        BHGMAN_ACTUAL_N: actual_n,
        "bhgman.drift.severity": severity,
    }
    if note is not None:
        attrs["bhgman.drift.note"] = note
    span.add_event(_DRIFT_EVENT_NAME, attributes=attrs)
    return True


def _add_drift_event(span, record: DispatchSpanRecord) -> None:  # type: ignore[no-untyped-def]
    severity = "P1_underdispatch" if record.intent_n > record.actual_n else "P2_overdispatch"
    span.add_event(
        _DRIFT_EVENT_NAME,
        attributes={
            BHGMAN_CYCLE_ID: record.cycle_id,
            BHGMAN_WAVE_INDEX: record.wave_index,
            BHGMAN_INTENT_N: record.intent_n,
            BHGMAN_ACTUAL_N: record.actual_n,
            "bhgman.drift.severity": severity,
        },
    )
