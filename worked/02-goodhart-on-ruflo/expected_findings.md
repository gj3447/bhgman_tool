# Expected findings

When you run `python3 analyze.py` (default target = `ruflo_readme_snapshot.md`):

```
Goodhart Antipattern Audit
==========================
Target: ruflo_readme_snapshot.md
LensSet: goodhart-detection-2026-05-13 (3 lenses)

[Lens 1] lens-goodhart-metric-as-marketing — DETECTED
  Evidence: ... 84.8% SWE-Bench solve rate ...
  Evidence: ... 32.3% token reduction ...
  external_canonical_citation: ABSENT

[Lens 2] lens-enumeration-inflation — DETECTED
  Evidence: ... 100+ Agents ...
  Evidence: ... 314 MCP tools ...
  Evidence: ... 100 max concurrent agents ...
  responsibility_split_mention: ABSENT

[Lens 3] lens-self-improving-no-safeguard — DETECTED
  Evidence: ... Self-Learning ...
  Evidence: ... SONA neural patterns ...
  Evidence: ... ReasoningBank ...
  safeguard_acknowledgment: ABSENT

Summary:
  ErrorPatterns detected: 3 / 3
  Lakatos verdict: DEGENERATING
```

Exit code: **1** (DEGENERATING).

---

## Self-application on bhgman_tool's README

```bash
python3 analyze.py ../../README.md
```

Expected: **0/3 detected** (or possibly 1/3 if the comparison table mentions ruflo's metrics).

Why we expect ≤1:
- ✅ External canonical citations present (Goodhart 1975, Cherns 1976, Lakatos 1976 mentioned by name)
- ✅ `responsibility_split` mentioned explicitly
- ✅ `safeguard` mentioned in Goodhart safeguard discussions

If `analyze.py` returns 2+ detections on our own README, we have a *self-Goodhart problem* — would file an :ErrorPattern lesson against ourselves immediately.
