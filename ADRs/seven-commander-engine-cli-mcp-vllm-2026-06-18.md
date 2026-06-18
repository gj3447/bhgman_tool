# ADR: 7군단장 = 균일 엔진 (CLI + MCP + 측정-게이트된 vLLM enrich)

- **Status**: PRELIMINARY (propose). 두 verdict 대기:
  (1) 본 아키텍처 CANONICAL 승인,
  (2) **commander별 vLLM-enrich scope = 효능 preflight 측정 결과**(blanket 금지).
- **Date proposed**: 2026-06-18
- **KG ref**: `adr-seven-commander-engine-cli-mcp-vllm-2026-06-18`
- **Parent constraints**:
  - `adr-seven-commander-legion-architecture-2026-05-27` (7군단장 in-process 합성, substrate=KG, Contract-bound handoff, 닫힌 루프)
  - `adr-bhgman-tool-in-process-default-2026-05-19` (commander↔commander = in-process, RPC 마이크로서비스 아님)
  - `project_legion_unification_kg_engine_2026_06_01` (**결정론 코어 = 정체성·바닥 / LLM = optional enrichment**)
  - `project_bhgman_ab_falsifier_2026_05_30` (도구예산 통제 후 LLM 인지기여 ≈ 0, 가치 = operational substrate)
  - `project_efficacy_measurement_line_2026_06_01` (효능주장 전 **preflight 3-falsifier**[순환성/신호부재/신호역전] 게이트 필수, `engine/efficacy/`)
- **Authority**: 사용자 발화 2026-06-18 "비행기맨 7대 도구들이 거의 engine급으로 cli·mcp 통해서 각각 (dgx vllm) api 써서 돌아갔으면" + verdict "**먼저 측정부터**(vLLM가 실제 도움되는 군단장만)" + "**설계(ADR)만 먼저, 코드 다음**".

---

## Context

PROM 16(engine/OS 설계) 자가진단이 드러낸 현 상태:

| 측면 | 현 상태 | gap |
|---|---|---|
| **vLLM 백엔드** | 🟢 이미 배선 — `agents/client.py::AgentClient` dual-backend가 `BHGMAN_LLM_BASE_URL` → dgx vLLM(OpenAI-compat, Qwen)에 무의존 urllib로 붙음. graceful degrade. | LLM 군단장 **3개만**(prom/나생문/재배맨) 사용 |
| **CLI** | 🟢 7군단장 전부 subcommand (`prom/tlb/longinus/oc/hd/eu/jb/harness/legion/bot`) | 균일 facade 아님 (1623줄 ad hoc) |
| **MCP** | 🟡 **4/7만** 노출 (`prometheus/longinus/taliban/harness` + apt/tpa) | **occam·eureka·hades·legion·재배맨 MCP 도구 없음** |
| **결정론 4군단장** | 🟢 KG 엔진 (longinus/occam/eureka/hades) | **vLLM 경로 자체가 없음** — `commanders.py`의 `if client:` 분기가 prometheus·naesengmoon에만 |

**핵심 충돌(열어둠)**: "7개 다 vLLM" 직관은 부모 정전 `project_bhgman_ab_falsifier`와 부분 충돌한다 — A/B falsifier에서 *도구예산 통제 후 LLM 인지기여 ≈ 0*이 측정됐고, occam(중복정리)·hades(실현) 같은 결정론 본령에 vLLM을 박으면 latency만 늘고 측정 이득 ≈ 0일 위험. 사용자 verdict로 해소: **blanket-vLLM 금지, 측정-우선**.

## Decision

### D1. 7군단장 = 단일 `CommanderEngine` 모양 (균일 엔진화)

각 군단장을 *동일한 4-슬롯 엔진*으로 통일한다 (현재 CLI/MCP/legion이 따로 노는 것을 한 facade로):

```
CommanderEngine (uniform shape, per commander)
├─ deterministic_core(ctx) -> provides     ← 정체성·바닥. 인프라 0, KG만으로 동작·테스트 가능
├─ vllm_enrich(ctx) -> provides | None      ← OPTIONAL. client 있을 때만. 측정 게이트 통과한 군단장만 (D2)
├─ cli_binding                              ← parser subcommand (이미 있음, facade로 흡수)
└─ mcp_tool                                 ← registry + tools/<cmd>.py (gap 메움, D3)
```

