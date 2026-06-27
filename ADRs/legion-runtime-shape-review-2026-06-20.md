# ADR: legion 런타임 형상 — addressability / warm-state / dispatch (D3 정밀화 + OQ2 진입)

- **Status**: ACCEPTED (사용자 verdict 2026-06-20 "ㅇㅇ 그렇게 진행"). 두 verdict 승인:
  (1) D3 정밀화(MCP "7/7 균일" → **5 addressable + 2 structural**) ✅,
  (2) dispatch 라우팅·warm runtime = **측정 게이트 뒤 유지** ✅.
  후속: OQ1(hades verdict-provenance 게이트) 설계 착수 — 본 ADR §부록 아래 `design-oq1-hades-verdict-gate-2026-06-20` 참조.
- **Date proposed**: 2026-06-20
- **KG ref**: `adr-legion-runtime-shape-review-2026-06-20`
- **Parent constraints**:
  - `adr-seven-commander-engine-cli-mcp-vllm-2026-06-18` (D3 MCP 패리티, OQ2 daemon-multiplex — **본 ADR이 그 child**)
  - `adr-bhgman-tool-in-process-default-2026-05-19` (commander↔commander = in-process, RPC/split-process 배제)
  - `adr-seven-commander-legion-architecture-2026-05-27` (Contract-bound handoff, 닫힌 루프, substrate=KG)
  - `hades-canonical-2026-05-27` (INDEXED_PAIR; hades=능동 실현, c6 "가장 위험"/비가역, dry_run 기본)
- **Authority**: 사용자 발화 2026-06-20 — "7군단장이 각자 상주 서버를 가져야 하는데 개념적으로 부족" 직관 → 코드 기준 압박 리뷰 → "승격" verdict.

---

## Context

"7군단장 각자 상주 서버" 직관을 코드로 압박한 결과. 현 런타임 실태:

| 사실 | 근거 |
|---|---|
| legion = **단일 forward pass** (daemon 아님, while 없음) | `engine/legion/legion.py:96-147` |
| bot 모드 `while`은 work를 **originate**할 뿐 inbound listen 안 함 | `engine/legion/daemon.py` (socket/listen/uvicorn 0건) |
| MCP는 commander 개별 도구가 **2/7만** (prometheus/longinus); occam/eureka/hades/legion_run 일부만 | `engine/mcp_server/tools/` |
| dispatch 결정은 **기록만 하고 라우팅 안 함** (W2-A provenance) | `engine/legion/legion.py:47-56, 126` |

이미 2026-06-18 ADR의 **D3(MCP 패리티)**와 **OQ2(daemon multiplex)**가 이 영역을 열어두었다. 본 ADR은 그 둘을 코드 증거로 **정밀화**한다.

## Decision

### D1. D3 정밀화 — "MCP 7/7 균일 addressability"는 부정확

Contract `requires`(`engine/legion/commanders.py`)가 실제 분류를 강제한다:

| 군단장 | requires | 단독 호출 | 처리 |
|---|---|---|---|
| occam / eureka / longinus | `run_cypher`만 | ✅ 깔끔 | MCP 도구 신설 (canon-clean, **fresh-per-call**) |
| **hades** | `verdict` (`commanders.py:322`) | ⚠️ gated | **OQ1(verdict provenance) 해소 전 단독 노출 금지** |
| naesengmoon | 산출물(관계적) | ❌ | 주입 oracle gate — addressable verb 아님 |
| jaebaeman | — | ❌ | `run()` 루프 자체 (`legion.py:8-9`, CANONICAL_ORDER 제외) |

→ 2026-06-18 D3의 "occam/eureka/hades/legion/재배맨 5종 신설"을 **"occam·eureka 즉시 + hades(verdict-gated) + legion_run(기존) ; 재배맨·나생문은 도구화 대상 아님"**으로 정정. 목표 = "7/7"이 아니라 **5 addressable + 2 structural**.

### D2. 재현성 불변 — warm은 결정론 보존 한도에서만

