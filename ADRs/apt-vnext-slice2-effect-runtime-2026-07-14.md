# ADR: APT vNext Slice 2 effect-runtime proposal contract

- **Status**: PROPOSED — implementation contract for Slice 2; not a production verdict
- **Date**: 2026-07-14
- **Authority layer**: `SECONDARY_AI_ENGINEERING_PROPOSAL`
- **Upstream proposal**: `SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md`
- **Machine-readable companion**: `engine/apt_runtime/specs/apt_engine_fsm.v1.json`, version `1.1.0-proposal.8`
- **Canon warning**: the resolutions in this ADR are not `USER_PRIMARY`, are not a human sigma verdict, and have not been written to or ratified as KG canon. Existing KG references provide context only.

---

## Context

Slice 1 made event append, command receipts, snapshots, and requested-effect outbox rows durable. It deliberately left delivery ownership out of the `EventStore`: an outbox row says that an effect was requested, not that a particular worker may execute it.

Slice 2 must make duplicate delivery, stale leases, timeouts, cancellation, and the crash window after an external write auditable. The original proposal names lease owner, expiry, heartbeat, attempts, idempotency, and reconciliation, but its earlier companion did not completely define heartbeat facts, attempt fencing, cancellation authority, or result durability. It also left “post-cancellation late outcome” ambiguous between cycle cancellation and the absorbing effect state.

This ADR records the executable proposal.8 boundary implemented under `engine/apt_runtime/`. It does not promote the upstream proposal to canon and does not claim production readiness. It also does not supersede the accepted scope boundary in `apt-tpa-engine-substrate-scope-2026-06-14.md` (or its partially superseded predecessor): this branch-local runtime experiment does not make SA/SP/ST/SCW cognition deterministic or silently move that orchestration into production scope. Any such scope change still requires an explicit user/KG verdict.

## Decision

### 1. Every lease acquisition receives a fencing token and a verified execution grant

`EffectLeased` requires:

```text
lease_owner, lease_token, lease_expiry,
grant_ref, grant_hash, config_version,
authorization_ref, authorization_hash
```

The token identifies one acquisition of one effect. A later acquisition uses a different token. Lease-bound facts must cite the token they belong to; worker identity alone cannot fence a stale process after expiry and reclamation.

The immutable `EffectExecutionGrant` has this exact grant-hash scope:

```text
grant_ref, cycle_id, effect_id, capability, provider, risk_class,
config_version, resource_claims, budget,
authorization_ref, authorization_hash
```

It binds capability, provider, risk class, resource claims, runtime budget, configuration snapshot, authorization evidence, and the cycle-local effect identity. `effect_id` alone is not globally unique. `EffectScheduler.lease` accepts the grant only after the injected `EffectGrantVerifier` verifies it and after both `cycle_id` and `effect_id` match the canonical queued effect and cycle configuration. Its grant and authorization references and hashes are then stored in both `EffectLeased` and the operational lease row. The `EffectLeased` envelope supplies the same `cycle_id` and `effect_id`, while `grant_hash` commits those identities inside the grant itself.

An operational queue reservation may precede the domain fact while the scheduler arbitrates contenders. That reservation grants no authority to call an external system. External execution is forbidden until `EffectLeased` commits and the queue advances from `RESERVED` to `ACTIVE`. If the holder dies before that commit barrier, recovery may abandon the reservation without inventing an execution transition.

Implementation anchors: `domain/effect_runtime.py`, `application/effect_scheduler.py`, `ports/effect_queue.py`, `tests/test_effect_scheduler.py::test_commit_barrier_precedes_provider_and_success_is_durable`, and the pre-event-orphan cases in the SQLite and PostgreSQL queue tests.

### 2. Heartbeat renewal is canonical

The canonical event is `EffectHeartbeatRecorded` with:

```text
lease_owner, lease_token, heartbeat_at, lease_expiry
```

It has two explicit self-transitions:

```text
LEASED  --effect.heartbeat.leased-->  LEASED
RUNNING --effect.heartbeat.running--> RUNNING
```