- **floor 불변**: `deterministic_core`는 항상 존재하고 항상 먼저 시도된다. vLLM은 *그 위에 얹는 enrichment*이지 gate도 필수도 아님 (`legion_unification` 계승). client 없음/실패 → graceful degrade → 결정론 코어.
- **in-process-default 유지**: commander↔commander는 여전히 in-process(legion substrate). **vLLM만 외부 API** — 외부 LLM 백엔드 호출은 RPC 마이크로서비스화가 아님(부모 ADR 무위반). 각 엔진이 "자기 dgx vLLM api 써서 돈다"는 *이 enrich 슬롯*의 의미.
- "거의 engine급"의 구체화 = 7개가 (a) 독립 CLI 호출 (b) 독립 MCP 도구 (c) legion 닫힌 루프 stage — **3 진입점을 한 코어가 공유**.

### D2. vLLM-enrich scope = 효능 preflight 측정 게이트 (blanket 금지) — *측정-우선 verdict*

**어느 결정론 군단장이 `vllm_enrich` 슬롯을 갖는지는 측정이 결정한다.** 직관·욕망으로 박지 않음.

- 게이트 = 기존 `engine/efficacy/` **preflight 3-falsifier**(순환성/신호부재/신호역전) + cheap A/B. *재발명 금지, 이 라인 통과 필수* (`project_efficacy_measurement_line`).
- 절차(군단장 X마다): `deterministic_core(X)` vs `deterministic_core(X) + vllm_enrich(X)` 를 X 본령의 *borrowed test*(인용 이론 자체 falsifiable test, `feedback_efficacy_via_borrowed_theory_tests`)로 A/B → preflight 3-falsifier 통과한 **양(陽)의 신호만** enrich 슬롯 승격.
#### D2-측정 (2026-06-18, `efficacy/VERDICT.md` 2026-06-02 sweep 적용)

측정은 *이미 돌렸다* — 7군단장 전부 non-circular oracle로 잼(`falsifier.py` preflight). 헤드라인: **equal tool budget에서 인지적 우위 군단장 = 0** (두 독립 측정선 수렴). 이걸 vLLM-enrich scope에 적용:

| 군단장 | 실측 | vLLM-enrich verdict |
|---|---|---|
| occam | AUC 0.602, twin redundancy 약함(age/invocation 캐리), σ A/B preflight **INVERTED**(twin 41<59) | **REJECT** (측정확정) — deterministic-only |
| hades | 0.839 = operational completeness(test-reachability), 인지 locus 無 | **REJECT** — 순수 mechanism, 판단 locus 없음 |
| jaebaeman | 1.000 = dispatch fidelity | **REJECT** — 인지 아님 |
| longinus | synthetic Δ+0.227 → **실 git Δ+0.050**(noise, 4.5× 부풀림) | **REJECT** — sha256 결정론 코어 유지 |
| naesengmoon | mutation-catch 0.52 = base-LLM 동급, 가치=oracle렌즈(환각불가 precision) | **KEEP LLM, no-win** — 판단렌즈 유지하되 oracle이 본가치 |
| prometheus | verifiability 0.931 / novelty 0.933 = 진짜 synthesizer | **KEEP LLM** ✅ — vLLM 실제 작동, 이미 배선 |
| eureka | +1.000 = planted best-case, 실 KG = synchronic cover(7/319) | **OPEN** — FCA floor + vLLM 개념명명, *유일 미측정·그럴듯* locus → cheap A/B 후보(`eureka_naming_ab`) |

추가로 측정상 유일한 양의 신호 = **competence-boundary repair-LOOP**(per-commander enrich 아님, oracle-gated loop 구조): Lean error-feedback repair가 best-of-N 이김 **p=0.016 @ qwen 32b**. ⚠️ 32b raw JSONL 미커밋=historical/미확정, 7b 재핀=NULL → dgx 32b 재실행+커밋해야 확정.

