# Worked Example 1 — Longinus drift audit on a small Python project

> End-to-end reproducible scenario. Detect a *deliberate* drift between code and its KG reference annotation.
>
> KG: `span-worked-example-longinus-simple-2026-05-13` (:AtomicSpan)

---

## What you'll see

1. A small Python module (`sample.py`) with KG reference comments (`# KG: lesson-foo-2026-05-13`)
2. A deliberate **drift**: the comment claims one signature, the code has another
3. The Longinus drift audit detects the drift
4. Expected output matches `expected_output.md`

---

## Run

```bash
cd worked/01-longinus-simple/
./run.sh
```

Expected runtime: under 5 seconds (no external services).

---

## Files

| File | Role |
|---|---|
| `sample.py` | Small module with KG references; one of them is *intentionally* misaligned with the code |
| `run.sh` | Runs the audit and prints the report |
| `expected_output.md` | What you should see |
| `test_worked_01.py` | pytest that runs `run.sh` and diffs against `expected_output.md` |

---

## Drift introduced (spoiler)

In `sample.py`:
```python
# KG: lesson-validate-email-2026-05-13
def validate(email: str) -> bool:    # ← code says (email)
    return "@" in email
```

But the canonical KG record (simulated locally for this example) says:
```
lesson-validate-email-2026-05-13:
  expected_signature: validate(addr: str, strict: bool = False) -> bool
```

→ **SigMismatch drift** (Longinus T3, PutGet violation).

---

## What Longinus does about it

1. **Scan** `sample.py` for `# KG:` comments
2. **Resolve** each KG id against the local KG store (here: `kg_simulated.json`)
3. **Compare** the function signature (`(email)`) with the KG-claimed signature (`(addr, strict)`)
4. **Emit** a `DriftRecord(drift_type=SigMismatch, lens_law_violated=PutGet)`

---

## Expected output (excerpt)

```
Longinus Audit Report
=====================
Scanned: 1 file, 3 KG references
Drifts detected: 1

[SigMismatch @ sample.py:5]
  KG: lesson-validate-email-2026-05-13
  Expected: validate(addr: str, strict: bool = False) -> bool
  Actual:   validate(email: str) -> bool
  Layer violated: L3_TypePermission
  BX Lens law violated: PutGet
```

Full output: [expected_output.md](expected_output.md).

---

## Reproducibility

This example does **not** require:
- ❌ Network access
- ❌ Neo4j or external KG
- ❌ API keys

It **does** require:
- ✅ Python 3.11+
- ✅ The `longinus-drift-audit` package (installed via `pip install -e ../../engine/longinus_drift_audit`)

---

## Next steps

After this example:
- [02-goodhart-on-ruflo](../02-goodhart-on-ruflo/README.md) — apply Goodhart LensSet to a real OSS README (planned)
- [../docs/03-tutorials/longinus-drift-audit.md](../../docs/03-tutorials/longinus-drift-audit.md) — full Longinus tutorial
- [../docs/02-concepts/harness.md](../../docs/02-concepts/harness.md) — broader Harness context
