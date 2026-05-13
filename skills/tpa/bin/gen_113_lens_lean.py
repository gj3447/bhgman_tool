#!/usr/bin/env python3
"""
gen_113_lens_lean.py — generate Lean 4 type-checked registry of all 113 lenses
from the canonical taxonomy in THEORY/TALIBAN/113_LENS_TAXONOMY.md.

Output: MIND/lean_formalization/Taliban113Lens.lean

Each lens becomes:
  def Lens_LL_1 : LensSpec := ⟨"LL.1", "Propositional consistency", "Boole 1854; Frege 1879", "...">

The Lean file compiles standalone (no Mathlib needed) and provides:
- LensSpec structure (code, name, ref, rejects)
- 13 LensDomain enumerations
- 113 lens definitions
- registry : List LensSpec (canonical 113-element list)
- registry_count_113 : registry.length = 113 (PROVEN by reduction)

Future per-lens formalization replaces each LensSpec with a typed predicate.
"""

import textwrap

# ──────────────────────────────────────────────────────────────────────────────
# 113-lens canonical registry — duplicates THEORY/TALIBAN/113_LENS_TAXONOMY.md §2
# ──────────────────────────────────────────────────────────────────────────────

LENSES = [
    # LL — Logic & Foundations (9)
    ("LL", 1, "Propositional consistency", "Boole 1854; Frege 1879", "contradiction P AND NOT P derivable"),
    ("LL", 2, "First-order soundness", "Godel 1930 completeness", "semantic |= violated by syntactic |-"),
    ("LL", 3, "Model-theoretic non-triviality", "Tarski 1936", "target admits only trivial model"),
    ("LL", 4, "Proof-theoretic cut-elimination", "Gentzen 1934", "rule system fails subformula property"),
    ("LL", 5, "Modal frame correspondence", "Kripke 1963", "modality lacks intended frame condition"),
    ("LL", 6, "Intuitionistic constructivity", "Brouwer / BHK", "LEM used where constructive proof required"),
    ("LL", 7, "Linear-logic resource", "Girard 1987", "linear resource reused"),
    ("LL", 8, "Paraconsistent ex falso block", "Priest LP / Belnap 4-valued", "target trivializes under contradiction"),
    ("LL", 9, "Set-theoretic foundation choice", "ZFC/NBG/NF/HoTT", "universe levels conflated"),
    # CT — Category Theory (9)
    ("CT", 1, "Functoriality", "Mac Lane CWM I", "F(g.f) <> F(g).F(f)"),
    ("CT", 2, "Naturality square", "Mac Lane CWM I.4", "natural transformation square non-commuting"),
    ("CT", 3, "Adjunction triangle", "Mac Lane CWM IV.1", "triangle identity fails"),
    ("CT", 4, "Monad laws", "Moggi 1991; Manes 1976", "left/right unit or associativity fails"),
    ("CT", 5, "Limit/colimit universality", "Mac Lane CWM III", "no unique mediating morphism"),
    ("CT", 6, "Kan extension existence", "Kan 1958", "Lan/Ran missing where claimed"),
    ("CT", 7, "Topos subobject classifier", "Lawvere-Tierney", "no true Omega"),
    ("CT", 8, "Enriched coherence", "Kelly 1982", "associator/unitor coherence fails"),
    ("CT", 9, "inf-category higher coherence", "Lurie HTT", "n-cell lacks (n+1)-cell witness"),
    # TT — Type Theory (9)
    ("TT", 1, "STLC subject reduction", "Curry-Feys; Pierce TAPL", "typing not preserved under beta"),
    ("TT", 2, "Dependent Pi/Sigma", "Martin-Lof 1984; CIC", "Pi/Sigma rule violations"),
    ("TT", 3, "MLTT canonicity", "Martin-Lof 1984", "closed term not canonical"),
    ("TT", 4, "HoTT univalence", "Voevodsky 2010", "equivalence conflated with strict equality"),
    ("TT", 5, "Polymorphism parametricity", "Reynolds 1983; Wadler 1989", "free theorem violation"),
    ("TT", 6, "Refinement-type subset", "Liquid Haskell; F*", "refinement vacuous or unsound"),
    ("TT", 7, "Gradual-type guarantee", "Siek-Taha 2006", "dynamic gradual guarantee violated"),
    ("TT", 8, "Session-type duality", "Honda 1993", "client/server protocol non-dual"),
    ("TT", 9, "Linear/affine resource", "Wadler 1990; Rust borrow", "linear consumed twice / affine leaked"),
    # AL — Algebra (9)
    ("AL", 1, "Group axiom", "Lang Algebra", "assoc/identity/inverse violation"),
    ("AL", 2, "Ring distributivity", "Lang Algebra", "(a+b)c <> ac+bc"),
    ("AL", 3, "Field nonzero invertibility", "Lang Algebra", "nonzero non-unit"),
    ("AL", 4, "Module action coherence", "Lang Algebra", "(rs)x <> r(sx) or 1.x <> x"),
    ("AL", 5, "Universal algebra signature", "Burris-Sankappanavar", "no closure under H,S,P"),
    ("AL", 6, "Galois correspondence", "Galois 1832", "subgroup-subfield bijection fails"),
    ("AL", 7, "Lie bracket Jacobi", "Lie 1888", "antisymmetry or Jacobi fails"),
    ("AL", 8, "Hopf antipode", "Hopf 1941", "S.id <> epsilon"),
    ("AL", 9, "Galois descent / Tannakian", "Grothendieck SGA1", "descent not effective; fiber not faithful"),
    # OL — Order & Lattice (8)
    ("OL", 1, "Partial order axiom", "Birkhoff 1940", "refl/antisym/trans violation"),
    ("OL", 2, "Total order trichotomy", "Cantor", "incomparable pair where linearity claimed"),
    ("OL", 3, "Well-order minimum", "Zermelo 1904", "nonempty subset lacks least element"),
    ("OL", 4, "Chain-complete sup", "CPO; Scott 1976", "directed set lacks sup"),
    ("OL", 5, "Distributive law", "Birkhoff", "a AND (b OR c) <> (a AND b) OR (a AND c)"),
    ("OL", 6, "Modular law", "Dedekind 1900", "modular identity fails"),
    ("OL", 7, "Boolean complement uniqueness", "Stone 1936", "non-unique complement"),
    ("OL", 8, "Heyting implication adjoint", "Heyting 1930", "implication adjoint fails"),
    # TG — Topology & Geometry (8)
    ("TG", 1, "Open-set axiom", "Hausdorff 1914", "arbitrary union or finite intersection fails"),
    ("TG", 2, "Compactness (open cover)", "Heine-Borel", "open cover without finite subcover"),
    ("TG", 3, "Connectedness", "Cantor", "partitions into nonempty disjoint open subsets"),
    ("TG", 4, "Hausdorff T2", "Hausdorff 1914", "distinct points lack disjoint nbhds"),
    ("TG", 5, "Homotopy class", "Hurewicz 1935", "no continuous deformation"),
    ("TG", 6, "Homology functoriality", "Eilenberg-Steenrod", "H_n violates excision or LES"),
    ("TG", 7, "Fiber-bundle local triviality", "Steenrod 1951", "no local product structure"),
    ("TG", 8, "Sheaf gluing", "Grothendieck SGA4", "local sections fail to glue uniquely"),
    # AN — Analysis (8)
    ("AN", 1, "Limit epsilon-delta", "Cauchy 1821; Weierstrass", "epsilon-delta definition fails"),
    ("AN", 2, "Continuity preservation", "Bolzano 1817", "continuous map breaks on compact/connected"),
    ("AN", 3, "Differentiability vs continuity", "Weierstrass", "diff not continuous (impossible)"),
    ("AN", 4, "Riemann/Lebesgue integral", "Riemann 1854; Lebesgue 1902", "sign-error or measure-zero positive"),
    ("AN", 5, "Measure sigma-additivity", "Caratheodory 1914", "countable additivity fails"),
    ("AN", 6, "Probability space", "Kolmogorov 1933", "sigma-algebra closure fails or P(Omega)<>1"),
    ("AN", 7, "Ergodic invariance", "Birkhoff 1931", "nontrivial invariant set"),
    ("AN", 8, "Functional-analytic boundedness", "Banach-Steinhaus", "unbounded operator claimed bounded"),
    # CD — Combinatorics & Discrete (9)
    ("CD", 1, "Counting principle bijection", "Cantor; Stanley EC", "overcount via missed bijection"),
    ("CD", 2, "Graph degree sum 2|E|", "Euler 1736", "sum of degrees <> 2|E|"),
    ("CD", 3, "Hypergraph k-uniform", "Berge 1973", "edge of size <> k"),
    ("CD", 4, "Matroid exchange axiom", "Whitney 1935", "exchange property fails"),
    ("CD", 5, "Design balance BIBD", "Fisher 1940; Wilson 1972", "replication count fails"),
    ("CD", 6, "Ramsey monochrome", "Ramsey 1930", "coloring lacks forced monochromatic substructure"),
    ("CD", 7, "Generating function radius", "Wilf gfology", "series diverges in claimed analytic regime"),
    ("CD", 8, "Polytope Euler V-E+F", "Euler; Schlafli", "convex polytope V-E+F <> 2 (3D)"),
    ("CD", 9, "Simplicial complex closure", "Eilenberg-Steenrod", "face of simplex absent"),
    # NT — Number Theory (8)
    ("NT", 1, "Unique factorization UFD", "Euclid IX.14; Lang", "element with 2+ inequiv factorizations"),
    ("NT", 2, "Primality / Wilson", "Wilson 1770", "composite passes Wilson congruence"),
    ("NT", 3, "Modular CRT", "Sun Zi; Gauss DA", "pairwise-coprime CRT violated"),
    ("NT", 4, "Diophantine solvability", "Hilbert 10; Matiyasevich 1970", "undecidable claim with decision procedure"),
    ("NT", 5, "p-adic ultrametric", "Hensel 1897", "|x+y| > max(|x|,|y|)"),
    ("NT", 6, "Algebraic minimal poly", "Kronecker", "non-minimal annihilator"),
    ("NT", 7, "Analytic zeta functional eq", "Riemann 1859", "s-1 symmetry violated"),
    ("NT", 8, "Transcendence Lindemann-Weierstrass", "Lindemann 1882", "alg combo of e-alpha non-zero violated"),
    # CC — Computability & Complexity (9)
    ("CC", 1, "Turing-computable", "Turing 1936", "algorithm exceeds Turing machine model"),
    ("CC", 2, "Decidability boundary", "Church-Turing", "decision procedure for halting/Hilbert-10"),
    ("CC", 3, "Recursion-theoretic degree", "Post 1944", "Sigma_n conflated with Pi_n"),
    ("CC", 4, "P vs NP separation", "Cook-Levin 1971", "unconditional P=NP or P<>NP without proof"),
    ("CC", 5, "BPP / randomization", "Adleman 1978", "derandomization violates oracle separation"),
    ("CC", 6, "PSPACE / parallelism", "Savitch 1970", "PSPACE = NPSPACE violated"),
    ("CC", 7, "Oracle separation", "Baker-Gill-Solovay 1975", "relativized claim contradicting oracle world"),
    ("CC", 8, "Circuit lower bound", "Razborov-Smolensky 1987", "monotone bound violated by AC0"),
    ("CC", 9, "Communication complexity", "Yao 1979", "protocol breaks Omega(n) lower bound"),
    # FV — Formal Verification (9)
    ("FV", 1, "Hoare triple", "Hoare 1969", "{P}c{Q} pre fails to establish post"),
    ("FV", 2, "Separation logic frame", "Reynolds 2002; OHearn", "local reasoning violated by hidden aliasing"),
    ("FV", 3, "Refinement Z/B", "Abrial 1996", "concrete differs from abstract observably"),
    ("FV", 4, "LTL/CTL model checking", "Pnueli 1977; Clarke-Emerson", "property holds but counterexample trace"),
    ("FV", 5, "Abstract interpretation soundness", "Cousot-Cousot 1977", "abstract not sound abstraction"),
    ("FV", 6, "SMT theory combination", "Nelson-Oppen 1979", "combined theory unsound on shared term"),
    ("FV", 7, "Theorem-prover proof object", "Lean4/Coq/Isabelle", "tactic proof lacks kernel-checked term"),
    ("FV", 8, "BX lens law GetPut/PutGet", "Foster-Pierce 2007", "round-trip identity fails"),
    ("FV", 9, "Curry-Howard correspondence", "Curry 1934; Howard 1980", "proof term doesnt inhabit propositions type"),
    # GD — Game Theory & Decision (9)
    ("GD", 1, "Nash equilibrium existence", "Nash 1950", "no-deviation property fails"),
    ("GD", 2, "Minimax theorem", "von Neumann 1928", "mixed strategy violates value equality"),
    ("GD", 3, "Mechanism design truthfulness", "Vickrey 1961; Myerson 1981", "profitable misreport exists"),
    ("GD", 4, "Social-choice impossibility", "Arrow 1951", "rule satisfies all 4 Arrow axioms"),
    ("GD", 5, "Bayesian game posterior", "Harsanyi 1967", "type-belief inconsistent with common prior"),
    ("GD", 6, "Evolutionary stable strategy", "Maynard Smith 1973", "invadable by mutant of fitness epsilon"),
    ("GD", 7, "Auction revenue equivalence", "Myerson 1981", "reserve-price asymmetry breaks equiv"),
    ("GD", 8, "Online-learning regret", "Cesa-Bianchi-Lugosi 2006", "o(T) regret violated by adversarial sequence"),
    ("GD", 9, "Adversarial robustness GAN/RL", "Goodfellow 2014", "GAN Nash exhibits mode collapse"),
    # IC — Information & Coding (9)
    ("IC", 1, "Shannon entropy non-neg", "Shannon 1948", "H(X) < 0"),
    ("IC", 2, "Mutual-info data-processing", "Cover-Thomas", "post-processing increases I(X;Y)"),
    ("IC", 3, "Channel capacity (noisy-coding)", "Shannon 1948", "rate R > C reliably transmittable"),
    ("IC", 4, "Hamming bound", "Hamming 1950", "code (n,k,d) exceeds sphere-packing bound"),
    ("IC", 5, "Compression Kraft", "Kraft 1949", "prefix code violates sum 2^-l_i <= 1"),
    ("IC", 6, "Hash collision-resistance", "Merkle-Damgard", "efficient collision found"),
    ("IC", 7, "Signature unforgeability", "Goldwasser-Micali-Rivest 1988", "EUF-CMA broken poly-time"),
    ("IC", 8, "Zero-knowledge soundness", "Goldwasser-Micali-Rackoff 1989", "ZK leaks beyond witness or fails"),
    ("IC", 9, "MPC privacy threshold", "Yao 1982; BGW 1988", "t < n/2 honest broken by t = ceil(n/2)"),
]

