# apt-cleanup — CanonicalServiceTemplate (folder taxonomy)

> **Lazy-load reference** — read when 새 service/skill 생성 / fat folder 분해 시.
> Parent: [`../SKILL.md`](../SKILL.md).

---

## CanonicalServiceTemplate (사용자 박은 spec)

새 service 생성 시 권장 layout. **Vertical Slice + Bounded Context + DDD layered** 통합.

```
<service-name>/
├── domain/                  # entities, value objects, domain events, domain services
│   ├── __init__.py
│   ├── models.py            # entities + value objects (no IO)
│   ├── events.py            # domain events
│   └── services.py          # pure domain logic
│
├── application/             # use cases, commands, queries, ports
│   ├── __init__.py
│   ├── commands/            # write-side use cases (CQRS)
│   ├── queries/             # read-side use cases
│   └── ports/               # interfaces (driven ports)
│
├── infrastructure/          # adapters (DB, HTTP, MQ, Cache) — IO at boundary
│   ├── __init__.py
│   ├── persistence/         # repository implementations
│   ├── http/                # outbound HTTP clients
│   ├── messaging/           # MQ consumers/producers
│   └── adapters.py
│
├── api/                     # entry point (driving adapter)
│   ├── __init__.py
│   ├── routes.py            # REST/GraphQL/gRPC handlers
│   ├── schemas.py           # request/response DTOs
│   └── middleware.py
│
├── tests/                   # mirror domain/application structure
│   ├── unit/
│   │   ├── test_domain_models.py
│   │   └── test_application_commands.py
│   ├── integration/
│   │   └── test_persistence.py
│   └── e2e/
│       └── test_api.py
│
├── tach.toml                # ADP enforcement (folder dependency rules)
├── pyproject.toml           # deptry + complexipy config
└── README.md                # service intent (Screaming Architecture)
```

---

## CCP / CRP / ADP 적용

### CCP (Common Closure)
- 같은 *domain entity* 변경 → 같은 folder 내부 (`domain/models.py` + `domain/services.py`)
- application use case 추가 → `application/commands/` 또는 `application/queries/` 만 수정 (다른 folder 무관)

### CRP (Common Reuse)
- `domain/` 만 import 하는 use case → `application/`
- `application/` + `domain/` 만 import → `infrastructure/`
- import depth 가 layer 만큼 — 위반 시 tach 검출

### ADP (Acyclic Dependencies)
```toml
# tach.toml
[[modules]]
path = "domain"
depends_on = []                    # innermost — depend on nothing

[[modules]]
path = "application"
depends_on = ["domain"]            # depend only on domain

[[modules]]
path = "infrastructure"
depends_on = ["domain", "application"]

[[modules]]
path = "api"
depends_on = ["application", "infrastructure"]
```

→ 의존 방향 = 안쪽 (domain) ← 바깥쪽 (api). cycle 발생 시 tach 에러.

---

## Anti-pattern (감지 + 정정)

### 1. **Prefix-as-folder smell** (사용자 박은 evidence: prismv2)

```
api_gateway/src/
├── runner.py                  # 280 LOC
├── runner_38v.py              # 165 LOC, 60% overlap with runner.py ← SMELL
├── runner_legacy.py           # 95 LOC
└── handler_v2.py              # ...
```

prefix (`runner_*`, `*_v2`) 로 folder 효과 흉내 = anti-pattern. **진짜 folder** 로 분리:

```
api_gateway/src/
└── runner/
    ├── __init__.py            # public API (re-export)
    ├── current.py             # 통합본 (was runner.py + runner_38v.py)
    └── legacy.py              # was runner_legacy.py (deprecation marker)
```

### 2. **Fat file** (사용자 박은 evidence: api_gateway/main.py 963 LOC)

```
main.py 963 LOC                     →  분해
├── (혼재) auth, routing, db, ...     ├── api/main.py 80 LOC (entry only)
                                       ├── api/auth.py
                                       ├── api/routes/
                                       └── infrastructure/db.py
```

threshold: `MethodologyConfig.cleanup_fat_file_threshold` (default 500). lizard `--length 50` 함수 단위 + lizard 전체 파일 LOC 측정.

### 3. **Layer-by-layer flat** (Package by Layer anti-pattern)

```
src/
├── controllers/   ← ALL controllers (50 files)
├── services/      ← ALL services (50 files)
└── repositories/  ← ALL repositories (50 files)
```

→ feature 추가 시 3 folder 수정 (CCP 위반). 정정: Package by Feature.

### 4. **Duplicate module 60% overlap**

```python
# runner.py
def execute(task): ... 250 LOC ...

# runner_38v.py  ← 60% overlap (identical except 38 lines)
def execute_v38(task): ... 250 LOC, 38 different ...
```

→ 정정: 공통 부분 추출 + variant 분리

```python
# runner/core.py
def _execute_base(task, hooks=None): ... shared 212 LOC ...

# runner/current.py
def execute(task):
    return _execute_base(task)

# runner/v38.py
def execute_v38(task):
    return _execute_base(task, hooks=V38_HOOKS)
```

---

## "Screaming Architecture" 적용 — top-level 폴더는 도메인

### Bad (framework-driven)

```
src/
├── django_app/        # framework name
├── flask_routes/      # framework concept
└── sqlalchemy_models/ # ORM concept
```

→ "이게 Django app 이구나" 만 알 수 있음.

### Good (domain-driven)

```
src/
├── billing/           # 도메인
├── shipping/          # 도메인
├── inventory/         # 도메인
└── shared/            # cross-cutting
```

→ "이건 e-commerce 시스템이구나" 비명.

---

## Bounded Context 분리 (Modular Monolith)

```
modules/
├── billing/           # bounded context 1
│   ├── domain/, application/, infrastructure/, api/
│   └── tach.toml      # billing 만 import 허용
│
├── shipping/          # bounded context 2
│   └── ... (independent)
│
└── shared/            # 공유 kernel (최소화)
    └── value_objects.py
```

→ 각 BC = 독립 진화. 통신 = explicit interface (event bus / context map).

---

## tach.toml 예시 (CanonicalServiceTemplate 적용)

```toml
[[modules]]
path = "user.domain"
depends_on = ["shared"]

[[modules]]
path = "user.application"
depends_on = ["user.domain", "shared"]

[[modules]]
path = "user.infrastructure"
depends_on = ["user.domain", "user.application", "shared"]

[[modules]]
path = "user.api"
depends_on = ["user.application", "user.infrastructure", "shared"]

[[modules]]
path = "shared"
depends_on = []
```

---

## CleanupRun 후보 권고 (gate fail 시)

```python
recommendations = [
    f"Fat file: {path} ({loc} LOC) → split into {suggested_folder}/",
    f"Prefix smell: {prefix}_*.py → folder {prefix}/",
    f"Duplicate: {a} + {b} {overlap}% overlap → extract common to {shared}/",
    f"Layer-by-layer: top-level controllers/services/ → reorganize by feature",
]
```

→ KG 기록:

```cypher
MATCH (cr:CleanupRun {name: 'cleanup-' + $cycle})
SET cr.refactor_recommendations = $recommendations,
    cr.gate_passed = false
MERGE (sr:RefactorSpec {name: 'refspec-' + $cycle})
SET sr.recommendations = $recommendations, sr.severity = 'HIGH'
MERGE (cr)-[:RECOMMENDS]->(sr)
```

→ 다음 SCW cycle 에서 `RefactorSpec` 가 `SubagentTaskSpec` 으로 발아.

---

# KG: lesson-prismv2-services-flat-layout-decay-20260428
