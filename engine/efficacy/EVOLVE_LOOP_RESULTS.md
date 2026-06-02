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

## production 이식 — 검증 지식 플라이휠 (step 1-3 BUILT)

이 실험은 *시뮬레이션*으로 thesis를 확증했고, production 닫힌 루프를 `engine/legion/evolve_loop.py`로
배선했다 (단일 에이전트를 이기는 메커니즘 = 검증 지식 복리):

- **step 1 — oracle scalar 어댑터** ✅ `LensScalarOracle`: 나생문 `OracleLens`(boolean PASS/FAIL)를
  `score()→float`로 감쌈 (`to_scalar`: Lean 닫은 goal 수 / pytest pass-ratio / -drift-distance 주입).
- **step 2 — production evolve_loop** ✅ `run_evolve` / `run_sessions`: generate→score→record→
  read_best 닫힌 루프, 정확히 budget oracle-eval(equal-compute), 3 seam(Generator/ScalarOracle/
  CandidateCorpus) DIP로 실 컴포넌트(eureka/LLM/Lean) 교체 가능.
- **step 3 — KG 검증 corpus** ✅ `LocalKgCorpus`(JSON 영속, neo4j 불요) + `InMemoryCorpus`:
  oracle 통과분만 누적(`:EvolveCandidate`, schema 등록) + cross-session read_back = *복리 기억*.

검증(`engine/legion/tests/test_evolve_loop.py`, 6 pass): 같은 corpus 가로질러 세션이 쌓일수록
best **단조 비감소 + 최종 > 첫 세션**(복리) / feedback(steering) OFF면 훨씬 못 도달(load-bearing) /
passed=False는 누적 거부(oracle-gating) / 새 store 재로드 시 이전 세션 검증분 복원(영속).

### 실 컴포넌트 배선 (BUILT — `evolve_adapters.py` / `evolve_ab.py`)

- **실 oracle scalar 파서** ✅ `pytest_pass_ratio`(passed/(passed+failed)), `lean_cleanliness`
  (1/(1+errors+sorry)) + factory `pytest_oracle`/`lean_oracle`(`build_command`으로 후보를 실제
  `pytest -q`/`lake build` 실행). fake runner로 테스트(green), 실 subprocess는 런타임.
- **실 생성기(LLM)** ✅ `LlmGenerator`: `AgentClient`(dual-backend: local vLLM/Ollama 또는
  anthropic) 래퍼. best-K read-back을 프롬프트에 주입(`default_llm_render`) + 토큰 회계
  (`output_tokens`). 주입 transport로 테스트(green, 백엔드 불요), 실 백엔드는 런타임.
- **3-arm equal-budget A/B** ✅ `run_3arm`: BON(blind best-of-B×S) / LOOP_NOMEM(세션내 steering,
  기억 없음) / FLYWHEEL(영속 corpus 복리), 동일 총 oracle-eval. 결정론 demo 실측:
  **BON=16.0 < LOOP_NOMEM=19.0 < FLYWHEEL=20.0, Δ(fly−bon)=+4.0 → REAL_WIN, memory_adds=True.**
  평평(구조 없는) oracle은 NO_SIGNAL. generic이라 LlmGenerator + 실 Lean/pytest oracle에 그대로 꽂힘.
- **학습 환류 다리(천장 돌파)** ✅ `export_training_set`/`write_training_jsonl`: 검증 통과 corpus →
  (task, verified-solution, score) JSONL = inference-time→learning-time. 이 검증셋으로 fine-tune/RL.

### 실 LLM 라이브 런 (dgx qwen ollama, SSH 터널) — 정직한 결과

실 백엔드(dgx ollama qwen2.5 7B/32B)에 SSH 터널로 붙여 end-to-end 라이브 실행함:

- **실 oracle (pytest subprocess)**: test_pass→1.0, test_fail→0.0 ✅ 실 subprocess 작동.
- **실 LLM 생성기**: qwen 7B/32B 실 호출 성공 ✅ (`openai-compat @ localhost:11434`).
- **비-gameable 사전 oracle**: `/usr/share/dict/words` 235,976어 게이트, 가짜 단어 정확 reject ✅.
- **코딩 A/B (`coding_flywheel_ab.py`, qwen 7B, equal 6 calls/arm)**:
  `roman_to_int / valid_parens / rle` 전부 **BON=1.00✓ FLYWHEEL=1.00✓ Δ=0.00 (read_back=3)**.