Both owner and token must match the active lease. `heartbeat_at` and the renewed expiry are supplied through the injected clock boundary; the reducer does not read ambient time. The fact commits before the operational queue projection is renewed. Heartbeat therefore survives replay, participates in the canonical state hash, and can repair a stale queue projection.

Implementation anchors: `application/effect_scheduler.py::heartbeat`, `application/effect_recovery.py::_repair_heartbeat_projection`, `domain/effect_reducer.py`, `tests/test_effect_fencing.py`, and `tests/test_effect_recovery.py::test_heartbeat_is_canonical_and_wrong_owner_cannot_renew`.

### 3. Attempt outcomes, expiry, and cancellation use exact fenced payloads

The proposal.8 effect facts use these exact payloads:

| Fact | Required payload |
|---|---|
| `EffectStarted` | `attempt`, `lease_token` |
| `EffectSucceeded` | `attempt`, `lease_token`, `result_ref`, `result_hash` |
| `EffectFailed` | `attempt`, `lease_token`, `reason` |
| `EffectLeaseExpired` | `lease_token`, `reconciliation_ref`, `expected_heartbeat_at`, `expected_lease_expiry` |
| `EffectTimedOut` | `attempt`, `lease_token`, `reconciliation_ref`, `expected_heartbeat_at`, `expected_lease_expiry` |
| `EffectRetryQueued` | `guard_result`, `guard_evidence_refs`, `lease_token`, `reconciliation_ref`, `reconciliation_outcome` |
| `EffectCancelled` | `reason`, `authorization_ref`, `authorization_hash` |

`EffectLeaseExpired` represents expiry before execution starts, so it has no attempt field. A running timeout names both the started attempt and its lease. A retry cites the previous lease token and reconciliation evidence; the next lease acquisition creates the next token.

The two `expected_*` fields are compare-and-set evidence, not descriptive timestamps. Recovery or the scheduler reads the replayed canonical heartbeat and expiry and places those exact values in the expiry/timeout fact. The reducer rejects the fact if either value no longer equals the active canonical lease. `EffectFactWriter` then commits through the event-store stream-version CAS, so a concurrent heartbeat cannot be silently overwritten by a stale expiry decision.

Implementation anchors: `specs/apt_engine_fsm.v1.json`, `domain/effect_reducer.py::_expire_lease`, `domain/effect_reducer.py::_timeout_effect`, `application/effect_recovery.py`, and `tests/test_effect_fencing.py`.

### 4. Unknown external-write outcomes converge only through bounded reconciliation

Arbitrary external systems are not claimed to be exactly-once. The executor uses the effect idempotency key, target/input hash, fenced execution identity, and provider evidence to reconcile before any retry.

The provider reconciliation port returns the closed enum:

```text
APPLIED | NOT_APPLIED | FAILED | UNKNOWN
```

The canonical rules are:

1. expiry or timeout first becomes an auditable `TIMED_OUT` state;
2. only `NOT_APPLIED` may return `FAILED` or `TIMED_OUT` to `PENDING`, and only through `EffectRetryQueued` with a `PASS` idempotency/reconciliation guard;
3. `APPLIED` from a timed-out attempt persists and verifies the result, then drives `EffectSucceeded` through `effect.reconcile.succeed`;
4. `UNKNOWN` remains fenced and non-retryable; blind replay is forbidden;
5. a reconciliation-provider failure remains auditable failure evidence and does not authorize replay;
6. a reconciliation probe consumes the immutable `reconciliation_probes` budget independently from execution attempts and no-progress accounting.

`reconciliation_outcome` is the enum value, not provider prose. The reducer accepts `EffectRetryQueued` only when it is `NOT_APPLIED`; a `PASS` guard cannot relabel another outcome.

