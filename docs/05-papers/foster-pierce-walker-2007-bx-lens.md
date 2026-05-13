# Foster-Pierce-Walker 2007 — BX Lens Laws

**Reference**: Foster, J. Nathan; Pierce, Benjamin C.; Walker, Adam. "Combinators for Bidirectional Tree Transformations." *POPL '07: Proceedings of the 34th ACM SIGPLAN-SIGACT symposium on Principles of programming languages*, 2007.

(Often cited as the canonical formalization of **bidirectional transformations** (BX).)

---

## Statement

A **lens** is a pair `(get, put)` where:
- `get : S → V` extracts a view `V` from a source `S`
- `put : S × V → S` updates the source given a new view value

Subject to three laws:

| Law | Equation | Meaning |
|---|---|---|
| **GetPut** | `put(s, get(s)) = s` | If you set the view to its current value, the source is unchanged |
| **PutGet** | `get(put(s, v)) = v` | If you set the view to `v`, then `get` returns `v` |
| **PutPut** | `put(put(s, v1), v2) = put(s, v2)` | Successive updates: only the last counts |

These three laws are *not all independent*; "well-behaved" lenses satisfy GetPut + PutGet; "very well-behaved" lenses also satisfy PutPut.

---

## What it says, in plain words

When two structures (a *source* and a *view*) must stay synchronized through edits on either side, the lens laws are the *minimal consistency conditions*. They prevent the common bugs: phantom edits, lost updates, divergent histories.

This is exactly the situation when **knowledge graph (KG)** and **source code** must stay synchronized — every code edit may need a KG update; every KG annotation may need a code change.

---

## Why it grounds bhgman

Longinus (the KG↔code reference binding tool, one of the 5 weapons) is *literally* a bidirectional transformation between a KG state and source code. The 7-Layer Reference Model is structured to make this lens explicit:

- `sourceId` (KG node name) ↔ `sourcePath` (file:line) is a **lens**
- Drift detection = lens law violation detection
- Five drift types (Missing / Orphan / SigMismatch / PatternDiv / LabelRot) **surjectively map** onto the three lens laws:

| Drift type | Lens law violation |
|---|---|
| **Missing** (code exists, KG ref absent) | PutGet violation (failed update) |
| **Orphan** (KG ref exists, code absent) | GetPut violation (phantom value) |
| **SigMismatch** (ref ↔ signature mismatch) | PutGet violation |
| **PatternDiv** (same target ↔ conflicting refs) | PutPut violation |
| **LabelRot** (label/name change unreflected) | PutPut violation |

This is formalized in Longinus T3 (a Lean theorem proving the mapping is surjective).

---

## Lean formalization in this repo

`bhgman_tool/lean/Longinus_ConfidenceSchema_GraphifyAbsorbed.lean` — 7 theorems, 0 sorry, including:

| Theorem | Statement |
|---|---|
| `bx_getput` | Foster GetPut law for ReferenceSite (`get ∘ put = id` on the put value) |
| `bx_putget` | Foster PutGet law for ReferenceSite (`put ∘ get` is identity) |

The PutPut law is verified at the Python runtime level (`engine/longinus_drift_audit/bx_lens.py` `Lens.verify_put_put`).

---

## Practical use in this repo

```python
# bhgman_tool/engine/longinus_drift_audit/bx_lens.py
from longinus_drift_audit import Lens

# A simple lens between a dict (KG-like state) and string values at a key
lens = make_dict_lens(key="lesson-foo-2026")

# Verify all three laws
result = lens.verify_all(s={}, v1="code-edit-A", v2="code-edit-B")
assert result.get_put and result.put_get and result.put_put
```

See [../03-tutorials/longinus-drift-audit.md](../03-tutorials/longinus-drift-audit.md) for full walkthrough.

---

## Misuses to avoid

1. **"Lenses fix all sync bugs"** — No. Lenses are a *contract*; they catch *consistent* lenses from *inconsistent* ones, but they don't solve underlying domain modelling.
2. **"PutPut is optional"** — Sometimes. For audit-trail systems where edit history matters, you may *not want* PutPut (you want every intermediate state preserved). bhgman currently assumes well-behaved + very well-behaved depending on use.
3. **"Lenses imply round-tripping is free"** — No. Round-trips can still lose information; lens laws say they lose information *consistently*.

---

## Cross-references

- [../02-concepts/harness.md](../02-concepts/harness.md) §Longinus reference layer
- [../06-philosophy/hermeneutic-circle.md](../06-philosophy/hermeneutic-circle.md) — Lens as formal equivalent of hermeneutic circle
- [frege-1892-sense-reference.md](frege-1892-sense-reference.md) — Frege Sinn (sourceId) ↔ Bedeutung (sourcePath) 2-field structure underlying the lens

---

## Further reading

- Pierce, *Software Foundations* Vol. 3 (online) — bidirectional programming chapter
- Hu et al., "A Lens-Based Approach to Bidirectional Transformation" (BX 2018)
- Cheney, "Categorical Foundations of Bidirectional Transformations" (2009)
