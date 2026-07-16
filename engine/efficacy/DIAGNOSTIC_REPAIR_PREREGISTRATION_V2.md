# Diagnostic Repair Harness v2 — pre-registration addendum

> **STATUS: HASH SET RE-FROZEN / NOT YET CLAIM-BEARING.** The artifact,
> sandbox, run-design, and B1 fixture hashes were re-frozen on 2026-07-16 after
> an independent causal/security audit. No live model batch may claim this
> addendum until the manifest and this document are committed in a clean
> worktree, the B1 fixture passes from that checkout, and the recorded commit
> predates every result JSONL. No live 32B batch was run while constructing or
> hardening the harness.

This addendum supersedes no historical result. It defines a new bridge experiment
whose treatment invokes `engine.legion.diagnostic_repair.diagnostic_repair`
directly. The 2026-06-14 `8W/2T/0L` batch remains
`PLAUSIBLE-uncontrolled`: it used the legacy handwritten repair loop and lacked
decoy, plain-agent, and token controls.

The claim under test is deliberately narrow:

> A single-model, oracle-channelled, bounded diagnostic-repair loop can improve
> verified Lean proof completion at a competence boundary under matched compute.

It is not a collective-IQ, discovery, or general PI-cognition claim.

## 1. L_RT harness boundary

The control target is `diagnostic_repair_harness_contract.json`; it is marked
`TARGET_CONTRACT_NOT_RUNTIME_CONFORMANT` because the current local runner does
not implement resume, atomic finalization, aggregate budget governance, or a
publication outbox. The arm-loop FSM is likewise a reference model, not an
executed reducer.

Control ownership:

- model: proposes proof candidates only;
- frozen least-privilege Lean sandbox: owns `passed` and graded score;
- runner: owns arm order, seeds, K, records, and stopping;
- analyzer: owns P1-P5 computation but cannot generate candidates or verdicts;
- human: owns any publication of a positive efficacy claim.

Default stage adoption outside the experiment is verified-only.
Improved-but-unverified output requires an explicit experimental opt-in.

## 2. Frozen artifacts

The manifest is the machine-checked authority for the implementation artifacts,
thresholds, and B1 fixture. Any subsequent change requires a new manifest and
addendum version.

| artifact | SHA-256 |
|---|---|
| `engine/efficacy/diagnostic_repair_harness.py` | `3b2bdc029cb582ad0a813eeb0b11315d2f159174de3ded36648f29b811839cca` |
| `engine/efficacy/analyze_diagnostic_repair_harness.py` | `72beec85e14b592fbb1bc2348f4a00d5dbd6da57b8c1cfa0ccc30c200fafb33d` |
| `engine/legion/diagnostic_repair.py` | `7e7fcb016e75753ddb1a898090df1af7b330388a3fdd822853b653b9a530d3d0` |
| `engine/naesengmoon/diagnostic_oracle.py` | `e9fff40235d4cbee8b89eaffb8091541cf68db48a21c1d84d170d3d930e15a63` |
| `engine/efficacy/lean_headroom_run.py` | `112267121fa45ab2319f1cff73c172115f10b96e03accb742476f3f182932617` |
| `engine/efficacy/lean_tasks.py` | `4a73146e0e300439acf02a96390ca1303f25cd1b671d9ad3cb0462998504c2df` |
| `engine/efficacy/lean_oracle.py` | `2bad4e9d24fe1e08e62bcd7c297de8647234978d3adc6db6944b08278a454517` |
| `engine/agents/client.py` | `d03773f2e0caa8137aa3164b1d463b6c1edcfd7e55e0f4371d2aaf42499de6f5` |
| `engine/cli/runtime.py` | `3b1b593a8ab1b8753183f3c9351a1afe07dd710b584b4a9fbb23479fb7ab5826` |
| `engine/efficacy/lean_sandbox_runner_macos.py` | `9a70d14697bf7eee5b65b18fb871e3265ca0e81cd9e429fe1f34406e74d5df6b` |
| `lean/lean-toolchain` | `d55ca0039a5479db5b38919d005b2c427b89b3be4f0184a20f2f4eae931f5bdb` |
| `engine/efficacy/diagnostic_repair_harness_contract.json` | `c6dfde5dff7679ff8c93554c551dec48e2244d011b376a4945947f50a73b1f1c` |
| `engine/efficacy/diagnostic_repair_harness_fsm.json` | `d574c25772c8df4fd980a0a34a450b824392a82f22d2741fd5b007fd75eda0ee` |
| `engine/efficacy/diagnostic_repair_harness_fsm_traces.json` | `90650f6b91727c3ae2fd6ec9b97084e48b8ebdadf8aea91abfe88af3bd205963` |
| B1 fixture `engine/efficacy/tests/test_diagnostic_repair_harness.py` | `d8d6a413bc1a85546d8a1d5ae7e8b6b6d2a88ba01a9af569054562a62d2659d3` |
| `engine/efficacy/diagnostic_repair_harness_manifest.v2.json` | `b9d7d22567bea6ba04adcd177f17d36c20052e089ffbc40b95685d1c37c2e838` |

