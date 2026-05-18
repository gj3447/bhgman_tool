# Smith 1984 / Kiczales 1991 — Reflection and the Metaobject Protocol (MOP)

**References**:
- Smith, Brian Cantwell. "Reflection and Semantics in a Procedural Language." MIT/LCS/TR-272, 1982. *Reflection and Semantics in LISP*, POPL 1984.
- Kiczales, Gregor; des Rivières, Jim; Bobrow, Daniel G. *The Art of the Metaobject Protocol*. MIT Press, 1991.

---

## What "reflection" means

A programming system is **reflective** if it can:
1. **Introspect** — examine its own structure (types, methods, runtime state) at runtime
2. **Modify** — change its own behavior based on the introspection

Examples:
- Python's `inspect`, `__class__`, `getattr` — moderate reflection
- Lisp/Scheme `eval` — strong reflection (code = data)
- Java's `java.lang.reflect` — type-level reflection
- Smalltalk's full self-modification — extreme reflection

Smith's 1984 paper introduced the *formal* notion: a reflective system has a **causal connection** between its self-representation and its actual behavior — modifying the self-representation *causes* behavior change.

---

## The Metaobject Protocol (MOP, Kiczales 1991)

Kiczales et al. generalized Smith's reflection into a *design pattern* for object systems:
- Every object has a **metaobject** (the class) governing its behavior
- The metaobject is itself an object — has its own metaobject (the metaclass)
- The MOP is the *protocol* by which programmers customize the metaobject's behavior

Example: CLOS (Common Lisp Object System) MOP lets you customize:
- How method dispatch works (`compute-applicable-methods`)
- How instances are created (`allocate-instance`, `initialize-instance`)
- How slot access is performed (`slot-value-using-class`)

The MOP is the *meta-level* of the language, exposed as part of the language.

---

## Why it grounds bhgman

### APT MetaReview phase = MOP-style reflection

The APT cycle (described in [../03-tutorials/apt-cycle.md](../03-tutorials/apt-cycle.md)) has a **MetaReview phase** (Phase 5) that:
1. **Introspects** the just-completed cycle (what spans, what contracts, what code)
2. **Diagnoses** the cycle's quality (Lakatos progressive vs degenerating)
3. **Modifies** the framework itself (SKILL.md patches, KG :Lesson additions)
4. **Limits** itself (termination conditions: self_application_forbidden, max_depth=1)

This is *exactly* MOP-style reflection. The cycle inspects itself and modifies its own SKILL.md — the protocol for future cycles.

### Termination conditions = Smith's causal-connection limits

Smith warned: unbounded reflection leads to *infinite regress* (the meta-meta-meta-...-level keeps going). Practical reflective systems must *terminate* the regress.

bhgman terminates MetaReview at depth 1:
- `self_application_forbidden`: MetaReview cannot review itself (Tarski-compliant)
- `max_depth=1`: meta-meta-review not performed (Gödel/Smith-compliant)
- `delta=0`: if no new issues, terminate (Lakatos-compliant)

This is *engineering reflection*, not pure-philosophical reflection. The boundedness is a *feature*, not a limitation.

### Tarski + Smith together

Tarski 1936 says: self-truth-predicate cannot be defined within `L`.
Smith 1984 says: but self-representation *can* be causally connected, given a meta-language relationship.
Together: reflection is *useful* (Smith) but *bounded* (Tarski).

bhgman's MetaReview operates in this bounded reflection regime:
- **Meta-language** = Naesengmoon LensSet + Lean 4 + human review (external to the cycle being reviewed)
- **Causal connection** = SKILL.md patches actually change future cycles
- **Termination** = Tarski-aware (cannot fully self-judge)

---

## ACI mirror (Aspect-Class-Instance)

Kiczales et al. extended MOP into a three-layer ontology:
- **Aspect** — abstract concern (e.g., "logging," "caching") that cuts across classes
- **Class** — the type-level definition
- **Instance** — runtime particular

