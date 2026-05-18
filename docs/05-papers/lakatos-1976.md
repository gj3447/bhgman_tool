# Lakatos 1976 — Proofs and Refutations / Methodology of Scientific Research Programmes

**References**:
- Lakatos, Imre. *Proofs and Refutations: The Logic of Mathematical Discovery*. Cambridge University Press, 1976 (posthumous, edited by Worrall & Zahar).
- Lakatos, Imre. *The Methodology of Scientific Research Programmes: Philosophical Papers Volume 1*. Cambridge University Press, 1978.

---

## Two key ideas

### From *Proofs and Refutations* (1976)

Mathematics evolves through a dialectic of **proofs and refutations**:
- A *conjecture* is proposed
- A *proof* is attempted
- A *counterexample* (refutation) is found
- The proof is *not abandoned* but **refined**: lemmas are incorporated, monsters are barred, concepts stretched
- The cycle repeats — mathematics *grows*

Lakatos identifies recurring patterns:
1. **Monster-barring**: redefining terms to exclude counterexamples (often dishonest)
2. **Exception-barring**: weakening the conjecture to avoid counterexamples
3. **Monster-adjustment**: reinterpreting the counterexample to "really" satisfy the original
4. **Lemma-incorporation**: adding hypotheses that capture *why* the counterexample fails
5. **Concept-stretching**: redefining concepts to include or exclude problematic cases

Honest math = mostly lemma-incorporation. Dishonest math = mostly monster-barring.

### From *Methodology of Scientific Research Programmes* (1978)

Scientific theories are not single propositions but **research programmes**:
- **Hard core**: a few axioms that define the programme (e.g., Newton: F = ma + universal gravitation)
- **Protective belt**: auxiliary hypotheses that can be modified
- **Positive heuristic**: rules for elaborating the programme
- **Negative heuristic**: things never to challenge in the hard core

A research programme is:
- **Progressive** if its auxiliary hypotheses *predict novel facts* (Einstein 1915 GR → light bending prediction → 1919 Eddington observation)
- **Degenerating** if its auxiliary hypotheses are *ad hoc* (added after the fact to save the theory, predicting nothing new)

The verdict is *retrospective*: you look at the auxiliary hypotheses added over time and ask, "did they add novel content?"

---

## Why it grounds bhgman

bhgman performs **explicit Lakatos audits** on itself, at scale.

### Quarterly progressive/degenerating verdict

Every quarter, the framework asks:
- What hard-core claims define bhgman? *(the apostle definitions, the 5 weapons, family-expansion-pattern, ...)*
- What auxiliary hypotheses have we added this quarter?
- Are they predicting *novel* content (new patterns, new theorems, new flow phenomena)?
- Or are they ad-hoc patches saving the framework from counterexamples?

This is recorded as a `:LakatosVerdict` KG node:
- `lakatos-verdict-3-targets-2026-05-13` evaluated ruflo/CRG/graphify
- ruflo = **DEGENERATING** (enumeration inflation + marketing claims without novel predictions)
- code-review-graph = **PROGRESSIVE** (honest limitations + token discipline + novel daemon pattern)
- graphify = **PROGRESSIVE_CONDITIONAL** (multimodal extension is novel; "Memory Layer" marketing is degenerating signature)

### Lemma incorporation in bhgman

When bhgman finds a counterexample to one of its claims, it doesn't bar monsters — it incorporates the lemma:

| Counterexample | Lemma incorporated |
|---|---|
| ruflo flat-enumerates 100+ agents and seems to work | Add `responsibility_split` sub-type to family-expansion-pattern: flat enumeration is one sub-type, but doesn't satisfy STRONG Mirror |
| graphify's confidence schema (`EXTRACTED/INFERRED/AMBIGUOUS`) wasn't in Longinus | Lemma: 7-Layer Reference needs confidence axis. Add. T1 Lean theorem now codifies this. |
| Some apostle families don't fit `responsibility_split` (e.g., #2 ICE 6-family) | Lemma: 6 sub-types exist (responsibility_split / domain_decomposition / protocol_sequence / algorithm_variants / temporal_stage / concept_space). family-sub-type-heterogeneity now canonical. |

Each lemma-incorporation is recorded as a KG `:Lesson` with symmetric pair (`wrongAssumption ↔ truth`). This is *honest mathematical evolution* in Lakatos's sense.

---

## Monster-barring detected as antipattern

bhgman explicitly *refuses* the dishonest moves:

