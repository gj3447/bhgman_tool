# hades — KG Logging (Cypher MERGE Schema)

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). KG: `hades-canonical-2026-05-27`.
> 동사 = **실현한다** (추상→구체↓), 유레카의 dual. 이 문서 = 하데스가 KG에 *쓰고/읽는* Cypher 스키마.
> 정본 엔진: `bhgman_tool/engine/hades/` (hades.py / hades_runner.py / hades_models.py).

---

## 1. 무엇을 쓰나 (한 줄)

하데스의 KG 실현(`kind='kg'`)은 단 두 가지 효과만 낸다:
1. 한 `:AbstractClass` 노드를 **CANONICAL로 승격** (+ `realizedBy='hades'` 표식).
2. 그 추상의 멤버(extent)들을 `-[:INSTANCE_OF]->` 추상에 **연결**.
코드 실현(`kind='code'`)은 KG write 를 *하지 않는다* — 항상 PLANNED dry-run (§5).
# src: bhgman_tool/engine/hades/hades.py:67-73 (ops 튜플)

---

## 2. Write 스키마 — `realize_kg_abstraction`

dry_run=False + `apply_cypher` 주입 시에만 실제 실행 (그 외엔 PLANNED 계획만 방출).

```cypher
-- op0: 추상 노드 승격 (parameterized, injection-safe)
MERGE (a:AbstractClass {name:$concept})
SET a.status='CANONICAL', a.realizedBy='hades'

-- op1: 멤버 → 추상 INSTANCE_OF (op0의 (a) 바인딩은 안 넘어옴 → 재-MATCH 필수)
UNWIND $members AS m
MATCH (a:AbstractClass {name:$concept})
MATCH (o {name:m})
MERGE (o)-[:INSTANCE_OF]->(a)
```
# src: bhgman_tool/engine/hades/hades.py:67-73

- op1 이 `(a)` 를 *재-MATCH* 하는 이유: op0/op1 은 별개 쿼리라 바인딩이 안 넘어온다. 옛 bare `(a)` 는 익명 신규 노드를 MERGE 하던 버그였음. # src: hades.py:65-66 (주석)
- 멤버 노드는 **label-agnostic** 으로 매칭: `MATCH (o {name:m})` — 이미 KG 에 존재하는 어떤 노드든 name 으로 잡는다 (새로 만들지 않음). # src: hades.py:71
- 호출은 두 op 를 따로 실행: `apply_cypher(ops[0], {"concept": concept_name})` 그 다음 `apply_cypher(ops[1], {"concept": ..., "members": list(member_names)})`. # src: hades.py:82-83

### 노드 라벨 / 키 프로퍼티

| 라벨 | 키 | 하데스가 쓰는 프로퍼티 |
|---|---|---|
| `:AbstractClass` | `name` (MERGE 키) | `status`('CANONICAL') · `realizedBy`('hades') |

# src: hades.py:68. KG 확인: `:AbstractClass {name, status, realizedBy, verdictStatus, extent}` 실재 (e.g. `ac_l8_smoke_test_2026-05-20_v1`). # src: KG read MATCH (a:AbstractClass)

### 엣지

| 엣지 | 방향 | 의미 |
|---|---|---|
| `INSTANCE_OF` | `(member)-[:INSTANCE_OF]->(:AbstractClass)` | extent 멤버 → 실현된 추상 |

# src: hades.py:72

---

## 3. Undo 스키마 (reversibility-first covenant)

모든 `MaterializationPlan` 은 `undo` 튜플을 들고 다닌다 — "되돌릴 수 없으면 실현 안 함". KG 실현의 undo:

```cypher
-- undo op0: 승격 취소 (삭제 아님 — supersede)
MATCH (a:AbstractClass {name:$concept}) SET a.status='SUPERSEDED'

-- undo op1: INSTANCE_OF 엣지 제거
MATCH (o)-[r:INSTANCE_OF]->(a:AbstractClass {name:$concept}) DELETE r
```
# src: bhgman_tool/engine/hades/hades.py:74-77

undo 는 **노드 삭제가 아니라** `status='SUPERSEDED'` 표식 + 엣지만 DELETE — 오캄 supersession 과 같은 active/log 분리 규율. # src: hades.py:74; MaterializationPlan.undo 필드 hades_models.py:25

---

## 4. Read 스키마 — `fetch_accepted_cypher` (runner)

end-to-end runner 가 실현 *대상* 을 KG 에서 읽어오는 쿼리. 게이트 = `verdictStatus='ACCEPTED'` AND 미실현(`status<>'CANONICAL'`).

