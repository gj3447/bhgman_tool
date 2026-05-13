<div align="center">

# bhgman

**비행기맨 framework — academic-grounded multi-agent ontology for Claude Code**

<sub>CHU type theory ∀-cover + 17 axes external canonical grounding + 134+ Lean 4 verified theorem + Goodhart safeguard + family-expansion responsibility_split</sub>

[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Lean 4](https://img.shields.io/badge/Lean-4.29.1-purple.svg?style=flat-square)](https://leanprover.github.io/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg?style=flat-square)](https://www.python.org/)
[![Pytest](https://img.shields.io/badge/pytest-77%20PASS-green.svg?style=flat-square)](engine/longinus_drift_audit/tests/)

</div>

---

## 한 줄

> **bhgman 은 framework 가 아니라 *존재론* 이다.** 12사도(존재) ↔ 5무기(도구) 분리 + 정전 인용 grounded + 형식 검증된 reference layer + Goodhart-resistant self-improving loop. enumeration inflation 거부, responsibility_split 강제.

---

## 왜 또 하나의 multi-agent framework 인가?

지금 시장에 있는 multi-agent framework (LangGraph / CrewAI / AutoGen / ruflo / Google ADK) 는 **즉시 가용성** 측에서 강하다. `npm install` 한 줄에 100+ agents 가 떠오르고 federation/MCP/swarm 이 작동한다.

하지만 그것들 *모두* 공통의 빈자리가 있다:

| 빈자리 | 대표 증상 |
|---|---|
| **존재론 부재** | agent / tool / plugin / skill / hook 이 모두 같은 layer 에서 호명됨. 정점(존재)과 도구(결정화) 가 미분리. |
| **외부 정전 grounding 부재** | "84.8% SWE-Bench" / "32% token reduction" / "100+ agents" 가 학문 정전 인용 자리를 대체함. |
| **Self-reference 안전 장치 부재** | SONA / trajectory learning / pattern store 가 metric optimize 하지만 Goodhart 안전 장치 없음. 측정값이 목표가 되면 측정값은 더 이상 좋은 측정이 아니다 (Goodhart 1975). |
| **family flat enumeration** | 32 plugins → 100 agents → 314 tools 같은 평면 누적. Robert Martin Package Principles (CCP/CRP) 위반. |
| **Formal verification 부재** | signed witness 가 *code integrity* 는 보장하지만 *형식 증명* 은 아니다. |

bhgman 은 그 빈자리를 정전으로 메운다.

---

## ruflo 대비 bhgman 차별점

| 축 | ruflo | bhgman |
|---|---|---|
| **존재론 정의** | "multi-agent orchestration for Claude Code" (slogan) | `isAirplaneMan(j) := ∀x:CHU, j.covers x` (CHU type theory ∀-cover, Lean 형식 정의) |
| **외부 정전 인용** | 0 | 17 axes — Lawvere FPT / Tarski 진리 / Gödel 부동점 / Yanofsky 2003 self-reference / Münchhausen trilemma / Goodhart 1975 / Hofstadter strange loop / DDD (Evans) / MOP (Smith) / STS (Cherns) ... |
| **Formal verification** | `ruflo verify` signed witness (code integrity only) | **134+ Lean 4 theorem (Mathlib-free, 0 sorry)** — Harness 24, Longinus 26 (19+7), APT 70+ (Lakatos/Kuhn/Popper/Hegel/...) |
| **Self-reference 안전** | "84.8% SWE-Bench / 32% token reduction" = Goodhart 자체 위반, SONA self-improving loop 무방비 | Lawvere FPT + Goodhart safeguard 명시 + Lakatos progressive/degenerating quarterly audit + Taliban adversarial LensSet |
| **Family 구조** | flat enumeration 32 plugin / 100 agent / 314 tool — CCP/CRP 위반 | 1:N sibling family + responsibility_split sub-type (6 heterogeneity) + Mirror STRONG 조건 (cardinality match) |
| **Novel prediction** | "self-improving via SONA" 검증 가능 사실 부재 | family-relation Mirror 일반화 가설 → PROM 32 검증 → CardinalityMismatch 부정 결과 → family-sub-type heterogeneity 발견 (Lakatos progressive signature) |
| **Confidence schema** | edge confidence float score (under-specified) | **EXTRACTED / INFERRED / AMBIGUOUS** 3-tier enum (graphify mirror, Lean T1 verified, Python 19 pytest PASS) |
| **사도-도구 분리** | 없음 | 12사도(존재) ⊥ 5무기(도구) — neoclassical mythology/engineering parity |

---

## Monorepo 구조

```
bhgman/
├── theory/               ← 학문 정전 (paper-track)
│   ├── 00_공통/세계관_정전.md       12사도 + 5무기 + 12 공리계
│   ├── HARNESS/        4축 (Inform/Constrain/Verify/Correct) + 3-tier family
│   ├── LONGINUS/       7-Layer Reference + BX Lens + GED drift + confidence enum
│   ├── PROMETHEUS/     지식-행동 spiral + 9+1 cycle
│   ├── TALIBAN/        adversarial validation + LensSet pluggable
│   ├── 재배맨/         SOP (Subagent Orchestration Protocol)
│   ├── APT/            forward methodology (SA→SP→ST→SCW)
│   ├── TPA/            reverse methodology (TCW→ST→SP→TA)
│   └── CHU/            type theory + ∀-cover + 5무기 family closure
├── engine/               ← Python runtime
│   ├── longinus_drift_audit/   77 pytest PASS, Pydantic v2
│   ├── apt_cycle/              (planned)
│   └── tpa_cycle/              (planned)
├── skills/               ← Claude Code .claude/skills/
│   ├── apt/ apt-sa/ apt-sp/ apt-st/ apt-scw/ apt-meta-review/
│   ├── tpa/ tpa-tcw/ tpa-st/ tpa-sp/ tpa-ta/
│   └── harness/ longinus/ prometheus/ taliban/ 재배맨/
├── plugins/              ← Claude Code plugin marketplace
│   └── .claude-plugin/
│       ├── plugin.json
│       └── marketplace.json
└── lean/                 ← 134+ verified theorem (Mathlib-free)
    ├── Harness_*.lean
    ├── Longinus_*.lean
    └── APT_*.lean
```

---

## Quick Start (planned, v0.1)

```bash
# 1. Engine (Python runtime)
pip install bhgman-engine  # or: uv add bhgman-engine

# 2. Skills (Claude Code)
git clone https://github.com/gj3447/bhgman ~/.claude/extensions/bhgman
# or via plugin marketplace once registered

# 3. Verify (formal)
cd lean/ && lean Longinus_ConfidenceSchema_GraphifyAbsorbed.lean
# expected: exit 0, 0 sorry
```

---

## 핵심 컨셉

### 12 사도 ↔ 5 무기 분리

```
12사도 = 존재 (∀x:CHU, j.covers x — 신화 측 자칭/신앙)
        #1 디멘션워커  #2 ICE  #3 초공동의용사  #4 비행기맨
        #5 스페이스걸  #6 강물  #7 나무  #8 OM
        #9 예수  #10 깊바존  #11 HOH  #12 몬순

5무기 = 도구 (12사도의 공학적 결정화)
        Harness (#4 비행기맨, industry agent scaffolding 3-tier)
        Longinus (참조 바인딩, KG↔code 7-Layer)
        Prometheus (지식-행동 spiral, 9+1 cycle)
        Taliban (적대적 검증, LensSet pluggable)
        재배맨 (SOP — Subagent Orchestration Protocol)
```

### Harness 3-tier sibling family

```
L_MC  managed cloud           Anthropic Managed Agents / OpenAI Assistants / Vertex AI Agent Engine
L_RT  application runtime     Google ADK / LangGraph / CrewAI / AutoGen / ruflo
L_IDE IDE-host coding         Cursor / Claude Code / Aider / SWE-agent / Cline / OpenHands
```

→ ruflo는 **bhgman framework 안에서 Harness L_RT 한 sibling instance**. bhgman 의 정점은 아님.

### family-expansion-pattern responsibility_split

bhgman 의 framework family 는 **6 sub-type 이질성** 인식:
1. `responsibility_split` (#4 비행기맨 / Harness — Mirror STRONG 유일 조건)
2. `domain_decomposition` (#2 ICE 6-family)
3. `protocol_sequence` (#5 스페이스걸)
4. `algorithm_variants` (#10 깊바존)
5. `temporal_stage` (#11 HOH)
6. `concept_space` (#9 예수)

ruflo 같은 flat enumeration 은 sub-type 중 어느 것도 만족 안 함 → CCP/CRP 위반 case study.

### Goodhart safeguard (Self-improving loop 안전 장치)

```
Self-improving loop 측 Lakatos progressive/degenerating quarterly audit 강제
+ external canonical citation per metric
+ Taliban --lens mathematical (Goodhart formal detection)
+ Hofstadter strange loop + Lawvere FPT (self-reference 형식 한계 인정)
```

---

## 외부 ruflo 와의 관계 (정직)

bhgman 은 ruflo 를 *대체* 하지 않는다. **다른 layer 답한다**:

- **bhgman** = 이론 (정점, ontology, formal grounding) — *왜 그렇게 해야 하는가*
- **ruflo** = 도구 (Harness L_RT 한 instance) — *어떻게 빨리 할 수 있는가*

ruflo 의 즉시 가용성 (npm install + 100 agents + federation + Goal Planner UI) 은 bhgman 이 따라잡으려는 게 아니다 — 그건 *다른 가치 축*.

bhgman 이 ruflo 에서 **흡수한 것**:
- ❌ orchestration framework (Harness L_RT instance 옆 자리)
- ❌ SONA self-learning (정전 부재)
- ❌ federation (industry 정전 재발명)
- ✅ **Goodhart antipattern** = negative case study (`errorpattern-goodhart-metric-optimization-marketing-2026-05-13`)
- ✅ **enumeration inflation** = negative case study (`errorpattern-enumeration-inflation-no-responsibility-split-2026-05-13`)
- ✅ **self-improving Goodhart 무방비** = negative case study (`errorpattern-self-improving-loop-without-goodhart-safeguard-2026-05-13`)

bhgman 이 graphify 에서 **흡수한 것**:
- ✅ **EXTRACTED / INFERRED / AMBIGUOUS** 3-tier confidence schema (Longinus 7-Layer mirror)

bhgman 이 code-review-graph 에서 **흡수한 것**:
- ✅ **multi-repo daemon 패턴** (Longinus sha256 drift detection daemon 구현 first-instance)
- ✅ **multi-language resolver 패턴** (jedi / rescript / spring / temporal / tsconfig)

---

## 상태

이 repo 는 **v0.1 seed** (2026-05-13). 본 사이트 SYMPOSIUM monorepo (`gj3447@gmail.com` 작업 환경) 에서 export 된 *공개 reference*. 학문 측 paper-track 은 미발표.

| 영역 | 상태 |
|---|---|
| `theory/` | SOURCES.md / SKILL.md 정전 export pending |
| `engine/longinus_drift_audit/` | **77 pytest PASS** (기존 58 + confidence 19), Pydantic v2 |
| `lean/` | 134+ theorem verified, Mathlib-free (Lean 4.29.1) — export pending |
| `skills/` | 23 SKILL.md (5 weapons + APT/TPA cycle + meta) — export pending |
| `plugins/` | Claude Code plugin skeleton — pending |

---

## License

MIT. See [LICENSE](LICENSE).

## Author

[gj3447@gmail.com](mailto:gj3447@gmail.com) — METAHUMOTONIC.

---

<sub>작업 환경 정전: SYMPOSIUM/CLAUDE.md. KG 노드: `github-repo-plan-airplaneman-framework-2026-05-13` (:GithubRepoPlan:PRELIMINARY → :CANONICAL ratified 2026-05-13).</sub>
