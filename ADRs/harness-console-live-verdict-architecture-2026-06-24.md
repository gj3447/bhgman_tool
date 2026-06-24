# ADR: Harness Console for Live Verdict, Research Labeling, and Architecture Review

Date: 2026-06-24

Status: Proposed

# KG: plan-harness-console-live-verdict-2026-06-24
# KG: adr-harness-console-live-verdict-architecture-2026-06-24
# KG: longinus-binding-harness-console-adr-2026-06-24

## Context

The repository already has the methodological reason for human judgment:

- Longinus marks `AMBIGUOUS` references as requiring human verdict.
- Tarski grounding forbids a system from treating self-grading as ground truth.
- FixAgent escalates repeated reject loops to a human `sigma_oracle`.
- Eureka stops at `VerdictPending` and hands judgment to an LLM/human lens.

What is missing is the operating surface. Today those ideas exist as documents,
skills, and engine gates, but there is no live GUI where a human can watch runs,
label evidence, compare architecture, and submit verdicts.

The initial name "Lakatos tree GUI" is too narrow. Lakatos is one view. The
actual artifact should be a harness control room:

1. Human verdict queue.
2. AI labeling workbench.
3. Research navigator for 3D and bead projects.
4. Server and engine architecture analyzer.
5. Live streaming event timeline.
6. KG-ready audit log.

## Decision

Build a `harness_console`, not a standalone Lakatos-only GUI.

The console will use the Harness four-axis frame as its product architecture:

| Axis | Console responsibility |
| --- | --- |
| Inform | Surface project structure, evidence, code, docs, KG refs, run context. |
| Constrain | Show gates, required evidence, blocked transitions, schema violations. |
| Verify | Compare human, AI, tests, Lean, Longinus, Occam, Eureka, and Lakatos verdicts. |
| Correct | Turn rejected or ambiguous items into relabel tasks, patch tasks, or follow-up research. |

The first implementation should be local-first:

- FastAPI server.
- SQLite event store.
- Server-sent events for live streaming.
- Vite/React frontend.
- Three.js canvas for architecture and project graph views.
- KG write-back second, not first.

Neo4j/KG remains the eventual system of record, but the first trustworthy unit is
an append-only event log. The console must not silently overwrite human judgment
or collapse evidence into a single scalar score.

## Non-Goals

- Do not build a marketing dashboard.
- Do not let an LLM approve its own output as ground truth.
- Do not make Lakatos the only navigation model.
- Do not require a live Neo4j instance for MVP use.
- Do not make 3D or bead projects conform to source-code-only abstractions.

## Server Architecture

```text
Vite/React Harness Console
  |
  | REST: project query, evidence query, verdict submit, label export
  | SSE: live run events, queue updates, labeling updates
  v
FastAPI Harness Server
  |
  +-- SQLite Event Store
  +-- Project Snapshot Store
  +-- Verdict Queue
  +-- Label Task Queue
  +-- Engine Adapter Layer
       |
       +-- OccamEngine
       +-- LonginusEngine
       +-- Eureka pipeline
       +-- Legion runner
       +-- MCP tool adapters
       +-- PythonRepoAdapter
       +-- Node/ViteAdapter
       +-- ThreeDProjectAdapter
       +-- BeadProjectAdapter
       +-- GenericFileAdapter
```

The server has two separate responsibilities:

1. Run and observe engines.
2. Preserve human/AI judgment artifacts as auditable records.

Those should not be conflated. Engine output proposes; the verdict queue records.

## Engine Architecture

The facade should be explicit.

```python
class HarnessConsoleEngine:
    def ingest_project(self, target: ProjectTarget) -> ProjectSnapshot: ...
    def analyze_architecture(self, snapshot_id: str) -> ArchitectureReport: ...
    def create_label_tasks(self, snapshot_id: str) -> list[LabelTask]: ...
    def stream_run(self, run_id: str) -> Iterator[HarnessEvent]: ...
    def submit_verdict(self, verdict: HumanVerdict) -> VerdictReceipt: ...
```

Domain-specific project handling belongs behind adapters:

```python
class ProjectAdapter(Protocol):
    def supports(self, target: ProjectTarget) -> bool: ...
    def snapshot(self, target: ProjectTarget) -> ProjectSnapshot: ...
    def architecture(self, snapshot: ProjectSnapshot) -> ArchitectureGraph: ...
    def label_candidates(self, snapshot: ProjectSnapshot) -> list[LabelTask]: ...
```

Adapter priorities:

1. `PythonRepoAdapter`: Python modules, engines, tests, CLI/MCP entrypoints.
2. `NodeViteAdapter`: Vite/TypeScript projects such as `333q_demo`.
3. `ThreeDProjectAdapter`: scenes, cameras, shaders, assets, interaction loops, render pipeline.
4. `BeadProjectAdapter`: bead-specific artifacts once the project corpus is present.
5. `GenericFileAdapter`: fallback for research docs and mixed folders.

The bead adapter is intentionally reserved. This repository does not currently
show a concrete bead project corpus, so the console should define the extension
slot without pretending the schema is known.

## Core DTOs

```python
class HarnessEvent(BaseModel):
    id: str
    run_id: str
    sequence: int
    event_type: str
    source: str
    payload: dict
    created_at: datetime


class HumanVerdictRequest(BaseModel):
    id: str
    target_ref: str
    target_kind: Literal[
        "occam_candidate",
        "longinus_ambiguous",
        "eureka_abstract_class",
        "fix_attempt",
        "lakatos_shift",
        "architecture_node",
        "project_asset",
        "research_claim",
    ]
    context: dict
    evidence_refs: list[str]
    prior_verdicts: list[str]
    recommended_action: str | None
    allowed_verdicts: list[str]
    status: Literal["PENDING", "SUBMITTED", "DEFERRED", "APPLIED"]


class HumanVerdict(BaseModel):
    request_id: str
    verdict: Literal[
        "APPROVE",
        "REJECT",
        "VERIFY",
        "DEFER",
        "CANONICAL",
        "CANONICAL_DELEGATED",
        "PROGRESSIVE",
        "DEGENERATING",
    ]
    rationale: str
    reviewer_id: str
    evidence_refs: list[str]
    created_at: datetime


class LabelTask(BaseModel):
    id: str
    project_id: str
    target_ref: str
    target_kind: str
    proposed_label: str | None
    allowed_labels: list[str]
    ai_confidence: float | None
    evidence_refs: list[str]
    missing_evidence: list[str]
    blocking_questions: list[str]
    status: Literal[
        "PENDING",
        "AI_PROPOSED",
        "HUMAN_APPROVED",
        "HUMAN_REJECTED",
        "DEFERRED",
    ]
```

## Label Taxonomy

Architecture role labels:

- `ENTRYPOINT`
- `FACADE`
- `ENGINE`
- `ADAPTER`
- `DTO`
- `STORAGE`
- `TRANSPORT`
- `UI`
- `TEST`
- `DOC`
- `ASSET`
- `SHADER`
- `SCENE`

Research-use labels:

- `CORE_EVIDENCE`
- `SUPPORTING_EVIDENCE`
- `PRIOR_ART`
- `COUNTEREVIDENCE`
- `DISTRACTOR`
- `NEEDS_SOURCE`

Verdict labels:

- `PROGRESSIVE`
- `DEGENERATING`
- `AMBIGUOUS`
- `VERDICT_PENDING`
- `CANONICAL`
- `CANONICAL_DELEGATED`
- `REJECTED`
- `VERIFY`

The console may propose labels with AI, but human confirmation must be recorded
for labels that change project status, KG materialization, or archival decisions.

## GUI Views

### 1. Live Run Timeline

Purpose: streaming view for active engine/agent runs.

Shows:

- event sequence
- commander/source
- elapsed time
- status
- artifacts emitted
- pending human gates
- failed constraints

### 2. Verdict Queue

Purpose: human grading workbench.

Shows:

- pending verdict requests
- recommended action
- evidence bundle
- previous attempts
- AI label proposal
- required rationale field
- submit/defer/escalate controls

### 3. Lakatos Tree