```cypher
-- 전체 (concept 미지정)
MATCH (a:AbstractClass)
WHERE a.verdictStatus = 'ACCEPTED' AND (a.status IS NULL OR a.status <> 'CANONICAL')
RETURN a.name AS concept, a.verdictStatus AS verdict, coalesce(a.extent, []) AS members

-- 한 개 (concept 지정)
MATCH (a:AbstractClass {name: $concept})
WHERE a.verdictStatus = 'ACCEPTED' AND (a.status IS NULL OR a.status <> 'CANONICAL')
RETURN a.name AS concept, a.verdictStatus AS verdict, coalesce(a.extent, []) AS members
```
# src: bhgman_tool/engine/hades/hades_runner.py:23-32

- `members` = `a.extent` 프로퍼티 (list; 없으면 `[]` 로 coalesce). 이것이 op1 의 `$members` 로 흘러간다. # src: hades_runner.py:26-27, run_hades 74-80
- 이미 CANONICAL(=이미 실현됨) 인 추상은 제외 — **재실현 방지**. # src: hades_runner.py:25 (주석)
- read 게이트 프로퍼티: 하데스는 `:AbstractClass` 의 `verdictStatus`/`extent` 를 *읽기만* 하고 *쓰지 않는다* (이것들은 유레카 PROPOSE → fidelity/judgment 게이트가 채움). 하데스가 쓰는 건 `status`/`realizedBy` 뿐. # src: hades.py:68 vs hades_runner.py:26

---

## 5. KG write 를 **안 하는** 경로 (중요)

| 경로 | 결과 | KG write? |
|---|---|---|
| `realize_kg_abstraction(..., dry_run=True)` (기본) | `PLANNED` (ops/undo 계획만) | ✗ |
| `verdictStatus != 'ACCEPTED'` | `REFUSED` | ✗ |
| empty extent (`member_names=[]`) | `REFUSED` | ✗ |
| `realize_code_template(...)` / `realize_code_extract_superclass(...)` | code 백엔드 — **항상** PLANNED dry-run | ✗ (KG 미접촉) |
| `run_hades(apply=True, apply_cypher=None)` | PLANNED 유지 (write 불가) | ✗ |

# src: hades.py:52-62 (REFUSED 가드), hades.py:116-122 (code 항상 PLANNED), hades_runner.py:70-71 (apply_cypher 없으면 do_write=False)

코드 실현(Extract-Superclass)은 KG 가 아니라 *소스 파일* 을 건드린다 — 그리고 그것조차 characterization-test 게이트(`apply_extract_superclass_gated`)를 통과해야만; 실패 시 파일을 byte-for-byte 복원. # src: bhgman_tool/engine/hades/hades_apply.py:93-118

---

## 6. 실측 상태 (2026-06-02 KG)

- `:AbstractClass` 노드 실재 — `status`/`realizedBy`/`verdictStatus`/`extent` 프로퍼티 schema 일치 확인. # src: KG read MATCH (a:AbstractClass)
- 현재 `(member)-[:INSTANCE_OF]->(:AbstractClass)` 엣지 **0개**, `realizedBy='hades'` 노드 **0개** — dry-run-기본 covenant 와 정합 (아직 apply 한 적 없음). # src: KG read MATCH ...INSTANCE_OF / MATCH n.realizedBy='hades'
- `hades-canonical-2026-05-27` 노드 라벨 = `:AbstractNode:CanonicalName:LegionCommander`. # src: KG read MATCH {name:'hades-canonical-2026-05-27'}

---

## 7. Dispatch 측정 노드 (별개 schema, 하데스가 *생성*하진 않음)

measurement-driven conditional dispatch (`7cmd-measurement-driven-conditional-dispatch-2026-05-30`) 용 `:MeasurementFunction` 노드가 하데스 commander 앞으로 등록돼 있다 (하데스 실현 엔진이 쓰는 게 아니라 dispatch layer 가 읽음):

| `name` | `metric_name` | `scale` | `formula` |
|---|---|---|---|
| `mf-hades-spec-ambiguity-score` | `spec_ambiguity_score` | ratio | `1 - (unambiguous_spec_predicates / total_spec_predicates)` |
| `mf-hades-TDD-GREEN-failure-count` | — | — | — |
| `mf-hades-binding-completeness` | — | — | — |

공통 키: `commander`('hades') · `metric_name` · `scale` (Stevens 1946) · `formula` · `range_min`/`range_max` · `parent_canonical`. # src: KG read MATCH (m:MeasurementFunction) ... 'hades'; SKILL.md §"Measurement & Conditional Dispatch"

---

## 8. References

- 엔진 정본: `bhgman_tool/engine/hades/hades.py` · `hades_runner.py` · `hades_models.py` · `hades_apply.py`
- `../SKILL.md` (프로토콜 + 4 가드)
- `../../THEORY/하데스/INDEX.md` (정전 identity)
- KG: `hades-canonical-2026-05-27`, `eureka-canonical-2026-05-26` (dual), `7cmd-measurement-driven-conditional-dispatch-2026-05-30`
- 사이블: `../longinus/references/theory.md` (KG↔code binding schema), `../eureka/` (dual — 추상 PROPOSE 측)

# KG: hades-canonical-2026-05-27, ATOM_Skill_hades
