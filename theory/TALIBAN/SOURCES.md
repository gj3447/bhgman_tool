# Taliban (탈레반) — 공학 측 자료집

> **한 줄 정의:** *적대적 검증 framework.* APT 의 *면역 시스템*. Design=G, Taliban=D 의 GAN 협력. Popper 1959 falsifiability 의 LLM 결정화. v0.8.A1 4 LensSet ensemble + Pirsig synthesis. 5무기 family closure 의 *검증 측 종결자* — Prometheus 가 생성, 재배맨 SOP 위에서 작동, Longinus binding 사용.

---

## 0. 본 폴더의 위치

| 파일 | 본질 |
|---|---|
| 본 파일 (`SOURCES.md`) | 1차 소스 + 7 axis 학문 grounding |
| `INDEX.md` ~ `LEAN_REGRESSION_AUDIT.md` | 9 paper-track |
| `taliban_adversarial_runtime_prototype/` | Python 3.11+ (53 pytest PASS) |
| `lean_audit/` | Lean 4 v4.29.1 standalone (24 theorem, 0 sorry) |
| `113_LENS_TAXONOMY.md` | 113 mathematical lens 정전 (2026-05-02 closed) |
| `PROM_32_*.md` | legacy cycle |
| `lessons/`, `_findings/raw/` | 회고 + raw dump |

---

## 1. 핵심 주장 (논문 골격용 7 주장)

1. **탈레반 = APT 의 면역 시스템.** Design=G, Taliban=D, GAN 적대적 협력 (Goodfellow 2014).
2. **Popper falsifiability 의 LLM 결정화.** 만장일치 PASS — any FAIL → final FAIL. 반증 시도 없는 PASS 는 비과학적.
3. **5 LensSet pluggable** (v3.1): constitutional (9) / mathematical (113, 2026-05-02 closed) / solid (5) / longinus (7) / lakatos (4).
4. **v0.8.A1 Ensemble mode** (2026-05-04 RFC): 4 LensSet (const + long + lak + solid) UNION coverage ≥ 0.8. Pirsig 1974 holistic synthesis.
5. **D20 executor ≠ reviewer.** `parent-claude` ↔ `taliban-ensemble-critic` 구조적 분리. self-judge fallacy 차단.
6. **HR11 anti-rubber-stamp.** APPROVED verdict 는 specific evidence (RTI) 인용 의무 — 위반 시 PASS → NEEDS_EVIDENCE 자동 downgrade.
7. **Prometheus → Taliban auto-dispatch** (Step 7-A, SKILL.md prometheus L805-831). 5무기 family closure 의 결정점.

---

## 2. 1차 소스

### 2.1 공학 정본

| 경로 | 내용 |
|---|---|
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/taliban/SKILL.md` | **정본 v3.1.** + v0.8.A1 ensemble |
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/taliban/references/*.md` | references |
| `/Users/lagyeongjun/CD/SERVER/.claude/agents/taliban-ensemble-critic.md` | ensemble agent definition |
| `THEORY/TALIBAN/113_LENS_TAXONOMY.md` | 113-lens 정전 (2026-05-02 closed, 13 domain × {8,9,10}) |

### 2.2 본 SYMPOSIUM 측 PoC

| 경로 | 내용 |
|---|---|
| `taliban_adversarial_runtime_prototype/` | Python 3.11+ (53 pytest PASS) |
| `taliban_adversarial_runtime_prototype/adversarial_runner.py` | `TalibanAudit` + `dispatch_from_prometheus()` |
| `taliban_adversarial_runtime_prototype/ensemble_dispatch.py` | v0.8.A1 UNION + Pirsig synthesis |
| `taliban_adversarial_runtime_prototype/executor_reviewer.py` | D20 강제 |
| `taliban_adversarial_runtime_prototype/rti_fvr.py` | HR11 auto-downgrade |
| `lean_audit/TalibanAudit.lean` | Mathlib-free Lean (24 verified, 0 sorry) |

### 2.3 신화 측

| 경로 | 내용 |
|---|---|
| `METAHUMOTONIC/BHGMAN/taliban/SOURCES.md` | BHGMAN 측 자료집 |

---

## 3. 핵심 인용

### 3.1 SKILL.md

> **다른 방법론들이 "잘 만들자"라면, 탈레반만 "이거 틀렸어"라고 말하는 놈이다.**
> Design = Generator, Taliban = Discriminator. GAN의 적대적 협력.

> **HR11**: Every APPROVED verdict MUST cite specific evidence. Approvals without evidence = RUBBER_STAMP violation.

### 3.2 Goodfellow 2014

> minmax_{G,D} V(D, G) = E_x[log D(x)] + E_z[log(1 − D(G(z)))]
> (Equation 1, NeurIPS 2014)

