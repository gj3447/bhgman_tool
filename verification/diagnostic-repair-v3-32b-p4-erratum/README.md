# Diagnostic-repair v3 P4 erratum

The frozen v3 result remains rejected. This erratum corrects one gate label:
`P4=ABSENT` becomes `P4=FAIL` because multiple already measured compute ratios
violate the preregistered `[0.8, 1.25]` interval. An underpowered matched-token
conjunct cannot mask a known false conjunct in an `AND` gate.

## Corrected observation

- PI / best-N total-token ratio: `1.486902`
- PI / plain model-call ratio: `0.763547`
- PI / plain oracle-call ratio: `0.763547`
- PI / plain total-token ratio: `0.622249`
- Corrected P4: `FAIL`
- Original and corrected final claim: `rejected`

The original `analysis.json` remains byte-identical at SHA-256
`d92cdea0390f39d461d907ed030c0649808e59c91de6d7c933acdc5ebc213a61`.
The overlay binds that source plus its own generator hash; it does not rewrite
raw records, the frozen manifest, or the historical analyzer.

## Executable evidence

```bash
uv run python verification/diagnostic-repair-v3-32b-p4-erratum/run_erratum_checks.py
uv run pytest engine/efficacy/tests/test_diagnostic_repair_analysis_errata.py -q
python3 SKILLS/ooptdd-receipt/scripts/validate_receipt.py \
  GIT/bhgman_tool-wt-pi-runtime-20260716/verification/diagnostic-repair-v3-32b-p4-erratum/ooptdd-receipt.json \
  --verify-linked \
  --root GIT/bhgman_tool-wt-pi-runtime-20260716
```

The controlled negative changes every raw ratio to `1.0`. The same overlay
then rejects the correction with `ErratumError` instead of fabricating a P4
failure. Restoring the original input reproduces the positive overlay exactly.

The LakatoTree metric remains two confirmed gates (`B1` and `P5`), so the
existing deterministic `rejected` judgment is invariant under this correction.
