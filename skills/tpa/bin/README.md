# tpa-round-trip-ci — runtime prototype

Implements `THEORY/TPA/ROUND_TRIP_CI_SPEC.md` v1.0.

## Usage

```bash
# minimum invocation (first commit, no history)
tpa-round-trip-ci --forward apt_spec.json --reverse tpa_spec.json

# with history (for sliding-window Lakatos verdict)
tpa-round-trip-ci \
  --forward apt_spec.json \
  --reverse tpa_spec.json \
  --history trts_history.json \
  --output trts_history.json    # appends current verdict, ready for next run

# threshold override (per-project tuning)
tpa-round-trip-ci ... --thresholds custom_thresholds.json
```

## JSON contract

**Input — `forward` / `reverse`** (same shape, output of APT-ST and TPA-TA respectively):
```json
{
  "contracts": [
    {
      "name": "ContractName",
      "pre": "precondition_expression",
      "post": "postcondition_expression",
      "invariant": "invariant_expression",
      "access_rights": "...",
      "data_axis": "DTO_or_schema_label",
      "interaction_axis": "DesignPatternLabel (e.g. Strategy / Adapter / Repository)",
      "lifecycle_axis": "...",
      "consistency_axis": "...",
      "temporal_axis": "..."
    },
    ...
  ]
}
```

All 9 axes are optional. Missing axes are treated as empty strings; tolerance per-axis from `MethodologyConfig:tpa_axis_tolerance_v1`.

**Input — `history`** (list of prior commits' TRTS):
```json
[
  {"trts": {...}, "verdict": "progressive|degenerating|essential_constant|first_commit"},
  ...
]
```

**Output** (stdout JSON unless `--quiet`):
```json
{
  "trts": {
    "coverage_ratio": 0.6667,
    "drift_5tuple": [missing, orphan, sig_mismatch, pattern_div, label_rot],
    "drift_total": 3,
    "essential_residual": 2.1111,
    "spec_size_forward": 3,
    "spec_size_reverse": 3
  },
  "lakatos_verdict": "degenerating",
  "lakatos_verdict_window": "degenerating_3_of_5" | "ok",
  "ci_pass": true | false,
  "thresholds": {...}
}
```

**Exit codes**:
- `0` — TRTS passes (no blocking degenerating window)
- `1` — degenerating window triggered (block PR / commit)
- `2` — input JSON parse error

## Window semantics

- `degenerating_consecutive` (default 3) is **trailing** — recovery clears the block immediately. The invariant is *"currently in a degenerating shift"*, not *"ever was"*.
- `window_size` (default 10) limits how far back the trailing-consecutive scan reaches.

## CI templates

### Mode A — local pre-commit hook
```bash
#!/usr/bin/env bash
set -euo pipefail
apt --phase ST --output /tmp/apt_spec.json .
tpa --phase TA --output /tmp/tpa_spec.json .
tpa-round-trip-ci \
  --forward /tmp/apt_spec.json \
  --reverse /tmp/tpa_spec.json \
  --history .git/trts_history.json \
  --output .git/trts_history.json
```

### Mode B — GitHub Actions
```yaml
- name: TPA Round-Trip CI
  run: |
    tpa-round-trip-ci \
      --forward apt_spec.json \
      --reverse tpa_spec.json \
      --history .trts_history.json
```

## Tests

```bash
# Sample inputs in this directory
tpa-round-trip-ci --forward sample_forward.json --reverse sample_reverse.json
```

KG: `:CIPolicy {name:'tpa-round-trip-ci-v1'}`, `lesson-tpa-round-trip-ci-runtime-2026-05-02`
