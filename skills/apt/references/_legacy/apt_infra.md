# Part IV: Infrastructure

> APT v11 §23–§30 — Kafka Event Sourcing, KG-Git Sync, Indexes, HA, Observability, Incident Response, CI/CD

---

## §23 Kafka Event Sourcing

All state transitions go through Kafka. A single KG writer (consumer) projects events to Neo4j.
No agent writes directly to Neo4j — every mutation is an event first.

```
Agent ──[publish]──▶ Kafka topic ──[single consumer]──▶ Neo4j KG
  ↑                                                        │
  └──────────────────── [read query] ──────────────────────┘
```

### 23.1 Event Envelope

Every event shares a common envelope. The `payload` varies per event type.

```json
{
  "schema_version": 1,
  "event_type": "SpanDecomposed",
  "timestamp": "2026-03-25T12:00:00Z",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent": "agent_decomposer_1",
  "branch": "feature-auth-module",
  "payload": { }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | int | Monotonic. Consumer checks compatibility. |
| `event_type` | string | One of the 10 defined event types. |
| `timestamp` | ISO-8601 | Event creation time (agent clock). |
| `correlation_id` | UUID | Traces a logical operation across multiple events. |
| `agent` | string | Name of the agent that published the event. |
| `branch` | string | Git branch context. Used for KG-Git reconciliation. |
| `payload` | object | Event-specific data (see §23.2). |

### 23.2 Event Types (10)

#### 1. SpanDecomposed

A non-atomic Span was split into children via DECOMPOSES_TO.

```json
{
  "parent_name": "SPAN_PROJECT_Module",
  "children": ["SPAN_PROJECT_Auth", "SPAN_PROJECT_API", "SPAN_PROJECT_DB"],
  "relation": "DECOMPOSES_TO"
}
```

Consumer action: MERGE parent, MERGE each child, CREATE edges.

#### 2. SpanExplored

A Span was expanded via EXPLORES_VIA (alternatives, not parts).

```json
{
  "parent_name": "SPAN_PROJECT_Search",
  "alternatives": ["SPAN_PROJECT_ElasticSearch", "SPAN_PROJECT_Algolia", "SPAN_PROJECT_Meilisearch"],
  "strategy": "best_of_n"
}
```

Consumer action: MERGE parent, MERGE each alternative, CREATE EXPLORES_VIA edges with strategy property.

#### 3. SpanApproved

An AtomicSpan passed the σ-gate (both σ_auto and σ_oracle). Executor ≠ reviewer.

```json
{
  "span_name": "ATOM_PROJECT_SearchEngine",
  "reviewer": "reviewer_agent_2",
  "criterion": "sigma"
}
```

Consumer action: SET span label to AtomicSpan, CREATE APPROVED_BY edge, verify executor ≠ reviewer.

#### 4. SpanCrystallized

An AtomicSpan crossed the crystallization frontier into ST world. Twin, Task, Contract, and Hub created.

```json
{
  "atom_name": "ATOM_PROJECT_SearchEngine",
  "twin_name": "ST_PROJECT_SearchEngine",
  "contract_name": "CT_PROJECT_SearchEngine"
}
```

Consumer action: MERGE Twin, Task, Contract, Hub. CREATE CRYSTALLIZES_TO, HAS_CONTRACT, HAS_TASK, INVOLVES edges.

#### 5. ContractLockAcquired

An agent acquired an exclusive lock on a Contract for implementation.

```json
{
  "contract_name": "CT_PROJECT_SearchEngine",
  "agent": "agent_implementer_3",
  "fencing_token": 42
}
```

Consumer action: SET ct.locked_by = agent, ct.fencing_token = 42, ct.locked_at = datetime().

#### 6. ContractLockReleased

An agent released a lock after completing or aborting implementation.

```json
{
  "contract_name": "CT_PROJECT_SearchEngine",
  "agent": "agent_implementer_3",
  "fencing_token": 42
}
```

Consumer action: REMOVE ct.locked_by, ct.fencing_token, ct.locked_at (only if fencing_token matches).

#### 7. ContractMaterialized

A Contract was implemented — SourceCodeNode created, tests pass, fulfillment gate cleared.

```json
{
  "contract_name": "CT_PROJECT_SearchEngine",
  "source_file": "src/search/engine.py",
  "lines": 247
}
```

Consumer action: MERGE SourceCodeNode, CREATE MATERIALIZES edge, SET contract.status = 'fulfilled'.

#### 8. ContractAmended

A fulfilled Contract was amended due to discovery during SCW or regression.

```json
{
  "contract_name": "CT_PROJECT_SearchEngine",
  "amended_fields": ["postcondition", "acceptance_criteria"],
  "reason": "Edge case discovered: empty query input"
}
```

Consumer action: UPDATE contract properties, SET affected SourceCodeNodes to `needs_update`, trigger regression tests.

#### 9. FeedbackCreated

A feedback item was raised (bug, missing span, type mismatch, etc.).

```json
{
  "feedback_name": "FB_PROJECT_MissingErrorHandler",
  "category": "Missing",
  "severity": "P2"
}
```

Consumer action: MERGE AptFeedback node, SET properties (category, severity, status='open', created_at).

#### 10. ContractDeployed

A materialized Contract was deployed to production (CI/CD final step).

```json
{
  "contract_name": "CT_PROJECT_SearchEngine",
  "environment": "prod",
  "version": "1.2.0"
}
```

Consumer action: SET contract.deployed_env = environment, contract.deployed_version = version, contract.deployed_at = datetime().

### 23.3 Topic Design

```
Topic: apt-events
  Partitions:   config.kafka.partitions (default: 4)
  Partition Key: config.kafka.partition_key (default: entity_name)
  Retention:     config.kafka.retention_days (default: 30 days)
  Replication:   min.insync.replicas = 1 (dev), 2 (prod)
  Compression:   lz4

Topic: apt-events-dlq
  Partitions:   1
  Retention:     config.kafka.dlq_retention_days (default: 90 days)
  Purpose:       Failed events after 3 retries
