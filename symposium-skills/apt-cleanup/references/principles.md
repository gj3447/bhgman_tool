# apt-cleanup — Robert Martin Package Principles + Cohesion 학문 grounding

> **Lazy-load reference for `apt-cleanup` skill.**
> Read when: 학술 인용 필요 / 사용자가 "왜 SOLID만 하면 안되냐" 질문 / paper 작성.
> Parent: [`../SKILL.md`](../SKILL.md).
> KG: `lesson-solid-class-level-vs-package-level-mismatch-2026-04-29`.

---

## 1. SOLID는 class-level — Package Principles는 folder-level

### SOLID 5 (Robert Martin, *Agile Software Development*, 2002)

| | 원리 | layer |
|---|---|---|
| **S** | Single Responsibility | class |
| **O** | Open-Closed | class |
| **L** | Liskov Substitution | class hierarchy |
| **I** | Interface Segregation | class interface |
| **D** | Dependency Inversion | class dependency |

→ 모두 *class/method/interface* 단위 규칙.

### Package Principles 6 (Robert Martin, *Clean Architecture*, 2017)

| | 원리 | 한 줄 정의 |
|---|---|---|
| **CCP** | Common Closure Principle | "같이 변하는 것 같이 묶어라" — gathered for the same reason |
| **CRP** | Common Reuse Principle | "같이 재사용되는 것 같이 묶어라" — used together belong together |
| **REP** | Reuse-Release Equivalence | "재사용 단위 = 릴리즈 단위" — granule of reuse = granule of release |
| **ADP** | Acyclic Dependencies | "패키지 의존 cycle 금지" — directed acyclic graph |
| **SDP** | Stable Dependencies | "안정적인 쪽으로 의존" — depend in direction of stability |
| **SAP** | Stable Abstractions | "안정 = 추상도 비례" — stable packages should be abstract |

### LLM "SOLID하게" 지시 시 발생하는 일

```
입력:  "SOLID 원칙 따라서 만들어줘"
LLM:   class/function 분리 잘함 (SRP/OCP/LSP/ISP/DIP 각각 만족)
출력:  117 .py file ALL flat in one directory
진단:  - class-level: PASS (각 파일이 SRP 통과)
       - folder-level: FAIL (CCP/CRP 위반, 같이 변하는 것 흩어짐)
```

**원인**: SOLID 만으로는 *분리한 클래스를 어느 폴더에 둘지* 규칙이 없음. Package Principles 가 그 규칙.

→ **결론**: LLM/agent 에게 둘 다 명시해야 함:
- "SOLID 원칙 + CCP/ADP folder cohesion + Vertical Slice layout"

---

## 2. Cohesion / Coupling — 모든 architecture 이론의 끌리

### Stevens-Myers-Constantine (1974) "Structured Design"
원전: *IBM Systems Journal* 13(2), 1974.

**Cohesion 7-tier scale** (낮음→높음):
1. Coincidental — 임의 묶음
2. Logical — 논리적 분류
3. Temporal — 시간적
4. Procedural — 절차적
5. Communicational — 같은 데이터
6. Sequential — 출력→입력 사슬
7. **Functional** — 단일 목적 (BEST)

**Coupling 6-tier scale** (높음→낮음):
1. Content — 다른 module 내부 직접 변경 (WORST)
2. Common — global state 공유
3. Control — flag 전달
4. Stamp — 데이터 구조 일부만 사용
5. Data — primitive 만 전달
6. **None** — 무관 (BEST)

**모든 후대 architecture 이론** (DDD, Clean Arch, Hexagonal, Onion, Modular Monolith) = Stevens-Myers-Constantine 의 *cohesion 높이고 coupling 낮춤* 의 다른 표현.

### LCOM (Chidamber-Kemerer 1994)
원전: *IEEE Transactions on Software Engineering* 20(6), 1994.

```
LCOM = | {(i,j) : I_i ∩ I_j = ∅} | - | {(i,j) : I_i ∩ I_j ≠ ∅} |

I_k = method k 가 사용하는 instance variable set
LCOM 높음 = method 간 instance variable 공유 적음 = cohesion 낮음 = 분리 후보
```

→ 정량 metric. Phase 6 ratchet 의 이론 기반.

---

## 3. Architectural Patterns (folder layout)

### Package by Feature vs Package by Layer

**Package by Layer** (anti-pattern):
```
src/
├── controllers/   # ALL controllers
├── services/      # ALL services
├── repositories/  # ALL repositories
└── models/        # ALL models
```
→ feature 추가 시 4 folder 모두 수정 (CCP 위반). gravitational center 없음.