- 개별 commander 도구는 **fresh-per-call** 유지 (legion_run의 `build_default_legion()` 패턴) → `artifact_hash` 재현성 무손상.
- warm read-through 캐시는 **occam 임베더(텍스트→벡터, 결정론적)만** 허용.
- **eureka HNSW는 warm≠cold** — `engine/memory/vector_store.py:51` `init_index`에 `random_seed` 미설정 → warm-incremental ≠ cold-batch 근사이웃. 결정론-critical Leiden은 `randomSeed=42` 고정(`engine/eureka/stages.py:56`). ⇒ eureka warm은 **등가성/허용오차 invariant 테스트 선행** 조건.

### D3. dispatch 라우팅 · warm runtime = 측정 게이트 뒤 유지

dispatch 라우팅(고정 파이프라인→동적 제어흐름)·warm runtime은 **CUSUM 누적 상태**(`engine/legion/threshold_derivation/cusum.py`, `s_n`/`n_observed` mutable)가 cross-run 누수되면 같은 입력에 다른 dispatch → **멱등성/재현성 붕괴**. 2026-06-18 **OQ2(daemon multiplex)** 후속으로 유지하며, 그 **첫 결정사항 = 본 ADR의 OQ3**(cross-run 상태 배치).

## Findings (압박 산물 — KG: `finding-*-2026-06-20`)

- **F1** `finding-addressability-mis-target-7of7-2026-06-20` — "7/7 균일"은 틀린 목표 (위 D1).
- **F2** `finding-warm-not-equal-cold-hnsw-2026-06-20` — warm≠cold (HNSW 무seed; Leiden은 seed 고정).
- **F3** `finding-dispatch-routing-cusum-collision-2026-06-20` — dispatch 라우팅 ≠ 갭필 (W2-A provenance + CUSUM 충돌).

## Open Questions (승격 — KG: `oq-*-2026-06-20`)

- **OQ1** — hades 단독 실현 시 **verdict provenance**: 위조 verdict로 미검증 설계를 실현하는 oracle-gate 우회를 어떻게 막나? *canon 근거*: hades = 능동 실현, c6 **"가장 위험"/비가역**, dry_run 기본(`hades.py`). ⇒ 단독 노출은 **naesengmoon HMAC 서명 verdict node ref 재검증 필수**, 미검증 시 fail-closed.
- **OQ2** — **의미적 동등 ≠ 런타임 동등**: equal-standing canon을 런타임 형상에 투영하면 jaebaeman(substrate)/naesengmoon(gate)을 서버화하려는 범주혼동. *증거 보강*: harness가 7군단장에서 **3계층 floor로 강등**(`bihaenggiman-harness-demoted-3layer-2026-05-27`)된 것 자체가 "역할별 런타임 형상 이질성"의 canon 선례. ⇒ type-directed 형상 분류표를 canon에 명문화.
- **OQ3** — **cross-run 상태 배치**: warm runtime 시 CUSUM 누적 상태를 KG(외부, 멱등 유지, 현 in-process-default 정합) vs in-process(빠르나 멱등 붕괴) 어디 두나? daemon-multiplex 후속 ADR의 첫 결정.

## 부록 — hades ↔ harness 는 1:1 대응이 아니다 (OQ1·OQ2 관련)

사용자 질의(2026-06-20) 응답. **1:1 아님.** canon이 명시적으로 **INDEXED_PAIR (Place, Realize-Action)** = 한 존재의 두 직교 측면으로 정의, `relationship=USES (same entity, two aspects, **NOT alias merge**)` (`engine/hades/hades.py:6-10`).

- **harness** = 수동 場 + **진단/분류** 동사 (3계층 IDE-host/runtime/cloud × 4축 Inform/Constrain/Verify/Correct), read-only `HarnessDiagnosis` (`engine/harness/harness.py:1,158`). 7군단장에서 floor로 강등된 cross-cutting layer.
- **hades** = 능동 **실현** 동사 (ACCEPTED 추상→구체, eureka의 Galois dual), write `MaterializationPlan` (`engine/hades/hades.py:1`).
- 관계 = **로스터 슬롯 승계**(구 7번째=harness → 신 7번째=hades) + INDEXED_PAIR. verb·I/O·로스터 축이 전부 달라 **기능 1:1 매핑 아님**. (문서 내 SAME↔SEPARATE flip-flop은 indexed-pair 구조로 해소; 단 페어링은 hades 측 단방향 선언.)