bhgman's Harness mirrors this:
- **Apostle** (e.g., Airplane Man) ≈ Aspect (the abstract `∀x:CHU, j.covers x` concern)
- **Family tier** (e.g., L_MC, L_RT, L_IDE) ≈ Class (the type-level decomposition)
- **Industry instance** (e.g., Cursor, ruflo, LangGraph) ≈ Instance (runtime realization)

This 3-layer ACI mirror is **formally verified**: `Harness_ACI_Mirror.lean` 10 theorems prove the apostle-family-instance hierarchy is consistent.

The deeper claim: **bhgman is itself a MOP** for AI agent design. You're not stuck with a fixed agent model; you operate at the *meta-level* (apostle definitions) and customize the *object-level* (tools and instances).

---

## Practical reflection in this repo

```python
# pseudocode — APT MetaReview phase
from bhgman_tool import APTCycle, MetaReview, TalibanLensSet

cycle = APTCycle.load("auth-feature-2026-05-13")
review = MetaReview(cycle)

# Introspection
spans = review.spans                    # what spans were processed
contracts = review.contracts            # what contracts crystallized
lessons_found = review.discovered_issues()  # what surprised us

# Modification (MOP-style)
for lesson in lessons_found:
    # Add lesson to KG (causal connection: future cycles will see this)
    lesson.commit_to_kg()

    # Patch SKILL.md if needed (causal: future Phase 4 will use updated logic)
    if lesson.skill_patch_needed:
        apply_skill_patch(lesson.suggested_patch)

# Termination
assert review.depth == 1               # no meta-meta-review
assert not review.self_applied         # MetaReview hasn't reviewed itself
assert review.delta_from_prior() >= 0  # actual progress
```

---

## bhgman as a MOP for AI design

The radical claim: most AI framework discussions stay at the *object level* ("agent X vs agent Y," "tool A vs tool B"). bhgman operates at the *meta level* (apostle definitions, tool families, instance taxonomies). This is what makes bhgman:
- **Independent** of specific framework choices (you can use ruflo, LangGraph, ADK — bhgman frames them all)
- **Extensible** beyond current options (a new framework appears? slot it into an existing tier)
- **Diagnostic** for failure modes (when something goes wrong, you ask "which layer? aspect / class / instance?")

This is the *MOP for AI design*. The Kiczales et al. tradition continued.

---

## Misuses to avoid

1. **"Reflection = magic"** — No. Reflection is *causal* (in Smith's precise sense) but *bounded* (terminating). Magic implies unbounded; engineering implies bounded.
2. **"All reflective systems are slow"** — Common belief, but reflection's cost is *one-time* (at customization), not *per-invocation*. CLOS implementations are competitive with non-reflective OO languages.
3. **"MOP died with Lisp"** — No. MOP ideas appear in Aspect-Oriented Programming (Kiczales again), Python's `__init_subclass__` and `__set_name__`, Ruby's open classes, every modern dependency injection framework. The pattern is alive.

---

## Cross-references

- [tarski-1936-undefinability.md](tarski-1936-undefinability.md) — Reflection's formal limits
- [godel-1931.md](godel-1931.md) — Incompleteness applies to reflective systems too
- [../02-concepts/harness.md](../02-concepts/harness.md) §ACI mirror
- [../02-concepts/apt-tpa-cycles.md](../02-concepts/apt-tpa-cycles.md) §MetaReview phase
- [hofstadter-1979-strange-loop.md](hofstadter-1979-strange-loop.md) — Reflection as strange loop

---

## Further reading

- Maes, *Computational Reflection* (PhD thesis, 1987) — extended Smith's framework
- Demers & Malenfant, "Reflection in Logic, Functional, and Object-Oriented Programming" (1995)
- Cazzola et al., *Reflection, AOP and Meta-Data for Software Evolution* (Springer, 2007)
- Modern: Stripe's `signals` framework, Pyrolinear, etc. — practical MOP descendants