`NOT_APPLIED` has a strong provider-contract meaning: for the exact idempotency key and fenced execution identity, the external mutation was not applied **and no invocation from that identity remains capable of committing later**. A momentary read that finds no result while an earlier call is still in flight is not `NOT_APPLIED`; it is `UNKNOWN`. Resource claims and retry authority may be released only after this final non-application assertion. This rule is required to make cancellation/provider and timeout/provider races safe, not an optional policy refinement.

The operational single-flight permit protocol is specified separately below because it coordinates provider calls without becoming a second lifecycle authority.

One race remains deliberately unresolved in this proposal: recovery may commit `TIMED_OUT` while the original provider call is still in flight, after which that exact call may return a definitive success. The FSM can represent the resulting `RUNNING -> TIMED_OUT -> SUCCEEDED` attempt history, but the scheduler does not directly publish that late return because a concurrent reconciliation permit could be acquired between a non-atomic permit check and the success fact. The current safe behavior retains the queue in reconciliation and requires provider reconciliation. Direct convergence requires the no-charge atomic seal described under Deferred; a permit-free read check alone is not a multi-process fence.

Implementation anchors: `application/effect_reconciliation.py`, `domain/effect_reducer.py::_retry_effect`, `ports/effects.py`, and the APPLIED, UNKNOWN, NOT_APPLIED, and no-progress cases in `tests/test_effect_scheduler.py`.

### 5. Caller-initiated cancellation requires typed, trusted authority

`EffectScheduler.cancel` accepts an `EffectCancellationAuthorization`, not arbitrary actor/reason strings. The immutable authorization has this exact signature-verification scope:

```text
cycle_id, effect_id, actor, reason, authorization_ref, authorization_hash
```

The injected `EffectCancellationVerifier` is the trust boundary. Its signature or canonical-digest verification must include `cycle_id` as well as the other decision fields; structural validation, including lowercase SHA-256 shape, is not itself proof of authority. After trusted verification, the scheduler independently rejects an authorization whose `cycle_id` differs from the lease stream or whose `effect_id` differs from the leased effect before appending `EffectCancelled`. This second check prevents a verifier-approved authority for another cycle from being replayed where the same local effect id exists.

The canonical event payload carries `reason`, `authorization_ref`, and `authorization_hash`; its envelope carries `cycle_id`, `effect_id`, and `actor`. The `CanonicalCommandEnvelope.authorization_context` carries `cycle_id`, `effect_id`, `authorization_ref`, and `authorization_hash`, and the command envelope independently carries the same cycle. The durable command hash/receipt and event fact therefore preserve the complete cycle-effect decision provenance without treating caller-supplied hash syntax as authorization.

Automatic cancellation caused by an exhausted verified runtime budget is a distinct internal policy path. Its authorization reference/hash are deterministically derived from the cycle configuration version and verified grant hash. It does not make the public cancellation verifier optional.

Implementation anchors: `domain/effect_runtime.py::EffectExecutionGrant`, `ports/effects.py::EffectCancellationAuthorization`, `ports/effects.py::EffectCancellationVerifier`, `application/effect_scheduler.py::lease`, `application/effect_scheduler.py::cancel`, `application/effect_facts.py`, `tests/test_effect_scheduler.py::test_lease_rejects_verified_grant_bound_to_another_cycle`, and `tests/test_effect_scheduler.py::test_cancellation_requires_verified_effect_bound_authority`.

### 6. Effect cancellation is absorbing, while a started attempt remains an operational uncertainty

`EffectCancelled` moves any nonterminal effect lifecycle to absorbing `CANCELLED`. No success, failure, heartbeat, retry, or reconciliation event may transition the effect out of that state.

If cancellation races with or follows `EffectStarted`, the queue must not release resource claims merely because the canonical lifecycle became `CANCELLED`. It remains `RECONCILING` until provider evidence proves `NOT_APPLIED`, in which case it may close `CANCELLED`. An observed `APPLIED`, `UNKNOWN`, or provider/reconciliation failure remains fenced for compensation or manual resolution. A provider return after canonical cancellation cannot reopen the effect; a successful late return is recorded as durable result evidence when possible and the queue remains reconciling.

