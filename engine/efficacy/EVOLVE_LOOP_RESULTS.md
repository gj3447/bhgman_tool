# evolve-loop 효능 실험 — verification-grounded composition (FunSearch loop)

PROM 3종(`prom16-ma-intel` / `-eci-existence` / `-bhgman-ci-design`)의 결론을 *재는* 실험.
질문: **bhgman의 결정론 oracle을 가진 task에서, generate→oracle.score→accumulate→generate
루프가 같은 oracle-eval 예산의 blind best-of-N을 이기나? 그 이득은 "더 많은 compute"인가
"oracle-steerable 구조"인가?**

순수 함수 + 결정론(seed). oracle = 결정론 scalar scorer로 추상화(우리가 정의 = ground
truth, 비순환). 양 arm **정확히 동일 oracle-eval 예산**(equal compute). 재현:

```bash
uv run python -m engine.efficacy.evolve_loop_min_experiment   # 최소: 단일 셀 + 구조-실현 게이트
uv run python -m engine.efficacy.evolve_loop_max_experiment   # 최대: α×T 스윕 + 이질성 + 스케일
uv run pytest engine/efficacy/tests/test_evolve_loop_min_experiment.py \
              engine/efficacy/tests/test_evolve_loop_max_experiment.py -q   # 11 passed
```

---

## 최소 실험 (`evolve_loop_min_experiment.py`)

3 arm × 2 landscape, n=30 seeds, budget=256 evals:

| landscape | LOOP | BoN | ablation(피드백제거) | Δ(loop−bon) | perm p |
|---|---|---|---|---|---|
| **STRUCTURED** (locality 有) | **22.30** | 18.87 | 18.17 | **+3.43** | **0.0000** |
| **SHUFFLED** (구조 파괴) | 18.50 | 18.50 | 18.70 | +0.00 | 1.0000 |

**GATE: REAL_WIN** — 구조서 유의 우위 + 구조 파괴 시 이득 소멸 = oracle-steering 진짜.

읽기:
- STRUCTURED서 LOOP가 BoN을 **+3.43 (p<1e-4)** 이긴다. ablation(무작위 부모, 피드백 제거)은 BoN 수준(18.17)으로 붕괴 → **피드백이 load-bearing**.
- SHUFFLED(같은 점수 분포, locality만 제거)서 이득 **0.00, p=1.0** → 구조가 없으면 loop는 그냥 best-of-N.
- 이 "구조 없으면 소멸"이 핵심 증거: 이득은 더 많은 compute가 아니라 **oracle가 드러내는 구조**에서 온다.

---

## 최대 실험 (`evolve_loop_max_experiment.py`)

Δ(LOOP − BoN), α=구조(steerability) × T=예산, n=30 seeds (양 arm 동일 eval):

| budget \ α | α=0.0 | α=0.25 | α=0.5 | α=0.75 | α=1.0 |
|---|---|---|---|---|---|
| **T=64** | +0.27· | +0.18· | +1.02✅ | +1.58✅ | +1.77✅ |
| **T=128** | +0.17· | +0.06· | +1.30✅ | +2.77✅ | +3.27✅ |
| **T=256** | +0.20· | +0.32· | +1.58✅ | +3.19✅ | +4.10✅ |
| **T=512** | -0.13· | +0.04· | +1.58✅ | +3.41✅ | +4.37✅ |
| **T=1024** | -0.20· | +0.07· | +1.73✅ | +3.32✅ | +4.10✅ |

(✅ = REAL_WIN: Δ>0.5 ∧ perm p<0.01. · = NO_SIGNAL)

- **monotone-in-α = True, zero-at-α0 = True** (전 예산). 이득이 구조에 단조 증가하고, 구조 없으면(α=0) ~0 — 심지어 큰 예산서 살짝 음수(정직: 구조 없을 땐 elitism이 탐색을 좁혀 살짝 손해).
- **HETEROGENEITY** (α=1, T=256): homo(단일 변이연산자)=22.83 vs hetero(다양 연산자 1,2,4)=23.30, Δ=+0.47, **perm p=0.054** → "미미/없음". 문헌(finding-bci-C1, Self-MoA)의 "이질성 이득은 조건부, 공짜 아님"과 일치 — search-operator 다양성만으론 유의하지 않음.

---

## 결론 — bhgman 설계로 무엇을 말하나

1. **win은 진짜지만, oracle-steerable 구조에서만.** α↑에 단조, α=0서 0. → bhgman은 **결정론 verifier가 후보 점수에 구조를 부여하는 task**(Lean proof goal 수, pytest pass-ratio, cypher drift-distance, occam dead-node 수)에서만 equal-compute win을 얻는다. verifier 없는/평평한 task(서사·canon·주관 평가)는 α≈0 = 이득 0 = net loss 위험.
2. **피드백(accumulate→read best→steer)이 load-bearing.** ablation이 BoN으로 붕괴 → "fan-out 더 키우기"가 아니라 "loop 닫기"가 본질. 선행 PROM 결론 경험적 재확인.
3. **이질성은 보조.** 다양 연산자 이득 미미(p=0.054) → 4-lever ROI에서 heterogeneity 최저라는 finding-bci-D4와 정합.
4. **정직 라벨**: 이 win조차 "oracle로 채널링된 탐색"(search+verifier)이지 창발적 집단 IQ가 아니다. 단 real capability(blind이 못 찾는 optimum을 찾음) — FunSearch가 새 수학을 찾듯.

## 다음 (production 이식, 미구현)

이 실험은 *시뮬레이션*으로 thesis를 falsifiable하게 확증한다. production 이식(별도 작업):
`engine/legion/evolve_loop.py` 신설 → eureka.generate → `engine/naesengmoon/oracle_lens.py`에
`score()→float` 어댑터(Lean sorry 수 / pytest pass-ratio / cypher-recount delta) → KG에
점수付 :Candidate 누적 → best-K read-back. 자격 task: Lean 증명 / 테스트 동반 refactor /
KG drift 수복 / occam supersession. 검증: 3-arm equal-token A/B(LLM 실호출)로 본 시뮬레이션
결과가 실제 LLM 생성기에서도 재현되는지.

# KG: prom16-bhgman-ci-design-2026-06-02, lesson-bhgman-collective-intelligence-design-2026-06-02