The addendum does not hash itself. Each run-start record binds its current hash
alongside the manifest hash; the clean git commit binds both files.

## 3. Six arms

All task-solving arms use the same frozen task statement, oracle, K, output-token
ceiling, and declared model endpoint.

| arm | definition | isolation |
|---|---|---|
| `single` | one generation and one oracle call | competence floor |
| `bestN` | up to K independent seeded generations, no feedback | search-only |
| `legacy_repair` | prior handwritten real-diagnostic loop | bridge control |
| `pi_repair` | production `diagnostic_repair`, real diagnostic | treatment |
| `pi_decoy` | production `diagnostic_repair`, real acceptance but wrong-task diagnostic | oracle content vs context volume |
| `plain_baseline` | generic accumulated test-loop, same task and oracle | PI-specific scaffolding vs generic loop |

`pi_repair` uses one generated seed plus
`max_attempts=K-1`, `max_evaluations=K`. `pi_decoy` uses the identical production
loop. Wrong-task diagnostic construction is recorded as a `pi_decoy_setup`
receipt that binds the cyclic source task, reference proof, authoritative
verdict, diagnostic, and fallback seed diagnostic. The analyzer replays that
setup and requires every later supplied decoy to equal the frozen `_fit_decoy`
transform. Setup calls are excluded from the task-solving oracle-call budget;
both raw and excluded counts are reported.

## 4. Frozen run design

- literal reproduction tier: `qwen2.5:32b-instruct`;
- backend: `frontier:qwen2.5:32b-instruct`;
- endpoint class: `openai-compatible`;
- K: `4`;
- replications: `10`;
- seed offsets: `0,10,...,90`;
- temperature: `0.8`;
- maximum output tokens per attempt: `3072`;
- oracle isolation: frozen `external-sandbox-runner/v2`;
- Lean toolchain pin: `leanprover/lean4:v4.27.0`;
- Lean version: `Lean (version 4.27.0, arm64-apple-darwin24.6.0, commit db93fe1608548721853390a10cd40580fe7d22ae, Release)`;
- Lean executable SHA-256: `2974847fff2e2621502841f4c2dbac4035b4847d6060a4f2087cbc0d04005e37`;
- task band: the 12 ordered task fingerprints in the manifest;
- power gate: at least `6` live headroom tasks and at least `6` non-ties for
  each required exact sign test;
- alpha: `0.05`, two-sided exact sign tests;
- token/call parity interval: `[0.8, 1.25]`;
- decoy≈bestN paired Student-t TOST equivalence margin: `1.0` proven
  headroom task per run;
- concentration threshold: `top_task_delta_fraction > 0.5`.

A different capable model is a generalization run, not a 32B reproduction.
A hidden-usage backend cannot pass P4. The CLI requires
`--execute-frozen-run`, refuses a dirty worktree or redacted payloads, and
checks this exact design before the first model call.

## 5. Bridge and causal gates

### B1 — implementation bridge

Before live execution, deterministic recorded-completion fixtures must show
`legacy_repair` and `pi_repair` have identical:

- prompt sequence and diagnostic content;
- attempt seeds;
- candidate and oracle trace;
- K and early-stop semantics;
- verified terminal outcome.

Any mismatch blocks the live run until classified and explicitly preregistered.
The frozen B1 node is:

```text
engine/efficacy/tests/test_diagnostic_repair_harness.py::test_legacy_and_pi_repair_have_equivalent_generation_and_oracle_traces
```

The analyzer verifies that the manifest still binds this test source, but it does
not fabricate a pytest result. B1 must be run and recorded before live execution.

### P1 — edge

`pi_repair > bestN` with `p < 0.05`:

1. across replication-level headroom proven counts; and
2. across live-task paired proven counts.

The batch must contain at least six live tasks, six per-run non-ties, and six
per-task non-ties. Insufficient non-ties are `ABSENT`, not negative evidence.

### P2 — oracle signal

`pi_repair > pi_decoy`, `p < 0.05`, and `pi_decoy ≈ bestN` by paired
Student-t TOST. If the decoy is worse than bestN outside the frozen
equivalence margin, P2 fails rather than crediting treatment-vs-harm.

### P3 — PI-specificity

`pi_repair > plain_baseline`, `p < 0.05`. A failure means the value is the
generic generate-test-fix loop, not a PI-specific edge.

### P4 — matched compute

All of the following must hold:

- on the live headroom band, raw model-call and task-solving oracle-call ratios
  are within `[0.8,1.25]` against every comparator;
