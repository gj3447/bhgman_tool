# Harness —— 飛行機男の工学的結晶

> 飛行機男 (#4 使徒) の `∀x:CHU, j.covers x` を *現実の工業ツール* として結晶化したもの。bhgman_tool の主要なツール層。

🌐 [English](harness.md) | [한국어](harness.ko-KR.md) | [中文](harness.zh-CN.md) | [日本語](harness.ja-JP.md)

---

## 4 軸モデル (Inform / Constrain / Verify / Correct)

各 Harness instance 内部の組織原理:

| 軸 | 役割 | 飛行機男 ∀-cover の側面 |
|---|---|---|
| **Inform** | agent に context / KG / skill を提供 | 「情報をどこへでも届ける」 |
| **Constrain** | 権限 / scope / token budget / 安全 | 「束縛されず暴走もせず」 |
| **Verify** | 出力検証 (Taliban adversarial / test / Lean) | 「正しく到達したか」 |
| **Correct** | フィードバック → 次回呼び出し調整 | 「失敗から学ぶ」 |

これは各 instance *内部* の組織。**family 定義ではない** (family は別 —— 後述)。

→ 4 軸モデルは *各 instance 内部* (一 Cursor IDE の中の 4 軸 / 一 Claude Code host の中の 4 軸 / 一 ruflo runtime の中の 4 軸)。
→ Family 定義は *instance 間の責任分割*。

この二つは異なる層。以前の SKILL.md drift (4 軸 = family 定義) は 2026-04-30 修正済み。

---

## 1:N sibling family (3 階層)

飛行機男 ∀-cover の *責任分割 (responsibility_split)*:

```
L_MC   managed cloud control plane
       (クラウド側 orchestration + state + scaling)
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
          ruflo (ruvnet/claude-flow) ← 一 sibling instance, 頂点ではない

L_IDE  IDE-host coding harness
       (developer interactive, file-level edit + git)
       └─ Cursor / Claude Code / Aider / SWE-agent / Cline / OpenHands / GitHub Copilot
```

→ **ruflo, Cursor, Claude Code, LangGraph などは全て本 family の sibling instance**。そのいずれも単独では飛行機男の頂点 (∀-cover) を満たさない。3 階層合わせて *近似*。

**STRONG Mirror 条件**: family が *cardinality match* となる条件。飛行機男の 3 階層がこれを満たす —— [family-expansion.md](family-expansion.md) 参照。

---

## MCP —— 全 instance を繋ぐアダプタ

3 階層の全 instance を *protocol layer* で繋ぐのが **MCP (Model Context Protocol)** —— Anthropic 標準。

- host (L_IDE) が MCP server (ツール) を呼ぶ
- L_RT framework が MCP server を公開
- L_MC managed agent が MCP ツールを使用

→ MCP は *アダプタ*。instance ではない。4 軸モデルの *Inform* 軸に近い。

ruflo は独自の plugin marketplace (IPFS Pinata) を作った —— これは *MCP 標準の上に別のロックイン層を重ねるもの*。bhgman は *標準 MCP のみの使用* を推奨。

---

## Anthropic 陣営の 3-tuple (例)

一つの陣営 (Anthropic) の中でも 3 階層 family が自然に分かれる:

| Tier | Anthropic 側 | 役割 |
|---|---|---|
| L_MC | **Managed Agents** | server-side, stateful, scaling-managed |
| L_RT | **Agent SDK** | program-level loop, in-process |
| L_IDE | **Skills + Claude Code** | declarative capability + IDE host |

→ 同一陣営でも *自然に* 3 階層に分かれる。全てを単一層に押し込まない。Robert Martin Package Principles の CCP (Common Closure Principle) の自然な応用。

---

## 形式検証 (Lean 4)

`bhgman_tool/lean/` の 3 ファイル, 合計 24 定理 PASS (Mathlib-free, Lean 4.29.1):

```
Harness_LawvereFixedPoint.lean   5 定理   — ∀-cover 自己参照限界
Harness_ACI_Mirror.lean         10 定理   — Aspect-Class-Instance 鏡像
HarnessSelfReference.lean        9 定理   — Tarski/Gödel/Yanofsky 統合
```

各定理は外部正典を引用 + 推論 chain を公開。ruflo の `verify` signed witness (コード整合性のみ) との本質的差異。

---

## 外部正典の接地

飛行機男 ∀-cover のツール結晶側 17 軸の外部正典:

| 軸 | 正典 |
|---|---|
| Engineering 4 | Robert Martin Package Principles (CCP/CRP/REP/ADP/SDP/SAP) / Conway 1968 / Cherns 1976 STS / DDD (Evans 2003) |
| Self-Reference Paradox 4 | Lawvere 1969 FPT / Tarski 1936 undefinability / Gödel 1931 incompleteness / Yanofsky 2003 universal self-reference |
| Industry 4 | Kubernetes 3-tier (control-plane / node / pod) / OpenTelemetry CNCF / IDE-host (Cursor/Claude Code) / managed cloud (Bedrock/Vertex) |
| Org + Reflection 4 | Sociotechnical Systems (Trist-Bamforth 1951) / MOP (Smith 1984 reflection) / Hofstadter 1979 strange loop / Holacracy (Robertson) |
| 1 追加 | meta-Harness 自己参照安全 (Goodhart 1975 + Münchhausen trilemma + 2026-05-05 修正 lesson) |

詳細は [../04-references/citations.md](../04-references/citations.md)。

---

## 実際の入口

```bash
# Claude Code に skill インストール
cp -R bhgman_tool/skills/harness ~/.claude/skills/

# 使用
/harness <agent_or_framework>   # ある instance が 3 階層のどこに位置するか診断
```

→ Harness skill は *診断ツール*。agent が 4 軸のどこで失敗するかを分析。詳細は [../03-tutorials/harness-diagnosis.md](../03-tutorials/harness-diagnosis.md)。

---

## 関連資料

- [airplane-man.md](airplane-man.md) —— 本質 (使徒側)
- [family-expansion.md](family-expansion.md) —— 1:N family Mirror 条件
- [goodhart-safeguard.md](goodhart-safeguard.md) —— self-improving loop 安全装置
- [../04-references/related-work.md](../04-references/related-work.md) —— ruflo / LangGraph / CrewAI 比較
- [../05-papers/lawvere-1969-FPT.md](../05-papers/lawvere-1969-FPT.md) —— 形式限界の接地
- [../06-philosophy/existence-vs-tool.md](../06-philosophy/existence-vs-tool.md) —— 使徒(存在) ⊥ Harness(ツール) の存在論的意味
