# Evans 2003 — Domain-Driven Design

**Reference**: Evans, Eric. *Domain-Driven Design: Tackling Complexity in the Heart of Software*. Addison-Wesley, 2003.

---

## Core concepts

DDD organizes complex software around the *domain* (the business or problem space), not around technical concerns. Key building blocks:

### Ubiquitous Language
A *single* vocabulary shared by developers, domain experts, and the code itself. Names in code match names in conversation match names in models. Translation friction is eliminated.

### Bounded Context
A logical boundary within which a model has a *consistent* meaning. The same word ("Customer", "Order") may have *different* models in different bounded contexts — that's fine, as long as the boundary is explicit.

### Strategic patterns (chapter-level)
- **Bounded Context** — already described
- **Context Map** — explicit relationships between contexts (Shared Kernel / Customer-Supplier / Conformist / Anti-Corruption Layer / Open-Host Service / Published Language / Separate Ways / Big Ball of Mud)
- **Core Domain** — the part where the business actually differentiates; receives the most modeling investment

### Tactical patterns (within-context)
- **Entity** — identified by ID, mutable state
- **Value Object** — identified by attributes, immutable
- **Aggregate** — cluster of entities + value objects with one root (the only externally-referenced entity), enforces invariants
- **Service** — stateless operation on the domain
- **Repository** — abstraction over persistence for an aggregate
- **Factory** — encapsulates aggregate construction
- **Domain Event** — first-class notion of something happening in the domain

---

## Why it grounds bhgman

### Harness L_RT tier ≈ DDD Bounded Context

Each Harness L_RT instance (Google ADK / LangGraph / CrewAI / AutoGen / ruflo) is a *bounded context*:
- Its own "agent" model
- Its own "tool" model
- Its own "memory" model

These models *do not directly map* across instances. ADK's `Agent` ≠ LangGraph's stateful node ≠ CrewAI's role-based crew member. Each is internally consistent; cross-context translation requires an **Anti-Corruption Layer** (MCP serves as one).

### bhgman's Ubiquitous Language

The 12 apostles + 5 weapons + APT/TPA cycles form bhgman's ubiquitous language:
- Code uses `# KG: lesson-foo` (KG = knowledge graph, lesson-foo = specific lesson)
- Documentation uses the same names
- Conversations between users use the same names
- KG nodes use the same names

When a new contributor joins, they don't translate "agent runtime" / "agent execution context" / "agent host environment" — there's *one* word: Harness L_RT tier. Translation friction → zero.

### Aggregate roots for KG nodes

Each major KG node type acts as a DDD aggregate root:
- `:Span` — aggregate of C(S) 5-predicates + decision areas
- `:Contract` — aggregate of typed schemas + error variants + access rights
- `:Lesson` — aggregate of symmetric pair (wrongAssumption ↔ truth) + corrective action
- `:LakatosVerdict` — aggregate of progressive/degenerating evaluation
- `:ReferenceSite` — aggregate of (Sinn, Bedeutung, confidence)

External code may *only* reference the root. Internal structure stays inside the aggregate.

### Domain events in APT cycle

Each phase transition in APT is a **domain event**:
- `SaCompletedEvent` (after Phase 1 Gate passes)
- `CrystallizationFrontierReached` (after SP)
- `ContractEstablished` (after ST)
- `TddCycleCompleted` (after SCW for each Span)
- `MetaReviewClosed` (after Phase 5)
- `CleanupGatePassed` (after Phase 6)

These events are first-class in the KG, enabling event-sourcing-style reconstruction of any phase.

---

## bhgman's anti-corruption layer

When bhgman integrates with external frameworks (ruflo, LangGraph, etc.), it does *not* adopt their models directly. The integration uses an anti-corruption layer:

```
External model (ruflo "agent")
       ↓ ACL: translates to bhgman concept
bhgman model (Harness L_RT instance + role + responsibility)
       ↓ used internally
APT cycle / Longinus / Naesengmoon etc.
```

The ACL prevents *concept pollution* — bhgman's clean separation (apostle / tool / instance) survives integration with frameworks that don't make this separation.

This is why bhgman *can* absorb specific patterns (graphify's confidence schema, CRG's daemon pattern) without absorbing their *frame* (graphify's marketing claims, CRG's monorepo conventions).

---

## Core domain identification

In DDD, the *core domain* receives the most modeling effort. For bhgman, the core domain is:

> *The relationship between apostle definitions (existence) and engineering crystallizations (tools).*

This is where bhgman invests:
- Longinus 7-Layer Reference Model (binding apostle-level intent to code)
- APT/TPA cycles (the dialectic of design ↔ code)
- Naesengmoon LensSet (preserving apostle-level invariants across implementations)
- Lean formalization (proving the binding is sound)

Other parts (skill installation logistics, plugin metadata, etc.) are **supporting subdomains** or **generic subdomains** — solved-once, reuse-elsewhere.

---

## Conformist vs Customer-Supplier vs ACL

bhgman's relationships with external systems:

| External system | Relationship type |
|---|---|
| Claude Code (host) | **Customer-Supplier** — bhgman is customer, Claude Code is supplier. bhgman adapts to Claude Code's plugin API. |
| MCP (protocol) | **Conformist** — bhgman conforms to MCP spec without negotiation. (No negotiating power.) |
| ruflo / LangGraph | **Anti-Corruption Layer** — bhgman absorbs specific patterns through ACL; does not conform to their full models. |
| Neo4j (KG store) | **Customer-Supplier** — bhgman customer; uses Cypher as Neo4j's published language. |
| Lean (formal verification) | **Customer-Supplier** — bhgman customer; conforms to Lean 4 syntax. |

These relationships are *explicit* (not implicit). DDD's contribution: name your relationships; otherwise they degenerate to "Big Ball of Mud."

---

## Misuses to avoid

1. **"DDD = OOP"** — No. DDD predates OOP frameworks and applies to any paradigm (functional, actor-based, etc.). The patterns are conceptual, not language-tied.
2. **"DDD = microservices"** — No. Bounded Contexts ≠ microservices. Often one Bounded Context = one module within a monolith.
3. **"Just use entities everywhere"** — Entities are *one* tactical pattern. Value objects (immutable, attribute-identified) are often more appropriate. Many DDD implementations are entity-heavy because that's what ORMs encourage; this is a problem, not a feature.

---

## Cross-references

- [../02-concepts/harness.md](../02-concepts/harness.md) §3-tier sibling family (L_RT instances as bounded contexts)
- [cherns-1976-sts.md](cherns-1976-sts.md) — Boundary Location aligns with Bounded Context
- [../02-concepts/apt-tpa-cycles.md](../02-concepts/apt-tpa-cycles.md) — APT phases as domain events
- [foster-pierce-walker-2007-bx-lens.md](foster-pierce-walker-2007-bx-lens.md) — BX Lens as cross-context translation

---

## Further reading

- Evans, *Domain-Driven Design Reference* (2015, free PDF) — concise patterns reference
- Vernon, *Implementing Domain-Driven Design* (Addison-Wesley, 2013) — modern practical guide
- Fowler, "Bounded Context" article series — accessible introduction
- Khononov, *Learning Domain-Driven Design* (O'Reilly, 2021) — recent treatment