```

Partition key = `entity_name` ensures all events for the same entity (Span, Contract, etc.)
land on the same partition, preserving per-entity ordering. Cross-entity ordering is not
guaranteed but not required — events reference entities by name and consumer uses MERGE (idempotent).

### 23.4 Consumer HA

```
Consumer Group:   apt-kg-writer
Active Instances: 1 (single writer — prevents concurrent KG writes)
Standby:          1 (auto-promoted on active failure)
Heartbeat:        10s (consumer → broker)
Session Timeout:  30s (broker declares consumer dead if no heartbeat)
Offset Commit:    After successful KG write (at-least-once delivery)
Idempotency:      MERGE-based writes — replaying an event produces same state
Max Poll Records: 100
Max Poll Interval: 5 minutes
```

**Why single writer?** Multiple writers would cause race conditions on KG state.
MERGE is idempotent for individual events but concurrent writers could interleave
partial multi-statement transactions. Single writer + at-least-once + MERGE = safe.

**Standby promotion flow:**
1. Active consumer fails (no heartbeat for 30s)
2. Broker triggers rebalance
3. Standby joins group, receives partition assignments
4. Standby resumes from last committed offset
5. Some events may replay (at-least-once) — MERGE handles duplicates

### 23.5 Contract Locking via Kafka

Prevents two agents from implementing the same Contract simultaneously.
Uses Kafka events (not external lock service) to maintain consistency.

**Full flow:**

```
1. ACQUIRE
   Agent publishes: ContractLockAcquired {contract, agent, fencing_token=N}
   Consumer processes:
     IF ct.locked_by IS NULL:
       SET ct.locked_by = agent, ct.fencing_token = N, ct.locked_at = datetime()
     ELSE:
       Publish to DLQ: "Lock contention on {contract}"

2. HEARTBEAT
   Agent publishes: LockHeartbeat {contract, agent, fencing_token=N} every 30s
   Consumer processes:
     IF ct.fencing_token = N:
       SET ct.lock_heartbeat = datetime()
     ELSE:
       Ignore (stale heartbeat from old holder)

3. RELEASE
   Agent publishes: ContractLockReleased {contract, agent, fencing_token=N}
   Consumer processes:
     IF ct.fencing_token = N:
       REMOVE ct.locked_by, ct.fencing_token, ct.locked_at, ct.lock_heartbeat
     ELSE:
       Ignore (stale release)

4. AUTO-RELEASE
   Validation V17 (cron every 15min):
     MATCH (ct:AptContract)
     WHERE ct.locked_by IS NOT NULL
       AND ct.locked_at < datetime() - duration('PT1H')
     REMOVE ct.locked_by, ct.fencing_token, ct.locked_at, ct.lock_heartbeat
     // Timeout = config.concurrency.lock_timeout_minutes (default: 60)
```

**Fencing token:** Monotonically increasing integer. Prevents stale lock holders from
releasing a lock that was already auto-released and re-acquired by another agent.

### 23.6 Schema Evolution

| Change Type | Strategy | Example |
|-------------|----------|---------|
| New optional field | Add with default value | Add `priority` field, default `null` |
| New required field | Schema version bump + migration | Add `idempotency_key` to all events |
| Field rename | New schema version + backward-compat period | `agent_name` → `agent` |
| Breaking change | New topic + migration consumer | `apt-events-v2` with bridge consumer |

**Rules:**
- New fields with defaults: no version bump required. Consumer ignores unknown fields.
- Breaking changes: create new topic (`apt-events-v2`), deploy migration consumer that reads v1 and writes v2.
- `schema_version` in envelope: consumer checks version and dispatches to appropriate handler.
- Never delete fields from existing schema versions — only deprecate.

### 23.7 Dead Letter Queue (DLQ)

```
Processing flow:
  1. Consumer reads event from apt-events
  2. Attempt to write to Neo4j
  3. On failure: retry up to 3 times (exponential backoff: 1s, 4s, 16s)
  4. After 3 failures: publish original event to apt-events-dlq with error metadata
  5. Alert: DLQ depth > 0 triggers P2 Slack notification

DLQ event envelope (wraps original):
{
  "original_event": { ... },
  "error": "Neo4j connection timeout",
  "retry_count": 3,
  "failed_at": "2026-03-25T12:01:00Z",
  "consumer_instance": "apt-kg-writer-0"
}

Manual replay:
  1. Inspect DLQ events via Kafka consumer or UI
  2. Fix root cause (Neo4j down, schema issue, data corruption)
  3. Replay: publish corrected events back to apt-events
  4. Verify: DLQ depth returns to 0
