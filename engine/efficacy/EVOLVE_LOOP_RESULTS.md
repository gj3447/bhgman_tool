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

**남은 것 = 헤드룸 벤치마크 큐레이션(데이터 작업, 배선 아님)**: 1-shot이 신뢰성 있게 실패하는
task(SWE-bench류 실버그 / 경시대회 문제 / 다수 edge-case로 부분점수 나는 문제) 셋을 모아야
실 LLM에서 flywheel lift가 측정된다. harness(`coding_flywheel_ab.py`)는 그 셋만 꽂으면 바로 돈다.
p-hacking(positive 나올 때까지 task 사냥) 회피 위해 toy task 튜닝은 중단. + fine-tune/RL은 GPU 별 프로젝트.
fine-tune/RL 실행은 GPU 학습 인프라(별 프로젝트); export가 그 입력 artifact를 생산. 자격 task:
Lean 증명 / 테스트 동반 refactor / KG drift 수복 / occam supersession (결정론 verifier 보유분만).

# KG: prom16-bhgman-ci-design-2026-06-02, lesson-bhgman-collective-intelligence-design-2026-06-02