## §design-oq1-hades-verdict-gate-2026-06-20 — Verdict-Provenance Gate (red-team 하드닝본)

> 상태: ACCEPTED. red-team 3렌즈(forge / replay / keyless)가 **초안을 3/3 우회** → 하드닝으로 forge·keyless·replay·cross-artifact 봉쇄. 잔여 = 대칭 HMAC 구조적 천장(OQ1c).

### 위협 모델
오늘 `_run_realize`(`engine/legion/commanders.py:255-260`)는 `if oracle=="FAIL" or ensemble in {REJECT,FAIL}` **negative 체크**만 한다 → 빈 `{}`(oracle=None)·위조 `{"oracle":"PASS"}` 둘 다 통과해 **비가역 realize**. 무결성 검사 0.

| 위협 | 오늘 열린 경로 (검증됨) | 닫는 메커니즘 |
|---|---|---|
| **F** forge | 위조 verdict dict bare read (`commanders.py:255-260`) | canonical payload HMAC + **positive PASS 요구** |
| **O** fail-open | `{}`/키 누락 → `.get()`=None ∉ {FAIL,REJECT} | 빈/비-dict 거부 + 서명 강제 |
| **R** replay/cross-artifact | 타 cycle PASS 복사 / 같은 cycle 다른 artifact (`hades_runner.py:24-26` `verdictStatus='ACCEPTED'` 독립 fetch) | cycle_id + **artifact-binding** + 1회용 ledger |
| **K** keyless | 공개 in-repo default `bhgman-dev-secret-2026-05-30` / 빈키 silent fail-open (`measurement.py:34`) | 약/무/default 키 **import+verify HARD-REFUSE** |

### 서명 데이터 모델
producer(나생문 stage, `commanders.py:250` 직전)가 verdict에 append: `cycle_id`(서버-mint uuid4) / `artifact_id`(=`sha256(sorted(extent members)⊕concept)`, `hades_runner` fetch rows에서 재계산 가능) / `verdict_source="naesengmoon-verify"` / `hmac_signature`. canonical payload = `"naesengmoon-verify"|cycle_id|artifact_id|oracle|ensemble|sorted(degraded)|judgment|mode` (시간/난수 없는 순수함수). 재사용: `measurement.py` `_sign`:39 / `_signed_payload`:58 / `verify_signature`:89. **신규 키 `BHGMAN_VERDICT_HMAC_SECRET` (in-repo default 없음, dispatch 키와 분리).**

### realize-시 게이트 — `verify_verdict_provenance(verdict, expected_cycle_id, expected_artifact_id)` (순수함수)
0. **KEY**: 해석된 키가 빈/공백/dev-default/<32B → (test isolation 아니면) DENY + import `RuntimeError` [K]
1. dict 아니거나 빈 → DENY [O]
2. `verdict_source != "naesengmoon-verify"` → DENY
3. `hmac_signature` 부재/비-문자열 → DENY [forge-by-omission]
4. `cycle_id != expected`(★서버-held run state, caller input 금지) → DENY [R-freshness]
5. `artifact_id != expected`(realize-time 재계산) → DENY [R-cross-artifact]
6–7. HMAC 재계산 + `compare_digest` 불일치 → DENY [F]
8. `(cycle_id, artifact_id)` ledger 중복 → DENY [R-재사용]
9. **`oracle != "PASS"` → DENY** (positive 요구) ; `ensemble ∈ {REJECT,FAIL}` → DENY [O 하드닝]
→ 전부 통과해야 realize. 호출: `_run_realize` 최상단 + 신규 `hades_realize` MCP `_impl` + run-level G2(`gated_run.py:87-110`).

