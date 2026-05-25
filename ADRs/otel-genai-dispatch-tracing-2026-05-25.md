# ADR: OTel GenAI-semconv dispatch trace channel

- **Status**: IMPLEMENTED (PRELIMINARY — awaiting user CANONICAL verdict)
- **Date**: 2026-05-25
- **KG ref**: `finding-aidev-otel-dispatch-tracing-2026-05-25`
- **Parent driver**: PROM 16 cycle `prom16-ai-dev-tools-2026-05-25` lever ① (OTel GenAI semconv flagged "directly applicable to our tools"); cross-cut consensus C2/C5 (MCP-era observability, "evals/traces as first-class").
- **Layer**: Harness Tier 2 (application runtime) — bhgman_tool as the engineering crystallization of 비행기맨 (#4).

---

## Context

bhgman_tool already records subagent dispatch to the KG (`:DispatchHyperedge`,
`:SourceCodeDriftEvent` via `engine/longinus_drift_audit/dispatch_audit.py`). But
the KG channel is **causal-graph only** — there was no export to operational
observability backends (OTLP → Jaeger / Honeycomb / GCP Cloud Trace / Datadog),
and no alignment with the now-standardizing **OpenTelemetry GenAI semantic
conventions** (`gen_ai.*` attribute family; CNCF, adopted by GCP/AWS/Azure/Datadog).

This is the tool's own value proposition ("ephemeral subagent runs become
first-class, auditable records") meeting an industry standard — a clean,
vendor-neutral amplification rather than a new abstraction.

## Decision

Add an `otel_channel` **sibling to the existing `prov_channel` / `intoto_channel`
/ `urdna2015_channel` provenance channels**: it projects a dispatch to an
OpenTelemetry GenAI-semconv span (`gen_ai.operation.name` / `gen_ai.system` /
`gen_ai.agent.name` / `gen_ai.request.model` / `gen_ai.usage.*`) plus bhgman-native
cardinality attributes (`bhgman.intent_n` / `actual_n` / `cardinality_match`,
mirroring the jaebaeman V5 invariant, GH#29181).

- **Optional dependency** `bhgman_tool[otel]` (`opentelemetry-sdk` + OTLP exporter).
  Absent ⇒ every entry point is a graceful no-op; core dispatch stays decoupled.
- `dispatch_audit.record_drift` surfaces drift as a `gen_ai.dispatch.drift` span
  event on any active span (guarded; no-op when `[otel]` absent / no span).
- Host application owns TracerProvider/exporter wiring (e.g. `OTEL_EXPORTER_OTLP_ENDPOINT`);
  the channel mutates no global state.

## Rationale

- **Idiomatic**: reuses the established "one channel per provenance/observability
  standard" pattern rather than inventing a bespoke trace format.
- **Non-coupling**: pure mapping helpers (`span_name`, `span_attributes`) are
  importable + tested without the SDK; SDK-dependent emission is behind a guard.
- **Standards-aligned**: GenAI semconv is the vendor-neutral layer the 2026
  ecosystem is converging on (PROM 16 D-axis consensus).

## Consequences

- (+) Subagent runs become exportable to any OTLP backend; KG and OTel are
  complementary (causal graph vs operational latency/token/topology).
- (+) Zero new core dependency; ratchet unaffected (274 pass / 1 skip; +9 tests).
- (−) Full span timing requires the runtime to wrap dispatch in
  `otel_channel.dispatch_span(...)`; until then only post-hoc `emit_dispatch` +
  drift events are populated. Live-wrap adoption is the follow-up.
- Threshold/severity semantics reuse `dispatch_audit` (P1_underdispatch /
  P2_overdispatch) — no new policy surface.

## Status of follow-ups

- Live `dispatch_span()` wrap in the orchestration/runtime path (currently the
  reusable API exists; in-process runtime is partly on dgx per
  `apt-dgx-runtime-delegation-2026-05-25`).
- Token-usage population (`gen_ai.usage.*`) once the runtime threads model/usage
  metadata into the dispatch record.
