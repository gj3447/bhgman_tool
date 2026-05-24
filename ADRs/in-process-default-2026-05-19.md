# ADR: bhgman_tool agent runtime — in-process default + RPC as substrate-join

- **Status**: PRELIMINARY (propose, awaiting user CANONICAL verdict)
- **Date proposed**: 2026-05-19
- **Materialized**: 2026-05-20
- **KG ref**: `adr-bhgman-tool-in-process-default-2026-05-19`
- **Parent constraint**: `engineboy-architectural-exclusion-rpc-2026-05-19`
- **Authority**: user verdict (engineboy v5) — "agent 와 상계 분리 불가 continuous tight coupling" + r5 architectural exclusion

---

## Context

engineboy 정전 (apostle #8 OMC, LegionCommander 5인 중 1) = *agent operational necessity* 가 본질. 사용자 verdict (2026-05-19, engineboy 곱씹기 cycle 1 r5):

> agent 와 상계는 분리 불가 — continuous tight coupling 이 본질. RPC/separate-process orchestration 모델은 engineboy ontology 와 부적합.

bhgman_tool = engineboy 결정화의 공학 측 구현체. 따라서 ADR layer 에서 architectural 측 exclusion 확정 필요.

## Decision

bhgman_tool agent runtime 측 **in-process embedding** 측 default.

agent + KG + store + tool 측 *same process* 측 hosted. MCP remote tool 측 ad-hoc RPC 아닌 **substrate-join** (remote KG → local replica) 측 처리.

## Rationale

engineboy = agent operational necessity. continuous tight coupling 측 require.

separate-process RPC 측:
- latency (네트워크 hop + serialize/deserialize)
- state divergence (agent 측 view ≠ tool 측 view)
- coupling failure (partial network failure → 한쪽만 stale)
- 측 inevitable.

in-process 측:
- shared-memory (zero-copy)
- single GC scope (메모리 라이프사이클 통합)
- single failure domain (crash 시 일관성)

## Valid patterns (ADR-conforming)

- Anthropic Managed Agents (single-host process)
- Claude Code (single-process, embedded tools)
- in-process Tool binding (LangChain Tool, MCP local stdio)
- shared-memory actor (Erlang BEAM analogue)
- persistent context window (LLM context = always-live snapshot)

## Excluded patterns (ADR-violating)

- LangGraph orchestrator + remote worker pods
- CrewAI separate agent processes + queue
- AutoGen multi-agent RPC
- microservice agent + tool server RPC
- agent server + tool server 측 split process

## Consequences

1. **Horizontal scaling**: process-level multi-instance 측 사용 (NOT within-instance fanout).
2. **Remote tools**: access 측 strictly via substrate-join (replica), NOT direct RPC.
3. **Design narrowness**: bhgman_tool 측 design choice 측 narrow — most industry orchestration frameworks 측 unsuitable.
4. **Compatibility**: Anthropic Managed Agents + Claude Code direction 측 align.

## §3 Definitions (added rev3 per naesengmoon C3)

To dissolve the 3 OPEN questions, the following terms are defined inline. Future revs may promote to a separate glossary node.

- **fanout** — single agent process spawning multiple child workers (threads, processes, async tasks) to parallelize work *within one logical agent instance*. Distinguished from **horizontal scaling** (multiple independent agent instances launched by an external scheduler).
- **within-instance fanout** — fanout where the spawned workers share the agent's logical identity and state expectations (e.g., `mp.Pool` for CPU-bound work in the same agent). **Excluded** by consequence §1.
- **external-IO daemon fanout** — fanout where workers are per-resource I/O watchers (e.g., one process per repo for inotify), not per-task agent computation. **Carve-out candidate** — does not violate §1's intent (multi-agent shared-state coupling), but the literal text reads stricter. See OPEN Q4.
- **replica** — local materialization of a remote substrate's state, with explicit reconciliation semantics (push/pull schedule, conflict resolution). The agent reads/writes the replica; the replica syncs to/from the source.
- **substrate-join** — agent's access to a shared/persistent state store via a *replica* or via a *native protocol driver where the store is the agent's canonical state* (not a separate "tool" called for a discrete answer). **Allowed** by consequence §2.
- **direct remote RPC** — agent issues a request and waits for a discrete response from a remote process. The remote owns the result; the agent owns nothing. **Excluded** by consequence §2.
- **split-process** — two processes that participate in the same logical workflow but live in separate OS processes communicating over RPC. **Excluded** in the form "agent server + tool server", regardless of whether they share a host.
- **tool** — discrete capability invoked for a bounded answer (lean compile, OPA decision, KG query). The agent doesn't own its state.
- **infrastructure substrate** — shared state/policy backbone the agent depends on continuously (KG, Redis, OPA). The agent may own logical state in it.

The distinction `tool` vs `infrastructure substrate` is **role-based**, not protocol-based. Same protocol (HTTP, Bolt) can serve either.

## Audit findings (2026-05-20, q5 RPC audit — rev3 per naesengmoon C1-C5)

**Coverage**: 13 candidate files / 16 findings (some files contribute multiple distinct findings — `cli/main.py` has 3 distinct concerns, `symposium.py` has 2). Of 84 total `engine/*.py` files, **15.5% file-coverage**.

**Baseline drift note (rev2)**: first pass (9 files / 2 conflicts) missed `redis.Redis`, `GraphDatabase.driver` (Neo4j Bolt 2x), and `urllib.request` patterns due to too-narrow grep regex. Re-scan with broader catalog surfaced 4 additional files and 3 additional findings (2.5x drift on conflict count).

**Rev3 reclassification (per naesengmoon C1 HIGH)**: 4 findings whose conflict status depends on OPEN question answers are moved from `conflicts`/`borderline` into a new bucket `pending_open_q`. This reduces premature certainty.

### Findings table (file-unit / finding-unit clarification)

| File | Finding | Bucket |
|---|---|---|
| `engine/cli/tests/test_main.py` | subprocess test E2E | pure CONFORM |
| `engine/cli/main.py` (multi-line) | subprocess for lean / cypher-shell external CLI | pure CONFORM |
| `engine/cli/main.py:_cmd_gate_serve` | `uvicorn.run(gate_endpoint:app)` | borderline CONFORM |
| `engine/cli/main.py:_cmd_gate_check` L386-411 | `urllib.request.urlopen POST http://127.0.0.1:8765/gate/check` | **pending_open_q** (Q2) |
| `engine/longinus_drift_audit/sha256_baseline.py` | comment (explicitly avoids subprocess) | pure CONFORM |
| `engine/longinus_drift_audit/daemon.py` | `mp.Process` per-repo file-watcher | **POTENTIAL CONFLICT** (consequence §1; see Q4 for carve-out) |
| `engine/longinus_drift_audit/kg_client.py:145` | `GraphDatabase.driver(uri, auth)` Neo4j Bolt | **pending_open_q** (Q1) |
| `engine/gate/tests/test_opa_client.py` | httpx MockTransport | pure CONFORM |
| `engine/gate/opa_client.py` | `httpx.AsyncClient → OPA sidecar localhost:8181` | borderline CONFORM |
| `engine/gate/gate_endpoint.py` | FastAPI server + `build_redis_client()` | borderline CONFORM |
| `engine/gate/circuit_breaker.py:135` | `redis.Redis(**kwargs)` | **pending_open_q** (Q3) |
| `engine/mcp_server/tools/apt.py` | regex `invoke.` (false positive) | pure CONFORM |
| `engine/mcp_server/tools/symposium.py:153` | `subprocess.run([ssh dgx kubectl cypher-shell])` | **POTENTIAL CONFLICT** (consequence §2; not replica-mediated under any reading) |
| `engine/mcp_server/tools/symposium.py:218` | local script execution (cypher_validate.sh) | pure CONFORM |
| `engine/gate/tests/test_gate.py` | importorskip + fakeredis | pure CONFORM |
| `engine/resolver/cypher_kg_client.py:53` | `GraphDatabase.driver(cfg.uri, ...)` Neo4j Bolt | **pending_open_q** (Q1) |

**Totals**: 16 findings = 7 pure CONFORM + 3 borderline CONFORM + 2 POTENTIAL CONFLICT + 4 pending_open_q. (Distinct files: 13.)

### Open questions for user verdict (6, was 3)

| Q | Question | Triggers |
|---|---|---|
| Q1 | Neo4j Bolt native driver = substrate-join (via §3 def, `kg_client.py` is *agent's canonical state* — likely YES) or strict replica-only (NO)? | 2 pending_open_q items |
| Q2 | Localhost HTTP gate (CLI → FastAPI same host) = infrastructure exception (gate = admission control substrate) or actual split-process violation? | 1 pending_open_q item |
| Q3 | Redis circuit-breaker state store = infrastructure substrate (per §3 def, agent owns CB state in it — likely YES) or external tool? | 1 pending_open_q item |
| **Q4** | **(NEW per C2)** daemon I/O carve-out — does consequence §1 apply to external-IO file-watcher fanout, or only to within-instance task fanout? | Affects daemon.py conflict classification |
| **Q5** | **(NEW per C2)** `:GrepPatternCatalog` v1 scope ratification — current catalog (DB driver / HTTP client / lower-level socket / queue / messaging) sufficient, or add (LLM SDK calls / GPU IPC / file-locking IPC / shared-memory mmap)? | Affects future audit coverage |
| **Q6** | **(NEW per C2)** dynamic-invocation policy — does audit obligation cover `eval` / `getattr(module, name)(...)` / plugin loaders, or only static imports? | Affects coverage claim honesty |

### Coverage caveat (rev2)

71 of 84 engine `.py` files (85%) did not match the broader pattern catalog. Coverage was filename-grep, not AST — pure-import re-export or eval-based dynamic invocation would not be caught (see Q6). AST scan = future work.

### Lesson + enforcement (rev3 per C5)

KG node `lesson-audit-grep-coverage-drift-2026-05-20` (:Lesson:CANONICAL) — prevention measures now backed by:
- **KG `:GrepPatternCatalog` v1 node** (`grep-pattern-catalog-v1-2026-05-20`): 5 categories (DB driver / HTTP client / lower-level / queue / messaging) versioned and queryable.
- **Hook stub** (`bhgman_tool/bin/audit_grep_coverage.sh`): post-audit script. Reads catalog → grep → prints `files_scanned / total_py / coverage_pct` → exits non-zero if coverage < threshold.

Audit report KG node: `audit-q5-bhgman-tool-rpc-conformance-2026-05-20` (revision 3, naesengmoon-validated cycle 1, cycle 2 pending).

## References

- KG: `adr-bhgman-tool-in-process-default-2026-05-19`, `engineboy-canonical-2026-05-19`, `engineboy-architectural-exclusion-rpc-2026-05-19`
- Cycle: `engineboy-reflection-gopsibgi-2026-05-19` r5
- Format: MADR-lite (Markdown ADR)
- Longinus L4 forward binding: this file ↔ KG ADR node
