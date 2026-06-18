# Contract Examples — 3 Canonical Patterns (Phase-Specific)

> apt-st 결정화의 *형태*를 보여주는 3 예시. UserProfile (CRUD) / SearchIndex (bulk) / HelloAPT (CLI).

---

## Example 1: CT_UserProfile_Create (Full)

### Task

```yaml
description: "Create new user profile from registration form. Validate email,
  hash password, generate UUID, persist to DB. Handle duplicate/invalid input."
acceptance_criteria:
  - "Returns UserProfile with generated UUID"
  - "Password hashed (bcrypt)"
  - "Email validated with RFC 5322 regex"
  - "Duplicate email raises ConflictError"
  - "p99 latency < 200ms"
  - "Peak memory < 128MB"
impact_tests:
  - "tests/test_user_profile.py::test_create_returns_uuid"
  - "tests/test_user_profile.py::test_password_hashed"
  - "tests/test_user_profile.py::test_email_validation"
  - "tests/test_user_profile.py::test_duplicate_email"
  - "tests/test_user_profile.py::test_latency_p99"
  - "tests/test_user_profile.py::test_memory_peak"
target_file: "src/auth/user_profile.py"
estimated_lines: 85
```

### Contract

```yaml
input_type:    "RegistrationForm{name:str, email:str, password:str}"
output_type:   "UserProfile{id:str, name:str, email:str, created_at:datetime}"
precondition:  "form is not None and len(form.email) > 0 and len(form.password) >= 8
                and '@' in form.email"
postcondition: "result.id is not None and len(result.id) == 36
                and result.email == form.email and result.created_at is not None"
semantic_meaning: "User registration. ID is UUID v4. Password stored as bcrypt hash,
  never in plaintext. Email must be unique across all users."
target_file: "src/auth/user_profile.py"
status: "active"
nfr_latency_p99_ms: 200
nfr_memory_mb: 128
nfr_env_dev:  '{"mock": true, "latency_p99_ms": null, "use_in_memory_db": true}'
nfr_env_prod: '{"mock": false, "latency_p99_ms": 200, "db": "postgresql"}'
```

### Cypher

```cypher
MERGE (ct:AptContract {name: 'CT_UserProfile_Create'})
SET ct.input_type      = 'RegistrationForm{name:str, email:str, password:str}',
    ct.output_type     = 'UserProfile{id:str, name:str, email:str, created_at:datetime}',
    ct.precondition    = 'form is not None and len(form.email) > 0 and len(form.password) >= 8',
    ct.postcondition   = 'result.id is not None and len(result.id) == 36 and result.email == form.email',
    ct.semantic_meaning = 'User registration, UUID v4 ID, bcrypt password hash, unique email',
    ct.target_file     = 'src/auth/user_profile.py',
    ct.status          = 'active',
    ct.nfr_latency_p99_ms = 200,
    ct.nfr_memory_mb   = 128,
    ct.nfr_env_dev     = '{"mock": true, "latency_p99_ms": null}',
    ct.nfr_env_prod    = '{"mock": false, "latency_p99_ms": 200}',
    ct.created_at      = datetime()
```

---

## Example 2: CT_SearchIndex_Build (Bulk + Partial Failure)

### Task

```yaml
description: "Build search index from product catalog. Bulk insert with field mapping,
  tokenization, error handling. Partial failures OK."
acceptance_criteria:
  - "Returns IndexResult with counts"
  - "indexed_count + failed_count == input length"
  - "Empty products raises ValueError"
  - "Missing required fields go to errors list"
  - "< 5000ms for 1000 products"
  - "Peak memory < 1024MB"
target_file: "src/search/indexer.py"
estimated_lines: 180
```

### Contract

```yaml
input_type:    "products: list[Product{id:str, title:str, description:str, price:float, category:str}]"
output_type:   "IndexResult{indexed_count:int, failed_count:int, errors:list[str]}"
precondition:  "len(products) > 0 and all(p.id and p.title for p in products)"
postcondition: "result.indexed_count + result.failed_count == len(products)
                and result.indexed_count > 0"
semantic_meaning: "Bulk product indexing for search. Missing required fields → errors.
  Partial success acceptable."
nfr_latency_p99_ms: 5000
nfr_memory_mb: 1024
```

### SEQUENCED_WITH (Index → Search)

```cypher
MATCH (k1:AptContract {name: 'CT_SearchIndex_Build'})
MATCH (k2:AptContract {name: 'CT_ECommerce_ElasticSearch'})
MERGE (k1)-[:SEQUENCED_WITH {
  entailment: 'k1.postcondition(indexed_count > 0) entails k2.precondition(index exists)',
  condition: null,
  verified_at: datetime()
}]->(k2)
```

자세한 SEQUENCED_WITH 패턴: [sequenced_with.md](sequenced_with.md)

---

## Example 3: CT_HelloAPT_ParseArgs (Minimal CLI)

### Task

```yaml
description: "Parse --name (required, str) and --count (optional, int, default 1).
  Print greeting --count times. Raise UsageError for missing --name."
acceptance_criteria:
  - "--name Alice returns name='Alice'"
  - "--count 3 returns count=3"
  - "missing --name raises UsageError"
  - "--count -1 raises ValueError"
target_file: "src/hello_apt/parse_args.py"
estimated_lines: 45
```

### Contract

```yaml
input_type:    "list[str] — sys.argv[1:]"
output_type:   "ParsedArgs{name: str, count: int}"
precondition:  "len(argv) >= 2 and '--name' in argv"
postcondition: "result.name is not None and len(result.name) > 0 and result.count >= 0"
semantic_meaning: "CLI parsing for greeting. name=person, count=repetition (default 1).
  GNU-style long options."
```

### tau_check 5/5 PASS

| # | Check | Value | Pass? |
|:-:|---|---|:-:|
| 1 | input concrete? | `list[str]` | YES |
| 2 | output concrete? | `ParsedArgs{name:str, count:int}` | YES |
| 3 | precondition boolean? | `len(argv)>=2 and '--name' in argv` | YES |
| 4 | postcondition verifiable? | `result.name is not None and ...` | YES |
| 5 | semantic meaning? | "CLI parsing... GNU-style long options" | YES |

자세한 tau_check before/after: [tau_check.md](tau_check.md)

---

## 패턴 정리

| Example | 핵심 패턴 | 적용 시점 |
|---|---|---|
| UserProfile | CRUD + 환경 변형 NFR (dev/prod) | 표준 데이터 모델 결정화 |
| SearchIndex | Bulk + Partial Failure + SEQUENCED_WITH | 다단계 파이프라인 |
| HelloAPT | Minimal CLI + tau_check 검증 가이드 | 학습용 / 부트스트랩 |

# KG: APT_ST_ContractExamples_canonical
