# Diagnostic repair loop

`bhgman_tool` can now run a bounded, externally verified repair cycle in which
the concrete compiler/test diagnostic is visible to the next generation:

```text
candidate
  -> deterministic oracle
  -> typed diagnostic
  -> repair(diagnostic + current + best + history)
  -> reverify
  -> complete | capped | stuck | oracle_error | generator_error
```

This is an executable capability, not a claim that PI has superior cognition.
PI-specific lift still requires the preregistered equal-token and equal-oracle-call
comparison against plain, best-N, decoy-feedback, and repair arms.

## External designs inspected

The implementation is a clean-room synthesis. No upstream source was copied.
The repositories were cloned under the gitignored `GIT/oss-cognition-audit/`
nest and pinned during the 2026-07-16 review.

| Project | Pin | License | Mechanism retained |
|---|---:|---|---|
| [mini-SWE-agent](https://github.com/SWE-agent/mini-swe-agent/tree/388da74aad620a384ab47669b17c52133e30e7c3) | `388da74` | MIT | execution observation is appended before the next model query; step/cost/time limits |
| [OpenHands software-agent-sdk](https://github.com/OpenHands/software-agent-sdk/tree/51c102b9c0348bbdd4e6a84b1ac4199e0d77f827) | `51c102b` | MIT | typed events, repeated-state detection, explicit complete versus capped lifecycle, `missing` follow-up |
| [Aider](https://github.com/Aider-AI/aider/tree/5dc9490bb35f9729ef2c95d00a19ccd30c26339c) | `5dc9490` | Apache-2.0 | lint/test failure reflection with a small retry bound |

The review did **not** use the unfinished TPA engine as a code-analysis engine.
Python native AST was cross-checked with bhgman_tool's Tree-sitter + Jedi
indexer, and the new source was checked with Pyright.

## API

`CommandDiagnosticOracle` executes argv with `shell=False`, a timeout, and a
bounded head/tail capture. Host execution is disabled by default because this
controller is not a sandbox. When explicitly enabled for a trusted verifier,
candidate text can be sent over stdin so a single-file compiler/linter can check
an in-memory proposal without mutating the worktree.

`TextRepairGenerator` is compatible with `engine.agents.client.AgentClient`.
It injects the bounded diagnostic and current source into the next completion,
requires strict replacement markers, tracks backend-reported tokens, and
returns source in memory. Per-result receipts report the current run's token
delta even when a generator instance is reused; its configured total budget
remains lifetime-cumulative. It never writes a file and never decides success.

```python
import sys

from engine.agents.client import AgentClient
from engine.legion.diagnostic_repair import TextRepairGenerator, diagnostic_repair
from engine.naesengmoon.diagnostic_oracle import CommandDiagnosticOracle

oracle = CommandDiagnosticOracle(
    name="python-compile",
    kind="compiler",
    command=(
        sys.executable,
        "-c",
        "import sys; compile(sys.stdin.read(), '<candidate>', 'exec')",
    ),
    stdin=lambda source: source,
    timeout_s=10,
    allow_host_execution=True,  # trusted compiler only; this is not a sandbox
)
generator = TextRepairGenerator(
    client=AgentClient(),
    model="configured-model",
    max_tokens_per_attempt=1024,
    max_total_tokens=4096,
)
result = diagnostic_repair(
    "answer = (",
    generator,
    oracle,
    max_attempts=3,
    max_evaluations=4,
    max_wall_seconds=120,
)

if result.verified:
    verified_source = result.output
receipt = result.receipt()  # JSON-safe metadata; candidate and raw diagnostic bodies are omitted
# Private evidence only: result.receipt(include_diagnostics=True)
```

For a `CommanderStage`, use `make_diagnostic_repair_stage(...)`. The wrapper
preserves `name`, `verb`, `requires`, `provides`, and `measure`; it replaces the
seed only after an authoritative pass by default. An improved-but-still-failing
candidate remains telemetry unless an experimental caller explicitly selects
`adopt_unverified_improvement=True`. It is deliberately opt-in because prose,
canon, and subjective judgment do not have an authoritative external oracle.
This is currently a Python API/`CommanderStage` integration seam, not a default
Legion path, CLI, or MCP tool. Default exposure waits for a sandbox/materializer
policy for multi-file generated code.

The exact efficacy bridge lives in
`engine/efficacy/diagnostic_repair_harness.py`. It compares the production
`diagnostic_repair` loop with legacy repair, best-N, diagnostic-decoy, single,
and plain-agent controls under the v3 manifest/preregistration. A passing unit
suite proves the mechanism and trace contract; only a clean, hash-frozen live
batch can move the efficacy verdict.

### Live Lean isolation boundary

Lean source is executable: a model can append command-level syntax or
compile-time IO after an otherwise valid proof. Therefore the v3 efficacy
harness never falls back to the historical host `lean_oracle.evaluate` path.
It uses `ExternalSandboxLeanEvaluator` and fails before model initialization
when the frozen sandbox runner is unavailable or its hash drifts.

On macOS the frozen reference runner is
`engine/efficacy/lean_sandbox_runner_macos.py`. It resolves the exact
`lean/lean-toolchain` pin rather than elan's mutable default and binds the pin,
full `lean --version` output, and executable SHA-256 into every claim-bearing
run. It executes that exact Lean binary under `sandbox-exec`. File contents are
readable only from the private source directory, the frozen toolchain, and the
minimum system runtime paths; arbitrary home, repository, temporary, and
`/etc` reads are denied. Network, child process execution, and writes outside
the private directory are also denied. CPU, file-size, descriptor, process,
address-space, and wall-time limits are applied. Lean stdout/stderr is drained
incrementally into a bounded first/last-byte buffer; the process group is killed
at 64,000 bytes, so generated compile-time output cannot exhaust the trusted
parent. Random sandbox paths are normalized before recording so deterministic
replay can require exact diagnostic equality.
Obvious trailing Lean commands are rejected before this boundary as a canonical
failed observation. They never invoke Lean and cannot pass. The parser is
defense in depth; the sandbox remains the security and scoring authority for
safe proof terms.

The legacy host evaluator remains only for historical callers and local oracle
unit tests. It must not be passed to a live v3 run.

### Contract conformance boundary

The loop contract contains a production target control plane because its
validator requires typed interruption, checkpoint, approval, and effect
fields. It is explicitly marked
`TARGET_CONTRACT_NOT_RUNTIME_CONFORMANT`. The current executable slice is
local-only: fresh `x`-mode JSONL, one writer, and flush after each record. It
does not implement resume, atomic finalization, aggregate wall/token/cost
governance, publication outbox, or receipt reconciliation.

Likewise, the FSM is marked `REFERENCE_MODEL_NOT_RUNTIME_REDUCER`. Its checked
guarantee is that only an authoritative pass can enter `complete`; the runner
does not execute generated FSM commands. Runtime evidence comes from the
production diagnostic-repair lifecycle records plus the B1 legacy↔PI trace
fixture.

The independent analyzer consumes the physical JSONL order rather than sorting
attempts back into shape. It requires the frozen task and counterbalanced arm
blocks, contiguous attempts, the exact
`oracle_evaluated -> (repair_requested -> oracle_evaluated)* -> stopped`
lifecycle, and production candidate/diagnostic fingerprints that recompute from
the full payload. Before calculating any statistic, it replays every proof
through the exact frozen oracle boundary. Safe proofs and every
diagnostic-decoy setup execute in the frozen sandbox; obvious generated command
payloads reproduce the canonical pre-sandbox failed observation. It then
compares the compile/proven/sorry verdict, graded score, normalized diagnostic,
and hashes.
It also binds each attempt to the model ID actually returned by the backend,
rejects hidden endpoint/template overrides, hidden usage, per-attempt output
above the frozen maximum, and a recorded commit that does not predate every run
timestamp and result file.

## Safety and lifecycle contracts

- Acceptance belongs to the external compiler/test/linter/proof checker. An LLM
  response, sentinel, or self-report cannot produce `complete`.
- Commands must be argv sequences. Shell strings are rejected.
- Repair attempts and oracle evaluations have hard count caps.
- An explicitly enabled host command has an enforced parent/process-group
  timeout and bounded in-memory observation capture. This still cannot contain
  a deliberately detached process; it is process control, not isolation.
- Loop wall time is a cooperative deadline checked between synchronous effects.
  Each model and oracle adapter must enforce its own per-call timeout.
- `TextRepairGenerator` caps requested output by the remaining reported budget
  and fails closed when backend-reported usage crosses it. That is accounting,
  not proof of equal actual tokens across experimental arms.
- A repeated `(candidate digest, diagnostic digest)` state terminates as `stuck`.
  Binary scores may remain flat across distinct diagnostics without premature
  plateau termination.
- The loop tracks `current` for multi-step progress and `best` for rollback-safe
  return. A later regression does not overwrite the best verified/measured candidate.
- Append-only events are sequenced for an idempotent caller-owned durable sink.
  Sink failure propagates fail-closed.
- Model output and verifier commands are not a sandbox. `allow_host_execution`
  defaults to false. Run untrusted generated code only through a separately
  sandboxed oracle in a least-privilege container; an isolated worktree alone is
  not a security boundary. Default
  receipts omit raw diagnostics, command argv, and event details because they
  may contain source, paths, or secrets.
- Default candidates are exact built-in value trees (`str`, bytes, numeric
  scalars, and recursively safe list/tuple/dict/set values). Custom objects,
  cycles, and filesystem references nested at any depth are rejected without
  invoking user-defined copy/representation hooks.
- Mutable multi-file workspaces must supply explicit snapshot and patch/tree
  digest functions plus an isolated materializer or worktree. Directory-name
  hashing is rejected.

## Verification

```bash
.venv/bin/pytest \
  engine/naesengmoon/tests/test_diagnostic_oracle.py \
  engine/legion/tests/test_diagnostic_repair.py \
  engine/legion/tests/test_repair_stage.py \
  engine/legion/tests/test_evolve_loop.py \
  engine/efficacy/tests/test_diagnostic_repair_harness.py \
  engine/efficacy/tests/test_analyze_diagnostic_repair_harness.py \
  engine/efficacy/tests/test_diagnostic_repair_contracts.py -q

.venv/bin/ruff check \
  engine/naesengmoon/diagnostic_oracle.py \
  engine/legion/diagnostic_repair.py \
  engine/legion/repair_stage.py

uvx pyright \
  engine/naesengmoon/diagnostic_oracle.py \
  engine/legion/diagnostic_repair.py \
  engine/legion/repair_stage.py
```

The focused suite includes positive feedback injection, a real Python subprocess
compiler, flat-score multi-step progress, repeated-state termination, evaluation
and token caps, oracle/generator failure, output truncation, argv enforcement,
strict security booleans and finite timeouts, safe candidate snapshots, per-run
token receipts, telemetry collision rejection, best-candidate retention, JSON
receipts, and `CommanderStage` contract preservation.
