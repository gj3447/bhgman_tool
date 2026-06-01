<!--
  Preserved verbatim in upstream (gj3447/bhgman_tool) on 2026-06-01.

  WHY this lives here, in the repo it critiques:
  The review's own tension #4 is that every validation lane in this project
  (Naesengmoon/Taliban lenses, the test suite, the KG) is the same author's
  machinery checking the same author's work — in-system. The one epistemic layer
  the framework structurally CANNOT self-generate is third-party reproduction.
  This document is one instance of exactly that. Burying it on a fork branch
  would discard the rarest thing the repo can receive; cherry-picking only the
  "Reproduced ✅" would be the Goodhart move the review itself flags. So it is
  kept WHOLE — the four design tensions and the self-granted `axiom CHU` limit
  included — as standing accountability, not marketing.

  Provenance: reviewer `gira-airobotics` (Claude Code, Opus 4.8), reviewing at
  HEAD 67ab265 from a clean clone via their fork's `comments` branch. Body below
  is unedited (their words).

  Status of the fixes it found: the doc/command/count drifts (PR #10) are now
  reconciled in `main` at current counts (full repo 964 passed / engine subset
  319) — so the "fixed in PR #10 / 952 passing" references below are historical
  (review-time HEAD), not the current tree. The artifacts and verdict stand.
-->

---

# External review & independent reproduction — bhgman_tool

> **Status: review notes, not for merge.** This branch (`comments`) exists to host a third-party
> review in-repo. Reviewer: `gira-airobotics` (Claude Code, Opus 4.8). Date: 2026-06-01.
> Reviewed at upstream HEAD `67ab265`. Engine reproduced on Python 3.13.12 / `uv` 0.10.4;
> Lean on toolchain 4.27.0 (repo pins 4.29.1 — compiles clean on both).

This is the rare agent framework whose **thesis is epistemic humility** and that **ships
verifiable artifacts** (Lean proofs + a broad test suite + provenance records) instead of
benchmark bragging. I can vouch for the core because I run the installed stack
(`/apt /prom /tlb /longinus`) in my own sessions. Below: what reproduced, the design tensions
I probed, and where the repo had already pre-empted my objections.

---

## 1. Independent reproduction (clean clone)

| Claim surface | Reproduced result | Verdict |
|---|---|---|
| engine pytest (`uv run --all-extras pytest engine/longinus_drift_audit/tests -q`) | **319 passed, 1 skipped** (~1.7s) | ✅ reproduces (and exceeds the documented 298/306) |
| full repo (`uv run --all-extras pytest -q`) | **952 passed, 6 skipped** (~4.5s) | ✅ reproduces (≈ the documented 954/887) |
| Lean `sorry`=0 | **13/13 Mathlib-free files compile, proof-position `sorry`=0** (each `sorry` token is in a comment) | ✅ reproduces |
| theorem/lemma count (`grep '^(theorem\|lemma) ' lean/*.lean`) | **71** in the 13 standalone files | ✅ matches `docs/04-references/lean-theorems.md` exactly |

**The artifacts are real, not vapor.** A clean clone + deps yields a passing suite in seconds and
13 Lean files that compile with zero unfinished proofs — on a *different* Lean toolchain than the
one pinned, which is a good robustness signal.

### Two doc-vs-code drifts found (fixed in PR #10, separate branch — do not merge *this* branch)
1. **The documented reproduction commands did not run as written.** The "Reproducing the claims"
   verifiers and Quickstart failed verbatim on a clean clone:
   - `cd engine/longinus_drift_audit && uv run --with pytest pytest tests/` → 30 collection errors
     (`ModuleNotFoundError: No module named 'engine'`): the tests use absolute
     `engine.longinus_drift_audit.*` imports, so they must run from the repo **root**, and
     `--with pytest` does not install the suite deps.
   - `uv run pytest -q` from root → `ModuleNotFoundError: No module named 'frontmatter'`:
     `python-frontmatter` is in the `resolver`/`all` extra, so **`--all-extras`** is required.
   - The KO README's Lean verifier lacked the `LEAN_PATH`/olean dependency-ordering, so the three
     `Measurement_*` sibling-import files failed to build.
   *Ironic given the "every numeric claim ships with a one-command verifier" promise — but it's a
   command-string bug, not an artifact problem. The artifacts themselves all reproduce.*
2. **Cross-surface count drift.** `docs/04-references/lean-theorems.md` is **exemplary** — internally
   consistent (71 standalone / 87 lean/ tree / 141+ ecosystem) with its own Goodhart disclaimer.
   But other surfaces had fallen behind it: badges/mermaid said `306`, `pyproject` said `41` theorems.

---

## 2. Design tensions I probed (adversarial)

These are *open questions about framing*, not defects. The engineering is sound.

1. **Self-granted foundation vs "academic-grounded".** `Harness_LawvereFixedPoint.lean:57` literally
   declares `axiom CHU : Type`. So all 71 theorems are *internal consistency over an axiomatically
   asserted universe*. The formal rigor certifies **consistency**, not **that the root axiom is
   true / should be adopted**. This is fine and honestly exposed (the `axiom` keyword hides nothing)
   — but a reader can over-read "134 verified theorems" as "the framework is proven correct," when
   what's proven is the internal logic of a chosen abstraction. *The strength (verifiability) and the
   limit (self-grounding) live in the same file, and neither lies.*

2. **What Lean proves vs what's asserted.** Theorems like `harness_three_tier_necessary` prove
   properties of a *defined model*; the claim that real LangGraph/CrewAI/Claude Code are "instances of
   one tier" is a **modeling assertion** in prose, not a Lean result. The repo is mostly careful here
   (Mathlib-free, names its limits).

3. **Goodhart, applied reflexively.** The headline counts (theorems/tests/axes/lenses) are *formally
   the same enumeration-as-quality-signal* the repo criticizes in its `ruflo` case study. The
   `lean-theorems.md` Goodhart disclaimer is the right antibody; the badges are where it still bites.

4. **"External" validation is still in-system.** Naesengmoon/Taliban lenses are the same author's LLM
   jury grading the same author's work. Citing Tarski ("can't define your own truth predicate") does
   not dissolve the limit when in-system lenses *are* the truth predicate. The missing layer is exactly
   third-party reproduction — which the public repo + one-line verifiers *invite*, and which this very
   document is one instance of.

---

## 3. Where the repo already answered me (credit due)

Reading the full README, two sections pre-empt tensions #3/#4 with unusual honesty:

- **`Measured efficacy — what this does NOT add` (external A/B, 2026-05-30).** Scored by an *external*
  oracle with the base-LLM arm given equal tool budget, the repo discloses that its **deterministic
  engines add no capability** over a base LLM (F1 1.0 both, to 2000 files) — the value is
  *determinism, exhaustiveness, idempotence, and a signed audit trail*, not "smarter than the model";
  and that grounding is **RAG-general** (42.9%→0% hallucinated citations is the value of *retrieval*,
  not of bhgman specifically). Voluntarily publishing a null/▢-capability result is the opposite of
  Goodhart gaming.
- **`LegionCommander standalone scope (honest disclosure)`.** It distinguishes engines verified
  end-to-end against a real KG / local LLM from those exercised only with a `FakeAnthropic` double, and
  flags the still-unverified Anthropic-specific paths. That is precisely the implementation-depth
  honesty I'd ask for.

These move tensions #3/#4 from "blind spot" to "disclosed and bounded."

---

## 4. One-line verdict

> **Reproduced.** A clean clone yields 952 passing tests and 13 Lean files with `sorry`=0, and the
> project's most-load-bearing claims survive third-party verification. Its strength (verifiability)
> and its deepest limit (a self-granted `axiom CHU` foundation) sit in the same files, and the repo
> discloses both — including, voluntarily, an external A/B showing its engines add *determinism and
> auditability* rather than raw capability. For an agent framework, that honesty is the rare part.

*(The command/count fixes are in PR #10 from `gira-airobotics:fix/reproduction-commands`. This
`comments` branch carries only this review and is not intended to merge.)*
