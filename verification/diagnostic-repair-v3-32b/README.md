# Diagnostic-repair v3 exact 32B result

## Outcome

The harness and its evidence pipeline are operationally green, but the
preregistered cognitive-efficacy claim is **not confirmed**.

- Analyzer result: `confirm=false`
- Gates: `P1=ABSENT`, `P2=ABSENT`, `P3=FAIL`, `P4=ABSENT`, `P5=PASS`
- LakatoTree evidence: 2 confirmed gates out of 6 (`B1` and `P5`)
- Pure-judge result: `rejected`

The raw machine judgment is stored only in `judge-response.json`. The evidence
record and judgment packet contain no authored verdict.

## Frozen run

- Model: `qwen2.5:32b-instruct`
- Backend: OpenAI-compatible vLLM on Precision 7960
- Harness: `2.0.1`
- Lean: `leanprover/lean4:v4.27.0`
- Replications: 10, seed offsets `0..90` by 10
- Tasks: 12 per replication
- Task summaries: 120/120
- JSONL records: 3,661
- Proven totals out of 120:
  - single: 42
  - best-of-N: 53
  - legacy repair: 62
  - PI repair: 62
  - PI decoy: 48
  - plain baseline: 51

The run encountered 64 unsafe generated candidates, all in the plain-baseline
arm. They were converted into canonical failed oracle observations before
sandbox execution, and the batch completed instead of crashing.

## Integrity and restore checks

- Lean attempt replay: 1,821/1,821
- Lean setup replay: 120/120
- Replay mismatches: 0
- Replay errors: 0
- Fault injection: first `run_start.model_id` changed on an isolated copy
- Negative analyzer result: exit 2, `ContractError`, no claim-bearing analysis
- Untouched restore result: exit 0
- Original and restored analysis SHA-256:
  `d92cdea0390f39d461d907ed030c0649808e59c91de6d7c933acdc5ebc213a61`

## Gate interpretation

- P1 was absent: PI repair beat best-of-N in 5 of 6 non-tied runs, but only
  4 tasks were non-tied; the frozen gate requires at least 6 non-ties in both
  views.
- P2 was absent: PI repair beat the decoy strongly per run, while only 4 tasks
  were non-tied.
- P3 failed: PI repair beat the plain baseline per run, but the per-task exact
  test was not significant (`p=0.21875`).
- P4 was absent: matched-token comparisons lacked per-task non-tie power.
  Raw PI token usage was also 1.49x best-of-N, outside the frozen parity band.
- P5 passed: frozen provenance, model identity, task design, git state, and
  full Lean replay all matched.

The experiment therefore shows a plausible diagnostic-feedback signal, not a
task-general cognitive advantage. PI matched legacy repair on raw proven count
and did not clear the stronger causal, task-level, and compute-parity gates.

## Evidence chain

- `analysis.json`: primary analyzer output
- `analysis-restored.json`: untouched re-analysis with identical SHA
- `negative-oracle.json`: active fault-injection and restore receipt
- `ooptdd-receipt.json`: linked runtime-integrity envelope
- `lakato-evidence.json`: grounded, verdict-free evidence record
- `judge-response.json`: raw pure-judge machine result
- `judge-chain.json` and `judge-verify.json`: content-addressed re-derivation
- `judgment-packet.json`: verdict-free LakatoTree handoff
- `ooptdd-validation.log` and `judgment-validation.log`: linked-hash validator
  outputs

## Coordination note

The original task's primary OMD pathspec named the v2 evidence directory.
Before final v3 receipt writes, a dedicated v3 authority orbit was acquired:
`orb-d6155961a325`, fence 113. This does not retroactively authorize the
earlier v3 artifact creation, so the closeout records that process caveat
instead of silently treating it as clean historical coordination.
