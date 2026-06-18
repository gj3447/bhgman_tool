---
name: occam
kg_ref: occam-kam-canonical-2026-05-26
version: "1.0.0"
channel: stable
provenance: AI_DERIVED_FROM_USER_PRIMARY  # 동사 "정리한다" = 사용자 정전(비행기맨 #4 군단장, "오캄, 줄여서 캄").
description: >
  오캄(Occam, 줄여서 캄) 방법론 — 비행기맨 #4 산하 군단장 동사 **"정리한다"**(현재→과거↓, archive).
  하계(KG+소스코드) 전체에서 *업데이트로 대체된 낡은 과거*(중복·dead·stale 노드)만 선별 아카이빙.
  `/occam` == 오캄 해줘. `/prom`이 지식수집·`/eureka`가 개념창조이듯 `/occam`은 정리 동사.
  사용법: `/occam` (KG 전체 dedup, **dry-run 기본**) · `/occam --scope <label|path>` · `--apply`(write).
  CLI: `bhgman-tool occam [--scope X] [--apply]`. neo4j 부재 시 fetch cypher 출력(부모 Claude MCP 실행용).
  **covenant: archive-only, 삭제 금지** (occam.py·kg_adapter에 delete 함수 부재; write cypher에 DELETE/DETACH/REMOVE 토큰 assert로 차단). 마구잡이 금지 — twin 있는 superseded만. dry-run 기본.
  유레카(쌓기/+1)의 정반대 극(빼기/-, subtractive). 어원: William of Ockham 면도날.
  엔진 정본: `bhgman_tool/engine/occam/` (occam.py occam_pass[순수 분류] + kg_adapter[read/write IO, covenant] + occam_runner[end-to-end] + occam_models + oracle_lens). CLI=`engine/cli/main.py` occam verb.
  # KG: occam-kam-canonical-2026-05-26, lesson-occam-must-query-kg-node-dedup-not-just-filesystem-2026-05-27,
  #     occam-pass-kg-wide-2026-05-27
---

## 📚 References (lazy-load)

상세 지식은 `references/`에 분리 — 필요 시 로드 (2026-06-02 엔진/KG에서 수확. occam 전용 THEORY 폴더 없음):
- [`phases.md`](references/phases.md) — occam_pass 3 detection mode + 스테이지별 책무 + 안티패턴
- [`gates.md`](references/gates.md) — σ verdict cascade / twin·guard gate / covenant FORBIDDEN_TOKENS / DL consistency
- [`kg_logging.md`](references/kg_logging.md) — supersession Cypher 스키마 + CONTRACT_OccamArchiveRecord_v1 (R1-R6)
- [`quick_ref.md`](references/quick_ref.md) — 한 장 치트시트

---

## 🔗 MIC / 군단장

**동사**: 정리한다 (현재↔과거 시간축, archive). **정반대 극**: 유레카(쌓기/창조). **희미한 쌍 bright-line**:
참·거짓=나생문 vs 중복·낡음=오캄 / 죽은중복 치움=오캄 vs 반복패턴→추상=유레카. 오캄→나생문 GATE로 USES(≠IS).

---

## 핵심 — KG node-dedup이 PRIMARY (filesystem 아님)

> `lesson-occam-must-query-kg-node-dedup-not-just-filesystem-2026-05-27`. filesystem 스캔만으론 본령(중복·낡은 KG 노드) 놓침.

**dedup key = 타입별** (이번 세션 KG-wide occam 교훈 — name으로 dedup = 재앙):
| 노드 타입 | dedup key | 주의 |
|---|---|---|
| SourceCodeNode | **sourcePath** (name 아님!) | `INDEX.md`/`SOURCES.md`는 다른 폴더 같은 basename = 다른 파일 |
| ReferenceDocument/WebSourcePage | **url** | 제목 충돌 ≠ dup |
| Directory | **path** | |
| AbstractNode canon (Lesson/Consensus/…) | **name** (MERGE key) | |

**over-match 금지** (lesson 2회 재발): bare name으로 supersede = 다른 파일/타입 잘못 합침. `occam_pass`의 `normalize_path`(abs `/Users/.../bhgman_tool/X` ↔ rel `bhgman_tool/X` lineage 통합)로 *진짜* 중복만.

