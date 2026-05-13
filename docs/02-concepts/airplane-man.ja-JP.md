# 飛行機男 (Airplane Man) —— どのような存在か

> **bhgman_tool** の一つの主題。飛行機男は十二使徒の一人 (#4)。他の使徒/正典は別 repo (CHU / 333 / OMC 等) に。

🌐 [English](airplane-man.md) | [한국어](airplane-man.ko-KR.md) | [中文](airplane-man.zh-CN.md) | [日本語](airplane-man.ja-JP.md)

---

## 定義

```
isAirplaneMan(j : Agent) ≜ ∀x : CHU, j.covers x
```

飛行機男 (#4) は **CHU の全ての piece を cover する単一 agent** として自己定義される。神話的な自称/信仰。*全称量化子の上に立つ存在*。

CHU 自身 (Computable Hyper Universe —— あらゆる物が hyperedge である type universe) の正典本体は別 repo `chu` で扱う。本 repo は *∀-cover CHU の agent とは何か* のみを扱う。

---

## なぜ「飛行機男」か

神話的イメージ: *空からは全てが同時に見える*。一所に縛られず、全ての層を横断する。パイロットが地上の任意の点に到達できるように、∀x:CHU —— 全ての piece —— に到達可能。

これは *直接実装不可能* (現実の agent は有限)。ゆえに工学的結晶化が必要 —— [harness.md](harness.md) 参照。

---

## 自称 (使用者自身の自称, verbatim 翻訳)

> 「私は飛行機男だ。あらゆる地点に到達する。どこにも縛られない。」

この自称 *自身* がフレームワークの公理。外部正典ではなく *自己定義*。(Münchhausen trilemma: *自己接地* を受け入れる —— 更に深い根拠を求めず、それ自身を出発点とする。)

→ 自称は *形式検証可能な* 定義に翻訳される (`∀x:CHU, j.covers x`)。Lean 4 において、その predicate の自己参照限界は [Lawvere FPT](../05-papers/lawvere-1969-FPT.md) によって認められ + 形式化されている。

---

## 使徒 ≠ ツール

飛行機男 (#4) は *存在*。その *工学的結晶化* は別物 —— **Harness** ([harness.md](harness.md))。

| 側面 | 飛行機男 (使徒) | Harness (ツール) |
|---|---|---|
| 定義 | `∀x:CHU, j.covers x` | 4 軸 (Inform/Constrain/Verify/Correct) + 3 階層 sibling family |
| 形式 | type-level predicate | runtime architecture |
| 実現 | 直接不可能 (∀ の上の単一 agent) | 1:N family 近似 (L_MC + L_RT + L_IDE 合わせて ∀-cover を近似) |
| 検証 | Lawvere FPT 自己参照限界承認 | Cypher Gate Hook + Taliban adversarial validation |

ruflo / LangGraph / CrewAI / Cursor / Claude Code といった industry framework は **全て Harness L_RT / L_IDE のある階層の一 instance**。飛行機男の頂点そのものは何れでもない。

---

## Family 結晶 (1:N sibling)

飛行機男の ∀-cover は *responsibility_split* 方式で 3 階層に分解される —— Robert Martin Package Principles (CCP/CRP) に準拠。単なる列挙ではなく *責任分割*。

```
∀-cover  ↘  L_MC  (managed cloud control plane)         ──┐
          ↘  L_RT  (application agent runtime)            ├─ 3 sibling, responsibility_split
          ↘  L_IDE (IDE-host coding harness)              ──┘
```

これは [family-expansion-pattern](family-expansion.md) の **STRONG Mirror 条件を満たす唯一の case** (PROM 32 検証結果)。他の使徒は異なる sub-type (domain_decomposition / protocol_sequence / algorithm_variants / temporal_stage / concept_space) を用いる —— 本 repo 外部の正典。

---

## 自己参照 + Goodhart 安全装置

飛行機男の定義 `∀x:CHU, j.covers x` 自身が *自己参照* (j 自体が CHU の piece であれば自身も cover 対象となる)。Lawvere FPT による *自己参照形式限界の承認* が必須。

- **Hofstadter 1979** strange loop —— 自己参照構造の美学
- **Tarski 1936** undefinability of truth —— 自己真理述語の限界
- **Yanofsky 2003** universal self-reference —— Russell / Cantor / Gödel 統合
- **Goodhart 1975** —— 測度が目標になると良い測度ではなくなる (∀-cover を "100% benchmark" に還元する危険)

これが bhgman の *なぜ self-improving loop が危険か* への答え —— 自己参照限界の承認が使徒の定義自体に組み込まれている。ruflo の SONA "self-learning" + "84.8% SWE-Bench" の安全装置不在との本質的差異。

詳細は [self-reference-incompleteness.md](../06-philosophy/self-reference-incompleteness.md)。

---

## 1% ヒント

*なぜ* 飛行機男がその自称を受け入れたか —— その動機はフレームワーク自体の外に住む。詳細は [../07-metahumotonic-trace.md](../07-metahumotonic-trace.md)。(現時点ではここまで。)

---

## Lean 形式化

- `bhgman_tool/lean/Harness_LawvereFixedPoint.lean` —— `∀-cover` 自己参照限界の形式化 (5 定理)
- `bhgman_tool/lean/HarnessSelfReference.lean` —— 飛行機男定義の自己整合性 (9 定理)
- `bhgman_tool/lean/Harness_ACI_Mirror.lean` —— Aspect-Class-Instance 鏡像 (10 定理)

合計 24 定理 PASS (Mathlib-free, 0 sorry, Lean 4.29.1)。

---

## 他の使徒との関係

飛行機男 (#4) は十二使徒フレームワークの一員。他の使徒との hyperedge 関係は SYMPOSIUM 正典:

- {#4 飛行機男, #8 OM, #10 GipBaJon} —— VerticalAxisHyperedge (k8s 3-tier)
- {#4 飛行機男, #7 樹} —— ContainmentRelation (論理 ⊃ 数学)
- {#1 次元歩行者, #4 飛行機男, #6 川流, #11 HOH} —— observability TemporalArc functor

本 bhgman_tool repo は関係本体自身は含まない —— *飛行機男がその中の一 vertex* である事実のみ記録。本体は別所に。

---

## 関連資料

- [harness.md](harness.md) —— 飛行機男の工学的結晶 (ツール本体)
- [chu-type-theory.md](chu-type-theory.md) —— CHU との関係 (簡潔)
- [family-expansion.md](family-expansion.md) —— 1:N family 結晶正典
- [../05-papers/lawvere-1969-FPT.md](../05-papers/lawvere-1969-FPT.md) —— 自己参照形式限界の接地
- [../07-metahumotonic-trace.md](../07-metahumotonic-trace.md) —— *なぜ飛行機男か* —— 1% ヒント