**Package by Feature** (권장):
```
src/
├── user/          # user feature 모든 layer
│   ├── controller.py
│   ├── service.py
│   ├── repository.py
│   └── model.py
└── order/         # order feature 모든 layer
    ├── ...
```
→ feature 변경 → 한 folder. CCP 만족.

### Vertical Slice Architecture (Jimmy Bogard 2018)
원전: jimmybogard.com/vertical-slice-architecture/

> "Minimize coupling *between* slices, and maximize coupling *within* a slice."

각 feature = 자기 충족 vertical slice. controller→service→repo→DB 가 slice 내부에서 완성. slice 간 통신 = explicit interface.

→ Package by Feature 의 발전형. CQRS 와 정합.

### Screaming Architecture (Robert Martin)
원전: cleancoder.com/blog/2011/09/30/Screaming-Architecture.html

> "Your architecture should scream the intent of the system."

폴더 보면 *이게 무슨 앱인지* 비명질러야 함. Spring/Django framework 가 아닌 *도메인* (user, order, billing) 이 top-level.

### Modular Monolith (Simon Brown)
원전: codingthearchitecture.com/2014/

> "A monolith with explicit module boundaries."

microservices 의 distributed cost 없이 monolith 안에서 module 경계 강제. Vertical Slice + ADP 적용.

### Bounded Context (Eric Evans, *Domain-Driven Design*, 2003)
DDD 의 핵심 — 도메인 모델의 *명시적 경계*. 각 bounded context = 자기만의 ubiquitous language. context map 으로 관계 표현.

→ Package by Feature 의 도메인 driven 결정형.

---

## 4. GitClear 2024 — Industry Evidence

### "Coding on Copilot: 2024 Data Suggests Downward Pressure on Code Quality"

원전: gitclear.com/coding_on_copilot_data_shows_ais_downward_pressure_on_code_quality (2024)

**핵심 finding**:
- Copilot/AI agent 도입 후 *code churn 증가* (2 weeks 내 변경/삭제 비율)
- 같은 코드 다시 쓰기 (rewrite churn) 비율 GitHub 평균 대비 *2x*
- Refactoring vs Adding Code 비율 *감소*

**원인 가설**:
- AI agent 가 *append-mode* (새 파일/코드 추가) 선호
- 기존 코드 *consolidation/refactor* 안 함
- atomic-span shipping = 1 task → 1 file 정확히 이 패턴

→ **Phase 6 Cleanup Gate 가 정확히 이 churn 정정 메커니즘**:
- refactor:feature commit ratio ≥ 0.2 강제
- 누적 N 사이클 ratchet
- vulture 로 dead code 검출 → 자동 정리 권고

---

## 5. Symposium 의 정전 통합

### 사용자 박은 lesson 들

- `lesson-apt-phase6-cleanup-missing-2026-04-28` (HIGH, unresolved → spec'd by apt-cleanup v1.0.0)
- `lesson-prismv2-services-flat-layout-decay-20260428` (구체 evidence: api_gateway/main.py 963 LOC, runner.py + runner_38v 60% overlap)
- `lesson-solid-class-level-vs-package-level-mismatch-2026-04-29` (PROM 16 deepening — class-level vs folder-level dualism)

### KG ArchitecturalPrinciple 14 nodes

PROM 16 F7 에서 placeholder 로 결정화:
```cypher
MATCH (pp:ArchitecturalPrinciple) WHERE pp.cycle_id = 'prom16-skill-versioning-2026-04-29'
RETURN pp.name, pp.attribution, pp.layer, pp.short
```

도착 시 evidence text + Longinus L3 binding 채워짐 (사용자가 paper 가져오는 중).

---

## References (실제 1차 소스 URL — Longinus L3 후보)

- Robert Martin (2017) *Clean Architecture* — packageprinciples.html
- Stevens-Myers-Constantine (1974) "Structured Design" — *IBM Systems Journal* 13(2)
- Chidamber-Kemerer (1994) "A Metrics Suite for Object Oriented Design" — *IEEE TSE* 20(6)
- Jimmy Bogard (2018) "Vertical Slice Architecture" — jimmybogard.com
- Robert Martin "Screaming Architecture" — blog.cleancoder.com
- Simon Brown "Modular Monolith" — codingthearchitecture.com
- Eric Evans (2003) *Domain-Driven Design* — Addison-Wesley
- GitClear (2024) "Coding on Copilot" — gitclear.com

→ 사용자 자료 도착 시 URL/PDF MinIO 업로드 + ArchitecturalPrinciple node 14개에 :HAS_REFERENCE binding.

# KG: lesson-solid-class-level-vs-package-level-mismatch-2026-04-29