Purpose: research programme evaluation.

Nodes:

- hard core
- protective belt
- positive heuristic
- negative heuristic
- auxiliary hypothesis
- testable consequence
- corroboration
- failed prediction

Edges:

- `PROTECTS`
- `MODIFIES`
- `PREDICTS`
- `CORROBORATED_BY`
- `REFUTED_BY`
- `REQUIRES_VERDICT`

### 4. Architecture Graph

Purpose: server/engine analysis.

Sub-views:

- entrypoint map: CLI, MCP, HTTP, scripts, tests
- facade drift map: who bypasses the CommanderEngine facade
- dependency flow: adapters, engines, stores, transports
- contract map: DTOs and request/response models
- drift map: duplicate entrypoints, stale adapters, orphan tools

### 5. 3D Project Research View

Purpose: make 3D projects easy to study and label.

Entities:

- scene
- mesh
- material
- texture
- shader
- camera
- light
- interaction
- physics object
- asset pipeline step

Views:

- scene graph
- asset dependency graph
- render pipeline
- interaction loop
- performance events

### 6. Bead Project Research View

Purpose: reserve a domain-specific workbench for bead-related research.

The initial adapter should not invent bead semantics. It should start with:

- artifact inventory
- image/file grouping
- label queue
- evidence clipping
- comparison board
- freeform domain tags

Once the bead corpus is present, the adapter can add a stricter schema.

## Event Store

SQLite tables:

```sql
CREATE TABLE harness_events (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  source TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(run_id, sequence)
);

CREATE TABLE verdict_requests (
  id TEXT PRIMARY KEY,
  target_ref TEXT NOT NULL,
  target_kind TEXT NOT NULL,
  context_json TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  prior_verdicts_json TEXT NOT NULL,
  recommended_action TEXT,
  allowed_verdicts_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE human_verdicts (
  id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  verdict TEXT NOT NULL,
  rationale TEXT NOT NULL,
  reviewer_id TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE label_tasks (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  target_ref TEXT NOT NULL,
  target_kind TEXT NOT NULL,
  proposed_label TEXT,
  allowed_labels_json TEXT NOT NULL,
  ai_confidence REAL,
  evidence_refs_json TEXT NOT NULL,
  missing_evidence_json TEXT NOT NULL,
  blocking_questions_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

## KG Plan

The live environment for Neo4j is optional. If `NEO4J_URI` and
`NEO4J_PASSWORD` are not present, this plan should be written into local KG
or kept as Cypher until materialization.

Canonical plan node:

- `plan-harness-console-live-verdict-2026-06-24`

Cypher materialization:

```cypher
MERGE (p:ProjectPlan:AbstractNode {name: 'plan-harness-console-live-verdict-2026-06-24'})
SET p.status = 'PROPOSED',
    p.created_at = '2026-06-24',
    p.scope = 'harness_console',
    p.summary = 'Live human verdict, AI labeling, research navigation, and architecture analysis console',
    p.longinus_bound = true,
    p.adr = 'ADRs/harness-console-live-verdict-architecture-2026-06-24.md';

MERGE (adr:ArchitectureDecision:AbstractNode {name: 'adr-harness-console-live-verdict-architecture-2026-06-24'})
SET adr.path = 'ADRs/harness-console-live-verdict-architecture-2026-06-24.md',
    adr.status = 'Proposed',
    adr.created_at = '2026-06-24';

MERGE (p)-[:DOCUMENTED_BY]->(adr);

WITH p
UNWIND [
  ['task-harness-console-event-store-2026-06-24', 'Build SQLite event store and append-only HarnessEvent model', 1],
  ['task-harness-console-verdict-queue-2026-06-24', 'Build HumanVerdictRequest and HumanVerdict workflow', 2],
  ['task-harness-console-project-adapters-2026-06-24', 'Add PythonRepo, NodeVite, ThreeD, Bead, and GenericFile adapter slots', 3],
  ['task-harness-console-architecture-graph-2026-06-24', 'Build server and engine architecture analysis graph', 4],
  ['task-harness-console-ai-labeling-2026-06-24', 'Build AI-assisted label queue with human confirmation', 5],
  ['task-harness-console-lakatos-tree-2026-06-24', 'Build Lakatos research programme tree view', 6],
  ['task-harness-console-live-gui-2026-06-24', 'Build React/Vite live streaming GUI with SSE', 7],
  ['task-harness-console-kg-writeback-2026-06-24', 'Add optional KG write-back after local event log stabilizes', 8]
] AS row
MERGE (t:SubagentTaskSpec:AbstractNode {name: row[0]})
SET t.skill = 'harness',
    t.depth = row[2],
    t.status = 'READY',
    t.summary = row[1],
    t.plan = p.name
