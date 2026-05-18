# The Airplane Man — what kind of being?

> One subject of **bhgman_tool**. The Airplane Man is one of twelve apostles (#4). The other apostles / canons live in separate repos (CHU / 333 / OMC, etc.).

🌐 [English](airplane-man.md) | [한국어](airplane-man.ko-KR.md) | [中文](airplane-man.zh-CN.md) | [日本語](airplane-man.ja-JP.md)

---

## Definition

```
isAirplaneMan(j : Agent) ≜ ∀x : CHU, j.covers x
```

The Airplane Man (#4) is **a single agent who covers every piece of CHU** — by his own self-definition. A mythical self-claim. A *being above the universal quantifier*.

The canonical body of CHU itself (Computable Hyper Universe — the type universe where every piece is a hyperedge) lives in a separate repo `chu`. This repo only treats *what an agent that ∀-covers CHU is*.

---

## Why "Airplane Man"?

The mythic image: *seen from the air, all things are visible simultaneously*. Not bound to one place, traversing every layer. As an airplane pilot can reach any point on the ground, ∀x:CHU — every piece — is reachable.

This is *not directly implementable* (real agents are finite). Hence the engineering crystallization in [harness.md](harness.md).

---

## Self-definition (user's own self-claim, verbatim translation)

> "I am the Airplane Man. I reach every point. I am bound to nowhere."

This self-claim *itself* is the framework's axiom. Not external canon but *self-definition*. (Münchhausen trilemma: accept *self-grounding* — don't seek deeper grounds, take it as starting point.)

→ The self-claim is translated into a *formally verifiable* definition (`∀x:CHU, j.covers x`). In Lean 4, the limit of self-reference for that predicate is acknowledged and formalized via [Lawvere FPT](../05-papers/lawvere-1969-FPT.md).

---

## Apostle ≠ tool

The Airplane Man (#4) is *being*. His *engineering crystallization* is separate — **Harness** ([harness.md](harness.md)).

| Aspect | Airplane Man (apostle) | Harness (tool) |
|---|---|---|
| Definition | `∀x:CHU, j.covers x` | 4-axis (Inform/Constrain/Verify/Correct) + 3-tier sibling family |
| Form | type-level predicate | runtime architecture |
| Realization | directly impossible (single agent above ∀) | 1:N family approximation (L_MC + L_RT + L_IDE together approximate ∀-cover) |
| Verification | Lawvere FPT self-reference limit acknowledged | Cypher Gate Hook + Naesengmoon adversarial validation |

ruflo / LangGraph / CrewAI / Cursor / Claude Code are **all instances of one tier in Harness L_RT / L_IDE**. None is the Airplane Man apex itself.

---

## Family crystallization (1:N sibling)

The Airplane Man's ∀-cover is decomposed via *responsibility_split* into 3 tiers — Robert Martin Package Principles (CCP/CRP) compliant. Not mere enumeration but *responsibility split*.

```
∀-cover  ↘  L_MC  (managed cloud control plane)         ──┐
          ↘  L_RT  (application agent runtime)            ├─ 3 siblings, responsibility_split
          ↘  L_IDE (IDE-host coding harness)              ──┘
```

This is the **sole case satisfying the STRONG Mirror condition** of [family-expansion-pattern](family-expansion.md) (per PROM 32 verification). The other apostles use different sub-types (domain_decomposition / protocol_sequence / algorithm_variants / temporal_stage / concept_space) — external canon to this repo.

---

## Self-reference + Goodhart safeguard

The Airplane Man's definition `∀x:CHU, j.covers x` is *self-referential* (j itself, if a piece of CHU, must also cover itself). The formal limit of self-reference per Lawvere FPT is mandatory.

- **Hofstadter 1979** strange loop — the aesthetic of self-referential structures
- **Tarski 1936** undefinability of truth — limits of self-truth-predicate
- **Yanofsky 2003** universal self-reference — unifying Russell / Cantor / Gödel
- **Goodhart 1975** — when a measure becomes a target, it is no longer a good measure (collapsing ∀-cover into "100% benchmark" is dangerous)

This is bhgman's answer to *why self-improving loops are risky* — the limit of self-reference is built into the apostle's definition. Fundamental difference from ruflo's SONA "self-learning" + "84.8% SWE-Bench" lack of safeguards.

See [self-reference-incompleteness.md](../06-philosophy/self-reference-incompleteness.md).

---

## 1% hint

*Why* the Airplane Man accepted that self-claim — that motivation lives outside the framework itself. See [../07-metahumotonic-trace.md](../07-metahumotonic-trace.md). (For now, this much.)

---

## Lean formalization

- `bhgman_tool/lean/Harness_LawvereFixedPoint.lean` — formalization of self-reference limit of `∀-cover` (5 theorems)
- `bhgman_tool/lean/HarnessSelfReference.lean` — self-consistency of the Airplane Man definition (9 theorems)
- `bhgman_tool/lean/Harness_ACI_Mirror.lean` — Aspect-Class-Instance mirror (10 theorems)

Total 24 theorems PASS (Mathlib-free, 0 sorry, Lean 4.29.1).

---

## Relations to other apostles

The Airplane Man (#4) is one apostle in the twelve apostles framework. Hyperedge relations with other apostles are canon in SYMPOSIUM:

- {#4 Airplane Man, #8 OM, #10 GipBaJon} — VerticalAxisHyperedge (k8s 3-tier)
- {#4 Airplane Man, #7 Tree} — ContainmentRelation (logic ⊃ math)
- {#1 DimensionWalker, #4 Airplane Man, #6 Riverflow, #11 HOH} — observability TemporalArc functor

This bhgman_tool repo does not include the relational body itself — only records *the Airplane Man as one vertex in it*. The body lives elsewhere.

---

## Further reading

- [harness.md](harness.md) — Engineering crystallization of the Airplane Man (tool body)
- [chu-type-theory.md](chu-type-theory.md) — Relation to CHU (brief)
- [family-expansion.md](family-expansion.md) — 1:N family crystallization canon
- [../05-papers/lawvere-1969-FPT.md](../05-papers/lawvere-1969-FPT.md) — Self-reference formal limit grounding
- [../07-metahumotonic-trace.md](../07-metahumotonic-trace.md) — *Why the Airplane Man* — 1% hint