The cancellation/dispatch linearization point is the queue's atomic `ACTIVE -> RUNNING` start commit. If cancellation wins first and moves the queue to `CANCELLED` or `RECONCILING`, `start` must fail and the scheduler must not call the provider. If `start` commits first, dispatch already has permission: later cancellation is cooperative, so the provider invocation may continue and return late. In that branch cancellation preserves claims pending the strong `NOT_APPLIED` assertion or another authorized resolution. Consequently, a successful return from `cancel` does **not** promise that the provider was never called; it promises that no new dispatch may cross the start fence after cancellation won.

For a cancelled started attempt, the coordinator also rejects reconciliation probes before the original execution lease expires. Lease expiry is the minimum quiescence barrier against treating an obviously live invocation as absent; after expiry the provider must still satisfy the stronger `NOT_APPLIED` contract above before claims or retry authority can be released.

“Late outcome after cancellation” in the FSM's separate rule means an outcome submitted after the **cycle** was cancelled for an already-recorded effect that was not itself moved to `EffectLifecycle.CANCELLED`. Such an outcome may advance the effect's audit lifecycle but cannot reopen the cycle or materialize a current-generation artifact. It never means a transition out of effect-level `CANCELLED`.

The current Slice 2 implementation deliberately chooses safety over liveness here. It has no authorized compensation command or manual-resolution API that can release claims after cancelled `APPLIED`, `UNKNOWN`, or failed reconciliation; that work is deferred below.

Implementation anchors: `domain/effect_reducer.py::_cancel_effect`, `application/effect_scheduler.py::_record_post_cancel_result`, `application/effect_reconciliation.py`, `application/effect_recovery.py::_close_if_canonical_terminal`, and `tests/test_effect_recovery.py::test_late_success_after_cancellation_cannot_reopen_effect`.

### 7. Success facts cite results that were made durable first

`EffectSucceeded` stores a `result_ref` and `result_hash`, not inline provider output. Before emitting that fact, normal execution and APPLIED reconciliation call `EffectResultStore.persist`, compare the returned hash with canonical result bytes, and call `verify`. Failure to persist or verify does not append success.

`SqliteEffectResultStore` is the concrete Slice 2 adapter. It stores canonical JSON bytes under a content-addressed reference, enforces one immutable result per `(cycle_id, effect_id, attempt)`, supports idempotent re-persist across concurrent connections after a crash, and revalidates the reference, execution identity, canonical bytes, and digest on every read. Its namespaced `effect_result_store_schema`/`effect_result_store_results` v1 schema marker and exact DDL signature fail closed on incompatible tables or extra result-store DDL while allowing the store to share and reopen the runtime database; its concrete `load` returns a deeply immutable canonical mapping. This proposal does not claim a production PostgreSQL/object-store result adapter.

Implementation anchors: `application/effect_scheduler.py::_persist_result`, `application/effect_reconciliation.py::_persist_result`, `adapters/sqlite_effect_result_store.py`, `tests/test_effect_scheduler.py::test_commit_barrier_precedes_provider_and_success_is_durable`, and all cases in `tests/test_sqlite_effect_result_store.py`.

### 8. Resource, budget, and stale-recovery controls fence execution

Before external execution, the scheduler requires a committed effect lease, non-conflicting resource claims, remaining attempt and configured resource budgets, and a verified execution grant for the provider/capability/risk identity. Overlapping exclusive resource claims serialize or reject rather than racing. A stable no-progress signature and bounded probe count are accumulated in the operational usage ledger.

Recovery receives `heartbeat_stale_after_seconds` as a positive constructor argument and derives `heartbeat_before` from the injected clock. The queue may select a row because its lease expired or its heartbeat is at or before that cutoff, but recovery replays canonical state before deciding what to repair or expire.

The stale-heartbeat duration is currently an application-composition trust boundary, not a field proven by `EffectGrantVerifier`, a signed configuration object, or an FSM constant. Deployments must treat construction of `EffectRecovery` as trusted. Binding this value to signed policy is deferred; this ADR does not describe the current integer as canonically authorized configuration.