### fail-closed
`BHGMAN_SECURITY_ENFORCE`와 무관 **HARD**(무결성 게이트는 AUDIT 강등 불가). 어느 실패든 `{"realized":{"mode":"skipped",...}}` 반환(부분 write 없이), realize·`run_hades`·KG write **0건**. keyless = fail-OPEN **금지**(약키로 게이트 절대 live 안 됨). `hades_runner` dry_run/apply 가드는 이 게이트 **아래** defense-in-depth(대체 아님).

### 위치
`engine/legion/measurement.py`에 `_VERDICT_SECRET` + `sign_verdict` / `verify_verdict_provenance` / `_key_is_trustworthy` / `_verdict_ledger`. consumer 3 call-site(in-loop `_run_realize` / MCP `hades_realize` / run-level G2)가 **byte-identical** 동일 헬퍼 — hades측 단방향 페어링의 단일 진실원. MCP는 3-file 등록(`security.TOOL_CAPABILITIES` / `registry._CATALOG_SEED` / `server.build_server`) + caller-supplied verdict bytes 비신뢰(expected_* 서버 파생).

### 비대칭 해소
페어링은 hades측 단방향이므로 verdict를 self-authenticating(서명)하게 만들고 **소비측(hades)이 일방 검증** — return channel·harness 협력 불필요. harness는 신규 요구 0(passive 진단 floor).

### 잔여 리스크 → 신규 OQ (승격)
- **OQ1c — 대칭 HMAC 구조적 천장**: env를 읽는 fully-in-process forger는 키를 mint 가능(같은 프로세스가 sign+verify). 키 분리·default 제거·약키 refuse로 외부·in-ctx·공개키 forge는 닫지만 env-read 공격자는 못 막음. 완전 봉쇄 = **비대칭 서명(나생문=private, hades=public-only) 또는 process isolation**. (`oq-hades-verdict-asymmetric-key-2026-06-20`, residual)
- **OQ1b — selection-node 서명 (격상, OQ1과 동시 랜딩 권고)**: `hades_runner.py:24-26` `verdictStatus='ACCEPTED'`는 writable property라 verdict 게이트와 무관하게 artifact selection forge 가능. `(concept, verdictStatus, cycle_id)`를 HMAC-bound 서명 + realize 전 검증해야 완전. step5 artifact-binding이 완화하나 노드 서명이 완전해법. (`oq-hades-verdict-selection-node-signing-2026-06-20`)
- cycle_id 엔트로피(서버-mint uuid4 강제), canonical-payload drift(golden-vector pin), advisory 필드(`n_eff`/`rho`/`summary`) 미서명(게이트 미사용이라 수용).

### 마이그레이션 (요약)
`measurement.py` 헬퍼+키+ledger 추가(단위테스트 9종 + artifact 포함 golden-vector) → producer 배선(`commanders.py:250`) → cycle_id 서버-mint 강제 → consumer 교체(`_run_realize` blind read) → run-level G2 업그레이드 → **OQ1b 동시 랜딩** → MCP `hades_realize` 3-file 등록(`catalog_is_consistent_with_security` 통과) → e2e(forge/empty/replay/cross-artifact/ledger/keyless 전부 REFUSED).

# KG: adr-legion-runtime-shape-review-2026-06-20, adr-seven-commander-engine-cli-mcp-vllm-2026-06-18, adr-bhgman-tool-in-process-default-2026-05-19, adr-seven-commander-legion-architecture-2026-05-27, hades-canonical-2026-05-27, bihaenggiman-harness-demoted-3layer-2026-05-27, vp-hades-harness-indexed-pair-formalization-2026-05-28, finding-addressability-mis-target-7of7-2026-06-20, finding-warm-not-equal-cold-hnsw-2026-06-20, finding-dispatch-routing-cusum-collision-2026-06-20, finding-hades-harness-not-1to1-indexed-pair-2026-06-20, design-oq1-hades-verdict-gate-2026-06-20, oq-hades-verdict-provenance-standalone-realize-2026-06-20, oq-semantic-equal-vs-runtime-equal-commanders-2026-06-20, oq-cross-run-state-placement-warm-runtime-2026-06-20, oq-hades-verdict-selection-node-signing-2026-06-20, oq-hades-verdict-asymmetric-key-2026-06-20