---

## 사이클 (occam_pass)

> 엔진 정본 = `bhgman_tool/engine/occam/occam.py`. 본 SKILL은 프로토콜만.

| # | 단계 | 내용 |
|---|---|---|
| 1 | **SELECT** | KG 노드 조회 (타입별 key). cypher 먼저(PRIMARY), disk sha truth 보조 |
| 2 | **GROUP** | normalize_path/key로 그룹 → size>1 (twin 존재)만 후보 |
| 3 | **PICK_CURRENT** | disk sha 일치=HIGH / 없으면 max line_count=MEDIUM = keep |
| 4 | **GUARD** | twin 없으면 손대지 말 것. false-positive(다른 파일/타입 name 충돌) 배제 |
| 5 | **SUPERSEDE** | stale → `status='SUPERSEDED'` + supersededBy + reason + supersededAt. **삭제 0** |

### 분류 로직 (occam_models)
- exact duplicate (동일 sha) → "redundant"
- superseded (다른 sha, 낮은 lineCount/old lineage) → "superseded version"
- **SupersessionCandidate만 반환, OccamReport에 기록. delete 함수 없음 (covenant).**

---

## 가드 (마구잡이 차단)

- **archive-only**: SUPERSEDED 표시만, 삭제 절대 금지. reversible.
- **twin-only**: 같은 key에 2+ distinct 노드일 때만. 단독은 손 안 댐.
- **타입별 key**: sourcePath/url/path/name — bare name over-match 금지.
- **KG-first**: filesystem 스캔 아닌 KG cypher dedup이 본령.
- **유레카와 경계**: 죽은 중복=오캄(archive) vs 숨은 개념 있는 반복=유레카(추상화). 치우면 오캄, 올리면 유레카.

---

## What NOT To Do

| 금지 | 이유 |
|---|---|
| 삭제(delete) | covenant 위반. archive(SUPERSEDED)만 |
| bare name으로 supersede | 다른 폴더 같은 basename = 다른 파일 (over-match 재앙, lesson 2회) |
| filesystem만 스캔 | 본령(KG node-dedup) 놓침 |
| 낡은것 정리를 유레카가 | 그건 오캄 동사 (유레카=쌓기, 오캄=빼기) |
| 마구잡이 정리 | "착한놈" — 대체된 낡은 과거만 선별 |

# KG: ATOM_Skill_occam, occam-kam-canonical-2026-05-26, occam-pass-kg-wide-2026-05-27

---

## Measurement & Conditional Dispatch (2026-05-30 추가)

사용자 정전 정정 2026-05-30 (`user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30`): 7군단장 측 *고정 USES edge* retract → *measurement-driven conditional dispatch*. 본 commander도 `measure()` + `decide_dispatch()` API를 따른다.

### 본 commander metric & threshold

- 정전 SPEC: `SYMPOSIUM/THEORY/00_공통/7CMD_NEED_BASED_DISPATCH_SPEC.md` §3 Table
- 구현: `bhgman_tool/engine/legion/measurement.py` — 본 commander의 occamMeasurement class
- KG: `:MeasurementFunction` + `:DispatchThreshold` nodes (parent: `7cmd-measurement-driven-conditional-dispatch-2026-05-30`)

### Stevens scale type & 학문 grounding

각 metric의 Stevens 1946 scale type (nominal/ordinal/interval/ratio)을 `:MeasurementFunction.scale` field에 기록.
Goodhart drift (1975) mitigation은 Naesengmoon meta-check 또는 cycle-end invocation-log empirical reconcile (`lesson-occam-proxy-strength-needs-empirical-spot-check-2026-05-28`).

### Dispatch 정전

`measure()` → threshold-gated need detection → 다른 commander conditional invocation (Hades realization pattern universalized, parent `hades-canonical-2026-05-27`).
고정 USES는 *historical provenance only* (`:DispatchEvent` runtime record).

# KG: 7cmd-measurement-driven-conditional-dispatch-2026-05-30, user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30, hades-canonical-2026-05-27, mf-occam-*