**결론**: 4 REJECT(측정확정) + 2 KEEP-LLM + 1 OPEN(eureka). NULL은 "deterministic-only"로 정직 라벨(vLLM 미장착 ≠ 결함). 잴 가치 남은 lever 2개뿐 — (a) eureka 개념명명 A/B (b) 32b repair-loop 재현. 둘 다 dgx vLLM 가용 시 라이브.

### D3. MCP 패리티 (명확한 gap, vLLM scope와 독립)

`occam / eureka / hades / legion / 재배맨`을 MCP 도구로 신설. 기존 패턴 그대로:
- `mcp_server/tools/<cmd>.py` (occam/longinus와 동일 — 코어는 인프라 0, `--apply` 시에만 KG write)
- `registry.py::TOOL_CATALOG` + `security.py::TOOL_CAPABILITIES` 등록 (single-source 규율, `catalog_is_consistent_with_security` 통과)
- 결과: 7군단장 전부 **CLI ∧ MCP 양쪽**에서 호출 가능 (현재 CLI 7/7, MCP 4/7 → 7/7).
- **이 작업은 vLLM 측정과 독립** — 결정론 코어를 MCP로 노출하는 것이라 D2 verdict 없이 선행 가능.

## Consequences

**좋음**: "7개가 각각 엔진처럼 cli·mcp로 돌고 dgx vLLM 쓴다"는 목표를 *정전 충돌 없이* 달성 (vLLM = 측정-게이트된 enrich, 결정론 floor 불변). MCP 7/7로 외부(Claude Code·다른 MCP 클라이언트)에서 균일 호출. CommanderEngine facade가 CLI/MCP/legion 3 진입점의 drift를 막음.

**비용/리스크**:
- vLLM-enrich를 4 결정론 군단장에 *측정 없이* 박으면 A/B falsifier 정전 위반 + occam/hades latency↑ 이득0. → D2 게이트가 방어.
- dgx vLLM 의존성(가용성·latency): `client.py`가 이미 graceful degrade하므로 vLLM down → 결정론 코어로 자동 후퇴(이미 보장).
- facade 통일은 CLI 1623줄 리팩터 동반 — 별도 `/apt` 사이클(D1 구현 시).

## 권장 시퀀싱 (본 ADR 이후, 각자 별도 verdict)

1. **MCP 패리티** (D3) — occam/eureka/hades/legion/재배맨 MCP 도구 5종. vLLM verdict 불요, 선행 가능.
2. **효능 A/B 측정** (D2) — `engine/efficacy/`로 결정론 4군단장 × {core vs core+vLLM} preflight 3-falsifier 통과 측정 → enrich scope 표 확정. **이게 "먼저 측정부터" verdict의 실체.**
3. **CommanderEngine facade** (D1) — 측정 결과로 enrich 슬롯 확정 후, 7개를 한 모양으로 통일 + CLI/MCP/legion이 그 facade 공유.

## Open Questions (열어둠)

- **OQ1**: vLLM-enrich가 *어느 군단장에서* 양의 신호를 내는지 = D2 측정 전엔 미지(현 KG 효능맵 = 7군단장 전부 UNMEASURABLE). 사전가설은 eureka/prometheus/나생문-판단렌즈 PASS 예상이나 *측정이 정전*.
- **OQ2**: "engine급"의 하한 — PROM 16 triad(스케줄러/indirection-table/격리) 기준 legion은 아직 "검증 파이프라인"이지 자원-다중화 엔진 아님. 7군단장이 *동시*·*공유 vLLM 토큰예산* 위에서 돌기 시작하면 그때 triad(스케줄러+admission control) 필요 — 본 ADR 범위 밖, daemon multiplex 트리거 시 후속 ADR.

# KG: adr-seven-commander-engine-cli-mcp-vllm-2026-06-18, adr-seven-commander-legion-architecture-2026-05-27, adr-bhgman-tool-in-process-default-2026-05-19, bhgman-llm-commander-runtime-2026-05-28, project-bhgman-ab-falsifier-2026-05-30, project-legion-unification-kg-engine-2026-06-01, project-efficacy-measurement-line-2026-06-01
