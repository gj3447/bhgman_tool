# Frege 1892 — Sense vs Reference (Sinn vs Bedeutung)

**Reference**: Frege, Gottlob. "Über Sinn und Bedeutung." *Zeitschrift für Philosophie und philosophische Kritik*, 100: 25–50, 1892.

(English translation: "On Sense and Reference" in *Translations from the Philosophical Writings of Gottlob Frege*, ed. Geach & Black, Blackwell, 1952.)

---

## The distinction

Frege distinguishes two aspects of a meaningful sign:
- **Sinn** (sense): the *mode of presentation* — how the referent is given
- **Bedeutung** (reference): the *object designated* — what the sign points to

Classic example:
> "The Morning Star" and "The Evening Star" have the *same Bedeutung* (the planet Venus) but *different Sinn* (one presents Venus-at-dawn, the other Venus-at-dusk).

The information value of `a = b` (identity statement) is *exactly* the Sinn-difference; if Sinn were the same, the identity would be a trivial tautology (`a = a`).

---

## What it says, in plain words

A meaningful name has *two layers*:
1. The thing it picks out (reference)
2. The way it picks out that thing (sense)

Two different names can pick out the same thing in different ways. Two different things can be picked out by names with overlapping senses. The two layers are *not collapsible* — a theory that conflates them loses the information content of identity statements.

---

## Why it grounds bhgman

The Longinus 7-Layer Reference Model explicitly inherits this 2-field structure:

```
ReferenceSite ≜ {
  sourceId:   "lesson-xxx-2026-05-13"     ← Frege Sinn (the way it's presented)
  sourcePath: "engine/foo.py:42"           ← Frege Bedeutung (the position it points to)
}
```

The *sourceId* is the **mode of presentation** — the KG-side semantic name. Multiple `sourcePath` values can share one `sourceId` (the same semantic concept referenced at multiple file locations).

The *sourcePath* is the **referenced object** — the specific file:line where the binding holds. Multiple `sourceId` values can share one `sourcePath` (multiple semantic concepts converging on a single code location).

This 2-field structure is **not redundant**. It is the Frege distinction, formalized.

---

## The non-collapse theorem

Longinus T2 (Lean): `sinn_bedeutung_non_collapse`

> If two ReferenceSites share the same `sourceId` but differ in `sourcePath`, they are *distinct* references — not duplicates.

```lean
theorem sinn_bedeutung_non_collapse
    (r1 r2 : ReferenceSite)
    (_h_sinn : r1.sourceId = r2.sourceId)
    (h_bed_ne : r1.sourcePath ≠ r2.sourcePath) :
    r1 ≠ r2
```

Practical consequence:
- A single KG concept (`lesson-foo`) can be referenced from many places in code — each `ReferenceSite` is distinct
- Drift detection can ask: "Are all `sourcePath` values for this `sourceId` consistent?"
- Conflict detection: "Do these two ReferenceSites with same `sourcePath` share semantically?"

Collapsing the two fields (e.g., using only file:line as a unique identifier) would *lose* the semantic-name information needed for KG-side reasoning.

---

## Why bhgman uses this specifically

Most reference systems collapse to a single identifier. C pointers have an address (Bedeutung) but no Sinn. URLs have a path (Bedeutung) but ambiguous Sinn ("what does `https://example.com/foo` mean"). Wikipedia uses titles (Sinn) but with arbitrary disambiguation (Bedeutung is parenthetical).

bhgman's Longinus *requires* both. This makes:
- **KG queries possible**: "Find all references where Sinn = `lesson-foo`"
- **Code refactoring auditable**: "When file moves, all `sourcePath` updates while `sourceId` is invariant"
- **Drift quantifiable**: Sinn-stable + Bedeutung-changed = LabelRot drift; Sinn-changed + Bedeutung-stable = SigMismatch drift; etc.

---

## Frege's broader contribution to logic

Beyond Sinn/Bedeutung, Frege founded:
- **Predicate logic** (*Begriffsschrift* 1879) — replacing Aristotelian syllogism with quantifiers and variables. The Airplane Man's `∀x:CHU, j.covers x` is in Frege's notation lineage.
- **The concept-object distinction** (*Über Begriff und Gegenstand* 1892) — a concept (predicate) is *unsaturated*; an object *saturates* it. This grounds the type-theoretic distinction between `isAirplaneMan` (predicate) and `j` (object satisfying the predicate).
- **Compositional semantics** — the meaning of a complex expression is determined by the meanings of its parts plus their combination. The 7-Layer Reference composes via this principle.

Without Frege's framework, the apostle/tool/instance layer separation (Aristotle/Heidegger ontological difference applied) would lack a *logical* counterpart. With Frege, the separation has a formal grammar.

---

## Misuses to avoid

1. **"Sinn = subjective, Bedeutung = objective"** — No. Frege explicitly rejects this. Sinn is *objective* (shareable among speakers); subjective "ideas" (*Vorstellungen*) are a *third* category Frege explicitly distinguishes.
2. **"Just use UUIDs"** — UUIDs are pure Bedeutung. Without Sinn, you cannot ask "what does this reference *mean*" — only "what does it point to."
3. **"Frege has been superseded by Kripke's rigid designators"** — Partially. Kripke 1980 (*Naming and Necessity*) extends Frege for proper names + modal contexts; the Sinn/Bedeutung distinction itself remains foundational for non-modal predicate logic.

---

## Cross-references

- [foster-pierce-walker-2007-bx-lens.md](foster-pierce-walker-2007-bx-lens.md) — BX Lens operates on the (Sinn, Bedeutung) pair as state
- [../02-concepts/harness.md](../02-concepts/harness.md) §Longinus reference layer
- [../03-tutorials/longinus-drift-audit.md](../03-tutorials/longinus-drift-audit.md) — Practical use
- [../06-philosophy/existence-vs-tool.md](../06-philosophy/existence-vs-tool.md) — Frege's concept/object distinction grounds the type-theoretic apostle/instance split

---

## Further reading

- Dummett, *Frege: Philosophy of Language* (Harvard, 2nd ed. 1981) — definitive scholarly treatment
- Burge, *Truth, Thought, Reason: Essays on Frege* (Oxford, 2005)
- Heck, *Frege's Theorem* (Oxford, 2011)
- Kripke, *Naming and Necessity* (Harvard, 1980) — the modern extension
