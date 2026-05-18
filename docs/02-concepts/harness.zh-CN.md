# Harness —— 飞机人的工程结晶

> 飞机人 (#4 使徒) 的 `∀x:CHU, j.covers x` 结晶为 *现实工业工具*。bhgman_tool 主要工具层。

🌐 [English](harness.md) | [한국어](harness.ko-KR.md) | [中文](harness.zh-CN.md) | [日本語](harness.ja-JP.md)

---

## 4 轴模型 (Inform / Constrain / Verify / Correct)

每个 Harness instance 内部的组织原理:

| 轴 | 作用 | 飞机人 ∀-cover 侧面 |
|---|---|---|
| **Inform** | 向 agent 提供 context / KG / skill | "信息无处不至" |
| **Constrain** | 权限 / scope / token budget / 安全 | "无束缚但不失控" |
| **Verify** | 输出验证 (Naesengmoon adversarial / test / Lean) | "是否 *正确地* 到达" |
| **Correct** | 反馈 → 下次调用调整 | "从失败中学习" |

这是各 instance *内部* 的组织。**非 family 定义** (family 另立 —— 见下)。

→ 4 轴模型是 *各 instance 内部* (一 Cursor IDE 内的 4 轴 / 一 Claude Code host 内的 4 轴 / 一 ruflo runtime 内的 4 轴)。
→ Family 定义是 *instance 之间的责任分割*。

这两者属不同层级。早先 SKILL.md drift (4 轴 = family 定义) 已于 2026-04-30 修正。

---

## 1:N sibling family (3 层)

飞机人 ∀-cover 的 *责任分割 (responsibility_split)*:

```
L_MC   managed cloud control plane
       (云端 orchestration + state + scaling)
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
          ruflo (ruvnet/claude-flow) ← 一 sibling instance, 非顶点

L_IDE  IDE-host coding harness
       (developer interactive, file-level edit + git)
       └─ Cursor / Claude Code / Aider / SWE-agent / Cline / OpenHands / GitHub Copilot
```

→ **ruflo, Cursor, Claude Code, LangGraph 等均为本 family 的 sibling instance**。其中任何一个都无法独自满足飞机人顶点 (∀-cover)。三层合起来 *近似*。

**STRONG Mirror 条件**: family *cardinality match* 成立。飞机人 3 层满足此条件 —— 见 [family-expansion.md](family-expansion.md)。

---

## MCP —— 连接全部 instance 的 adapter

将三层中所有 instance 在 *protocol layer* 上连接的是 **MCP (Model Context Protocol)** —— Anthropic 标准。

- host (L_IDE) 调用 MCP server (工具)
- L_RT framework 暴露 MCP server
- L_MC managed agent 使用 MCP 工具

→ MCP 是 *adapter*。非 instance。更接近 4 轴模型的 *Inform* 轴。

ruflo 自建 plugin marketplace (IPFS Pinata) —— 这是 *MCP 标准之上的另一锁定层*。bhgman 推荐 *仅使用标准 MCP*。

---

## Anthropic 阵营 3 元组 (示例)

在一个阵营 (Anthropic) 内部,3 层 family 自然分化:

| Tier | Anthropic 侧 | 角色 |
|---|---|---|
| L_MC | **Managed Agents** | server-side, stateful, scaling-managed |
| L_RT | **Agent SDK** | program-level loop, in-process |
| L_IDE | **Skills + Claude Code** | declarative capability + IDE host |

→ 即使同一阵营也 *自然* 分为 3 层。不将所有内容塞入单一层。这是 Robert Martin Package Principles 中 CCP (Common Closure Principle) 的自然应用。

---

## 形式验证 (Lean 4)

`bhgman_tool/lean/` 中 3 个文件, 总计 24 定理 PASS (Mathlib-free, Lean 4.29.1):

```
Harness_LawvereFixedPoint.lean   5 定理   — ∀-cover 自指极限
Harness_ACI_Mirror.lean         10 定理   — Aspect-Class-Instance 镜像
HarnessSelfReference.lean        9 定理   — Tarski/Gödel/Yanofsky 统合
```

每条定理引用外部正典 + 公开推理 chain。与 ruflo `verify` signed witness (仅代码完整性) 的本质差异。

---

## 外部正典接地

飞机人 ∀-cover 工具结晶的 17 轴外部正典:

| 轴 | 正典 |
|---|---|
| Engineering 4 | Robert Martin Package Principles (CCP/CRP/REP/ADP/SDP/SAP) / Conway 1968 / Cherns 1976 STS / DDD (Evans 2003) |
| Self-Reference Paradox 4 | Lawvere 1969 FPT / Tarski 1936 undefinability / Gödel 1931 incompleteness / Yanofsky 2003 universal self-reference |
| Industry 4 | Kubernetes 3-tier (control-plane / node / pod) / OpenTelemetry CNCF / IDE-host (Cursor/Claude Code) / managed cloud (Bedrock/Vertex) |
| Org + Reflection 4 | Sociotechnical Systems (Trist-Bamforth 1951) / MOP (Smith 1984 reflection) / Hofstadter 1979 strange loop / Holacracy (Robertson) |
| 1 附加 | meta-Harness 自指安全 (Goodhart 1975 + Münchhausen trilemma + 2026-05-05 修正 lesson) |

详见 [../04-references/citations.md](../04-references/citations.md)。

---

## 实际入口

```bash
# 安装 skill 到 Claude Code
cp -R bhgman_tool/skills/harness ~/.claude/skills/

# 使用
/harness <agent_or_framework>   # 诊断某 instance 位于 3 层中何处
```

→ Harness skill 是 *诊断工具*。分析 agent 在 4 轴中哪轴失败。详见 [../03-tutorials/harness-diagnosis.md](../03-tutorials/harness-diagnosis.md)。

---

## 进一步阅读

- [airplane-man.md](airplane-man.md) —— 本质 (使徒侧)
- [family-expansion.md](family-expansion.md) —— 1:N family Mirror 条件
- [goodhart-safeguard.md](goodhart-safeguard.md) —— self-improving loop 安全装置
- [../04-references/related-work.md](../04-references/related-work.md) —— ruflo / LangGraph / CrewAI 比较
- [../05-papers/lawvere-1969-FPT.md](../05-papers/lawvere-1969-FPT.md) —— 形式极限接地
- [../06-philosophy/existence-vs-tool.md](../06-philosophy/existence-vs-tool.md) —— 使徒(存在) ⊥ Harness(工具) 的本体论含义
