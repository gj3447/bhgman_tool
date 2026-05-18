# Tarski 1936 — Undefinability of Truth

**Reference**: Tarski, Alfred. "Der Wahrheitsbegriff in den formalisierten Sprachen." *Studia Philosophica*, 1: 261–405, 1936.

(English: "The Concept of Truth in Formalized Languages" in *Logic, Semantics, Metamathematics*, ed. Corcoran, Hackett, 2nd ed. 1983.)

---

## Statement (informal)

For any sufficiently expressive consistent formal language `L`, the truth predicate `True_L(⌜φ⌝)` (meaning "the sentence `φ` is true in `L`") **cannot be defined within `L` itself**.

Truth-of-`L` must be defined in a *metalanguage* strictly more expressive than `L`.

**Slogan**: *No language can be its own semantic theory.*

---

## The diagonal proof (sketch)

Suppose `L` could define its own truth predicate `T(x)` (where `x` ranges over Gödel codes of sentences). Then construct, via diagonalization, a sentence `λ` saying "λ is not true":
```
λ ↔ ¬T(⌜λ⌝)
```
If `λ` is true, then `T(⌜λ⌝)` holds, so `λ` says `¬T(⌜λ⌝)` — contradicting the assumption `λ` is true.
If `λ` is false, then `¬T(⌜λ⌝)` holds, so `λ` says something true — contradicting the assumption `λ` is false.

Therefore: no such `T` exists in `L`. Truth is *outside* `L`.

---

## What it says, in plain words

You cannot build a system that *fully judges its own correctness*. The judging-of-correctness must come from *somewhere else*. Any system that *claims* to verify itself completely is either:
- Inconsistent (contains both `λ` and `¬λ`), or
- Has hidden external judgment dressed up as internal

This is the same shape as Yanofsky's universal self-reference (see [yanofsky-2003.md](yanofsky-2003.md)) — Tarski is the *semantic instance* of the unified diagonal pattern.

---

## Why it grounds bhgman

Self-improving frameworks face Tarski's wall directly:

> "Did my latest self-improvement make me better?"

This question requires the framework to *judge its own truth* — exactly what Tarski forbids. If the framework defines "better" via its own metrics, those metrics become Tarski-violating self-truth-predicates.

bhgman's structural response:
- **Naesengmoon LensSet** = the *external metalanguage* that judges bhgman's outputs
- **Executor != reviewer** = explicit Tarski compliance (the system that *makes* claims is not the system that *judges* claims)
- **External canonical citation** = Tarski's "metalanguage strictly more expressive than L"

ruflo and similar self-learning systems implicitly violate Tarski:
- SONA learns from successful patterns → success defined by ruflo's metrics → metrics judged by ruflo's own learning → circular
- ReasoningBank stores "what worked" → worked-according-to-whom? → ruflo itself → Tarski violation

---

## Tarski's hierarchy

To rescue truth predicates, Tarski constructed an *infinite hierarchy of metalanguages*:
- `L₀` — object language
- `L₁` — defines truth for `L₀` (but not for itself)
- `L₂` — defines truth for `L₁`
- ...
- `Lω` — limit, defines truth for all finite `Lₙ`
- ...

The hierarchy *cannot have a top* — that would itself be a `L∞` capable of self-truth-definition, contradicting Tarski.

bhgman parallels this in the **adversarial cascade**:
- Code is judged by tests + Lean (`L₁`)
- Tests + Lean are judged by Naesengmoon LensSet (`L₂`)
- Naesengmoon LensSet is judged by Naesengmoon meta-LensSet (`L₃`) — mathematical lens on mathematical lens
- Eventually: human review (`Lω` — external to the formal hierarchy)

No claim of "complete self-verification." Each layer judges the previous, and judgment terminates *outside* the formal system.

---

## Lean formalization in this repo

`bhgman_tool/lean/HarnessSelfReference.lean` theorem 4:

```lean
theorem tarski_instance :
  ¬ ∃ T : Sentence → Prop, ∀ φ : Sentence, T φ ↔ holds φ
```

(The apostle cannot define its own success criterion `T` such that `T φ ↔ holds φ` for all sentences `φ` it can express about itself.)

---

## Practical consequence for tool users

When using bhgman:
- ✅ Use Lean to *prove* a theorem — Lean is *outside* the proven content (Tarski-compliant)
- ✅ Use pytest to *test* code — tests are *outside* the tested code (Tarski-compliant)
- ✅ Use Naesengmoon to *validate* outputs — Naesengmoon is *outside* the validated agent (Tarski-compliant)
- ❌ Don't let an agent *self-grade* its own work and report the grade as ground truth — Tarski violation
- ❌ Don't compute a "framework health score" from inside the framework — Tarski violation

---

## Misuses to avoid

1. **"Tarski only applies to set theory"** — No. Applies to *any* sufficiently expressive formal language, including programming languages with self-reflection (Smith 1984 MOP — see [smith-1984-reflection-mop.md](smith-1984-reflection-mop.md)).
2. **"Tarski is solved by partial truth predicates"** — Kripke 1975 (*Outline of a Theory of Truth*) provides one such approach, but at the cost of giving up classical bivalence. bhgman uses classical logic, hence pure Tarski applies.
3. **"My LLM can grade itself"** — *Especially* dangerous. LLMs trained on human grades will reproduce *expected* grades, not *true* grades. The bias is invisible from inside the LLM. Tarski explicitly forbids this configuration.

---

## Cross-references

- [yanofsky-2003.md](yanofsky-2003.md) — Tarski as one of 6 unified instances
- [godel-1931.md](godel-1931.md) — Gödel's incompleteness shares the diagonal shape
- [smith-1984-reflection-mop.md](smith-1984-reflection-mop.md) — Reflection in programming languages
- [../02-concepts/goodhart-safeguard.md](../02-concepts/goodhart-safeguard.md) — Practical safeguard

---

## Further reading

- Tarski, "The Semantic Conception of Truth and the Foundations of Semantics" (1944) — author's accessible exposition
- Field, *Saving Truth from Paradox* (Oxford, 2008) — modern approaches to truth + Tarski's legacy
- McGee, *Truth, Vagueness, and Paradox* (Hackett, 1991)
