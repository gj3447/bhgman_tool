# Codex product feedback — 2026-06-18

Reviewer: Codex, local checkout originally at `03a3daa`; updated after `ca1f364`
vendored `symposium-skills/` into the repository.

## Short verdict

This review is intentionally **not** a judgment on the bhgman / Airplane Man essence layer. It is
an external engineering review of this repository as a tool/runtime. The repo's own philosophy
documents explicitly separate essence from tool; this review should be read inside that separation.
Where I say "engine is thin," I mean the tool-layer runtime is thin relative to the engineering
claim of capability amplification. I am not claiming the metaphysical or mythic frame is thin.

`bhgman_tool` reads as a serious research/verification substrate, not yet a product-shaped app.
More importantly, its engine is still thin relative to the original ambition of a capability
amplifier. That thinness should not be reframed as a design virtue. It is mostly an implementation
gap: many surfaces exist, but too many are route shims, prototypes, dry-run paths, or substrate
adapters that do not yet compound into a reliable autonomous improvement loop.

The core idea is still worth pursuing. The repo has real implementation mass: CLI commands, local
KG, Neo4j paths, Lean artifacts, pytest suites, and explicit anti-overclaim positioning. But the
main gap is no longer just packaging or user journey. The bigger gap is engine depth: the system
does not yet do enough work end-to-end to deserve the "capability amplifier" claim.

## Standalone install truth

Historical state at first review: the active submodule source was:

```bash
git submodule update --init --recursive
```

from `.gitmodules`:

```text
https://github.com/gj3447/symposium-skills.git
```

`git ls-remote` confirms that repository has `main` at `5af874f`, matching the pinned submodule.
The `skills/README.md` reference to `https://github.com/airobotics-inc/symposium-skills.git`
does not currently resolve publicly. That should be corrected or explained as a private/legacy
distribution path.

Current state after `ca1f364`: the submodule has been de-submoduled. `.gitmodules` is gone,
`symposium-skills/` is now a normal tracked directory, and a fresh clone/ZIP download contains the
skill files. Verified locally:

```text
.gitmodules: absent
gitlink count: 0
symposium-skills/apt/SKILL.md: present
symposium-skills/prometheus/SKILL.md: present
bhgman-tool version: 30 skills detected
```

This closes the "clone needs --recurse-submodules" failure for Git clone and GitHub ZIP users. It
does not automatically mean the PyPI wheel is standalone: the wheel still ships `engine/` only and
the sdist config still excludes `symposium-skills`.

## Why it does not feel like a finished product app yet

1. The first-run path is split across source install, missing submodule state, Claude skills,
   optional Neo4j, optional local KG, optional Lean, optional Anthropic/local LLM, and optional MCP.
   A product needs one default path that works end-to-end from a clean clone.

2. The README advertises slash-command workflows, but this checkout only has two local skill
   directories until the submodule is initialized. That makes the headline experience fail before
   the user reaches the core value.

3. The core concepts are powerful but named as internal mythology: commanders, weapons, apostles,
   taliban/tlb, metahumotonic, etc. That can work for a private research system, but a product user
   needs a task-oriented surface: "audit repo", "capture research", "verify claim", "dedupe KG",
   "run gated agent task".

4. The CLI is broad rather than guided. There are many verbs, but no single `bhgman-tool init`,
   `bhgman-tool doctor`, or `bhgman-tool demo` path that proves the system on the user's machine.

5. The repo has evidence, tests, and humility disclaimers, but not yet a product-level success loop:
   install → connect data/source → run useful workflow → see artifact → trust report → repeat.

6. Several features are substrate-dependent. Some paths need Neo4j, some use local JSON KG, some
   fall back to skill routing, some need LLM credentials, some are deterministic only. A product
   should make those modes explicit in a compatibility matrix and expose graceful degraded demos.

7. "Capability amplifier" is not yet demonstrated as a product claim. The README currently argues
   the opposite: governance/audit value, not cognition gain. If amplification is the goal, the repo
   needs a separate measured loop where the system improves outcomes over an equal-tool-budget
   baseline on real tasks.

## Engine thinness is not a feature

The uncomfortable read: compared with LangGraph, CrewAI, Graphiti, DeepEval, Guardrails,
OpenHands, or SWE-agent, `bhgman_tool` is not merely "minimal." It is under-developed for the
claim it wants to make. The existing breadth creates the impression of a complete architecture, but
the runtime depth is uneven.