assert len(LENSES) == 113, f"expected 113 lenses, got {len(LENSES)}"


def lean_escape(s: str) -> str:
    """Lean 4 string-literal escape: backslash and double-quote."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def lean_id(domain: str, n: int) -> str:
    return f"Lens_{domain}_{n}"


def emit_lean() -> str:
    out = []
    out.append(textwrap.dedent("""\
        /-
        SYMPOSIUM Taliban 113-lens registry — Lean 4 type-checked enumeration.

        Generated from THEORY/TALIBAN/113_LENS_TAXONOMY.md (canonical 2026-05-02 closure).
        Source generator: SKILLS/tpa/bin/gen_113_lens_lean.py.

        Provides:
          - LensDomain (13-case enum)
          - LensSpec structure (code/name/canonical_ref/rejects/domain)
          - 113 individual lens definitions Lens_LL_1, ..., Lens_IC_9
          - registry : List LensSpec — canonical 113-element list
          - registry_count : registry.length = 113 (PROVEN by reduction)
          - by_domain : LensDomain -> List LensSpec — domain-indexed view

        Future per-lens *predicate* formalization (where each LensSpec is upgraded
        to a typed rejection-criterion proof) is tracked as
        lesson-113lens-per-lens-formalization-2026-05-02 :FutureSprint.

        Lean 4.30.0-rc2 exit 0:
          $ lean Taliban113Lens.lean

        KG: lesson-113lens-lean-registry-2026-05-02
        -/

        namespace SymposiumTaliban

        inductive LensDomain : Type where
          | LL  -- Logic & Foundations
          | CT  -- Category Theory
          | TT  -- Type Theory
          | AL  -- Algebra
          | OL  -- Order & Lattice
          | TG  -- Topology & Geometry
          | AN  -- Analysis
          | CD  -- Combinatorics & Discrete
          | NT  -- Number Theory
          | CC  -- Computability & Complexity
          | FV  -- Formal Verification
          | GD  -- Game Theory & Decision
          | IC  -- Information & Coding
          deriving Repr, DecidableEq, Inhabited

        structure LensSpec where
          code          : String  -- e.g. "LL.1"
          name          : String
          canonical_ref : String
          rejects       : String
          domain        : LensDomain
          deriving Repr, Inhabited

    """))

    # 113 individual lens definitions
    for domain, n, name, ref, rejects in LENSES:
        ident = lean_id(domain, n)
        code = f"{domain}.{n}"
        out.append(
            f'def {ident} : LensSpec :=\n'
            f'  ⟨"{code}", "{lean_escape(name)}", "{lean_escape(ref)}", '
            f'"{lean_escape(rejects)}", LensDomain.{domain}⟩\n'
        )

    # Canonical 113-element list
    out.append("\ndef registry : List LensSpec := [\n")
    items = [f"  {lean_id(d, n)}" for (d, n, *_rest) in LENSES]
    out.append(",\n".join(items))
    out.append("\n]\n\n")

    # Cardinality theorem (decidable by reduction)
    out.append(textwrap.dedent("""\
        theorem registry_count : registry.length = 113 := by decide

        -- Domain-indexed view
        def by_domain (d : LensDomain) : List LensSpec :=
          registry.filter (fun l => l.domain = d)

        -- Per-domain cardinality (matches taxonomy spec §1)
        theorem ll_count : (by_domain LensDomain.LL).length = 9 := by decide
        theorem ct_count : (by_domain LensDomain.CT).length = 9 := by decide
        theorem tt_count : (by_domain LensDomain.TT).length = 9 := by decide
        theorem al_count : (by_domain LensDomain.AL).length = 9 := by decide
        theorem ol_count : (by_domain LensDomain.OL).length = 8 := by decide
        theorem tg_count : (by_domain LensDomain.TG).length = 8 := by decide
        theorem an_count : (by_domain LensDomain.AN).length = 8 := by decide
        theorem cd_count : (by_domain LensDomain.CD).length = 9 := by decide
        theorem nt_count : (by_domain LensDomain.NT).length = 8 := by decide
        theorem cc_count : (by_domain LensDomain.CC).length = 9 := by decide
        theorem fv_count : (by_domain LensDomain.FV).length = 9 := by decide
        theorem gd_count : (by_domain LensDomain.GD).length = 9 := by decide
        theorem ic_count : (by_domain LensDomain.IC).length = 9 := by decide

        end SymposiumTaliban
    """))

    return "".join(out)


if __name__ == "__main__":
    import sys
    output_path = sys.argv[1] if len(sys.argv) > 1 else "Taliban113Lens.lean"
    with open(output_path, "w") as f:
        f.write(emit_lean())
    print(f"wrote {output_path} ({len(LENSES)} lenses)")
