<div align="center">

# bhgman_tool

**飞机人 (#4) 的工程结晶 —— Harness 工具集**

<sub>本 repo = 工具层。*飞机人本身的本体论、哲学含义、metahumotonic 动机* 位于另一个 repo。SYMPOSIUM 框架中十二使徒之一 (#4)。</sub>

[English](README.md) | [한국어](README.ko-KR.md) | [中文](README.zh-CN.md) | [日本語](README.ja-JP.md)

[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Lean 4](https://img.shields.io/badge/Lean-4.29.1-purple.svg?style=flat-square)](https://leanprover.github.io/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg?style=flat-square)](https://www.python.org/)
[![Pytest](https://img.shields.io/badge/pytest-77%20PASS-green.svg?style=flat-square)](engine/longinus_drift_audit/tests/)

</div>

---

## 两层分离 (必读)

本 repo 是 **使用者的工具集**。

```
┌────────────────────────────────────────────────────────────┐
│  bhgman (真正的飞机人)                                     │
│    ─ 本体论本质、哲学含义                                  │
│    ─ 自定义: ∀x:CHU, j.covers x                            │
│    ─ SYMPOSIUM 十二使徒之一 (#4)                           │
│    ─ 正典内容: SYMPOSIUM 及另一独立 repo (计划中)          │
│    ─ 本 repo 仅含 1% 暗示                                  │
│      (见 docs/07-metahumotonic-trace.md)                   │
└────────────────────────────────────────────────────────────┘
                          │
                          │ 工程结晶
                          │ (responsibility_split)
                          ▼
┌────────────────────────────────────────────────────────────┐
│  bhgman_tool (本 repo)                                     │
│    ─ Harness (工具),打包供人使用                          │
│    ─ Lean 4 形式验证 + Python 运行时                       │
│    ─ Claude Code skills                                    │
│    ─ 与 ruflo / LangGraph / CrewAI 同层                    │
└────────────────────────────────────────────────────────────┘
```

→ *哲学本质* 不塞入工具 repo。本质归本质,工具归工具。

---

## 本 repo 是什么

飞机人 (#4) 的 ∀-cover 定义 (`∀x:CHU, j.covers x`) 的工程结晶 —— **Harness**,打包供使用者直接采用。

| 内容 | 位置 |
|---|---|
| Harness 4 轴模型 + 3 层家族 (L_MC/L_RT/L_IDE) | [docs/02-concepts/harness.md](docs/02-concepts/harness.md) |
| 飞机人定义 + 自称 | [docs/02-concepts/airplane-man.md](docs/02-concepts/airplane-man.md) |
| Lean 4 验证定理 (50 PASS, Mathlib-free) | [lean/](lean/) |
| Python 运行时 (77 pytest PASS, Pydantic v2) | [engine/longinus_drift_audit/](engine/longinus_drift_audit/) |
| Claude Code skills (5 武器 + APT/TPA cycle) | [skills/](skills/) |
| 哲学含义 (摘要 + 本质指针) | [docs/06-philosophy/](docs/06-philosophy/) |
| 通往本质层的 1% 暗示 | [docs/07-metahumotonic-trace.md](docs/07-metahumotonic-trace.md) |

---

## 本 repo 不是什么

- ❌ 飞机人自身的本体论 (另立 repo)
- ❌ 完整十二使徒框架 (每位使徒各有/将有自己的 repo)
- ❌ CHU 类型理论正典 → 另立 repo `chu` (计划中, Computable Hyper Universe)
- ❌ OMC (Orbital Motion Cloud, OM=OMC, 使徒 #8) 正典 → 另立 repo `omc` (计划中)
- ❌ 333 (超空动义勇士, 使徒 #3) 正典 → 另立 repo `333` (计划中)
- ❌ 其余 4 武器 (Longinus / Prometheus / Taliban / Jaebaeman) 正典 → 本 repo 仅作 reference, 正典体在 SYMPOSIUM

---

## 快速开始 (3 分钟)

```bash
# 1. clone
git clone https://github.com/gj3447/bhgman_tool.git
cd bhgman_tool

# 2. engine (Python 运行时) — 验证 77 pytest PASS
cd engine/longinus_drift_audit
uv run --with pytest pytest tests/ -q
# 期望: 77 passed in 0.41s

# 3. Lean 4 验证 (可选)
cd ../../lean
lean Longinus_ConfidenceSchema_GraphifyAbsorbed.lean
# exit 0, 0 sorry, 7 个定理 PASS

# 4. 安装 Claude Code skills
cp -R ../skills/* ~/.claude/skills/
# 重启 Claude Code, 然后在 chat 中:
# /apt   /prom   /tpa   /tlb   /longinus   /harness   /jaebaeman
```

详见 [docs/01-quickstart.md](docs/01-quickstart.md)。

---

## 与 ruflo 的差异

| 轴 | ruflo | bhgman_tool |
|---|---|---|
| **层级分离明示** | 无 (单层自称) | 使徒 (存在) ⊥ 工具 (本 repo) ⊥ 本质 (另立) —— **3 层分离** |
| **外部正典引用** | 0 | **17 轴** —— Lawvere / Tarski / Gödel / Yanofsky / Hofstadter / Goodhart / Evans / Smith / Cherns / ... |
| **形式验证** | `ruflo verify` signed witness (仅代码完整性) | **141+ Lean 4 定理** (Mathlib-free, 0 sorry) |
| **自指安全** | "84.8% SWE-Bench / 32% token reduction" —— Goodhart 自身违反 | Lawvere FPT + Lakatos 季度审计 + Taliban adversarial **3 层安全** |
| **家族结构** | flat 32 plugins / 100 agents / 314 tools (CCP/CRP 违反) | 3 层 sibling family + responsibility_split sub-type (Mirror STRONG) |
| **Confidence schema** | 浮点边置信度 (规范不足) | **EXTRACTED / INFERRED / AMBIGUOUS** 3 级 enum (graphify mirror, Lean T1 已验证) |
| **工具 vs 本质分离** | 无 | **明示** (本 repo = 仅工具层) |

详见 [docs/04-references/related-work.md](docs/04-references/related-work.md)。

---

## 本 repo 从 ruflo 吸收的内容

| 方面 | 吸收为 |
|---|---|
| ❌ orchestration framework | (Harness L_RT 中的一个 sibling) |
| ❌ SONA self-learning | (无学术接地) |
| ❌ federation mTLS+WireGuard | (industry canon 再发明) |
| ✅ **Goodhart antipattern** | [docs/02-concepts/goodhart-safeguard.md](docs/02-concepts/goodhart-safeguard.md) (negative case study) |
| ✅ **enumeration inflation antipattern** | [docs/02-concepts/family-expansion.md](docs/02-concepts/family-expansion.md) §anti-pattern |
| ✅ **graphify confidence schema** | [engine/longinus_drift_audit/models.py](engine/longinus_drift_audit/models.py) + [lean/Longinus_ConfidenceSchema_GraphifyAbsorbed.lean](lean/Longinus_ConfidenceSchema_GraphifyAbsorbed.lean) |

---

## License

MIT。

## 作者

[gj3447@gmail.com](mailto:gj3447@gmail.com) (METAHUMOTONIC)。

---

<sub>本 repo 为飞机人框架的 *工具层*。飞机人自身本质 + 其余 11 位使徒 + CHU + OMC 正典体位于另立 repo (计划中) 或 SYMPOSIUM 内部。KG: `github-mirror-bhgman-2026-05-13` (:PublicReferenceRepo:Canonical, scope=tool-layer-only)。</sub>