Concrete gaps:

1. Too many commands are control-plane labels over partial implementations. A verb existing in the
   CLI is not the same as an engine capability. The product surface says "7 commanders"; the code
   often says "runner, dry-run, fallback, route to skill, or prototype."

2. The skill layer carries too much of the methodology. If the "real phase logic" lives in
   `SKILL.md` and the CLI often routes to a skill rather than executing the phase, then the Python
   engine is not yet the authoritative engine. It is a launcher plus partial substrate.

3. The gate server is a prototype by its own README. It has real FastAPI/circuit-breaker/OPA paths,
   but audit persistence, break-glass alerting, and several fallback decisions are still incomplete
   or stubbed. That is fine as a prototype; it is not enough for a hard governance backend.

4. The KG story is split. There is local JSON KG, Neo4j adapters, MCP routing, source comments,
   code scanners, and provenance export, but not yet a single always-on data model that every
   commander must write to and read from with enforced contracts.

5. "Capability amplification" requires a closed feedback loop: attempt task, capture trace, run
   oracles, diagnose failure, update plan/context, retry, and measurably improve. Pieces exist, but
   the loop is not yet robust enough to beat a well-instrumented baseline.

6. There is no strong scheduler/runtime. `legion`, `bot`, and daemon modules exist, but the repo
   does not yet look like a production-grade task runner with queues, leases, retries, persisted
   runs, cancellation, replay, and backpressure.

7. There is no decisive artifact model. A serious amplifier needs first-class artifacts: task,
   plan, attempt, patch, test result, critique, oracle verdict, KG delta, and final report. Today
   these concepts appear across modules, but the lifecycle is not hard enough.

8. The verification surface is promising but narrow. `oracle` is the right idea, but the engine
   needs more substrate-disjoint oracles and a policy that every autonomous write must pass through
   them. Otherwise verification is a tool users may call, not a property of the system.

9. The code-to-KG path is not yet strong enough to be a differentiator. To compete with code graph
   systems, it needs symbol identity, cross-file references, call graphs, ownership, tests, runtime
   traces, and stable incremental updates. Partial tree-sitter/Jedi ingestion is a start, not the
   finish line.

10. The LLM-agent runtime is not deep enough. Compared with real agent runtimes, it lacks a mature
    model abstraction, tool sandbox, multi-attempt strategy, context packing policy, memory policy,
    and failure recovery protocol.

11. The tool surface exposes ontology language before the tool-layer engine fully earns it for
    outside users. The commander names and theory may be meaningful within the bhgman philosophy;
    this review is not competent to reject that. The narrower engineering point is that users and
    evaluators who enter through this repository will judge whether the tool executes, verifies, and
    improves tasks. The runtime should work even for users who do not yet understand the canon.

12. Thin wrappers create false confidence. A route to `SKILL.md`, a dry-run report, a fake-client
    unit test, or a TODO-backed endpoint should be labeled as scaffolding, not as a completed
    commander.

13. The test count is not enough evidence. Many tests prove local invariants and parser behavior.
    The missing evidence is scenario-level: seeded repo task → agent attempt → verifier catches
    fault → retry fixes it → final patch passes → trace is replayable.

14. The product lacks one hard benchmark it owns. It should ship a reproducible "bhgman amplifies
    this task class" benchmark, even if small and unflattering at first.

15. The tool layer does not yet have a center of gravity. At the essence layer, bhgman may already
    have a coherent role; this review is not evaluating that. At the repository/runtime layer, it
    currently presents as an agent orchestrator, KG memory, code drift auditor, eval framework,
    Claude skill pack, MCP server, and coding agent backend at once. It can eventually be several
    of these, but the engine needs one dominant executable use case first.

## What "real engine depth" should mean

The target should be stricter than "commands run":

1. `bhgman-tool init --local` creates a local KG and a runnable demo workspace.

2. `bhgman-tool demo --amplifier --local` runs a seeded coding/research task end-to-end with no
   external services.

3. Every run creates durable nodes: `Task`, `Plan`, `Attempt`, `Artifact`, `OracleVerdict`,
   `Critique`, `KGDelta`, and `ReplayBundle`.