```

---

## §24 KG-Git Synchronization

### 24.1 Dual Source of Truth

KG and Git each own different artifacts. Neither is a full replica of the other.

| Artifact | Source of Truth | Secondary Store | Sync Direction |
|----------|:--------------:|:---------------:|:--------------:|
| Code files (*.py, *.ts, etc.) | **Git** | KG (`SourceCodeNode.file_path`) | Git → KG |
| Test files | **Git** | KG (`Task.impact_tests`) | Git → KG |
| Contracts (spec) | **KG** | Git (`contracts/*.yaml` export) | KG → Git |
| Span structure | **KG** | Git (`apt-structure.yaml` export) | KG → Git |
| Config (`apt-config.yaml`) | **Git** | KG (`AptConfig` node) | Git → KG |
| Feedback | **KG** | Git (issue tracker sync, optional) | KG → Git |

**Principle:** Code lives in Git. Metadata lives in KG. Exports exist for human readability
and CI validation, not as canonical sources.

### 24.2 Reconciliation Loop

Two mechanisms keep Git and KG in sync:

**Mechanism 1: Commit Hook + CI (Git → KG)**

```
Developer/Agent commits code
  → pre-commit hook: lint + basic checks
  → push to remote
  → CI pipeline triggers:
      1. Export KG contracts to YAML (scripts/kg_export_contracts.py)
      2. Diff exported YAML vs contracts/*.yaml in repo
      3. If mismatch:
         - Flag as CI failure
         - Create AptFeedback {category: 'Conflict', severity: 'P2'}
      4. Verify all SourceCodeNode.file_path entries exist in Git
      5. Verify all Task.impact_tests paths are valid test files
```

**Mechanism 2: Kafka Consumer (KG → Git)**

```
Kafka event processed by consumer
  → Consumer writes to KG
  → Post-write hook:
      1. If ContractMaterialized: verify source_file exists in Git
         - If missing: publish FeedbackCreated {category: 'Missing'}
      2. If ContractAmended: check if affected source files need update
         - Mark SourceCodeNode.status = 'needs_update'
      3. If SpanDecomposed/SpanExplored: update apt-structure.yaml export
         - Export runs async (not blocking event processing)
```

### 24.3 Branch Strategy

Kafka events carry a `branch` field that tracks the Git branch context.

```
Rules:
  - Events on feature branches: scoped to that branch's KG namespace
  - Events on main/master: canonical KG state
  - Branch merge in Git → reconciliation check:
      1. List all events published on the feature branch
      2. Check for conflicts with main branch events (same entity, different values)
      3. If conflicts: block merge, require manual resolution
      4. If clean: replay feature branch events onto main KG state
```

### 24.4 Conflict Detection

| Conflict Type | Detection | Resolution |
|---------------|-----------|------------|
| Same Contract, different fields on two branches | Diff contract properties at merge time | Manual: choose one, or merge fields |
| SourceCodeNode path changed in Git but not in KG | CI reconciliation step | Update KG via ContractAmended event |
| Span decomposed differently on two branches | Compare DECOMPOSES_TO children sets | Manual: re-decompose from common parent |
| Lock held on feature branch, merged to main | V17 detects stale lock | Auto-release (lock_timeout) |

---

## §25 Create Strategy: MERGE-Only

### 25.1 Why CREATE Is Forbidden

`CREATE` in Cypher produces a new node every time it runs. In an event-sourced system where
events can be replayed (at-least-once delivery, DLQ replay, disaster recovery), `CREATE` would
produce duplicate nodes on every replay.

`MERGE` is idempotent: it creates the node if it does not exist, or matches the existing one.
This makes the entire KG rebuildable from the Kafka event log without duplicates.

**Additional reasons:**
- Kafka consumer may process the same event twice (at-least-once semantics)
- DLQ replay sends events through the pipeline again
- Disaster recovery rebuilds KG from Kafka log
- Multiple agents may race on the same entity (single writer serializes, but retries happen)

### 25.2 MERGE Key Table

| Node Type | Label | MERGE Key | Naming Convention | Example |
|-----------|-------|-----------|-------------------|---------|
| SemanticAnchor | `SemanticAnchor` | `name` | `{PROJECT}` | `ECommerceApp` |
| AptSpan | `AptSpan` | `name` | `SPAN_{PROJECT}_{AREA}` | `SPAN_PROJECT_Search` |
| AtomicSpan | `AtomicSpan` | `name` | `ATOM_{PROJECT}_{UNIT}` | `ATOM_PROJECT_SearchEngine` |
| SemanticTwin | `SemanticTwin` | `name` (unique) | `ST_{PROJECT}_{UNIT}` | `ST_PROJECT_SearchEngine` |
| AptContract | `AptContract` | `name` | `CT_{PROJECT}_{UNIT}` | `CT_PROJECT_SearchEngine` |
| SemanticTask | `SemanticTask` | `name` | `TASK_{PROJECT}_{UNIT}` | `TASK_PROJECT_SearchEngine` |
| CrystallizationEvent | `CrystallizationEvent` | `name` | `CX_{PROJECT}_{UNIT}` | `CX_PROJECT_SearchEngine` |
| SourceCodeNode | `SourceCodeNode` | `file_path` | Actual file path | `src/search/engine.py` |
| AptFeedback | `AptFeedback` | `name` | `FB_{PROJECT}_{DESC}` | `FB_PROJECT_MissingHandler` |

### 25.3 Property Conflict Resolution

When two events set different values for the same property on the same node:

```
Resolution: Last-Writer-Wins (LWW) via Kafka ordering.

Since there is a single consumer processing events sequentially from each partition,
and partition key = entity_name, all events for the same entity are processed in order.
The last event's SET overwrites previous values.

This is safe because:
  1. Single writer (no concurrent KG mutations)
  2. Kafka guarantees per-partition ordering
  3. entity_name as partition key groups related events
```

---

## §26 Index Strategy

### 26.1 Full Cypher DDL

```cypher
-- Index 1: AptSpan name lookup
-- Accelerates: Span retrieval by name (used in every decomposition, exploration, approval)
-- Used by: V2, V3, V4, V5, V6, V13, V16, phase detection, Decompose(), Crystallize()
CREATE INDEX apt_span_name IF NOT EXISTS FOR (n:AptSpan) ON (n.name);

-- Index 2: AptContract name lookup
-- Accelerates: Contract retrieval by name (lock acquisition, materialization, amendment)
-- Used by: V1, V7, V8, V12, V17, Implement(), ContractLockAcquired/Released
CREATE INDEX apt_contract_name IF NOT EXISTS FOR (n:AptContract) ON (n.name);

-- Index 3: AptContract status filtering
-- Accelerates: Queries filtering contracts by lifecycle state (draft, active, fulfilled, etc.)
-- Used by: Dashboard queries, fulfillment rate SLI, contract lifecycle FSM transitions
CREATE INDEX apt_contract_status IF NOT EXISTS FOR (n:AptContract) ON (n.status);

-- Index 4: CrystallizationEvent name lookup
-- Accelerates: Hub retrieval during crystallization and validation
-- Used by: V14, Crystallize(), hub consistency checks
CREATE INDEX cx_name IF NOT EXISTS FOR (n:CrystallizationEvent) ON (n.name);

-- Index 5: AptFeedback status filtering
-- Accelerates: Open feedback queries, feedback triage dashboard
-- Used by: Feedback system, PH6 operations, feedback SLA monitoring
CREATE INDEX feedback_status IF NOT EXISTS FOR (n:AptFeedback) ON (n.status);

-- Index 6: SourceCodeNode file_path lookup
-- Accelerates: Code file lookups during materialization and KG-Git reconciliation
-- Used by: V13, ContractMaterialized consumer, KG-Git sync, phase detection
CREATE INDEX source_path IF NOT EXISTS FOR (n:SourceCodeNode) ON (n.file_path);

-- Index 7: SemanticTwin name lookup
-- Accelerates: Twin retrieval during crystallization and validation
-- Used by: V7, V9, V10, Crystallize(), phase detection
CREATE INDEX twin_name IF NOT EXISTS FOR (n:SemanticTwin) ON (n.name);

-- Index 8: AptAgent name lookup
-- Accelerates: Agent retrieval during approval and lock operations
-- Used by: V15, APPROVED_BY edge creation, lock ownership checks
CREATE INDEX agent_name IF NOT EXISTS FOR (n:AptAgent) ON (n.name);

-- Constraint 1: SemanticTwin uniqueness
-- Enforces: No duplicate Twins (V10 prevention at DB level)
-- Required by: A4 (CrystallizationFrontierUniqueness), V10 validation
CREATE CONSTRAINT twin_unique IF NOT EXISTS FOR (tw:SemanticTwin) REQUIRE tw.name IS UNIQUE;

-- Constraint 2: SourceCodeNode file_path uniqueness
-- Enforces: One-to-one mapping between file paths and SourceCodeNodes
-- Required by: MATERIALIZES functional property, KG-Git sync integrity
CREATE CONSTRAINT source_path_unique IF NOT EXISTS FOR (src:SourceCodeNode) REQUIRE src.file_path IS UNIQUE;

-- Relationship Index 1: INVOLVES role property
-- Accelerates: Hub queries filtered by role (atom, twin, task, contract, source)
-- Used by: V14, hub consistency checks, CrystallizationEvent queries
CREATE INDEX involves_role IF NOT EXISTS FOR ()-[r:INVOLVES]-() ON (r.role);
```

### 26.2 Index-to-Query Mapping Summary

| Index / Constraint | Queries Accelerated | Hot Path? |
|--------------------|---------------------|:---------:|
| `apt_span_name` | V2–V6, V13, V16, phase detection, Decompose() | Yes |
| `apt_contract_name` | V1, V7, V8, V12, V17, Implement() | Yes |
| `apt_contract_status` | Dashboard, fulfillment SLI, lifecycle queries | Yes |
| `cx_name` | V14, Crystallize() | Medium |
| `feedback_status` | Feedback triage, PH6 | Medium |
| `source_path` | V13, KG-Git reconciliation | Medium |
| `twin_name` | V7, V9, V10, Crystallize() | Yes |
| `agent_name` | V15, approval checks | Low |
| `twin_unique` (constraint) | V10 prevention | Write-time |
| `source_path_unique` (constraint) | MATERIALIZES integrity | Write-time |
| `involves_role` (rel index) | V14, hub queries | Medium |

---

## §27 KG High Availability

### 27.1 Write-Ahead: Kafka as WAL

Kafka serves as the durable write-ahead log (WAL) for the Knowledge Graph.
The KG is a materialized view of the Kafka event stream — it can be fully
reconstructed by replaying all events from the beginning of the topic.

```
Durability chain:
  Agent event → Kafka (persisted to disk, replicated) → Consumer → Neo4j

If Neo4j is lost:
  1. Deploy fresh Neo4j instance
  2. Run index/constraint DDL (§26)
  3. Reset consumer offset to beginning
  4. Consumer replays all events → KG fully rebuilt
  5. MERGE idempotency ensures correct final state
```

### 27.2 Backup Strategy

```
Schedule: Daily at 03:00 UTC (cron)
Tool:     neo4j-admin database dump neo4j
Target:   MinIO bucket: apt-docs/backups/
Naming:   neo4j-dump-{YYYY-MM-DD}.dump
Retention: 30 days (rolling)

Backup script (cron entry):
  0 3 * * * /usr/local/bin/neo4j-admin database dump neo4j \
    --to-path=/tmp/neo4j-backup/ \
    && mc cp /tmp/neo4j-backup/neo4j.dump \
       minio/apt-docs/backups/neo4j-dump-$(date +\%Y-\%m-\%d).dump \
    && rm -f /tmp/neo4j-backup/neo4j.dump

Verification:
  - Weekly restore test to staging Neo4j instance
  - Compare node/relationship counts against production
  - Run V1-V17 validations on restored instance
```

### 27.3 Recovery RTO

| Failure Mode | RTO | Procedure |
|-------------|-----|-----------|
| Neo4j crash (data intact) | < 5 min | Restart container, consumer resumes from last offset |
| Neo4j data corruption | 15–30 min | Restore from latest dump + replay Kafka events since dump |
| Neo4j + volume loss | 30–60 min | Full Kafka replay from offset 0 (rebuild entire KG) |
| Kafka + Neo4j loss | 1–4 hours | Restore Neo4j from MinIO dump (last daily backup) |

**Full Kafka replay time estimate:**
- ~10,000 events: < 5 minutes
- ~100,000 events: < 30 minutes
- ~1,000,000 events: < 3 hours

Performance depends on Neo4j write throughput and MERGE complexity.

### 27.4 Read Replicas (Optional)

For high-read-throughput scenarios, Neo4j Enterprise supports read replicas:

```
Architecture:
  Primary (single writer, receives from Kafka consumer)
    └── Read Replica 1 (agent queries)
    └── Read Replica 2 (dashboard / observability)

Benefits:
  - Agents read from replicas, reducing load on primary
  - Dashboard queries don't compete with event processing
  - Replicas can be in different regions for latency

Trade-off:
  - Requires Neo4j Enterprise license
  - Replication lag (typically < 1s)
  - Not needed for small-to-medium projects (< 100K nodes)
```

---

## §28 Observability

### 28.1 SLI / SLO Table

| # | SLI (Service Level Indicator) | SLO (Service Level Objective) | Measurement Source | Collection Method |
|---|------|-----|---------|-------------------|
| 1 | σ-gate response time | < `config.approval.sigma_sla_hours` (default: 4h) | Kafka timestamps (SpanApproved - SpanDecomposed) | Kafka consumer computes delta on SpanApproved |
| 2 | V1–V17 validation violations | 0 for axiom violations (V1–V6); < 5 for warnings (V7–V17) | Cron job running validation queries every 15 min | cypher-shell → Prometheus push gateway |
| 3 | Kafka consumer lag | < 100 events | Kafka JMX: `records-lag-max` | Prometheus JMX exporter |
| 4 | KG write latency | p99 < 500ms | Consumer-side timing around Neo4j MERGE calls | Consumer internal metrics → Prometheus |
| 5 | Fulfillment rate | > 90% Contracts fulfilled per sprint | KG query: fulfilled / total active contracts | Scheduled query → Prometheus gauge |
| 6 | DLQ depth | 0 (any non-zero triggers alert) | Kafka JMX: consumer lag on apt-events-dlq | Prometheus JMX exporter |

### 28.2 Monitoring Stack

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Kafka JMX   │────▶│  Prometheus  │────▶│   Grafana    │
│  Exporter    │     │              │     │  Dashboards  │
└──────────────┘     └──────────────┘     └──────────────┘
                           ▲
┌──────────────┐           │
│  Neo4j       │───────────┘
│  Metrics     │  (neo4j.metrics.prometheus.enabled=true)
└──────────────┘
                           ▲
┌──────────────┐           │
│  V1-V17 Cron │───────────┘
│  (15min)     │  (push gateway)
└──────────────┘
                           ▲
┌──────────────┐           │
│  σ-gate      │───────────┘
│  Tracker     │  (Kafka consumer computed metrics)
└──────────────┘
```

**Kafka JMX Metrics (key):**
- `kafka.consumer:type=consumer-fetch-manager-metrics,client-id=*` → records-lag-max, fetch-rate
- `kafka.consumer:type=consumer-coordinator-metrics,client-id=*` → commit-rate, heartbeat-rate

**Neo4j Metrics (key):**
- `neo4j.bolt.connections_opened` — connection pool health
- `neo4j.database.transaction.committed` — write throughput
- `neo4j.database.cypher.replan_events` — query plan cache effectiveness
- `neo4j.page_cache.hit_ratio` — memory pressure indicator

**V1–V17 Cron:**
- Runs every 15 minutes via system cron or n8n workflow
- Executes all 17 validation queries against Neo4j
- Pushes violation counts as Prometheus metrics
- Zero violations for V1–V6 (axioms) is a hard SLO

**σ-gate Tracker:**
- Kafka consumer computes time between SpanDecomposed/SpanExplored and SpanApproved
- Tracks per-agent and per-span approval latency
- Alerts on SLA breach (default 4 hours)

### 28.3 Alerting Table

| # | Alert Name | Severity | Condition | Channel | Escalation |
|---|-----------|:--------:|-----------|---------|------------|
| P1-1 | Axiom Violation | P1 | V1–V6 returns any row | PagerDuty | Immediate: on-call engineer. 15min: team lead. |
| P1-2 | Consumer Down | P1 | Consumer heartbeat missing > 60s | PagerDuty | Immediate: on-call. Standby auto-promotes. |
| P1-3 | Self-Approval Detected | P1 | V15 returns any row | PagerDuty | Immediate: remove approval, re-review required. |
| P2-1 | σ-gate SLA Breach | P2 | SpanApproved - SpanDecomposed > SLA hours | Slack #apt-alerts | Auto-delegate chain after timeout. |
| P2-2 | DLQ Non-Empty | P2 | apt-events-dlq has > 0 unconsumed events | Slack #apt-alerts | On-call investigates within 1 hour. |
| P2-3 | Consumer Lag High | P2 | records-lag-max > 100 for > 5 min | Slack #apt-alerts | Check consumer health, scale if needed. |
| P3-1 | Stale Lock | P3 | V17 returns any row | Slack #apt-ops | Auto-release after lock_timeout. |
| P3-2 | KG Write Latency High | P3 | p99 > 500ms for > 10 min | Slack #apt-ops | Check Neo4j load, indexes, disk I/O. |
| P4-1 | Sparse Links | P4 | V16 count > 10% of AtomicSpans | Slack #apt-quality | Quality improvement sprint item. |
| P4-2 | Fulfillment Rate Low | P4 | < 90% per sprint | Slack #apt-quality | Sprint retrospective agenda item. |
| P5-1 | Backup Failure | P5 | neo4j-admin dump exit code ≠ 0 | Slack #apt-ops | Investigate storage, retry manually. |

### 28.4 Distributed Tracing via correlation_id

Every Kafka event carries a `correlation_id` (UUID). This ID traces a logical operation
across multiple events and system boundaries.

```
Example trace for a full SA→SP→ST→SCW cycle:

correlation_id: 550e8400-e29b-41d4-a716-446655440000

  1. SpanDecomposed   {parent: ROOT, children: [A, B, C]}     t=0ms
  2. SpanDecomposed   {parent: A, children: [A1, A2]}         t=50ms
  3. SpanApproved     {span: A1, reviewer: r1}                t=3600000ms (1h)
  4. SpanCrystallized {atom: A1, twin: ST_A1, ct: CT_A1}      t=3660000ms
  5. ContractLockAcquired {contract: CT_A1, agent: impl_1}     t=3700000ms
  6. ContractMaterialized {contract: CT_A1, source: a1.py}     t=7200000ms (2h)
  7. ContractLockReleased {contract: CT_A1, agent: impl_1}     t=7200500ms

Trace query (find all events for a logical operation):
  Kafka consumer: filter by correlation_id
  Grafana: Loki log search by correlation_id label
  Neo4j: MATCH (n) WHERE n.correlation_id = $id RETURN n
```

**correlation_id propagation rules:**
- A decomposition and all its child events share the same correlation_id
- Feedback events get a new correlation_id (new logical operation)
- ContractAmended from feedback gets the feedback's correlation_id
- CI/CD pipeline propagates correlation_id from the triggering event

---

## §29 Incident Response Matrix

All 17 validations mapped to severity, auto-fix capability, and full 4-step runbooks.

### V1 — A1 Violation: Contract not owned by Twin

| | |
|---|---|
| **Validation** | `MATCH (x)-[:HAS_CONTRACT]->(c) WHERE NOT x:SemanticTwin RETURN x.name` |
| **Severity** | P1 (Axiom) |
| **Auto-fix** | No — requires semantic judgment |

**Runbook:**
1. **Detect:** V1 query returns non-Twin node `x` owning a Contract.
2. **Diagnose:** Identify `x` label and how the HAS_CONTRACT edge was created. Check Kafka events for the erroneous write. Determine if the Contract should belong to an existing Twin or if a Twin is missing.
3. **Fix:** If Twin exists: `MATCH (x)-[r:HAS_CONTRACT]->(c), (tw:SemanticTwin {name: $correct_twin}) DELETE r MERGE (tw)-[:HAS_CONTRACT]->(c)`. If Twin is missing: create Twin via SpanCrystallized event, then re-link.
4. **Verify:** Re-run V1. Confirm zero results. Check V7/V8 to ensure no secondary violations introduced.

### V2 — A3 Violation: Sibling DEPENDS_ON

| | |
|---|---|
| **Validation** | `MATCH (p)-[:DECOMPOSES_TO]->(a),(p)-[:DECOMPOSES_TO]->(b) WHERE a<>b AND (a)-[:DEPENDS_ON]->(b) RETURN a.name, b.name` |
| **Severity** | P1 (Axiom) |
| **Auto-fix** | No — requires re-decomposition |

**Runbook:**
1. **Detect:** V2 query returns pairs `(a, b)` that are siblings with a DEPENDS_ON edge.
2. **Diagnose:** Determine if the dependency is real or an artifact. If real: the parent was decomposed incorrectly (children are not independent). If artifact: the DEPENDS_ON edge was created erroneously.
3. **Fix:** If real dependency: re-decompose parent. Merge `a` and `b` into a single span, or restructure so `b` is a child of `a` (not a sibling). If artifact: `MATCH (a)-[r:DEPENDS_ON]->(b) DELETE r`.
4. **Verify:** Re-run V2. Run V3 (branching factor) to ensure re-decomposition didn't create single-child spans.

### V3 — A2 Violation: Single-child decomposition

| | |
|---|---|
| **Validation** | `MATCH (s:AptSpan)-[:DECOMPOSES_TO]->(c) WHERE NOT s:AtomicSpan WITH s, count(c) AS k WHERE k=1 RETURN s.name` |
| **Severity** | P2 |
| **Auto-fix** | No — requires judgment (add child or merge) |

**Runbook:**
1. **Detect:** V3 query returns Spans with exactly 1 child.
2. **Diagnose:** Determine if the span should have more children (incomplete decomposition) or if the span and its single child should be merged (unnecessary intermediate level).
3. **Fix:** Option A: decompose further — publish SpanDecomposed event adding sibling children. Option B: merge — delete DECOMPOSES_TO edge, transfer child's edges to parent, remove child node.
4. **Verify:** Re-run V3. Confirm all non-atomic spans have ≥ `config.min_children` children.

### V4 — A2 Violation: Non-terminated leaf

| | |
|---|---|
| **Validation** | `MATCH (l:AptSpan) WHERE NOT (l)-[:DECOMPOSES_TO]->() AND NOT l:AtomicSpan RETURN l.name` |
| **Severity** | P3 |
| **Auto-fix** | No — requires decomposition or atomic approval |

**Runbook:**
1. **Detect:** V4 query returns leaf Spans without the AtomicSpan label.
2. **Diagnose:** Check if C(S) was evaluated. If all predicates pass: σ-gate is pending. If predicates fail: decomposition is incomplete.
3. **Fix:** If C(S) passes: request σ-gate approval, then label AtomicSpan. If C(S) fails: continue decomposition (publish SpanDecomposed event).
4. **Verify:** Re-run V4. Confirm all leaves are either AtomicSpan or have children.

### V5 — A4 Violation: Non-CRYSTALLIZES_TO SP→ST edge

| | |
|---|---|
| **Validation** | `MATCH (s:AptSpan)-[r]->(t:SemanticTwin) WHERE type(r)<>'CRYSTALLIZES_TO' RETURN s.name, type(r)` |
| **Severity** | P1 (Axiom) |
| **Auto-fix** | Yes — delete the erroneous edge |

**Runbook:**
1. **Detect:** V5 query returns Span→Twin edges that are not CRYSTALLIZES_TO.
2. **Diagnose:** Identify the edge type. Likely a data entry error or migration artifact.
3. **Fix:** Auto-delete: `MATCH (s:AptSpan)-[r]->(t:SemanticTwin) WHERE type(r)<>'CRYSTALLIZES_TO' DELETE r`. Publish alert to Slack for audit trail.
4. **Verify:** Re-run V5. Confirm zero results. Check V7 to ensure CRYSTALLIZES_TO edges are still intact.

### V6 — Cycle Detection

| | |
|---|---|
| **Validation** | `MATCH path=(s)-[:DECOMPOSES_TO*2..]->(s) RETURN [n IN nodes(path)\|n.name] LIMIT 1` |
| **Severity** | P1 (Axiom) |
| **Auto-fix** | No — requires identifying the youngest (most recent) edge in the cycle |

**Runbook:**
1. **Detect:** V6 query returns a cycle path.
2. **Diagnose:** Identify all edges in the cycle. Determine which edge was created most recently (check Kafka event timestamps or node `updated_at` properties).
3. **Fix:** Delete the youngest edge in the cycle: `MATCH (a {name: $source})-[r:DECOMPOSES_TO]->(b {name: $target}) DELETE r`. If the edge is needed, re-decompose to avoid the cycle.
4. **Verify:** Re-run V6. Confirm no cycles exist. Run V3/V4 to check for orphaned spans created by edge removal.

### V7 — Injectivity Violation: Multiple CRYSTALLIZES_TO

| | |
|---|---|
| **Validation** | `MATCH (a:AtomicSpan)-[:CRYSTALLIZES_TO]->(t1),(a)-[:CRYSTALLIZES_TO]->(t2) WHERE t1<>t2 RETURN a.name` |
| **Severity** | P2 |
| **Auto-fix** | No — requires choosing the correct Twin |

**Runbook:**
1. **Detect:** V7 query returns AtomicSpans linked to multiple Twins.
2. **Diagnose:** Determine which Twin is correct. Check Kafka event history for the AtomicSpan to see which CRYSTALLIZES_TO was intended.
3. **Fix:** Delete the duplicate edge: `MATCH (a:AtomicSpan {name: $atom})-[r:CRYSTALLIZES_TO]->(t:SemanticTwin) WHERE t.name <> $correct_twin DELETE r`. Clean up orphaned Twin if needed.
4. **Verify:** Re-run V7. Check V10 for duplicate Twins. Check V14 for hub consistency.

### V8 — Functional Violation: Multiple HAS_CONTRACT

| | |
|---|---|
| **Validation** | `MATCH (t:SemanticTwin)-[:HAS_CONTRACT]->(c1),(t)-[:HAS_CONTRACT]->(c2) WHERE c1<>c2 RETURN t.name` |
| **Severity** | P2 |
| **Auto-fix** | No — requires merging Contracts |

**Runbook:**
1. **Detect:** V8 query returns Twins with multiple Contracts.
2. **Diagnose:** Compare the two Contracts' fields. Determine if one is a stale version, or if they represent distinct concerns that should be separate Twins.
3. **Fix:** If stale: delete older Contract and its edge. If distinct concerns: split the Twin into two Twins, each with one Contract. Publish appropriate Kafka events.
4. **Verify:** Re-run V8. Check V7 and V13 for cascading issues.

### V9 — Disjointness Violation: Multi-labeled node

| | |
|---|---|
| **Validation** | `MATCH (n) WHERE (n:AptSpan AND n:SemanticTwin) OR (n:SemanticTwin AND n:AptContract) RETURN n.name` |
| **Severity** | P2 |
| **Auto-fix** | Yes — remove the incorrect label |

**Runbook:**
1. **Detect:** V9 query returns nodes with conflicting labels.
2. **Diagnose:** Determine the node's true type from Kafka event history.
3. **Fix:** Auto-remove incorrect label: `MATCH (n {name: $name}) REMOVE n:IncorrectLabel`. Publish alert for audit.
4. **Verify:** Re-run V9. Confirm zero results.

### V10 — Duplicate Twin Names

| | |
|---|---|
| **Validation** | `MATCH (tw:SemanticTwin) WITH tw.name AS n, count(tw) AS c WHERE c>1 RETURN n` |
| **Severity** | P2 |
| **Auto-fix** | No — requires merging duplicates |

**Runbook:**
1. **Detect:** V10 query returns Twin names that appear more than once.
2. **Diagnose:** Identify all nodes with the duplicate name. Compare properties. Determine which is canonical (usually the one with more edges).
3. **Fix:** Merge duplicates: transfer all edges from the duplicate to the canonical node, then delete the duplicate. Use MERGE operations to prevent data loss.
4. **Verify:** Re-run V10. Confirm `twin_unique` constraint would now hold. Check V7, V8, V14 for edge consistency.

### V11 — Null Status

| | |
|---|---|
| **Validation** | `MATCH (n) WHERE (n:AptSpan OR n:SemanticTwin OR n:AptContract) AND n.status IS NULL RETURN n.name` |
| **Severity** | P3 |
| **Auto-fix** | Yes — SET status = 'draft' |

**Runbook:**
1. **Detect:** V11 query returns nodes missing a status property.
2. **Diagnose:** These are typically nodes created by incomplete events or migration artifacts.
3. **Fix:** Auto-fix: `MATCH (n) WHERE (n:AptSpan OR n:SemanticTwin OR n:AptContract) AND n.status IS NULL SET n.status = 'draft'`.
4. **Verify:** Re-run V11. Confirm zero results.

### V12 — Orphan Contract

| | |
|---|---|
| **Validation** | `MATCH (ct:AptContract) WHERE NOT ()-[:HAS_CONTRACT]->(ct) RETURN ct.name` |
| **Severity** | P3 |
| **Auto-fix** | No — requires linking or deletion judgment |

**Runbook:**
1. **Detect:** V12 query returns Contracts not owned by any Twin.
2. **Diagnose:** Check if a Twin exists that should own this Contract (naming convention match). Check Kafka events for how the Contract was created.
3. **Fix:** If matching Twin exists: `MERGE (tw:SemanticTwin {name: $twin})-[:HAS_CONTRACT]->(ct:AptContract {name: $contract})`. If no match: delete the orphan Contract (after confirming no SourceCodeNode depends on it).
4. **Verify:** Re-run V12. Confirm zero results. Check V1 to ensure new link doesn't create axiom violation.

### V13 — Broken Chain: Atom → Twin → Contract count mismatch

| | |
|---|---|
| **Validation** | `MATCH (root)-[:DECOMPOSES_TO*1..6]->(a:AtomicSpan) WITH DISTINCT a OPTIONAL MATCH (a)-[:CRYSTALLIZES_TO]->(tw) OPTIONAL MATCH (tw)-[:HAS_CONTRACT]->(ct) WITH count(a) AS atoms, count(tw) AS twins, count(ct) AS cts WHERE atoms<>twins OR twins<>cts RETURN atoms, twins, cts` |
| **Severity** | P2 |
| **Auto-fix** | No — requires completing missing links |

**Runbook:**
1. **Detect:** V13 query returns mismatched counts (atoms ≠ twins ≠ contracts).
2. **Diagnose:** Identify which AtomicSpans are missing Twins or which Twins are missing Contracts. `MATCH (a:AtomicSpan) WHERE NOT (a)-[:CRYSTALLIZES_TO]->() RETURN a.name`.
3. **Fix:** For each missing link: run the Crystallize() procedure (PH4) for the AtomicSpan. Publish SpanCrystallized events as needed.
4. **Verify:** Re-run V13. Confirm atoms = twins = contracts.

### V14 — Incomplete Hub

| | |
|---|---|
| **Validation** | `MATCH (cx:CrystallizationEvent) WHERE NOT (cx)-[:INVOLVES{role:'atom'}]->() RETURN cx.name` |
| **Severity** | P3 |
| **Auto-fix** | No — requires adding INVOLVES edges |

**Runbook:**
1. **Detect:** V14 query returns Hubs missing the 'atom' role (minimum required INVOLVES edge).
2. **Diagnose:** Check which roles are present on the Hub. A complete Hub should have: atom, twin, task, contract (and optionally source after PH5).
3. **Fix:** Identify the correct AtomicSpan by naming convention (`CX_X` → `ATOM_X`). Add missing edge: `MATCH (cx:CrystallizationEvent {name: $hub}), (a:AtomicSpan {name: $atom}) MERGE (cx)-[:INVOLVES{role:'atom'}]->(a)`. Repeat for other missing roles.
4. **Verify:** Re-run V14. Extend check: verify all Hubs have at least atom + twin + contract roles.

### V15 — Self-Approval

| | |
|---|---|
| **Validation** | `MATCH (s:AtomicSpan)-[:APPROVED_BY]->(r:AptAgent) WHERE s.executor = r.name RETURN s.name` |
| **Severity** | P1 |
| **Auto-fix** | Yes — remove the APPROVED_BY edge |

**Runbook:**
1. **Detect:** V15 query returns AtomicSpans where executor = reviewer.
2. **Diagnose:** Violation of separation of duties. The approval is invalid regardless of correctness.
3. **Fix:** Auto-remove: `MATCH (s:AtomicSpan {name: $span})-[r:APPROVED_BY]->(a:AptAgent) WHERE s.executor = a.name DELETE r`. Remove AtomicSpan label: `MATCH (s {name: $span}) REMOVE s:AtomicSpan`. Require re-approval from a different reviewer.
4. **Verify:** Re-run V15. Confirm zero results. Verify the span lost its AtomicSpan label and is queued for re-review.

### V16 — Sparse Links

| | |
|---|---|
| **Validation** | `MATCH (s:AtomicSpan) WITH s, size([(s)-[:INFORMED_BY]->()\|1]) AS l WHERE l < 5 RETURN s.name` |
| **Severity** | P4 |
| **Auto-fix** | No — quality improvement, not critical |

**Runbook:**
1. **Detect:** V16 query returns AtomicSpans with fewer than `config.min_informed_by` (default 5) INFORMED_BY links.
2. **Diagnose:** These spans may have been rushed through without sufficient research or context gathering. Low link density suggests incomplete D4 (DenseBeforeContract) compliance.
3. **Fix:** For each sparse span: gather additional context (requirements, related spans, external references). Add INFORMED_BY edges: `MATCH (s:AtomicSpan {name: $span}), (ref {name: $reference}) MERGE (s)-[:INFORMED_BY]->(ref)`.
4. **Verify:** Re-run V16. Track as sprint quality metric rather than blocking issue.

### V17 — Stale Lock

| | |
|---|---|
| **Validation** | `MATCH (ct:AptContract) WHERE ct.locked_by IS NOT NULL AND ct.locked_at < datetime() - duration('PT1H') RETURN ct.name` |
| **Severity** | P3 |
| **Auto-fix** | Yes — release the lock |

**Runbook:**
1. **Detect:** V17 query returns Contracts locked for longer than `config.concurrency.lock_timeout_minutes` (default 60 minutes).
2. **Diagnose:** The agent holding the lock likely crashed or lost connection. Check agent logs and heartbeat history.
3. **Fix:** Auto-release: `MATCH (ct:AptContract {name: $contract}) REMOVE ct.locked_by, ct.fencing_token, ct.locked_at, ct.lock_heartbeat`. Log the release for audit.
4. **Verify:** Re-run V17. Confirm zero results. Check if the agent's in-progress work needs cleanup.

---

## §30 CI/CD Pipeline

### 30.1 GitHub Actions Workflow

```yaml
# .github/workflows/apt-ci.yaml
name: APT CI/CD Pipeline
on:
  push:
    branches: [main, 'feature/**']
  pull_request:
    branches: [main]

env:
  NEO4J_URI: bolt://localhost:7687
  NEO4J_USER: neo4j
  NEO4J_PASSWORD: ${{ secrets.NEO4J_PASSWORD }}
  KAFKA_BOOTSTRAP: localhost:29092
  COVERAGE_THRESHOLD: 0.8

jobs:
  # ─────────────────────────────────────────────
  # Job 1: Validate KG integrity and code quality
  # ─────────────────────────────────────────────
  apt-validate:
    runs-on: self-hosted
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        # Checks out the repository code for validation.

      - name: Run V1–V17 Validation Queries
        run: cypher-shell -f validations/v1_v17.cypher
        # Executes all 17 validation queries against the live Neo4j instance.
        # Any axiom violation (V1–V6) fails the pipeline immediately.
        # Warning violations (V7–V17) are logged but may not block (configurable).

      - name: Run Unit Tests with Coverage
        run: pytest --cov --cov-fail-under=$COVERAGE_THRESHOLD
        # Runs the full test suite with coverage measurement.
        # Fails if coverage drops below the configured threshold (default: 80%).
        # Includes TDAD impact tests and stochastic NFR tests.

      - name: KG-Git Reconciliation
        run: python scripts/kg_git_reconcile.py
        # Exports KG contracts to YAML and diffs against contracts/*.yaml in repo.
        # Verifies all SourceCodeNode.file_path entries exist as actual files.
        # Verifies all Task.impact_tests reference valid test files.
        # Flags mismatches as CI failures with detailed diff output.

      - name: Lint and Type Check
        run: |
          ruff check .
          mypy --strict src/
        # Static analysis to catch issues before they reach KG.
        # Type checking ensures Contract type annotations are valid.

  # ─────────────────────────────────────────────
  # Job 2: Verify approval gates and fulfillment
  # ─────────────────────────────────────────────
  apt-gate:
    runs-on: self-hosted
    needs: apt-validate
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Check σ-Approvals
        run: python scripts/check_sigma_approvals.py
        # Queries KG for all AtomicSpans in this branch.
        # Verifies each has a valid APPROVED_BY edge with criterion='sigma'.
        # Verifies executor ≠ reviewer for every approval.
        # Fails if any AtomicSpan lacks approval or has self-approval.

      - name: Check Fulfillment Gates
        run: python scripts/check_fulfillment_gates.py
        # For each Contract marked as 'fulfilled' in this branch:
        #   1. All acceptance tests pass (re-run)
        #   2. Output type matches contract.output_type
        #   3. Pre/postconditions are checked in source code
        #   4. KG ref comments present (# KG: TASK_xxx, CONTRACT_xxx)
        #   5. Complexity ≤ threshold
        #   6. Test-Contract alignment (tests verify postcondition)
        #   7. NFR assertions pass (if defined)
        # Any failed check blocks the pipeline.

      - name: Check Contract Chain Completeness
        run: python scripts/check_chain_completeness.py
        # Runs V13 equivalent: verifies atoms = twins = contracts.
        # Ensures no AtomicSpan is left without crystallization.
        # Reports which spans need attention.

  # ─────────────────────────────────────────────
  # Job 3: Deploy (publish event, update KG)
  # ─────────────────────────────────────────────
  apt-deploy:
    runs-on: self-hosted
    needs: apt-gate
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Publish ContractDeployed Events
        run: python scripts/publish_kafka_event.py ContractDeployed
        # For each Contract that was fulfilled in this merge:
        #   Publishes a ContractDeployed event to Kafka with:
        #     - contract_name
        #     - environment: prod
        #     - version: git tag or commit SHA
        #     - correlation_id: from the merge commit
        # Consumer updates KG: SET contract.deployed_env, deployed_version, deployed_at.

      - name: Export KG Snapshot
        run: python scripts/kg_export_snapshot.py
        # Exports current KG state to apt-structure.yaml and contracts/*.yaml.
        # Commits the export to the repo (auto-commit, skip CI).
        # Ensures Git always has a readable copy of KG metadata.

      - name: Notify
        run: python scripts/notify_deploy.py
        # Posts deployment summary to Slack #apt-deployments.
        # Includes: contracts deployed, coverage, validation status.
        # Links to Grafana dashboard for post-deploy monitoring.
```

### 30.2 Pipeline Flow Diagram

```
Push / PR
    │
    ▼
┌─────────────────┐
│  apt-validate    │
│                  │
│  V1-V17 queries  │──── FAIL → Block merge, create AptFeedback
│  pytest + cov    │
│  KG-Git reconcile│
│  lint + typecheck│
└────────┬────────┘
         │ PASS
         ▼
┌─────────────────┐
│  apt-gate        │
│                  │
│  σ-approvals     │──── FAIL → Block merge, notify reviewer
│  fulfillment     │
│  chain complete  │
└────────┬────────┘
         │ PASS
         ▼
┌─────────────────┐
│  apt-deploy      │   (main branch only)
│                  │
│  Kafka events    │
│  KG snapshot     │
│  Slack notify    │
└─────────────────┘
```

### 30.3 Branch Protection Rules

```
Branch: main
  Required checks:   apt-validate, apt-gate
  Required reviews:  1 (separate from σ-gate — this is code review)
  Merge strategy:    Squash merge (clean history)
  Auto-delete head:  Yes

Branch: feature/**
  Required checks:   apt-validate
  Required reviews:  0 (σ-gate covers approval at KG level)
```

---

*APT v11 Infrastructure — §23 Kafka Event Sourcing (10 events, envelope, topics, consumer HA, locking, schema evolution, DLQ) · §24 KG-Git Sync (dual truth, reconciliation, branch strategy, conflicts) · §25 MERGE-Only (9 node types, naming, LWW) · §26 Index Strategy (8 indexes, 2 constraints, 1 rel index) · §27 KG HA (Kafka WAL, backup, RTO, replicas) · §28 Observability (6 SLIs, monitoring stack, 11 alerts, tracing) · §29 Incident Response (17 validations × 4-step runbook) · §30 CI/CD (3 jobs, branch protection).*
