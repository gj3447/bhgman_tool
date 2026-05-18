<div align="center">

# bhgman_tool

**飛行機男 (#4) の工学的結晶 —— Harness ツールキット**

<sub>本 repo = ツール層。*飛行機男自身の存在論・哲学的含意・メタヒューモトニック動機* は別 repo に。SYMPOSIUM フレームワークの十二使徒の一人 (#4)。</sub>

[English](README.md) | [한국어](README.ko-KR.md) | [中文](README.zh-CN.md) | [日本語](README.ja-JP.md)

[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Lean 4](https://img.shields.io/badge/Lean-4.29.1-purple.svg?style=flat-square)](https://leanprover.github.io/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg?style=flat-square)](https://www.python.org/)
[![Pytest](https://img.shields.io/badge/pytest-77%20PASS-green.svg?style=flat-square)](engine/longinus_drift_audit/tests/)

</div>

---

## 二層分離 (必読)

本 repo は **使用者のツールキット**。

```
┌────────────────────────────────────────────────────────────┐
│  bhgman (本当の飛行機男)                                   │
│    ─ 存在論的本質、哲学的含意                              │
│    ─ 自己定義: ∀x:CHU, j.covers x                          │
│    ─ SYMPOSIUM 十二使徒の一人 (#4)                         │
│    ─ 正典本体: SYMPOSIUM + 別 repo (予定)                  │
│    ─ 本 repo には 1% のヒントのみ                          │
│      (docs/07-metahumotonic-trace.md 参照)                 │
└────────────────────────────────────────────────────────────┘
                          │
                          │ 工学的結晶
                          │ (responsibility_split)
                          ▼
┌────────────────────────────────────────────────────────────┐
│  bhgman_tool (本 repo)                                     │
│    ─ Harness (ツール), 人が使えるようパッケージ化         │
│    ─ Lean 4 形式検証 + Python ランタイム                   │
│    ─ Claude Code skills                                    │
│    ─ ruflo / LangGraph / CrewAI と同じ層                   │
└────────────────────────────────────────────────────────────┘
```

→ *哲学的本質* をツール repo に押し込まない。本質は本質に。ツールはツールに。

---

## 本 repo は何か

飛行機男 (#4) の ∀-cover 定義 (`∀x:CHU, j.covers x`) の工学的結晶 —— **Harness** —— を使用者が直接採用できるようパッケージ化。

| 内容 | 場所 |
|---|---|
| Harness 4 軸モデル + 3 階層 family (L_MC/L_RT/L_IDE) | [docs/02-concepts/harness.md](docs/02-concepts/harness.md) |
| 飛行機男の定義 + 自称 | [docs/02-concepts/airplane-man.md](docs/02-concepts/airplane-man.md) |
| Lean 4 検証済み定理 (50 PASS, Mathlib-free) | [lean/](lean/) |
| Python ランタイム (77 pytest PASS, Pydantic v2) | [engine/longinus_drift_audit/](engine/longinus_drift_audit/) |
| Claude Code skills (5 武器 + APT/TPA cycle) | [skills/](skills/) |
| 哲学的含意 (要約 + 本質へのポインタ) | [docs/06-philosophy/](docs/06-philosophy/) |
| 本質層への 1% ヒント | [docs/07-metahumotonic-trace.md](docs/07-metahumotonic-trace.md) |

---

## 本 repo に *含まれないもの*

- ❌ 飛行機男自身の存在論 (別 repo)
- ❌ 完全な十二使徒フレームワーク (各使徒が独自 repo を持つ/予定)
- ❌ CHU 型理論正典 → 別 repo `chu` (予定, Computable Hyper Universe)
- ❌ OMC (Orbital Motion Cloud, OM=OMC, 使徒 #8) 正典 → 別 repo `omc` (予定)
- ❌ 333 (超空洞義勇士, 使徒 #3) 正典 → 別 repo `333` (予定)
- ❌ 他の 4 武器 (Longinus / Prometheus / Naesengmoon / Jaebaeman) 正典 → 本 repo は reference のみ, 本体は SYMPOSIUM

---

## クイックスタート (3 分)

```bash
# 1. clone
git clone https://github.com/gj3447/bhgman_tool.git
cd bhgman_tool

# 2. engine (Python ランタイム) — 77 pytest PASS を検証
cd engine/longinus_drift_audit
uv run --with pytest pytest tests/ -q
# 期待: 77 passed in 0.41s

# 3. Lean 4 検証 (オプション)
cd ../../lean
lean Longinus_ConfidenceSchema_GraphifyAbsorbed.lean
# exit 0, 0 sorry, 7 定理 PASS

# 4. Claude Code skills インストール
cp -R ../skills/* ~/.claude/skills/
# Claude Code 再起動後, chat にて:
# /apt   /prom   /tpa   /tlb   /longinus   /harness   /jaebaeman
```

詳細は [docs/01-quickstart.md](docs/01-quickstart.md)。

---

## ruflo との差別化

| 軸 | ruflo | bhgman_tool |
|---|---|---|
| **層分離の明示** | なし (単一層自称) | 使徒 (存在) ⊥ ツール (本 repo) ⊥ 本質 (別 repo) —— **3 層分離** |
| **外部正典引用** | 0 | **17 軸** —— Lawvere / Tarski / Gödel / Yanofsky / Hofstadter / Goodhart / Evans / Smith / Cherns / ... |
| **形式検証** | `ruflo verify` signed witness (コード整合性のみ) | **141+ Lean 4 定理** (Mathlib-free, 0 sorry) |
| **自己参照の安全** | "84.8% SWE-Bench / 32% token reduction" —— Goodhart 自身違反 | Lawvere FPT + Lakatos 四半期監査 + Naesengmoon adversarial **3 層安全装置** |
| **家族構造** | flat 32 plugins / 100 agents / 314 tools (CCP/CRP 違反) | 3 階層 sibling family + responsibility_split sub-type (Mirror STRONG) |
| **Confidence schema** | 浮動小数の edge confidence (仕様不足) | **EXTRACTED / INFERRED / AMBIGUOUS** 3 段 enum (graphify mirror, Lean T1 検証済) |
| **ツール vs 本質分離** | なし | **明示** (本 repo = ツール層のみ) |

詳細は [docs/04-references/related-work.md](docs/04-references/related-work.md)。

---

## 本 repo が ruflo から吸収したもの

| 側面 | 吸収結果 |
|---|---|
| ❌ orchestration framework | (Harness L_RT の一 sibling にすぎず) |
| ❌ SONA self-learning | (学術接地なし) |
| ❌ federation mTLS+WireGuard | (industry canon の再発明) |
| ✅ **Goodhart antipattern** | [docs/02-concepts/goodhart-safeguard.md](docs/02-concepts/goodhart-safeguard.md) (negative case study) |
| ✅ **enumeration inflation antipattern** | [docs/02-concepts/family-expansion.md](docs/02-concepts/family-expansion.md) §anti-pattern |
| ✅ **graphify confidence schema** | [engine/longinus_drift_audit/models.py](engine/longinus_drift_audit/models.py) + [lean/Longinus_ConfidenceSchema_GraphifyAbsorbed.lean](lean/Longinus_ConfidenceSchema_GraphifyAbsorbed.lean) |

---

## License

MIT。

## 著者

[gj3447@gmail.com](mailto:gj3447@gmail.com) (METAHUMOTONIC)。

---

<sub>本 repo は飛行機男フレームワークの *ツール層*。飛行機男自身の本質 + 他 11 使徒 + CHU + OMC 正典本体は別 repo (予定) または SYMPOSIUM 内部。KG: `github-mirror-bhgman-2026-05-13` (:PublicReferenceRepo:Canonical, scope=tool-layer-only)。</sub>