4. Every commander reads and writes the same lifecycle model; no hidden side channel via prose-only
   skill instructions.

5. The gate is not optional in autonomous mode. Writes and final claims pass through deterministic
   checks by default.

6. Failures are productive. A failed oracle verdict automatically changes the next attempt, and the
   trace records why.

7. Local and Neo4j backends have the same semantics for the core lifecycle, with tests proving
   parity.

8. The LLM runtime has pluggable backends, stable tool-call schema, timeout/retry policy,
   cancellation, and cost/token accounting.

9. Code-to-KG binding is incremental and symbol-stable, not just grep/comment anchored.

10. The benchmark is part of CI or an explicit nightly job. If the amplifier regresses, CI says so.

Until this exists, call the engine "prototype substrate" or "verification scaffold", not a
capability amplifier.

## How to move toward the original capability-amplifier goal

1. Define "amplification" operationally. Example: higher pass rate on repo tasks, faster verified
   completion, fewer regressions, better citation precision, or better recovery from failed agent
   attempts. Pick one primary metric.

2. Keep the governance layer as the foundation, but present it as the mechanism: task attempts are
   decomposed, grounded, checked by deterministic oracles, and retried based on failures.

3. Add a canonical demo that works without external services:

```bash
uv run bhgman-tool doctor
uv run bhgman-tool demo --local
uv run bhgman-tool oracle --kind pytest-ratio --target engine/kg_local/tests --json
```

4. Add one LLM-backed demo path for amplification:

```bash
export BHGMAN_LLM_BASE_URL=...
export BHGMAN_LLM_MODEL=...
uv run bhgman-tool apt "fix a seeded bug" --gated --ground-truth "uv run pytest ..."
```

5. Separate product docs from research canon:
   - `README.md`: one clear user journey.
   - `docs/research/`: Lean, A/B, philosophy, commander ontology.
   - `docs/product/`: install, doctor, examples, troubleshooting.

6. Rename or alias risky/internal terms at the product surface. Keep canon internally if desired,
   but expose neutral verbs to users: `verify` instead of `tlb`, `research` instead of `prom`,
   `bind`/`audit` instead of `longinus`, `plan` instead of `jaebaeman`.

7. Ship `bhgman-tool doctor`. It should check Python version, uv, package import, submodule state,
   skill count, Neo4j availability, local KG path, Lean availability, LLM backend, and MCP config.

8. Ship `bhgman-tool init --local`. It should initialize the local KG, install or link skills if
   available, and print exactly what works offline.

9. Make the submodule failure impossible to miss. If `symposium-skills/` is empty, `install-skills`
   should say exactly:

```text
Submodule missing. Run: git submodule update --init --recursive
```

10. Preserve the honest "not a cognition amplifier yet" language until the amplification loop has
    an external, repeatable benchmark. That honesty is a strength; the product claim should catch up
    to the measurement, not the other way around.

11. Stop treating breadth as progress. Pick one loop and make it real:

```text
task -> plan -> attempt -> artifact -> oracle -> critique -> retry -> verified artifact -> replay
```

12. Mark every commander with a maturity tier:

```text
M0: route/prose only
M1: dry-run deterministic report
M2: writes durable KG state
M3: participates in closed loop
M4: improves benchmark outcome vs equal-tool baseline
```

13. Add a `bhgman-tool maturity` command that prints this table from code, not README claims.

14. Move TODO/stub/prototype disclaimers into machine-readable metadata so README badges cannot
    accidentally imply more than the engine does.

15. Build one boring, undeniable workflow before expanding the tool surface:

```text
Given a repo with a seeded failing test, bhgman creates a patch, runs tests, records the attempt,
critiques the failure if any, retries once, and emits a replayable report.
```

## Branch state observed

Local branches:

- `main` only.

Remote branches after `git fetch --all --prune`:

- `origin/main` at `03a3daa`
- `origin/dependabot/pip/ruff-0.15.17` at `aa1e425`
- `origin/feat/evolve-loop-efficacy-experiment` at `5d365df`

So the repo is not locally split into many active branches, but the remote does have two additional
work branches besides `main`.

Later observed: `origin/main` advanced to `ca1f364` with the standalone clone vendoring commit; the
local review commit was rebased on top as `de24f2a`.
