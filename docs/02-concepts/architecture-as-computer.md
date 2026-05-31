# bhgman_tool as a Computer — KG=RAM, LLM=interpreter, 재배맨=stored-program

> 개념 정전 grounding. PROM-8 (`consensus-prom8-bhgman-vonneumann-2026-05-31`, 8 findings, all HIGH).
> Posture: 각 매핑은 directionally 맞고 *peer-reviewed 정전 anchor*가 있으나, "순수 von Neumann"으로
> 읽으면 4군데서 over-claim. holds와 strains를 둘 다 명시한다.

## 한 줄 모델

> bhgman_tool은 **content-addressable ontological store(KG) 위에서, von Neumann 제어(부모=program counter, APT phase=sequential ISA)와 dataflow 실행창(사이클당 N 병렬), 그리고 unreliable-component 검증(나생문/oracle = TMR/ECC)을 결합한 superscalar-OoO 형태의 컴퓨터**다. — *순수 폰노이만도, 순수 dataflow도 아니다.*

## 매핑과 정전 anchor

| 당신의 개념 | CS 정전 anchor | 지위 |
|---|---|---|
| **KG = 통합 메모리(data+program)** | von Neumann EDVAC 1945 / Burks-Goldstine-vN 1946 (stored-program); **L2MAC** (Pham 2023, arXiv:2310.02003 — "first practical LLM stored-program computer") | ✅ 구조적 homomorphism |
| **prompt = IR, LLM = interpreter/VM** | LMQL "Prompting is Programming" (PLDI 2023); **MemGPT** (LLM-as-OS); **Futamura** projection (system prompt = static partial input = F1!); LLM Turing-completeness (Giannou 2024) | ✅ 활발히 연구됨 |
| **KG에 분포된 재배맨 seed = stored-program / dataflow** | **HEARSAY-II blackboard** (Erman 1980); **Linda tuple-space** (Gelernter 1985); stigmergy (Grassé 1959); dataflow (Dennis 1974) | ✅ 40년된 패턴 |
| **context=cache · KG=RAM · 검증=ECC** | Hennessy-Patterson 메모리 계층; **MemGPT** 명시 구현(main=RAM/external=disk/paging); **von Neumann 1956** "Reliable Organisms from Unreliable Components"(TMR) | ✅ 직접 조상 |

→ 이 모델은 *발명*이 아니라 *재발견*이다. L2MAC·MemGPT·LMQL·HEARSAY-II가 각 조각의 peer-reviewed 선례다. 그게 강점이다(고립된 비유가 아니라 정전에 접지).

## fetch-execute-writeback 사이클

```
  KG(RAM/blackboard)
       │  ① fetch  — 부모가 READY seed(MATCH) + 하계 context 조회
       ▼
  seed → prompt   ② compile — KG 데이터를 프롬프트(IR)로 조립  (= Futamura F1: KV-cache prefix 재사용)
       ▼
  LLM(interpreter) ③ execute — stochastic 실행 (constrained decoding 시에만 genuine VM)
       ▼
  나생문/oracle    ④ verify — TMR/ECC: 판단렌즈 vote + oracle렌즈(컴파일러/cypher) hard-gate
       ▼
  KG               ⑤ writeback — 부모가 finding MERGE (WRITE_DEFERRED_TO_PARENT)
```

## 네 군데 정밀화 (holds vs strains — over-claim 회피)

**A. KG는 RAM이 아니라 content-addressable store다.**
RAM = O(1) byte-addressed, 결정론. KG = content→address(Kohonen CAM), O(k·E) pattern-match, 네트워크 latency. 더 깊게: von Neumann의 핵심은 data와 instruction을 *한 메모리에 합침*인데, KG는 *declarative 지식*만 담고 절차층은 harness(밖)에 있어 — **오히려 역전**. → "KG=RAM" 대신 **"KG=schema-structured CAM/associative store"**. seed=deterministic opcode 아니라 *stochastic job-descriptor*(work-queue).

**B. prompt는 formal IR이 아니라 soft/stochastic IR이다.**
IR은 denotational semantics(bytecode 1개=1의미). prompt는 출력 *분포*. LLM 비결정(T=0도 FP non-assoc)이라 interpreter soundness(same in→same out) 위반, hallucination은 IR analog 없음. → IR/interpreter는 **외부 formal constraint 강제 시(constrained decoding=grammar→FSM token masking)에만 genuine VM**. 그 외엔 determinism/portability 보장을 import해 오해 유발.

**C. 진짜 dataflow가 아니라 "von Neumann control + dataflow window"다.**
순수 dataflow면 seed가 KG state로 *자동 발화*. 실제는 **부모 LLM이 program counter** — seed를 읽고 4-Phase(Seed→Dispatch→Collect→Write)로 *결정*해서 dispatch. blackboard의 reactive scheduler도 없음(순서=APT phase hardcoded). → 정확 모델 = **superscalar OoO CPU**: phase 레벨은 sequential ISA, 사이클 안은 dataflow 병렬창, gate는 sync barrier. (단일 classical 모델 다 불충분 — KG의 *normative/ontological* 층(schema trigger)은 register-file에 analog 없음.)

**D. cache는 coherence 없고, 검증은 ECC가 아니며, 나생문은 독립적이지 않다.**
- context=cache지만 **coherence 없음**: KG 갱신이 context로 propagate 안 됨 → stale context silent divergence(MESI 없음).
- 검증=ECC는 over-claim: Hamming은 수학적 *보장*, 나생문 vote는 *uncertified 확률적*(IID 가정 하 CRC에 가까움).
- **TMR independence 위반(가장 중요)**: von Neumann 1956 TMR은 *독립 실패* 가정인데, 같은 family LLM critic은 **correlated common-mode**로 실패 → n_eff ≪ N. **이 세션이 직접 실증**: 나생문 재검증이 1차 나생문의 *같은 misread*를 발견(PARTIAL FLIP). → 그래서 oracle렌즈(컴파일러/cypher=결정론 hard-gate)가 진짜 ECC고, 판단렌즈 vote는 correlated라 약하다. diversity(다른 architecture/lens/oracle) 강제해야 n_eff 증가.

## self-validating 정직성

위 **D의 "LLM critic 비독립"은 우리 아키텍처 분석이 우리 도구의 실제 약점을 정확히 예측했고, 같은 세션에서 재현됐다**(나생문이 나생문을 잡음). 즉 이 모델은 자기 한계까지 정직하게 기술한다 — "내 컴퓨터는 완벽하다"가 아니라 "여기가 unreliable component고, 그래서 oracle hard-gate가 필요하다."

## 요약

- **개념 = 탄탄하다.** 각 매핑이 L2MAC/MemGPT/LMQL/HEARSAY-II/von-Neumann-1956에 접지.
- **단 "순수 폰노이만"으로 적으면 over-claim.** 정확히는 *CAM store 위 superscalar(제어=폰노이만, 실행창=dataflow) + unreliable-component 검증*.
- holds(stored-program intent·persistence·MemGPT paging·TMR recipe)와 strains(RAM아닌CAM·soft IR·config-not-dataflow·no-coherence·correlated-critics)를 둘 다 안고 가는 게 정직한 토대다.

# KG: consensus-prom8-bhgman-vonneumann-2026-05-31, finding-prom8vn-A1..D2