GAN 의 정확 형식. Taliban = D 의 LLM 시대 결정화.

### 3.3 Popper 1959

> *Eine Aussage ist wissenschaftlich nur, wenn sie falsifizierbar ist.*
> (어떤 주장은 *반증 가능* 일 때에만 과학적이다.)

만장일치 PASS 의 정확 grounding.

### 3.4 Pirsig 1974

> *Quality is not a thing, it is an event.*
> Classical (분석) ∧ Romantic (총체) 의 통일.

v0.8.A1 의 UNION coverage + per-lens verdict 종합의 grounding.

---

## 4. 학문 정전 정확 인용 (7 axis)

→ `AXIS_DEEP_GROUNDING.md` 상세.

### 4.1 A. GAN
- **Goodfellow et al. 2014** *Generative Adversarial Nets* — NeurIPS.
- **Arjovsky et al. 2017** *Wasserstein GAN* — ICML.

### 4.2 B. Popper falsifiability
- **Popper 1959** *Logik der Forschung* / *The Logic of Scientific Discovery*.
- **Popper 1963** *Conjectures and Refutations*.

### 4.3 C. Lakatos
- **Lakatos 1976** *Proofs and Refutations* Cambridge UP.
- **Lakatos 1978** *Methodology of Scientific Research Programmes*.

### 4.4 D. D20 game theory
- **Selten 1965** subgame perfect equilibrium.
- **Nash 1950** *PNAS* 36:48.

### 4.5 E. HR11 (자체 정전)
- SKILL.md `HR11`. anti-rubber-stamp.

### 4.6 F. Pirsig holistic synthesis
- **Pirsig 1974** *Zen and the Art of Motorcycle Maintenance* William Morrow.

### 4.7 G. Adversarial ML
- **Szegedy et al. 2014** *Intriguing properties of neural networks* ICLR.
- **Madry et al. 2018** *Towards Deep Learning Models Resistant to Adversarial Attacks* ICLR.

---

## 5. Industry 비교 (10 방법론)

→ `COMPARISON_METHODOLOGIES.md`. Taliban 만이 5축 (D20 / Multi-lens / HR11 / LLM-native / Lean) 모두 hard-positive.

---

## 6. 5무기 family closure 안에서의 위치

```
                        Prometheus(G)
                              │
                              │ INVOKES_VALIDATOR (Step 7-A 자동)
                              ↓
                          Taliban(D)
                              │
              ┌───── USES_SLOT (SubagentSeeder)──→ 재배맨
              │       (각 lens 가 SubagentTaskSpec 결정화)
              │
              └───── USES_KG_BINDER ──────────→ Longinus
                      (검증 대상 7-Layer 추적)
```

탈레반 = 3 무기 위 *최종 검증자*. **5무기 closure 의 종결자**.

---

## 7. 논문 작성 시 발전 가능 축 (8)

- **(a) GAN Nash equilibrium 의 LLM 적용** — Design ↔ Taliban 의 수렴성 정량.
- **(b) Popper falsifiability 의 형식화** — 만장일치 PASS 의 Lean T6 grounding.
- **(c) Pirsig 의 quality 일자성** — classical (per-lens) + romantic (UNION) 의 변증법.
- **(d) D20 self-judge fallacy** — Selten subgame perfect equilibrium 적용.
- **(e) HR11 evidence cite** — RTI 5 evidence_type 체계.
- **(f) 113 mathematical lens 의 exhaustive coverage proof** (후속 sprint).
- **(g) Lakatos hard core/belt 분리** — 6 hard core + N belt.
- **(h) Adversarial robustness (Madry 2018)** 의 LLM 적용.

---

## 8. KG 정전 노드

| 노드 | 의미 |
|---|---|
| `ATOM_Skill_taliban` | anchor |
| `sv-taliban-v3.1.0` | 이전 |
| `sv-taliban-v3.1.1-2026-05-12` | 신버전 (본 grounding) |
| `taliban-hardening-master-plan-2026-05-06` | hardening plan → GROUNDED PENDING |
| `taliban-adversarial-runtime-prototype-2026-05-12` | Python PoC |
| `taliban-lean-audit-2026-05-12` | Lean audit |
| `rfc-taliban-v08-concern-coverage-2026-05-04` | v0.8.A1 RFC |
| `pirsig-holistic-synthesis-layer-v0.8-2026-05-05` | Pirsig RFC |
| `lesson-taliban-v08-single-lensset-insufficient-2026-05-04` | 단일 LensSet borderline lesson |
| `MIC_v1` + `MethodologySlot:AdversarialValidator` | MIC binding |
| 5 `LensSet` 노드: constitutional / mathematical / solid / longinus / lakatos |  |

# KG: ATOM_Skill_taliban, sv-taliban-v3.1.1-2026-05-12
