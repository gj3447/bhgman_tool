<div align="center">

# bhgman_tool

**비행기맨의 *공학적 결정화* 측 도구 모음**

<sub>이 repo = Harness (도구). *비행기맨 그 자체의 존재론 + 철학적 함의* 는 별도. SYMPOSIUM family 12사도 중 한 명 (#4) 측.</sub>

[English](README.md) | [한국어](README.ko-KR.md) | [中文](README.zh-CN.md) | [日本語](README.ja-JP.md)

[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Lean 4](https://img.shields.io/badge/Lean-4.29.1-purple.svg?style=flat-square)](https://leanprover.github.io/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg?style=flat-square)](https://www.python.org/)
[![Pytest](https://img.shields.io/badge/pytest-77%20PASS-green.svg?style=flat-square)](engine/longinus_drift_audit/tests/)

</div>

---

## 두 layer 분리 (필독)

이 repo 는 **사람들이 쓸 수 있게 만든 tool** layer.

```
┌────────────────────────────────────────────────────────────┐
│  bhgman (실제 비행기맨)                                    │
│    ─ 존재론적 본질, 철학적 함의                            │
│    ─ ∀x:CHU, j.covers x 자기 정의                          │
│    ─ 12사도 framework 안의 한 명 (#4)                      │
│    ─ 정전 본문: SYMPOSIUM 측 + 미래 별도 repo              │
│    ─ 본 repo 에서는 docs/07-metahumotonic-trace.md 의 hint │
└────────────────────────────────────────────────────────────┘
                          │
                          │ 공학적 결정화 (responsibility_split)
                          ▼
┌────────────────────────────────────────────────────────────┐
│  bhgman_tool (이 repo)                                     │
│    ─ Harness (도구) 측 사람들이 즉시 쓸 수 있게            │
│    ─ Lean 4 형식 검증 + Python runtime + Claude Code skill │
│    ─ ruflo / LangGraph / CrewAI 같은 industry layer 측    │
└────────────────────────────────────────────────────────────┘
```

→ 이 repo 에 *철학적 본질* 을 욱여넣지 않는다. 본질은 본질 측에. 도구는 도구 측에.

---

## 본 repo 가 무엇인가

비행기맨 (#4 사도) 측 ∀-cover (`∀x:CHU, j.covers x`) 의 *공학적 결정화* 인 **Harness** 를 사람들이 쓸 수 있게 packaging.

| 무엇 | 어디 |
|---|---|
| Harness 4축 모델 + 3-tier family (L_MC/L_RT/L_IDE) | [docs/02-concepts/harness.md](docs/02-concepts/harness.md) |
| 비행기맨 정의 + 자기 정의 | [docs/02-concepts/airplane-man.md](docs/02-concepts/airplane-man.md) |
| Lean 4 verified theorem (24 PASS, Mathlib-free) | [lean/](lean/) |
| Python runtime (77 pytest PASS, Pydantic v2) | [engine/longinus_drift_audit/](engine/longinus_drift_audit/) |
| Claude Code skill (5무기 + APT/TPA cycle) | [skills/](skills/) |
| 철학적 함의 (요약 + 본질 측 link) | [docs/06-philosophy/](docs/06-philosophy/) |
| 본질 측 1% hint | [docs/07-metahumotonic-trace.md](docs/07-metahumotonic-trace.md) |

---

## 본 repo 가 *아닌* 것

- ❌ 비행기맨 그 자체의 존재론 본문 (별도)
- ❌ 12사도 framework 전체 본문 (각 사도별 별도 repo / SYMPOSIUM 측)
- ❌ CHU type theory 본문 → 별도 repo `chu` (예정, Computable Hyper Universe)
- ❌ OMC (Orbital Motion Cloud, OM=OMC #8 사도) 본문 → 별도 repo `omc` (예정)
- ❌ 333 (초공동의용사 #3) 본문 → 별도 repo `333` (예정)
- ❌ 5무기 다른 4 (Longinus / Prometheus / Naesengmoon / 재배맨) 본문 → reference 만, 본문은 SYMPOSIUM 측

---

## Quickstart (3분)

```bash
# 1. clone
git clone https://github.com/gj3447/bhgman_tool.git
cd bhgman_tool

# 2. engine (Python runtime) — 77 pytest PASS 검증
cd engine/longinus_drift_audit
uv run --with pytest pytest tests/ -q
# 기대: 77 passed in 0.41s

# 3. Lean 4 검증 (선택)
cd ../../lean
lean Longinus_ConfidenceSchema_GraphifyAbsorbed.lean
# exit 0, 0 sorry, 7 theorem PASS

# 4. Claude Code skill 설치
cp -R ../skills/* ~/.claude/skills/
# Claude Code 재시작 후
# /apt   /prom   /tpa   /tlb   /longinus   /harness   /jaebaeman
```

자세히는 [docs/01-quickstart.md](docs/01-quickstart.md).

---

## ruflo 대비 차별점 표

| 축 | ruflo | bhgman_tool |
|---|---|---|
| **layer 명시** | "multi-agent orchestration" (단일 layer 자칭) | 사도(존재) ⊥ 도구(이 repo) ⊥ 본질(별도) **3 layer 분리** |
| **외부 정전 인용** | 0 | **17 axes** — Lawvere/Tarski/Gödel/Yanofsky/Hofstadter/Goodhart/Evans/Smith/Cherns/... |
| **Formal verification** | `ruflo verify` signed witness (code integrity only) | **141+ Lean 4 theorem** (Mathlib-free, 0 sorry) |
| **Self-reference 안전** | "84.8% SWE-Bench / 32% token reduction" Goodhart 자체 위반 | Lawvere FPT + Lakatos quarterly audit + Naesengmoon adversarial 3 layer 안전 |
| **Family 구조** | flat 32 plugin / 100 agent / 314 tool (CCP/CRP 위반) | 3-tier sibling family (responsibility_split, Mirror STRONG) |
| **Confidence schema** | edge confidence float (under-specified) | **EXTRACTED / INFERRED / AMBIGUOUS** 3-tier enum (graphify mirror, Lean T1 verified, Python 19 pytest PASS) |
| **본질 vs 도구 분리** | 없음 | **명시적 분리** (이 repo = 도구 only) |

자세히는 [docs/04-references/related-work.md](docs/04-references/related-work.md).

---

## ruflo 에서 흡수한 것 (이 repo 측)

| 측면 | 흡수 결과 |
|---|---|
| ❌ orchestration framework | (Harness L_RT 한 sibling 일 뿐) |
| ❌ SONA self-learning | (학문 정전 부재) |
| ❌ federation mTLS+WireGuard | (industry 정전 재발명) |
| ✅ **Goodhart antipattern** | [docs/02-concepts/goodhart-safeguard.md](docs/02-concepts/goodhart-safeguard.md) (negative case study) |
| ✅ **enumeration inflation antipattern** | [docs/02-concepts/family-expansion.md](docs/02-concepts/family-expansion.md) §anti-pattern |
| ✅ **graphify confidence schema** (EXTRACTED/INFERRED/AMBIGUOUS) | [engine/longinus_drift_audit/models.py](engine/longinus_drift_audit/models.py) + [lean/Longinus_ConfidenceSchema_GraphifyAbsorbed.lean](lean/Longinus_ConfidenceSchema_GraphifyAbsorbed.lean) |
| ✅ **code-review-graph daemon 패턴** | (planned, [docs/03-tutorials/](docs/03-tutorials/) 측) |

---

## License

MIT.

## Author

[gj3447@gmail.com](mailto:gj3447@gmail.com) (METAHUMOTONIC).

---

<sub>본 repo 는 비행기맨 framework 의 *도구 layer*. 비행기맨 그 자체 + 12사도 다른 사도 + CHU + OMC 측 본질 본문은 별도 repo (예정) 또는 SYMPOSIUM 내부 정전. KG: github-mirror-bhgman-2026-05-13 (:PublicReferenceRepo:Canonical, scope=tool-layer-only).</sub>