**정직한 판정 — 파이프라인은 PROVEN, 효능 분리는 toy task로 못 봄**:
실 LLM 런 3종(vowel / dict-vowel / 코딩) 모두 *분리 실패*했는데 일관된 이유가 있다 —
(a) 모델이 1-shot에 푸는 task(7B가 코딩 3/3, 32B가 sequoia 즉시) → BON 포화 → Δ=0
    (이건 equal-compute 명제 그대로: 1-shot 역량 안의 task엔 loop 이득 0),
(b) 모델이 못 푸는/gameable task(7B vowel-soup) → corpus 미seed → 복리 불가.
**플라이휠 lift는 "1-shot 실패하지만 verify-retry로 성공"하는 좁은 헤드룸 band에서만 보인다.**
결정론 실험(`evolve_loop_min`, 24비트 graded 공간)이 lift를 깨끗이 보인 건(Δ+3.43) 그 band를
설계로 보장했기 때문. read_back=3은 corpus seed·누적·read-back이 *실제로 작동*함을 확인한다.

### HARD 셋 라이브 측정 — 진짜 lift 측정 시도, 정직한 NULL/NEGATIVE 결과

헤드룸을 원리적으로 설계한 `HARD_PROBLEMS`(edge-case 다수 + anti-memorization 트위스트:
atoi_clamp 커스텀 clamp / brackets_angle `<>` 추가 / rle_decode / compare_version / simplify_path)로
qwen 7B, 8 calls/arm, 2 trials 라이브 실행:

```
[atoi_clamp]      BON=1.00✓  FLYWHEEL=1.00✓  Δ=+0.00
[brackets_angle]  BON=1.00✓  FLYWHEEL=1.00✓  Δ=+0.00
[rle_decode]      BON=1.00✓  FLYWHEEL=0.67   Δ=-0.33   ← best-K 피드백이 오히려 해침(anchoring)
[compare_version] BON=1.00✓  FLYWHEEL=1.00✓  Δ=+0.00
[simplify_path]   BON=1.00✓  FLYWHEEL=1.00✓  Δ=+0.00
TOTAL solved: BON=5/5  FLYWHEEL=4/5  mean Δ=-0.067
```

**정직한 결론 (네 번째 일관된 측정)**: qwen 7B는 HARD 트위스트 문제도 전부 1-shot에 풀었다
(BON=5/5). 헤드룸을 못 만들었다 — 그리고 rle_decode에선 FLYWHEEL이 **더 나빴다**(Δ-0.33):
best-K(이전 시도) 컨텍스트가 stochastic 샘플을 anchoring/distract시켜 해친 것. 이는 equal-compute
문헌의 두 예측을 *실 LLM 실코딩에서 동시 확증*한다: (1) 1-shot 역량 안의 task엔 멀티스텝 이득 0,
(2) 멀티에이전트/피드백은 anchoring·conformity로 **net harm**도 가능.