Implementation anchors: `domain/effect_runtime.py`, both queue adapters, `application/effect_scheduler.py`, `application/effect_recovery.py`, `tests/test_sqlite_effect_queue.py`, `tests/test_postgres_effect_queue.py`, and `tests/test_effect_recovery.py`.

### 9. The queue journal is an operational integrity ledger, not canonical lifecycle authority

The cycle event stream replayed with the pinned FSM specification is authoritative for effect lifecycle and canonical grant/cancellation facts. The queue owns the pre-event reservation, current delivery projection, resource exclusion, cumulative runtime usage, and reconciliation coordination needed to reach the next fact.

SQLite and PostgreSQL keep per-lease, position-contiguous, hashed state/usage journal entries and cross-check mutable lease/usage rows against those entries. Queue schema v2 additionally inserts one immutable cryptographic prefix checkpoint for every journal position. Each checkpoint commits to the prior checkpoint hash plus lease token, position, action, timestamp, and detail hash. Appending validates all existing checkpoints before inserting the journal row and its next checkpoint in the same transaction; loading performs exact typed replay and verifies the entire checkpoint sequence. Deleting a final `USAGE_RECORDED` or `PROBE_ACQUIRED` tail and rewinding the mutable ledger/permit therefore leaves a later checkpoint and fails closed instead of refunding budget or authorizing a duplicate probe.

The runtime code only `INSERT`s checkpoints. SQLite exact DDL includes `BEFORE UPDATE`/`BEFORE DELETE` guards; PostgreSQL includes an exactly audited statement trigger covering `UPDATE`, `DELETE`, and `TRUNCATE`, and rejects unreviewed rewrite rules. This boundary protects ordinary runtime DML, including a compromised worker using the deployment DML role. A schema owner can drop/disable the guard and rewrite both history and checkpoints, and a DBA/storage administrator can roll back the whole database; those actors are outside this adapter-local tamper-evidence boundary and require separate least-privilege deployment, backup, and external audit controls. “Canonical” in queue helper names refers to canonical JSON encoding and exact schema/projection rules; it does not elevate `effect_runtime_journal` above the event stream or let a queue row authorize a domain transition.

The operational ledger is nevertheless authoritative for its own non-event coordination data, including resource locks, charged usage, and probe permits. Those values are not all reconstructible from effect facts. Losing the queue therefore requires an explicit operational recovery/migration procedure; it is not permission to synthesize lifecycle events, reset budgets, or replay an external effect. On ordinary divergence, recovery repairs or closes the projection from canonical replay, or fails closed when grant/owner/config evidence disagrees.

Implementation anchors: `application/effect_facts.py`, `ports/effect_queue.py`, `_effect_queue_journal_chain.py`, `_effect_queue_journal_replay.py`, both queue schema modules, `_sqlite_effect_queue_integrity.py`, `_postgres_effect_queue_journal.py`, and the journal tail-deletion, checkpoint-guard, typed-replay, and rewind cases in both adversarial queue test modules.

## Reconciliation probe permit protocol

The durable permit is operational coordination scoped to one lease epoch. `LeaseRecord` carries a monotonically increasing `probe_generation` and an optional `ReconciliationProbePermit`:

```text
permit_token, generation, state,
acquired_at, expires_at,
concluded_at?, conclusion?
```

`state` is `ACTIVE` or `CONCLUDED`. A `ReconciliationProbeConclusion` seals the provider outcome, evidence references, reason, and—only for `APPLIED`—the already-durable result reference/hash. The conclusion has a canonical digest beside its stored bytes.

The protocol is:

1. `begin_reconciliation_probe` requires a `RECONCILING` lease, a non-empty permit token, and `expires_at > acquired_at`. The coordinator normally obtains a token from its injected ID generator, but the adapters do not treat global or historical token uniqueness as the safety fence.
2. With no existing permit, acquisition advances the generation and atomically journals `PROBE_ACQUIRED` and charges exactly one `reconciliation_probes` unit. The returned `ReconciliationProbeAcquisition.charged` is true.
3. A second acquisition before the active permit expires conflicts. After expiry, takeover advances to the next generation even when an adapter caller reuses the same token. It inherits the already-charged logical probe (`charged == false`) rather than refunding or charging again, so a process crash cannot consume the entire immutable probe budget. The authoritative anti-ABA fence is the lease epoch plus monotonically increasing probe generation; the token is additional identity, not a freshness guarantee. The stale generation can no longer conclude.
4. `conclude_reconciliation_probe` succeeds only for the exact current active permit, before that generation's expiry. It atomically replaces it with a `CONCLUDED` permit and journals the hashed conclusion. A replaced token/generation, an expired generation, or replay with different evidence is rejected.
5. `APPLIED` result bytes must be persisted and verified before the conclusion is sealed. A concluded APPLIED permit therefore contains only a durable result identity, never an unbacked success reference.
6. Final queue mutation (`finish` or `mark_reconciling`) must present the exact concluded permit; the adapter then clears it. A live active permit or stale concluded generation cannot release claims or publish a lifecycle consequence.
7. If the process crashes after conclusion but before its canonical fact or queue finalization, the coordinator resumes the sealed conclusion without calling the provider or charging budget again. For APPLIED it reloads and verifies the durable result first. Recovery closes a projection when the matching canonical fact already exists; otherwise it reports the conclusion as pending for coordinator resumption.
8. Recovery reports an unexpired active generation as `PROBE_IN_FLIGHT` and an expired one as `PROBE_TAKEOVER_READY`; it does not overwrite either permit.

`reconciliation_probe_ttl_seconds` is a positive coordinator-construction value used to derive permit and conclusion expiry from the injected clock. Like the current heartbeat-staleness duration, it is an application-composition trust boundary in proposal.8, not an FSM constant or independently signed policy field.

Permit fields and `PROBE_ACQUIRED`/`PROBE_CONCLUDED` entries remain in the operational integrity ledger. They fence provider calls and make observations resumable, but only canonical `EffectSucceeded`, `EffectRetryQueued`, or `EffectCancelled` facts may change the effect lifecycle.

Implementation anchors: `ports/effect_queue.py`, `application/effect_reconciliation.py`, `application/effect_recovery.py`, `_sqlite_effect_queue_probe.py`, `adapters/postgres_effect_queue.py`, the queue schemas/codecs, `tests/test_reconciliation_probe_fencing.py` (takeover, persist-failure, both before/after-fact conclusion resumes, cancellation quiescence, and recovery distinctions), and `tests/test_postgres_effect_queue.py::test_postgres_probe_takeover_and_conclusion_match_sqlite_fencing`.

## Consequences

- Heartbeats add event traffic and stream-version contention, but lease history and expiry decisions become replayable.
- Lease tokens fence delayed heartbeats and results from a prior acquisition; expected heartbeat/expiry values also fence stale recovery decisions within that acquisition.
- The operational reservation/domain-commit split has an intentional safe asymmetry: abandoned reservations may temporarily delay work, while no reservation can authorize an uncommitted external action.
- Durable result persistence closes the success-fact dangling-reference window; an idempotent store can resume the persist-before-fact crash window.
- A sealed reconciliation conclusion is a durable continuation: crashes before or after its canonical fact resume without another provider call or budget charge, and APPLIED resume re-verifies the stored result.
- `TIMED_OUT -> SUCCEEDED` preserves an honest unknown interval and avoids duplicating an external mutation already proved applied.
- Started cancellation and uncertain reconciliation may retain resource claims indefinitely until the deferred compensation/manual-resolution path exists.
- Effect queue schema v2 is intentionally incompatible with the unanchored v1 queue. There is no in-place v1 backfill in this proposal: disposable proposal databases may be recreated, while any non-disposable queue requires an explicit migration that reconstructs and verifies every historical typed journal before writing checkpoints. Merely changing the schema marker or resetting operational tables is forbidden because it can refund budget or erase an uncertain external outcome.
- Proposal.8 changes the pinned FSM specification and state semantics. Earlier proposal streams remain bound to their original specification hash; this slice provides no schema upcaster. Disposable proposal databases may be recreated. Production migrations/upcasters remain a hardening-slice concern.