| Move | bhgman policy |
|---|---|
| **Monster-barring** ("X doesn't count because Y") | Reject if Y is invented post-hoc. Require Y to have *independent* canonical grounding. |
| **Monster-adjustment** ("the counterexample really satisfies original") | Reject without external verifier (Naesengmoon). |
| **Concept-stretching** (silent redefinition) | Reject. All concept evolutions must be KG-tracked with explicit version + symmetric pair lesson. |
| **Ad-hoc protective belt expansion** | Lakatos verdict will flag as degenerating; framework rollback options open. |

This is *opposite* to frameworks where new features are continuously added without Lakatos accountability. ruflo's 32 plugins → 100 agents → 314 MCP tools is a textbook degenerating sequence under Lakatos: each addition is a *protective belt* widening, not a *novel prediction*.

---

## The hard core of bhgman

To run Lakatos honestly, bhgman must declare its hard core explicitly:

1. The Airplane Man (#4) is defined as `∀x:CHU, j.covers x` (type-level predicate, not runtime object).
2. Apostle (existence) ⊥ Tool (engineering crystallization) ⊥ Instance (industry implementation) — strict layer separation.
3. Self-reference is *accepted*, not eliminated (Lawvere/Tarski/Gödel limits acknowledged).
4. External canonical citation is mandatory for every quantitative claim.
5. The 5 weapons (Harness/Longinus/Prometheus/Naesengmoon/Jaebaeman) form a *closed family* (mutually grounded).

Anything else (specific theorem count, specific 17 axes, specific Lean files) is **protective belt** — can be modified as long as Lakatos verdict stays progressive.

---

## Lean grounding (this repo)

`bhgman_tool/lean/` does *not* claim to be Lakatos-final. Each theorem is a *checkpoint in the auxiliary-hypothesis layer*. Adding theorems is fine if they predict novel content (T6 `ambiguous_in_list_forces_preliminary` was added because the AMBIGUOUS contagion was a *novel prediction* during graphify absorption).

In fact, the entire history of bhgman is a sequence of Lakatos cycles:
- v0.1 hard core: 4 weapons → counterexample (Subagent Orchestration unclear) → lemma incorporation: add Jaebaeman → v0.2
- v0.2 hard core: 5 weapons → counterexample (PROM 32 family mirror cardinality mismatch) → lemma: family-sub-type-heterogeneity → v0.3
- v0.3 → ... ongoing

---

## Practical use for tool users

When you maintain a framework or codebase:

1. **Identify your hard core** — 3-5 axioms you'll never compromise.
2. **Track auxiliary hypotheses** — every other claim is in the protective belt.
3. **Lakatos verdict at intervals** — quarterly is reasonable. Ask "did my belt additions predict novel content?"
4. **If degenerating**: rollback or refactor. Don't continue adding ad-hoc patches.
5. **Honest counter-examples**: incorporate as lemmas, don't bar as monsters.

The Naesengmoon `--lens lakatos` provides automated diagnosis (4 lens variant: `lens-set-lakatos`, KG node).

---

## Misuses to avoid

1. **"Lakatos says all frameworks degenerate"** — No. Lakatos says *some* frameworks degenerate; others stay progressive for *decades* (e.g., quantum field theory, evolutionary biology). The point is: actively monitor.
2. **"Lakatos = anything goes"** — Opposite. Lakatos is *more demanding* than Popper falsifiability — it demands *novel content*, not just falsifiability.
3. **"Just refactor when degenerating"** — Sometimes. Other times the hard core itself is wrong and needs replacement. Lakatos doesn't prescribe; he diagnoses.

---

## Cross-references

- [../04-references/related-work.md](../04-references/related-work.md) — ruflo/CRG/graphify Lakatos verdicts
- [../02-concepts/goodhart-safeguard.md](../02-concepts/goodhart-safeguard.md) — Lakatos audit as Goodhart safeguard
- [../06-philosophy/airplane-man-implications.md](../06-philosophy/airplane-man-implications.md) §4
- [goodhart-1975.md](goodhart-1975.md) — Strathern's audit critique extends Lakatos

---

## Further reading

- Lakatos, *Proofs and Refutations* (Cambridge, 1976) — accessible mathematics dialogue
- Worrall, "Theory Confirmation and History" in *Lakatos's Philosophy of Mathematics* (2003)
- Larvor, *Lakatos: An Introduction* (Routledge, 1998)
- Feyerabend's *Against Method* (1975) — critical response, partial agreement with Lakatos's anti-foundationalism
