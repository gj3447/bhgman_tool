# Expected output

```
Longinus Audit Report
=====================
Scanned: 1 file, 3 KG references
Drifts detected: 1

[SigMismatch @ sample.py:18]
  KG: lesson-validate-email-2026-05-13
  Expected: validate(addr: str, strict: bool = False) -> bool
  Actual:   validate(email: str) -> bool
  Layer violated: L3_TypePermission
  BX Lens law violated: PutGet

```

Exit code: **1** (drifts present)
