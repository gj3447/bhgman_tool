# Expected output

```
=== Step 1: bhgman-tool version (CLI entry registered) ===
bhgman-tool 0.1.0
  repo root: <ABSOLUTE_PATH>/bhgman_tool
  skills (22): 88-taliban, apt, apt-cleanup, apt-meta-review, apt-sa, ...
  engine (4): cli, longinus_drift_audit, mcp_server, memory
  worked (3): 01-longinus-simple, 02-goodhart-on-ruflo, 03-apt-cycle-on-self
  layer: tool (Airplane Man #4 engineering crystallization)
  essence layer: separate (see docs/07-metahumotonic-trace.md)
[PASS] bhgman-tool version emits version string

=== Step 2: pytest engine/cli + engine/mcp_server (35 new tests) ===
.....................................  [100%]
N passed in <time>s
[PASS] pytest passed (see /tmp/worked-03-step2.out for count)

=== Step 3: SemanticAnchor name persisted in apt-progress.md ===
[PASS] anchor name found in apt-progress.md

=== Step 4: last 3 commits contain Phase 3 markers ===
<sha> feat(APT v26.1 Phase 3 ...): ...
[PASS] Phase 3 commit present in recent log

=== Summary ===
pass=4  fail=0  skip=0
```

Exit code: **0** (all checks pass).

## What you might see instead

- **`[SKIP]` on steps 1+2 with "uv not installed"** — install uv first.
- **`worked (3): ... 03-apt-cycle-on-self`** — after this commit lands. Before commit, the directory listing in step 1 may show `worked (2)`.
- **Skill count `(22)`** drifts as new SKILL dirs are added. The exact number is not stable; the assertion in step 1 only checks the version header.

## What this output does NOT contain (Goodhart safeguard)

- No single percentage score
- No "84.8% accuracy"-style headline metric
- Raw pass/fail/skip counts only — consumer judges fitness from the list
