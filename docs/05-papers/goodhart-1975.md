# Goodhart 1975 + Strathern 1997 — Goodhart's Law

**Primary reference**: Goodhart, Charles A. E. "Problems of Monetary Management: The U.K. Experience." Papers in Monetary Economics, Reserve Bank of Australia, 1975.

**Popular formulation**: Strathern, Marilyn. "'Improving Ratings': Audit in the British University System." *European Review* 5(3): 305–321, 1997.

> "When a measure becomes a target, it ceases to be a good measure."
> — Strathern's distillation of Goodhart's original observation

---

## Statement (original Goodhart 1975)

> "Any observed statistical regularity will tend to collapse once pressure is placed upon it for control purposes."

The original context was monetary policy: when the Bank of England targeted a specific monetary aggregate (M3, M0, etc.), agents adjusted their behaviour to game the measurement, and the *previously stable* relation between the aggregate and the underlying economic state broke down.

---

## What it says, in plain words

Measurement is *informative* only when it is *not the target of optimization*. The moment a measure becomes what you are *trying to maximize*, the optimization pressure distorts the very thing the measure was tracking.

Examples:
- **University rankings** (Strathern): once universities optimize for league-table position, the rankings stop indicating educational quality.
- **AI benchmarks** (modern): once a model is fine-tuned to beat SWE-Bench / HumanEval, the benchmark stops indicating real-world coding ability.
- **OKRs / KPIs**: once teams game the metric, the metric stops indicating actual progress.

---

## Why it grounds bhgman

bhgman's *primary safety condition* against degenerating frameworks is Goodhart resistance.

The Airplane Man framework explicitly:
1. **Refuses self-improvement loops that optimize a single metric** — see [../02-concepts/goodhart-safeguard.md](../02-concepts/goodhart-safeguard.md)
2. **Requires external canonical citation** for every quantitative claim — not "X% better" but "X is better according to [external standard]"
3. **Treats benchmarks as diagnostics, not goals** — pass/fail, not score-to-maximize

This is the *opposite* of frameworks like ruflo that prominently feature numbers like "84.8% SWE-Bench" as marketing — Goodhart predicts that *exactly that* number will diverge from real coding ability under optimization pressure.

---

## The bhgman test (operationalized)

For any framework claim, ask:
1. Is there a single number that is *being optimized*?
2. Is that number being *promoted as evidence of quality*?
3. Is there a *self-improvement loop* that adjusts the system to maximize the number?

If yes to all three → **Goodhart antipattern** active. KG: `errorpattern-goodhart-metric-optimization-marketing-2026-05-13`.

bhgman's own metrics (89 Lean theorems, 1149 pytest PASS, 17 axes) are *diagnostics*, not targets:
- A theorem is *valid or invalid*. There's no "more valid" version to optimize.
- A test passes or fails. There's no "more passing" version to optimize.
- An axis is a *cited canonical work*. There's no number-of-citations-to-maximize.

By making each metric *non-optimizable* (binary or externally-rooted), Goodhart pressure is structurally blocked.

---

## Münchhausen + Goodhart together

A subtle point (cf. [../06-philosophy/airplane-man-implications.md](../06-philosophy/airplane-man-implications.md) §2 + §4):

- Münchhausen says: every justification must eventually stop somewhere.
- Goodhart says: but it must *not* stop at "this metric is our justification."

bhgman's chosen Münchhausen stopping point is the *Airplane Man's self-claim* — accepted as axiomatic, *not* as a measurable performance.

If we instead stopped at "84.8% SWE-Bench is our justification," we'd commit a *combined* Münchhausen + Goodhart violation: dogmatic stop at a measurable, which then becomes the optimization target.

---

## Strathern's audit critique

Strathern's 1997 paper extends Goodhart from finance to *audit culture*:

> "The pursuit of audit confounded the prior values of trust, learning, and judgment with the new value of having a verifiable record."

Translation: when a system is *audited*, the auditable surface (paperwork, metrics, traces) becomes the *real activity*, displacing the original purpose.

bhgman's safeguard:
- *Audit the auditor* (Naesengmoon LensSet on Naesengmoon itself)
- Quarterly Lakatos progressive/degenerating verdict on the framework
- KG records *symmetric pairs* (`wrongAssumption ↔ truth`) — both success and failure modes, preventing audit-driven success-bias

---

## Misuses to avoid

1. **"All metrics are bad"** — No. Metrics are *informative*; they become *bad* under optimization pressure with no Goodhart awareness.
2. **"Goodhart only applies to monetary economics"** — Original context yes, but the structural insight generalizes (Strathern 1997 + decades of social-science replication).
3. **"My SONA / RL loop is fine because it learns"** — Especially dangerous. *Learning* + *single metric* + *no Goodhart awareness* = textbook degeneration.

---

## Cross-references

- [../02-concepts/goodhart-safeguard.md](../02-concepts/goodhart-safeguard.md) — Practical safeguard mechanism
- [../06-philosophy/epistemic-humility.md](../06-philosophy/epistemic-humility.md) — Why metrics need humility
- [../06-philosophy/airplane-man-implications.md](../06-philosophy/airplane-man-implications.md) §4 — Self-reference + Goodhart combined
- [../04-references/related-work.md](../04-references/related-work.md) — ruflo as case study

---

## Further reading

- Goodhart, "Goodhart's Law: Its Origins, Meaning and Implications for Monetary Policy" (1984) — author's later reflection
- Manheim & Garrabrant, "Categorizing Variants of Goodhart's Law" (2018, arXiv:1803.04585) — ML-specific taxonomy
- Krakovna et al., "Specification Gaming Examples in AI" (DeepMind, 2020) — recent AI-system examples
