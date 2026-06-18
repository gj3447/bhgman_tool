# tpa — Theory

> **Lazy-load reference for `tpa` skill.**
> Loaded *only when* the orchestrator enters the relevant phase/gate.
> Parent skill: [`../SKILL.md`](../SKILL.md). Sibling reference (mirror direction): [`../../apt/references/theory.md`](../../apt/references/theory.md).
> Refactor source: APT v24 hardening parity (2026-05-06).
> KG: `tpa-hardening-master-plan-2026-05-06`, `lesson-tpa-hardening-bootstrap-2026-05-06`.

---

## 1. APT Mirror Diagram

TPA is APT run in reverse. Code is the *given*; Design is the *recovered*.

| APT (forward, design → code) | TPA (reverse, code → design) | Inversion property |
|------------------------------|------------------------------|--------------------|
| SA: SemanticAnchor (identity bootstrap) | TA: TargetAnchor (final anchor + drift audit) | TPA's *terminal*, APT's *initial* |
| SP: SemanticPyramid (recursive decomposition) | SP: TargetPyramid (pattern matching, Library-as-corpus) | Same role, opposite direction (compose ↔ recognize) |
| ST: SemanticTwin (contract crystallization) | ST: TargetSemanticTwin (contract *extraction* from pub symbols) | Same artifact, opposite source (intent ↔ implementation) |
| SCW: SourceCodeWorld (TDD GREEN/REFACTOR) | TCW: TargetCodeWorld (raw symbol harvest from existing code) | TPA's *entry*, APT's *exit* |

**Phase order**: TCW → ST → SP → TA. Each gate enforced by `apt-gate-check.sh` v0.8-per-span (default 2026-05-06).

---

## 2. Design Recovery Theory

| Domain | TPA Element |
|--------|-------------|
| Reverse engineering (Chikofsky-Cross 1990) | TCW (artifact extraction) → ST (abstraction recovery) |
| Abstract interpretation (Cousot 1977) | ST contract extraction with `confidence` lattice |
| Pattern recognition (Gamma et al. GoF) | SP DesignPattern Library (51 nodes) + INSTANCE_OF/RESEMBLES distinction |
| Concept analysis (Ganter-Wille FCA) | ConventionalContract (≥3 implementors share signature shape) |
| Refinement type theory | AptContract (explicit interface) vs ConventionalContract (implicit shape) — Liquid-types-style precision split |
| Trace abstraction | call graph + AST in SP/Behavioral patterns |
| Semantic version drift | TA 5-Drift kinds (Missing / Orphan / SigMismatch / PatternDiv / LabelRot) |

---

## 3. Why "TargetXxx" Naming

Every recovered artifact carries a `Target*` prefix to mark **non-authorial** provenance. The original author did not approve these names. Any drift between recovered name and authorial intent is irreducible (TR15: "Essential ✗").

This is not a defect — it is a **theorem of reverse engineering**: any recovery process loses information unless lossless source is available. TPA's `confidence` field quantifies this loss.

---

## 4. INSTANCE_OF vs RESEMBLES — Lattice Order

```
1.0 ─── (definitional: rule-based, e.g. trait declared in code)
        ↓
0.9 ─── (high confidence: every required element from checklist matched + evidence cited)
        ↓                ──── INSTANCE_OF threshold (≥ 0.7)
0.7 ─── (canonical match: most required elements, weak evidence)
        ↓
0.5 ─── (resembles: name match + 1-2 elements)
        ↓
0.3 ─── (cosmetic: name only, no structural evidence)
```

Threshold (0.7) lives in `MethodologyConfig.tpa_pattern_confidence_instance_of` slot, not prose.

---

## 5. Adversarial Mirror

APT's adversarial round attacks **proposed** design.
TPA's adversarial round attacks **recovered** design.

Both use the same Naesengmoon GAN-D mechanism (constitutional 9-lens default, mathematical 113-lens for distributed-pattern verification). Difference:

| | APT Critic targets | TPA Critic targets |
|---|---|---|
| Density | Was the source set diverse enough? | Is the symbol manifest complete? |
| Falsifiability | Will the spec break if violated? | Is the recovered contract a stable shape across implementors? |
| Ground truth | cargo test PASS | parser output matches LOC count from `wc -l`; manifest = union(agent_files) |

---

## 6. Feedback Loop (Lesson System)

TPA's purpose is not to recover one project's design — it is to extract **lessons** to apply to *our* projects. The `:Lesson` node lifecycle:

```
TPA discovery (Similarity / QualityGap / NovelPattern / AntiPattern)
      ↓
:Lesson (problem + truth + solution + resolved=false)
      ↓
:ActionPlan (improvements[]) ← TRIGGERS
      ↓
APT /apt-scw materialization (real code change in our project)
      ↓
Naesengmoon gate (independent verification)
      ↓
:Lesson { resolved = true, resolved_at, evidence }
```

This loop is what distinguishes TPA from a code-walker. **A scan that produces no Lesson is a wasted TPA cycle.**

---

## 7. Hard Rules ↔ APT Mirror

| TPA | APT mirror | Theme |
|-----|-----------|-------|
| TR1 (every gate Naesengmoon) | HR1 | Adversarial mandatory |
| TR2 (evidence required) | HR11 | Anti-rubber-stamp |
| TR3 (phase order) | HR7 | Gate transition logged |
| TR11 (executor ≠ reviewer) | HR15 = D20 | Self-approval ban |
| TR15 (Essential ✗) | C40-C44 | Acknowledged limit, not bug |

---

## 8. Version History

| Ver | Key Change |
|-----|-----------|
| v0.3 | Initial 4-phase recovery |
| v0.4 | MetaVerifier integration for distributed patterns (88-Naesengmoon) |
| **v1.0** | **HR1-HR15 (TR series), Lesson feedback loop, MIC slot resolution, gate hook integration** |
| **v1.1** | **Phase prefix unification (tt → st, tp → sp). Reference doc parity with APT (9 files). TpaHardeningPlan equivalent (2026-05-06).** |

---
