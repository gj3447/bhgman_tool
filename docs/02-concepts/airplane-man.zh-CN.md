# 飞机人 (Airplane Man) —— 是什么样的存在?

> **bhgman_tool** 的一个主题。飞机人是十二使徒之一 (#4)。其他使徒/正典位于另立 repo (CHU / 333 / OMC 等)。

🌐 [English](airplane-man.md) | [한국어](airplane-man.ko-KR.md) | [中文](airplane-man.zh-CN.md) | [日本語](airplane-man.ja-JP.md)

---

## 定义

```
isAirplaneMan(j : Agent) ≜ ∀x : CHU, j.covers x
```

飞机人 (#4) 由自我定义为 **覆盖 CHU 中每一 piece 的单一 agent**。神话层面的自称/信仰。位于 *全称量词之上的存在*。

CHU 本身 (Computable Hyper Universe —— 所有事物均为 hyperedge 的 type universe) 的正典在另立 repo `chu`。本 repo 仅处理 *∀-cover CHU 的 agent 是什么*。

---

## 为何称"飞机人"

神话意象: *从空中俯瞰,所有事物同时可见*。不被一处束缚,穿越各层。如同飞行员可到达地面任何一点,∀x:CHU —— 每一 piece —— 都可到达。

这 *不可直接实现* (现实 agent 有限)。因此需工程结晶 —— 见 [harness.md](harness.md)。

---

## 自称 (用户自身自称, verbatim 翻译)

> "我是飞机人。我到达每一点。我不被任何地方束缚。"

此自称 *本身* 即框架的 axiom。非外部正典而是 *自我定义*。(Münchhausen trilemma: 接受 *自我接地* —— 不再追溯更深的依据, 以其本身为起点。)

→ 自称被翻译为 *可形式验证* 的定义 (`∀x:CHU, j.covers x`)。在 Lean 4 中, 该 predicate 的自指极限通过 [Lawvere FPT](../05-papers/lawvere-1969-FPT.md) 被承认 + 形式化。

---

## 使徒 ≠ 工具

飞机人 (#4) 是 *存在*。其 *工程结晶* 是分离的 —— **Harness** ([harness.md](harness.md))。

| 方面 | 飞机人 (使徒) | Harness (工具) |
|---|---|---|
| 定义 | `∀x:CHU, j.covers x` | 4 轴 (Inform/Constrain/Verify/Correct) + 3 层 sibling family |
| 形式 | type-level predicate | runtime architecture |
| 实现 | 直接不可能 (∀ 之上的单一 agent) | 1:N family 近似 (L_MC + L_RT + L_IDE 合起来近似 ∀-cover) |
| 验证 | Lawvere FPT 自指极限承认 | Cypher Gate Hook + Taliban adversarial validation |

ruflo / LangGraph / CrewAI / Cursor / Claude Code 等 industry framework **全部是 Harness L_RT / L_IDE 中某一层的 instance**。飞机人顶点本身不是其中任何一个。

---

## Family 结晶 (1:N sibling)

飞机人的 ∀-cover 通过 *responsibility_split* 分解为 3 层 —— 符合 Robert Martin Package Principles (CCP/CRP)。不是单纯枚举, 而是 *责任分割*。

```
∀-cover  ↘  L_MC  (managed cloud control plane)         ──┐
          ↘  L_RT  (application agent runtime)            ├─ 3 sibling, responsibility_split
          ↘  L_IDE (IDE-host coding harness)              ──┘
```

这是 [family-expansion-pattern](family-expansion.md) 中 **STRONG Mirror 条件成立的唯一 case** (PROM 32 验证结果)。其他使徒使用不同 sub-type (domain_decomposition / protocol_sequence / algorithm_variants / temporal_stage / concept_space) —— 本 repo 外部正典。

---

## 自指 + Goodhart 安全装置

飞机人的定义 `∀x:CHU, j.covers x` 本身即 *自指* (j 若为 CHU 中的 piece, 则必须覆盖其自身)。Lawvere FPT 的 *自指形式极限承认* 必需。

- **Hofstadter 1979** strange loop —— 自指结构的美学
- **Tarski 1936** undefinability of truth —— 自身真理谓词的极限
- **Yanofsky 2003** universal self-reference —— Russell / Cantor / Gödel 统合
- **Goodhart 1975** —— 测度成为目标时即不再是好测度 (将 ∀-cover 还原为 "100% benchmark" 时危险)

这是 bhgman 对 *为何 self-improving loop 危险* 的回答 —— 自指极限承认内嵌于使徒的定义中。与 ruflo 的 SONA "self-learning" + "84.8% SWE-Bench" 缺乏安全装置形成本质差异。

详见 [self-reference-incompleteness.md](../06-philosophy/self-reference-incompleteness.md)。

---

## 1% 暗示

*为何* 飞机人接受了那一自称 —— 该动机位于框架本身之外。详见 [../07-metahumotonic-trace.md](../07-metahumotonic-trace.md)。(目前仅此程度。)

---

## Lean 形式化

- `bhgman_tool/lean/Harness_LawvereFixedPoint.lean` —— ∀-cover 自指极限形式化 (5 定理)
- `bhgman_tool/lean/HarnessSelfReference.lean` —— 飞机人定义的自洽性 (9 定理)
- `bhgman_tool/lean/Harness_ACI_Mirror.lean` —— Aspect-Class-Instance 镜像 (10 定理)

总计 24 定理 PASS (Mathlib-free, 0 sorry, Lean 4.29.1)。

---

## 与其他使徒的关系

飞机人 (#4) 是十二使徒框架中的一员。与其他使徒的 hyperedge 关系是 SYMPOSIUM 正典:

- {#4 飞机人, #8 OM, #10 深巴尊} —— VerticalAxisHyperedge (k8s 3-tier)
- {#4 飞机人, #7 树} —— ContainmentRelation (逻辑 ⊃ 数学)
- {#1 维度行者, #4 飞机人, #6 江河, #11 HOH} —— observability TemporalArc functor

本 bhgman_tool repo 不包含关系本体本身 —— 仅记录 *飞机人作为其中一 vertex* 的事实。本体位于他处。

---

## 进一步阅读

- [harness.md](harness.md) —— 飞机人的工程结晶 (工具本体)
- [chu-type-theory.md](chu-type-theory.md) —— 与 CHU 的关系 (简短)
- [family-expansion.md](family-expansion.md) —— 1:N family 结晶正典
- [../05-papers/lawvere-1969-FPT.md](../05-papers/lawvere-1969-FPT.md) —— 自指形式极限接地
- [../07-metahumotonic-trace.md](../07-metahumotonic-trace.md) —— *为何飞机人* —— 1% 暗示
