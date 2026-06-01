# 오캄 정량 scoring + 온톨로지 DL 정합성 — 이론 grounding

> 오캄(Occam) LegionCommander의 "롱기누스급 엄밀성" 요구에 대한 응답.
> 그동안 오캄은 철학 grounding(Ockham→Bayes→Kolmogorov→MDL→AGM)은 풍부했으나
> **코드/형식화/정량 metric이 얕았다** (Confidence가 HIGH/MEDIUM 2값 enum, σ 부재,
> 온톨로지는 손으로 친 cypher pass). 이 문서 + `scoring.py` + `ontology.py` + Lean이 그 공백을 채운다.

## 1. 연속 supersession score σ ∈ [0,1]

정전 `consensus-occam-entropy-truth-2026-05-26`의 **"entropy selects, truth-guard gates"**를 정량화:

```
σ = candidacy(C) · guard(G)
```

### candidacy C — "entropy selects" (noisy-OR of 3 독립 obsolescence 증거)

| 성분 | 정의 | 학문 정전 |
|---|---|---|
| redundancy r | 동일 sha twin=1.0, 아니면 line-count 겹침 비율 | MDL (Rissanen 1978) / Kolmogorov·Solomonoff — "compressible = clutter" |
| staleness s | `1 − 2^(−age/halflife)`, age=halflife→0.5 | 망각곡선 (Ebbinghaus 1885), 지수감쇠 |
| deadness d | `2^(−invocation/scale)`, inv=0→1.0 | 사용기반 (lesson-occam-needs-invocation-log-2026-05-28) |

```
C = 1 − (1−r)(1−s)(1−d)        (noisy-OR, Pearl 1988 — 한 신호만 강해도 C↑)
```

### guard G — "truth-guard gates" (거부권)

```
G = (1 − e) · twin_gate
```

- **entrenchment e** — AGM epistemic entrenchment (Gärdenfors–Makinson 1988). `canonical/lesson/contract/verdict = e=1.0 ⇒ G=0 ⇒ never archive` (정전 tier). 아래로 ordinal 감소.
- **twin_gate** — AGM contraction은 후속자 없이 믿음을 버리지 않는다. 살아있는 twin/후속 노드 부재 ⇒ gate=0 ⇒ σ=0 (**machloket / Eilu va-Eilu: flag만, supersede 금지**).

### verdict (KG `dt-occam-*` threshold grounded)

- `σ ≥ 0.7` (dt-occam-naesengmoon-confidence) → **SUPERSEDE**
- `0.3 ≤ σ < 0.7` → **VERIFY** (나생문 dispatch)
- `σ < 0.3` → **KEEP**
- `e=1.0` → **PROTECTED** / twin 부재 → **FLAG_ONLY**

> **보수성 정리**: 온톨로지 클래스(e=0.7)는 완전 stale·중복이어도 σ 최대 = 1·(1−0.7) = 0.3 →
> **절대 auto-SUPERSEDE 불가, 항상 VERIFY**. 침묵 자동삭제 금지(covenant)가 entrenchment로 강제됨.

## 2. 온톨로지 DL 정합성 (`ontology.py`)

단순 dedup을 넘어 **형식 온톨로지 / Description Logic 정합성** 검사. 𝒮ℛ𝒪ℐ𝒬(D) = OWL 2 DL 기반.

| # | 검사 | 종류 |
|---|---|---|
| 1 | SUBSUMPTION_CYCLE — subClassOf DAG 위반 | 논리 비정합 |
| 2 | DANGLING_PARENT — 없는 상위 클래스 subClassOf | 무결성 경고 |
| 3 | DANGLING_TYPE — 없는 클래스 rdf:type | 무결성 경고 |
| 4 | PUNNING — class ∧ instance 동명 (라벨충돌) | 무결성 경고 |
| 5 | UNSATISFIABLE_CLASS — 두 disjoint 상위의 공통 하위 ⇒ ⊥ | 논리 비정합 |
| 6 | DISJOINTNESS_VIOLATION — instance가 disjoint 두 type | 논리 비정합 |

`is_consistent` = 1·5·6 부재. 위생(stale/dup 클래스)은 §1 σ로 점수화 → covenant(삭제 0, twin 없으면 flag) 유지.

학문 정전: Baader et al. *The Description Logic Handbook* (2003/2007); W3C OWL 2 (2012); Gruber (1993); Guarino (1998).

## 3. Lean 형식화 (`lean/Occam_SupersessionScore.lean`, Mathlib-free)

[0,1]을 0..1000 basis-point 정수로 mirror. 증명된 안전 불변식 6:

1. `score_le_candidacy` — σ ≤ candidacy mass
2. `score_le_scale` — σ ≤ SCALE (경계)
3. `protected_score_zero` — e=SCALE ⇒ σ=0 (canonical never archive)
4. `no_successor_zero` — twin 부재 ⇒ σ=0 (machloket)
5. `score_antitone_entrench` — entrenchment↑ ⇒ σ↓ (truth-guard 단조성)
6. `candidacy_le_scale` — noisy-OR ∈ [0, SCALE]

+ 수치 sanity 4 (`#decide`): guard at canonical=0 / plain=SCALE / σ(완전후보,plain)=SCALE / σ(완전후보,ontology e=700)=300.

## 4. 테스트

- `tests/test_scoring.py` — decay 정확값 + noisy-OR formula + 경계·단조성 property-based(hypothesis) + verdict + config 검증.
- `tests/test_ontology.py` — 6종 DL 위반 탐지 + scored 위생 covenant.
- `tests/test_occam.py` — occam_pass score_meta 통합 (redundancy는 occam dedup이 권위).

# KG: occam-kam-canonical-2026-05-26, consensus-occam-entropy-truth-2026-05-26,
#     occam-quant-scoring-engine-2026-06-01, verdict-user-occam-gains-ontology-hygiene-responsibility-2026-05-27
