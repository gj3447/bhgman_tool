# C(S) 5 Predicates — SP Atomicity Check (Phase-Specific)

> apt-sp의 핵심 평가. Span이 *atomic*인지 판정하는 5 술어. **cheap-first 평가 순서 강제** (v11 이후).

---

## 평가 순서: v → t → i → d → s

v10 이전엔 s (인간 검토)를 먼저 수행하여 자동 거를 수 있는 것에도 4시간 SLA 인간 검토 낭비 (E10 참조). v11에서 비용 낮은 자동 검사 우선.

| 순서 | 술어 | 비용 | 설명 |
|:----:|:----:|:----:|------|
| 1 | **v(S)** | ~0 (휴리스틱) | 구현 크기 추정 |
| 2 | **t(S)** | 낮음 (타입 분석) | 입출력 타입 구체성 |
| 3 | **i(S)** | 낮음 (assertion 스케치) | 테스트 가능한 postcondition 존재 |
| 4 | **d(S)** | 낮음 (크기 추정) | 과잉 분해 방지 |
| 5 | **s(S)** | 높음 (인간/에이전트 판단) | semantic 완전성 (s_auto + s_oracle) |

**핵심**: v, t, i, d 모두 PASS해야 s 평가로 진행. 하나라도 FAIL이면 s_oracle 요청 없이 즉시 분해.

---

## v(S) — Implementation Feasibility (복잡도)

**판정 기준:** `estimated_lines > cfg.complexity_threshold` 이면 FAIL.
현재 `cfg.complexity_threshold` = `cfg.vibe_coding_sweet_max` (= 500, [magic_number_table.md](../../../THEORY/APT/magic_number_table.md) I.2).

**예시:**
- PASS: "사용자 인증 토큰 검증" — 추정 200줄, 단일 책임
- FAIL: "전체 API 게이트웨이" — 추정 2000줄, 다중 책임

**실패 시 분할 전략:** 기능 영역별로 분할. 예: 게이트웨이 → 라우팅 + 인증 + 레이트리밋 + 로깅

---

## t(S) — Type Expressibility

**판정 기준:** `def f(x: ConcreteDTO) -> ConcreteDTO` 를 작성할 수 있는가? 타입이 "data", "any", "object", "result", "info" 이면 FAIL.

**예시:**
- PASS: `input: PointCloud(N x 3, float32) -> output: TransformMatrix(4x4, float64)`
- FAIL: `input: data -> output: result` (너무 추상적)

**실패 시 분할 전략:** 출력 타입 경계로 분할. 한 함수가 여러 타입을 반환하면 각각 별도 Span.

---

## i(S) — Test Feasibility

**판정 기준:** `assert result.field == specific_value` 를 작성할 수 있는가? 구체적 테스트 assertion이 불가능하면 FAIL.

**예시:**
- PASS: "JSON 파서" — `assert parse('{"a":1}')['a'] == 1`
- FAIL: "시스템 성능 개선" — 구체적 assertion 불가

**실패 시 분할 전략:** 구체적 예시로 명세를 날카롭게. 추상 목표를 측정 가능한 하위 목표로 분해.

---

## d(S) — Decomposition Diseconomy

**판정 기준:** `estimated_lines < cfg.delta_diseconomy_min_lines AND parent exists` 이면 FAIL.
현재 `cfg.delta_diseconomy_min_lines` = 100 (vibe_coding_sweet_min/2 휴리스틱).

**예시:**
- PASS: 추정 250줄 — 적절한 크기
- FAIL: 추정 50줄 — 더 분해하면 20줄 조각, 오버헤드 > 이득

**실패 시 분할 전략:** 분할하지 않음. 부모로 merge up. 이미 atomic.

---

## s(S) — Semantic Completeness

### s_auto (자동)

- 용어 커버리지: `S.description` 의 모든 도메인 용어에 대응하는 INFORMED_BY 링크 존재
- 도메인 온톨로지 매칭: KG 내 기존 도메인 개념과 라벨/관계 패턴 일치
- 명명 규약: `S.name` 이 프로젝트 패턴 따름

### s_oracle (인간/에이전트)

- **executor != reviewer 필수** (분리 의무, V15 검증)
- 질문: "이것이 올바른 분해인가? 이 Span이 응집적이고 완전한 의미 단위를 포착하는가?"
- SLA: `cfg.sigma_sla_hours` (기본 4시간)
- 타임아웃 시: 위임 체인 (Primary → Secondary → Human → Auto-REJECT)

### 흐름

```
s_auto PASS → s_oracle 요청
s_auto FAIL → 즉시 Step 3 (분해)
s_oracle APPROVED → AtomicSpan 라벨링
s_oracle REJECTED → Step 3 (분해)
```

`cfg.allow_agent_sigma = true` (dev 환경) 이면 에이전트가 s_oracle 역할 가능. 단, executor와 다른 에이전트여야 함.

---

## anti-pattern

[_common/error_pattern_template.md](../../_common/error_pattern_template.md):

### E-SP-CS-1: s-First Order Waste (v10 legacy)
**Context:** s를 v/t/i/d 전에 수행. 자동 거를 수 있는 Span에도 4시간 인간 검토 SLA 소비.
**Lesson:** cheap-first 평가는 경제성 의무. 비싼 인간 시간 절약.
**Guard:** SP SKILL.md의 평가 cypher가 v→t→i→d→s 순서 강제. s 호출 전 4개 PASS 검증.

### E-SP-CS-2: v 임계값 하드코딩
**Context:** SKILL.md 본문에 "estimated_lines > 500" 직접 작성.
**Lesson:** magic number는 `cfg.complexity_threshold` slot resolve 의무. drift 시 한 곳만 갱신.
**Guard:** SP SKILL.md `{{cfg.complexity_threshold}}` 마커 사용 (skill-magic-migration 적용 후).

# KG: APT_SP_CS_predicates_canonical, magic_number_table_v27_A6.1