MERGE (p)-[:DECOMPOSES_TO]->(t);
```

## Longinus Binding

This ADR is the first Longinus-bound reference for the harness console plan.

Binding intent:

- `adr-harness-console-live-verdict-architecture-2026-06-24`
  `REALIZED_BY` this ADR file.
- `plan-harness-console-live-verdict-2026-06-24`
  `DOCUMENTED_BY` the ADR node.
- Future code files must include a `# KG:` reference to the plan or task node.

Expected first code anchors:

- `engine/harness_console/models.py`
  `# KG: task-harness-console-event-store-2026-06-24`
- `engine/harness_console/store.py`
  `# KG: task-harness-console-event-store-2026-06-24`
- `engine/harness_console/server.py`
  `# KG: task-harness-console-live-gui-2026-06-24`
- `harness_console/src/App.tsx`
  `# KG: task-harness-console-live-gui-2026-06-24`

## Implementation Sequence

### PR 1: Plan and Event Core

- Add ADR.
- Add `engine/harness_console/models.py`.
- Add SQLite event store.
- Add tests for append-only sequence and verdict request lifecycle.

### PR 2: Server Skeleton

- Add FastAPI app.
- Add REST endpoints:
  - `GET /health`
  - `GET /events/{run_id}`
  - `GET /verdict-requests`
  - `POST /verdicts`
  - `GET /label-tasks`
- Add SSE endpoint:
  - `GET /runs/{run_id}/stream`

### PR 3: Project Snapshot and Architecture Analyzer

- Add `ProjectAdapter` protocol.
- Add Python repo adapter.
- Add Node/Vite adapter.
- Add architecture graph DTO.
- Detect entrypoints, facades, engines, adapters, DTOs, storage, transports.

### PR 4: GUI MVP

- Create `harness_console/` Vite app.
- Implement workbench layout:
  - left project navigator
  - center architecture/timeline view
  - right verdict panel
- Add label queue.
- Add verdict submit flow.

### PR 5: Lakatos and Research Views

- Add Lakatos tree DTO and view.
- Add research claim/evidence clipping.
- Add export JSONL for AI labeling datasets.

### PR 6: 3D and Bead Adapters

- Add `ThreeDProjectAdapter`.
- Add `BeadProjectAdapter` placeholder with corpus-driven schema evolution.
- Add Three.js graph view for architecture and 3D asset maps.

### PR 7: KG Write-Back

- Add optional Neo4j/local KG materializer.
- Preserve SQLite as append-only audit source.
- Write only confirmed human verdicts and stable plan/task nodes.

## Consequences

Positive:

- Human judgment becomes first-class infrastructure instead of chat memory.
- AI labeling becomes auditable and exportable.
- Architecture drift can be studied visually.
- 3D and bead projects get research-friendly domain adapters.
- KG materialization is grounded by an event log, reducing premature ontology pollution.

Negative:

- More surface area: server, GUI, store, adapters.
- Requires careful schema discipline to avoid another multi-entrypoint drift problem.
- Human verdict UX becomes load-bearing; poor UI will degrade review quality.

## Open Questions

1. Where is the bead project corpus?
2. Should the first GUI live under `harness_console/` or `apps/harness_console/`?
3. Should FastAPI be a new dependency in root `pyproject.toml` or isolated in a subpackage?
4. Should KG write-back target local KG first, Neo4j first, or both behind one interface?
5. Which identity model is enough for MVP: local reviewer string or authenticated user?
