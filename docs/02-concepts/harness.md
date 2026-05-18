# Harness — Engineering crystallization of the Airplane Man

> The Airplane Man (#4)'s `∀x:CHU, j.covers x` made into a *real industrial tool*. The main tool layer of bhgman_tool.

🌐 [English](harness.md) | [한국어](harness.ko-KR.md) | [中文](harness.zh-CN.md) | [日本語](harness.ja-JP.md)

---

## 4-axis model (Inform / Constrain / Verify / Correct)

The internal organizing principle of each Harness instance:

| Axis | Role | Airplane Man ∀-cover aspect |
|---|---|---|
| **Inform** | provide context / KG / skills to the agent | "reach information anywhere" |
| **Constrain** | permissions / scope / token budget / safety | "untethered yet not runaway" |
| **Verify** | output verification (Naesengmoon adversarial / tests / Lean) | "did we *correctly* reach?" |
| **Correct** | feedback → next-call adjustment | "learn from failure" |

This is the *internal* organization of each instance. **Not the family definition** (family is separate — below).

→ The 4-axis model is *inside each instance* (4 axes inside one Cursor IDE / 4 axes inside one Claude Code host / 4 axes inside one ruflo runtime).
→ The family definition is *the responsibility split between instances*.

These are different layers. The earlier SKILL.md drift (4-axis = family definition) was corrected 2026-04-30.

---

## 1:N sibling family (3-tier)

The *responsibility split* of the Airplane Man's ∀-cover:

```
L_MC   managed cloud control plane
       (cloud-side orchestration + state + scaling)
       └─ Anthropic Managed Agents (Claude Sonnet 4.6 / Opus 4.7 server-side agents)
          Vertex AI Agent Engine (Google managed)
          OpenAI Assistants API
          Bedrock Agents (AWS)

L_RT   application agent runtime
       (program-level multi-agent orchestration, in-process)
       └─ Google ADK (Agent Development Kit)
          LangGraph (LangChain stateful graphs)
          CrewAI (role-based)
          AutoGen (Microsoft conversational)
          ruflo (ruvnet/claude-flow) ← one sibling instance, not the apex

L_IDE  IDE-host coding harness
       (developer interactive, file-level edit + git)
       └─ Cursor / Claude Code / Aider / SWE-agent / Cline / OpenHands / GitHub Copilot
```

→ **ruflo, Cursor, Claude Code, LangGraph, etc. are all sibling instances of this family**. None of them alone satisfies the Airplane Man's apex (∀-cover). The 3 tiers together *approximate* it.

**STRONG Mirror condition**: family with *cardinality match*. The Airplane Man's 3-tier satisfies this — see [family-expansion.md](family-expansion.md).

---

## MCP — the adapter connecting all instances

What connects all instances in the three tiers at the *protocol layer* is **MCP (Model Context Protocol)** — Anthropic standard.

- The host (L_IDE) calls MCP servers (tools)
- L_RT frameworks expose MCP servers
- L_MC managed agents use MCP-side tools

→ MCP is an *adapter*. Not an instance. Closer to the *Inform* axis of the 4-axis model.

ruflo created its own plugin marketplace (IPFS Pinata) — that's *another lock-in layer on top of the MCP standard*. bhgman recommends *standard MCP only*.

---

## Anthropic three-tuple (example)

Within one camp (Anthropic), the 3-tier family also divides:

| Tier | Anthropic side | Role |
|---|---|---|
| L_MC | **Managed Agents** | server-side, stateful, scaling-managed |
| L_RT | **Agent SDK** | program-level loop, in-process |
| L_IDE | **Skills + Claude Code** | declarative capability + IDE host |

→ Even one camp *naturally* splits into 3-tier. Not stuffing everything into a single layer. This is a natural application of Robert Martin Package Principles' CCP (Common Closure Principle).

---

## Formal verification (Lean 4)

3 files in `bhgman_tool/lean/`, total 24 theorems PASS (Mathlib-free, Lean 4.29.1):

```
Harness_LawvereFixedPoint.lean   5 theorems  — ∀-cover self-reference limit
Harness_ACI_Mirror.lean         10 theorems  — Aspect-Class-Instance mirror
HarnessSelfReference.lean        9 theorems  — Tarski/Gödel/Yanofsky unified
```

Each theorem cites external canon + makes the inference chain public. Fundamental difference from ruflo's `verify` signed witness (code integrity only).

---

## External canonical grounding

17 axes external canon for the tool crystallization of the Airplane Man's ∀-cover:

| Axis | Canon |
|---|---|
| Engineering 4 | Robert Martin Package Principles (CCP/CRP/REP/ADP/SDP/SAP) / Conway 1968 / Cherns 1976 STS / DDD (Evans 2003) |
| Self-Reference Paradox 4 | Lawvere 1969 FPT / Tarski 1936 undefinability / Gödel 1931 incompleteness / Yanofsky 2003 universal self-reference |
| Industry 4 | Kubernetes 3-tier (control-plane / node / pod) / OpenTelemetry CNCF / IDE-host (Cursor/Claude Code) / managed cloud (Bedrock/Vertex) |
| Org + Reflection 4 | Sociotechnical Systems (Trist-Bamforth 1951) / MOP (Smith 1984 reflection) / Hofstadter 1979 strange loop / Holacracy (Robertson) |
| 1 additional | meta-Harness self-reference safety (Goodhart 1975 + Münchhausen trilemma + 2026-05-05 correction lesson) |

See [../04-references/citations.md](../04-references/citations.md).

---

## Practical entry

```bash
# Install skill into Claude Code
cp -R bhgman_tool/skills/harness ~/.claude/skills/

# Usage
/harness <agent_or_framework>   # diagnose where an instance sits in the 3 tiers
```

→ The Harness skill is a *diagnostic tool*. It analyzes where an agent fails among the 4 axes. See [../03-tutorials/harness-diagnosis.md](../03-tutorials/harness-diagnosis.md).

---

## Further reading

- [airplane-man.md](airplane-man.md) — Essence (apostle side)
- [family-expansion.md](family-expansion.md) — 1:N family Mirror condition
- [goodhart-safeguard.md](goodhart-safeguard.md) — Self-improving loop safeguards
- [../04-references/related-work.md](../04-references/related-work.md) — Comparison with ruflo / LangGraph / CrewAI
- [../05-papers/lawvere-1969-FPT.md](../05-papers/lawvere-1969-FPT.md) — Formal limit grounding
- [../06-philosophy/existence-vs-tool.md](../06-philosophy/existence-vs-tool.md) — Ontological meaning of apostle(existence) ⊥ Harness(tool)