- on that band, raw input+output token ratios are within `[0.8,1.25]`;
- every attempt has positive visible input-token and output-token usage;
- at each paired task/run, success is recomputed at the minimum shared
  cumulative-token budget;
- `pi_repair` remains significant at matched-token budgets against `bestN`,
  `pi_decoy`, and `plain_baseline`.

Early success may spend less than K. It receives no fabricated calls or tokens;
the matched-budget recomputation is the primary equal-token comparison.

### P5 — provenance

Analyzer gate P5 passes only when:

- every run-start artifact, manifest, and addendum hash matches the frozen
  checkout;
- the recorded git commit exists, its clean-status digest is `sha256("")`, and
  `git show` at that commit reproduces every frozen file hash;
- backend, model, endpoint class, temperature, K, replications, ordered seeds,
  ordered task fingerprints, sandbox identity, Lean toolchain pin, full Lean
  version, and Lean executable SHA-256 match the manifest, while UTC timestamps
  are valid and batch-consistent;
- all six arms and all task summaries are present;
- attempt numbers and seeds are contiguous, feedback/prior-proof hashes chain,
  physical JSONL task/arm/attempt order matches the frozen counterbalanced
  execution order, PI lifecycle kinds and candidate/diagnostic fingerprints
  bind every attempt, stop receipts conserve attempts/tokens, and aggregate
  conservation checks pass;
- every attempt has nonzero visible token telemetry and its output usage is no
  greater than the frozen per-attempt maximum;
- every attempt carries a backend-observed response model ID equal to the
  frozen model; requested-model fallback metadata is insufficient;
- payload mode is `full`, containing proof, authoritative diagnostic, supplied
  feedback, and their hashes;
- every live proof and every `pi_decoy_setup` source proof is replayed by the
  analyzer through the hash-frozen sandbox; recorded compile/proven/sorry,
  graded score, normalized diagnostic payload, and hashes must match exactly;
- `BHGMAN_LLM_ENDPOINTS` and `BHGMAN_LLM_NO_THINK` are absent so hidden
  endpoint routing or prompt-template changes cannot alter the frozen arm.
- the recorded clean commit timestamp predates every run timestamp and each
  result JSONL modification time.

Before publication, the raw JSONL and analyzer JSON must additionally be
committed with their SHA-256 values. This post-analysis publication receipt is
not something the analyzer can truthfully infer while producing that JSON.

`top_task_delta_fraction` is:

```text
max(max(pi_repair_task - bestN_task, 0))
------------------------------------------------
sum(max(pi_repair_task - bestN_task, 0))
```

It is `null` when the denominator is zero. A value above `0.5` does not erase a
real P1-P5 edge, but forces the headline `SIGNAL_CONCENTRATED_IN_ONE_TASK` and
forbids a generality claim.

## 6. Verdict

Final-claim `CONFIRM` requires B1 and P1-P5 all PASS. `ABSENT` is not PASS.
The analyzer's `confirm` field is explicitly scoped to P1-P5 only; it emits
`final_claim_confirm: null` because B1 is an external preflight.

- missing hashes, arms, payloads, or usage → `INVALID/ABSENT`;
- fewer than six live tasks or required non-ties → `INCONCLUSIVE`;
- lower-tier model null → capability-floor negative control;
- P2 failure → no oracle-content edge;
- P3 failure → operational generic repair loop only;
- P4 failure → compute-confounded;
- bridge failure → the new engine was not semantically equivalent to the
  intended repair treatment.

The first non-Lean follow-up must use at least six live tasks across pytest,
Pyright/Mypy, or Ruff diagnostics. A Lean-only confirmation remains a bounded
Lean competence-boundary result.

## 7. Planned commands

These commands become claim-bearing only after §2 is frozen and committed.

```bash
uv run pytest \
  engine/efficacy/tests/test_diagnostic_repair_harness.py::test_legacy_and_pi_repair_have_equivalent_generation_and_oracle_traces \
  -q

export BHGMAN_LLM_BASE_URL="<32b-openai-compatible-endpoint>"
export BHGMAN_LLM_MODEL="qwen2.5:32b-instruct"
export LEAN_TEMP="0.8"
export LEAN_MAX_TOKENS="3072"
unset BHGMAN_LLM_ENDPOINTS
unset BHGMAN_LLM_NO_THINK

uv run python -m engine.efficacy.diagnostic_repair_harness \
  --k 4 \
  --replications 10 \
  --seed-offset 0 \
  --seed-step 10 \
  --execute-frozen-run \
  --out-dir verification/diagnostic-repair-v2-32b

uv run python -m engine.efficacy.analyze_diagnostic_repair_harness \
  --json \
  verification/diagnostic-repair-v2-32b \
  > verification/diagnostic-repair-v2-32b/analysis.json
```