**메커니즘은 거짓이 아니다 — task headroom 문제다.** 결정론 실험(`evolve_loop_min`, 24비트 graded
공간)은 헤드룸을 *설계로 보장*해 lift를 깨끗이 보였다(Δ+3.43). 실 LLM에서 그 band("1-shot 실패
∧ retry 성공")는 손으로 쓴 kata로는 안 잡힌다 — qwen 7B가 전부 1-shot하거나(포화) 전부 실패(미seed).

**진짜 lift 측정의 전제조건 = 그 band를 실제로 차지하는 벤치마크**: SWE-bench Verified류 실버그,
경시대회 hard, 또는 *훨씬 약한 모델*(0.5B/1.5B)에 중간 난도. 이건 데이터/모델 큐레이션이지 배선이
아니다. harness(`coding_flywheel_ab.py`)는 그 셋만 꽂으면 바로 돈다. 4회 일관 결과로 toy 사냥은
중단(p-hacking 회피). + fine-tune/RL 환류는 GPU 별 프로젝트.

**한 줄**: 파이프라인은 라이브로 완전 작동(실 LLM+실 pytest+corpus 복리 read_back=4 확인). 진짜 lift는
결정론 헤드룸에선 +3.43으로 증명됐고, 실 LLM 실측은 within-competence라 0~약간 음수 — 메커니즘이
아니라 *task가 헤드룸 band를 안 차지*해서다. 이게 정직한 종착.
fine-tune/RL 실행은 GPU 학습 인프라(별 프로젝트); export가 그 입력 artifact를 생산. 자격 task:
Lean 증명 / 테스트 동반 refactor / KG drift 수복 / occam supersession (결정론 verifier 보유분만).

### 재배맨 dispatch-policy fix 실 LLM 확증 — harm 제거 검증 (qwen 7B, 3-way)

HARD 셋 측정이 드러낸 결함(best-K mode-lock으로 rle_decode 등 FLYWHEEL<BON)을 재배맨
`oracle_gated_dispatch`(1-shot→풀리면 early-exit / miss면 explore+feedback escalate)로 고친 뒤
**실 LLM로 재측정** (budget 6, 2 trials, BON vs 구 pure-feedback FLYWHEEL vs 신 DISPATCH):

```
[atoi_clamp]      BON=1.00  FLYWHEEL_old=0.95  DISPATCH_new=1.00   evals=1.5
[brackets_angle]  BON=1.00  FLYWHEEL_old=1.00  DISPATCH_new=1.00   evals=1.0
[rle_decode]      BON=1.00  FLYWHEEL_old=0.33  DISPATCH_new=1.00   evals=1.5   ← harm 제거
[compare_version] BON=1.00  FLYWHEEL_old=1.00  DISPATCH_new=1.00   evals=1.5
[simplify_path]   BON=1.00  FLYWHEEL_old=1.00  DISPATCH_new=1.00   evals=1.0
MEAN Δ: flywheel_old=-0.143   dispatch_new=+0.000
HARM(arm<bon): flywheel_old=2/5   dispatch_new=0/5
```

**확증**: 구 pure-feedback FLYWHEEL은 2/5에서 BON을 *해침*(rle_decode 1.00→0.33, mean Δ-0.143).
신 `oracle_gated_dispatch`는 **harm 0/5, Δ+0.000으로 BON과 동일** (1-shot solve→early-exit). 게다가
**evals ~1-1.5** vs BON 6 = **~4-6배 싸다**. 단 7B는 within-competence(전부 1-shot solve)라 이 0-harm은
*early-exit 덕*이지 dominance가 아님 — 헤드룸에선 다르다(아래).

### 헤드룸 regime 측정 — 약모델 1.5B (첫 LLM lift 신호 + 정정)

7B는 다 1-shot이라 헤드룸이 없었다. **약모델 qwen 1.5B**(PROM의 genuine-lift 4조건 중 "약모델")로
진짜 헤드룸 확보 후 BON(blind 6) vs DISPATCH(gated, explore_prob 0.4) 측정(n=1, noisy):

```
[atoi_clamp]      BON=0.90  DISPATCH=0.70  Δ=-0.20
[brackets_angle]  BON=0.50  DISPATCH=0.88  Δ=+0.38   ← LIFT
[rle_decode]      BON=0.17  DISPATCH=0.33  Δ=+0.17   ← LIFT
[compare_version] BON=0.83  DISPATCH=0.67  Δ=-0.17
[simplify_path]   BON=1.00  DISPATCH=0.67  Δ=-0.33
MEAN: BON=0.680  DISPATCH=0.648  Δ=-0.032   LIFT 2/5  HARM 3/5
```

**두 가지 정직한 발견**:
1. **LLM 플라이휠 lift가 처음으로 관측됨** — brackets_angle +0.38, rle_decode +0.17. 약모델이 best-K
   피드백으로 실패 케이스를 실제로 고쳐 blind보다 나아짐. 메커니즘이 LLM에서 *작동*한다(결정론 실험
   Δ+3.43이 LLM에서도 재현 가능함을 처음 확인).
2. **그러나 net wash(Δ-0.032), 3/5 harm** — 그리고 이게 앞선 "dispatch는 구조적으로 BON 못 밑돈다"
   주장을 **반증**한다(정정함). 원인: equal budget에서 escalation이 explore_prob=0.4로 blind 예산을
   feedback과 trade → 모델이 feedback 활용 못 하는 문제(atoi/compare/simplify)에선 blind가 적어져 손해.

**종합 — positive lift band의 정확한 조건**: lift는 (task headroom ∧ 모델이 feedback 활용 가능) 둘 다
성립할 때만. 7B=feedback 활용 가능하나 헤드룸 없음(1-shot). 1.5B=헤드룸 있으나 feedback 활용이 들쭉날쭉
(2/5만 성공). band가 좁다. 정책 보정 방향(데이터 기반, 미적용): explore_prob 상향(blind 예산 보존) 또는
escalation을 "BON 위에 feedback 추가"형으로(blind를 줄이지 않게) + n 증가로 노이즈 축소. n=1 noisy 경고.

# KG: prom16-bhgman-ci-design-2026-06-02, lesson-bhgman-collective-intelligence-design-2026-06-02,
#     jaebaeman-planfirst-essence-reframe-2026-05-27, 7cmd-measurement-driven-conditional-dispatch-2026-05-30