## Required falsifiers

The Slice 2 contract is not fulfilled unless tests prove:

1. concurrent claims yield one committed active lease token and conflicting resources serialize in both adapters;
2. execution cannot begin before `EffectLeased` commits, and an unactivated orphan never pins execution authority;
3. forged or effect-mismatched execution/cancellation authority is rejected by a trusted verifier;
4. matching heartbeats renew both `LEASED` and `RUNNING`, while stale owner/token heartbeats are rejected;
5. a stale expiry/timeout fact carrying an old expected heartbeat or expiry is rejected;
6. an expired lease can be reclaimed without a global marker and the old token cannot start or complete the new attempt;
7. duplicate delivery does not duplicate an idempotent external mutation;
8. a crash after an external write but before `EffectSucceeded` can remain `TIMED_OUT`, then converge only through evidence to safe retry or direct success; a blocked/in-flight invocation cannot be mislabeled `NOT_APPLIED` and later commit after its claims are released;
9. result bytes survive restart, cannot be rebound to another value for the same execution identity, and fail verification after tampering;
10. reconciliation permit acquisition is single-flight, charges its bounded budget atomically, fences stale conclusion, and has tested expiry takeover in both adapters;
11. the cancellation/start race linearizes at queue `ACTIVE -> RUNNING`: cancellation-first prevents provider invocation, while start-first permits a late return, rejects pre-expiry reconciliation probes, and retains claims until strong `NOT_APPLIED` or an authorized future resolution; effect-level `CANCELLED` remains absorbing in both branches;
12. queue journal gaps, rewinds, digest tampering, grant drift, mutable-row divergence, coordinated tail/projection rewind, and checkpoint mutation fail closed rather than refunding budget or changing canonical lifecycle; PostgreSQL typed replay enforces the same action-specific carry-forward, time monotonicity, and probe-generation rules as SQLite.

## Deferred

- an authorized compensation/manual-resolution contract for a started cancelled attempt observed as `APPLIED`, `UNKNOWN`, or reconciliation failure, including how and when retained claims may be released;
- an atomic no-charge late-execution-success seal for the race where recovery commits `TIMED_OUT` while the original provider call is still in flight and that exact token/attempt then returns success. The queue operation must require `RECONCILING`, the exact attempt, and no current permit, then install a durable `CONCLUDED(APPLIED)` continuation before the success fact. A plain `probe_permit is None` read is insufficient because another process may acquire a probe before the fact commits;
- persistence of an `APPLIED` provider observation before result-store success, so a result-store outage on the final allowed logical probe can reuse that observation without calling the provider again; the current expired-permit takeover avoids a second budget charge but must re-probe because no conclusion can be sealed without a durable result identity;
- binding `heartbeat_stale_after_seconds` and `reconciliation_probe_ttl_seconds` to signed and verified runtime-policy configuration instead of trusting application composition;
- production PostgreSQL/object result storage, real commander/Hades integration, and dynamic provider selection;
- KG, CLI, MCP, hook, and OPA adapters;
- production multi-process topology, observability, schema upcasters, and legacy migration;
- any `USER_PRIMARY` or KG canonical verdict on this engineering proposal.

## Rollback

Revert proposal.8 and this ADR together. Streams already created under any pinned proposal specification must continue replaying against that exact specification; do not reinterpret their events under another profile. Operational queue/result schemas require their own explicit migration or disposal decision; never reset them in a way that silently refunds budget or drops an uncertain external outcome.

# KG context only: apt-tpa-legion-engine-canon-2026-06-12, verdict-bihaenggiman-7commander-unify-2026-06-07, user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30
