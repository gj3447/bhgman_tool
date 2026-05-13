# Worked Example 2 — Goodhart antipattern detection on ruflo

> Reproduce the **Lakatos DEGENERATING** verdict for ruflo independently. Apply 3-lens Goodhart detection to a snapshot of ruflo's README and recover the 3 canonical ErrorPatterns.
>
> KG: `span-worked-example-goodhart-on-ruflo-2026-05-13` (:AtomicSpan)

---

## What you'll see

1. A **deterministic snapshot** of ruflo's README (committed locally — no live network call)
2. `analyze.py` applies the `goodhart-detection` LensSet (3 lenses) to the snapshot
3. Output reproduces the **3 canonical ErrorPatterns**:
   - `goodhart-metric-optimization-marketing` (e.g., "84.8% SWE-Bench" claim)
   - `enumeration-inflation-no-responsibility-split` (e.g., "100+ agents / 32 plugins / 314 MCP tools" flat enumeration)
   - `self-improving-loop-without-goodhart-safeguard` (SONA + ReasoningBank + no Tarski/Goodhart acknowledgment)
4. Final verdict: **Lakatos = DEGENERATING**

The point is **reproducibility**. Our KG records the verdict; this example lets *anyone* recompute it from the source text.

---

## Run

```bash
cd worked/02-goodhart-on-ruflo/
python3 analyze.py
```

Expected runtime: under 2 seconds. Pure regex + heuristic, no LLM, no network.

---

## Files

| File | Role |
|---|---|
| `ruflo_readme_snapshot.md` | Deterministic excerpt of ruflo README (committed) |
| `analyze.py` | 3-lens detector + Lakatos verdict |
| `expected_findings.md` | What you should see |
| `test_worked_02.py` | pytest verification |

---

## The 3 lenses applied

### Lens 1 — `lens-goodhart-metric-as-marketing`
Detects quantitative claim (X% / N+) promoted as primary value signal **without** external canonical citation.

Pattern: `\d+\.?\d*%\s+(SWE-Bench|HumanEval|MMLU|...)`, `\d+%\s+(token|reduction|faster|improvement)`, ...

### Lens 2 — `lens-enumeration-inflation`
Detects flat enumeration of technical units (plugins / agents / tools) ≥ 10 on the same layer **without** responsibility_split sub-type mention.

Pattern: `\d+\+?\s+(agents|plugins|tools|commands)` AND no occurrence of `responsibility_split` / `CCP` / `boundary location` / 3-tier sibling family.

### Lens 3 — `lens-self-improving-no-safeguard`
Detects self-improving loop mention (SONA / ReasoningBank / RL learning) **without** Tarski/Goodhart/Lakatos acknowledgment.

Pattern: `(self[- ]learning|SONA|ReasoningBank|trajectory)` AND no occurrence of `(Goodhart|Lakatos|Tarski|Yanofsky|safeguard)`.

---

## Expected findings (excerpt)

```
Goodhart Antipattern Audit
==========================
Target: ruflo (snapshot 2026-05-13)
LensSet: goodhart-detection (3 lenses)

[Lens 1] goodhart-metric-as-marketing — DETECTED
  Evidence: 84.8% SWE-Bench solve rate (line N)
  Evidence: 32% token reduction (line N)
  External canonical citation: ABSENT

[Lens 2] enumeration-inflation — DETECTED
  Evidence: 100+ Agents (line N)
  Evidence: 32 plugins (line N)
  Evidence: 314 MCP tools (line N)
  responsibility_split mention: ABSENT

[Lens 3] self-improving-no-safeguard — DETECTED
  Evidence: Self-Learning / SONA neural patterns (line N)
  Goodhart/Lakatos/Tarski acknowledgment: ABSENT

Summary:
  ErrorPatterns detected: 3 / 3
  Lakatos verdict: DEGENERATING
```

Full output: [expected_findings.md](expected_findings.md).

---

## Why this matters

1. **Reproducibility** — Our KG records `lakatos-verdict-3-targets-2026-05-13` with `ruflo = DEGENERATING`. This example lets anyone *reconstruct* that verdict from the source text, not from our claim.
2. **Goodhart safeguard as falsifiable** — If a reader disagrees with our LensSet, they can modify `analyze.py` and see what the lenses *actually* match against. The argument becomes *concrete*, not rhetorical.
3. **Self-application** — Anyone can run this on *bhgman_tool's own README* to check if we commit the same patterns. (Self-application *should* return *no* ErrorPatterns in our case — that's our Goodhart safeguard hypothesis.)

---

## Self-check

```bash
# Apply the same lenses to bhgman_tool's README
python3 analyze.py ../../README.md
```

If our framework commits Goodhart antipatterns, this will detect them. (As of 2026-05-13: expected 0 detections.)

---

## Next steps

After this example:
- [01-longinus-simple](../01-longinus-simple/README.md) — drift detection walkthrough
- [../docs/05-papers/goodhart-1975.md](../../docs/05-papers/goodhart-1975.md) — canonical paper
- [../docs/02-concepts/goodhart-safeguard.md](../../docs/02-concepts/goodhart-safeguard.md) — full safeguard architecture
