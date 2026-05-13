# Tutorial — APT Cycle Walkthrough

> 새 프로젝트 / feature / 결정의 *결정화* 를 위한 forward methodology. SemanticAnchor → SemanticPyramid → SemanticTwin → SourceCodeWorld → MetaReview → Cleanup. 각 phase 사이 Gate Check Hook 강제.

---

## 0. 사전 준비

```bash
# bhgman_tool skill 설치
cp -R bhgman_tool/skills/* ~/.claude/skills/
# Claude Code 재시작

# 또는 plugin marketplace
/plugin marketplace add gj3447/bhgman_tool
/plugin install bhgman-apt-cycle@bhgman_tool
```

---

## 1. 전체 cycle 한 눈에

```
사용자 발화 "X 만들어줘"
         ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 1: SemanticAnchor (SA)                            │
│   project identity + objective + 5 core field 설정      │
│   Gate: AnchorIdentity / ProgressiveDisclosure /        │
│         ContextBudget / KG-first                        │
│   Skill: /apt-sa                                        │
└─────────────────────────────────────────────────────────┘
         ↓ SA Gate 통과
┌─────────────────────────────────────────────────────────┐
│ Phase 2: SemanticPyramid (SP)                           │
│   recursive Span decomposition (DAG, N:N)               │
│   C(S) 5-predicate 만족까지 D(S) recurrence             │
│   Gate: LensSet completeness + Taliban adversarial      │
│   Skill: /apt-sp                                        │
└─────────────────────────────────────────────────────────┘
         ↓ SP Gate (Crystallization Frontier — all leaves AtomicSpan)
┌─────────────────────────────────────────────────────────┐
│ Phase 3: SemanticTwin (ST)                              │
│   Contract (typed DTO/Schema) + Task + 8 decision area  │
│   8 area: AST/Workflow/DesignPattern/ProjectStructure   │
│           /DataFlow/Algorithm/Store/ClassDesign         │
│   Skill: /apt-st                                        │
└─────────────────────────────────────────────────────────┘
         ↓ ST Gate
┌─────────────────────────────────────────────────────────┐
│ Phase 4: SourceCodeWorld (SCW)                          │
│   TDD: Contract → RED test → GREEN code → REFACTOR      │
│   Gate: FulfillmentGate 7 checks (executor!=critic,     │
│         LensSet completeness, prior VR APPROVED, ...)   │
│   Invariant: 모든 코드에 `# KG: lesson-xxx` 주석        │
│   Skill: /apt-scw                                       │
└─────────────────────────────────────────────────────────┘
         ↓ SCW Gate
┌─────────────────────────────────────────────────────────┐
│ Phase 5: MetaReview                                     │
│   의심/피드백 → 스킬 강화 자동 루프                     │
│   SKILL.md 패치 + MATERIALIZES 갱신 + Taliban Gate      │
│   Termination: self_application_forbidden, max_depth=1  │
│   Skill: /apt-meta-review                               │
└─────────────────────────────────────────────────────────┘
         ↓ MetaReview Gate
┌─────────────────────────────────────────────────────────┐
│ Phase 6: Cleanup Gate                                   │
│   TDD REFACTOR 의 cycle-level mirror                    │
│   Folder-level: Robert Martin Package Principles        │
│   (CCP/CRP/REP/ADP/SDP/SAP)                             │
│   4-tool ratchet: Tach / complexipy / Lizard /          │
│                    vulture / deptry                     │
│   Skill: /apt-cleanup                                   │
└─────────────────────────────────────────────────────────┘
         ↓
완성된 결정화 산출물
```

---

## 2. 실 예시 — "user authentication 추가"

### Phase 1 — SemanticAnchor

```
사용자: user authentication 추가해줘
AI: /apt-sa

→ 5 core field 설정:
  objective: "Add user authentication to the application"
  definition: "JWT-based authentication with bcrypt password hashing,
               session management via HttpOnly cookies"
  keyAssertion: "Every protected route requires valid JWT;
                 expired tokens trigger refresh flow"
  C_S: ["security_critical", "session_managed", "stateless_jwt"]
  contextBudget: 8000 tokens for SP phase

→ Gate check (Cypher):
  ✓ AnchorIdentity: project node 'auth-feature-2026-05-13' 생성
  ✓ ProgressiveDisclosure: definition < contextBudget
  ✓ ContextBudget: 8000 within session limit
  ✓ KG-first: 기존 :Lesson 측 검색 (lesson-jwt-handling-*, ...)
  → SA Gate PASS
```

### Phase 2 — SemanticPyramid (recursive decomposition)

```
AI: /apt-sp 'auth-feature-2026-05-13'

→ D(S) 첫 round:
  Span 1: "JWT token generation & validation"
  Span 2: "Password hashing & verification (bcrypt)"
  Span 3: "Session management (HttpOnly cookies)"
  Span 4: "Protected route middleware"
  Span 5: "Token refresh flow"

→ 각 Span 의 C(S) 5-predicate 평가:
  Span 1: objective ✓ / definition ✓ / keyAssertion ✓ / verification ✓ / c_s_predicate ✓
    → AtomicSpan (leaf)
  Span 2: AtomicSpan
  Span 3: definition 부족 → D(S) recurse
    Span 3.1: "Set HttpOnly cookie on login"
    Span 3.2: "Clear cookie on logout"
    Span 3.3: "Refresh cookie on activity"
    각각 AtomicSpan
  Span 4: AtomicSpan
  Span 5: AtomicSpan

→ Crystallization Frontier: 7 AtomicSpan (1, 2, 3.1, 3.2, 3.3, 4, 5)

→ Gate check:
  ✓ LensSet completeness: constitutional 9-lens 모두 적용
  ✓ Taliban adversarial: executor != reviewer
  → SP Gate PASS
```

### Phase 3 — SemanticTwin (crystallization)

```
AI: /apt-st 'auth-feature-2026-05-13'

→ 각 AtomicSpan 측 Contract + Task + 8 decision area:

Span 1 "JWT token generation & validation":
  Contract:
    - shape: typed DTO (Pydantic v2)
    - fields: { sub: str, exp: datetime, iat: datetime, aud: str }
    - methods: generate(user_id) → str, verify(token: str) → claims | None
    - error_variants: ExpiredTokenError, InvalidSignatureError, MalformedTokenError
    - shared: false
    - access_rights: {read: all, write: auth_service}
  Task: "Implement JWT codec via PyJWT library, verify against secret rotation"
  8 decision areas:
    AST: "auth/jwt_codec.py module"
    Workflow: "issue → verify on every request"
    DesignPattern: "Strategy (codec swappable)"
    ProjectStructure: "src/auth/jwt_codec.py"
    DataFlow: "user_id → token → claims"
    Algorithm: "HS256 (or RS256 for asymmetric)"
    Store: "secret in env var, not DB"
    ClassDesign: "JwtCodec class, methods generate/verify"

Span 2 ... 7: similar
```

### Phase 4 — SourceCodeWorld (TDD)

```
AI: /apt-scw 'auth-feature-2026-05-13'

→ Span 1 (JWT codec) TDD:

  RED:
    # tests/auth/test_jwt_codec.py
    # KG: lesson-jwt-handling-2026-05-13
    def test_generate_includes_claims():
        token = JwtCodec.generate(user_id="u-1")
        claims = JwtCodec.verify(token)
        assert claims['sub'] == "u-1"
        assert 'exp' in claims

    def test_verify_rejects_expired():
        token = make_expired_token()
        with pytest.raises(ExpiredTokenError):
            JwtCodec.verify(token)

    # pytest fails (JwtCodec doesn't exist yet)
    # RED ✓

  GREEN:
    # src/auth/jwt_codec.py
    # KG: lesson-jwt-handling-2026-05-13 (Longinus L4 SemioticBinding)
    import jwt
    from datetime import datetime, timedelta

    class JwtCodec:
        @classmethod
        def generate(cls, user_id: str) -> str:
            payload = {
                'sub': user_id,
                'exp': datetime.utcnow() + timedelta(hours=1),
                'iat': datetime.utcnow(),
                'aud': 'app',
            }
            return jwt.encode(payload, SECRET, algorithm='HS256')

        @classmethod
        def verify(cls, token: str) -> dict | None:
            try:
                return jwt.decode(token, SECRET, algorithms=['HS256'], audience='app')
            except jwt.ExpiredSignatureError:
                raise ExpiredTokenError() from None

    # pytest passes ✓

  REFACTOR:
    - 추출: secret loading → SecretProvider DI
    - 명명: SECRET → _SECRET (private)
    - 주석 정리

→ FulfillmentGate 7 checks:
  ✓ executor != critic (User: executor / Taliban: critic)
  ✓ LensSet completeness: constitutional 9-lens
  ✓ prior VR APPROVED: Span 1 SP gate passed
  ✓ KG ref present: `# KG: lesson-jwt-handling-2026-05-13` in code + test
  ✓ Longinus ReferenceSite 7-tuple verified
  ✓ Test coverage: 100% on jwt_codec.py
  ✓ Type check (mypy): passes
  → SCW Gate PASS for Span 1

→ Span 2 ... 7: 동일 TDD cycle

→ 전체 cycle 완료 후 SCW Gate (cycle-level)
```

### Phase 5 — MetaReview

```
AI: /apt-meta-review 'auth-feature-2026-05-13'

→ 의심/피드백 수집:
  - Lesson 후보: "lesson-jwt-secret-rotation-strategy-2026-05-13"
    (작업 중 발견: secret 회전 시 grace period 필요 — 1차에 누락)
  - Skill 패치 후보: apt-scw/SKILL.md 측 "secret-handling checklist" 추가

→ Symmetric pair 박기:
  wrongAssumption: "JWT secret 은 단일 값으로 충분"
  truth: "Secret rotation 시 grace period (이전 secret 도 일정 시간 verify 허용) 필요.
          그렇지 않으면 모든 active session 이 invalidate."

→ SKILL.md 패치 + KG :Lesson 노드 박기

→ Taliban Gate:
  ✓ Lesson grounded in external canon (RFC 8725 JWT BCP)
  ✓ Symmetric pair complete
  ✓ resolved=false (rotation logic 아직 구현 안 됨, 별 sprint)
  → MetaReview Gate PASS

→ Termination:
  - self_application_forbidden: 이 meta-review 가 자기 자신 review 불가
  - max_depth=1: meta-meta-review 진행 안 함
  - delta=0: 이상 더 의심 / 피드백 없음
```

### Phase 6 — Cleanup

```
AI: /apt-cleanup 'auth-feature-2026-05-13'

→ Folder-level Robert Martin Package Principles 검증:
  CCP (Common Closure): auth/ 내부가 함께 변하는 단위 ✓
  CRP (Common Reuse): auth/ 의 일부만 reuse 가능 (jwt_codec / password_hasher) ✓
  REP (Reuse-Release Equivalence): auth/ 한 단위 release 가능 ✓
  ADP (Acyclic Dependencies): src/auth → src/core (단방향) ✓
  SDP (Stable Dependencies): src/auth 가 src/core 에 의존 (안정 의존) ✓
  SAP (Stable Abstractions): src/core 가 더 추상적 ✓

→ 4-tool ratchet:
  Tach: import 경계 ✓
  complexipy --ratchet: 복잡도 baseline 유지 ✓
  Lizard: function size baseline 유지 ✓
  vulture: dead code 없음 ✓
  deptry: dependency 정합 ✓

→ Commit ratio metric:
  refactor commits : feature commits = 0.25 (≥ 0.2 OK)

→ Cleanup Gate PASS
```

---

## 3. 진입 명령 요약

```bash
/apt              # 전체 cycle 자동 진입
/apt-sa <name>    # SA phase 직접
/apt-sp <span>   # SP phase recursive decomposition
/apt-st <span>   # ST crystallization
/apt-scw <task>  # SCW TDD implementation
/apt-meta-review # MetaReview phase
/apt-cleanup     # Cleanup phase
```

---

## 4. KG 측 결정화 결과

각 phase 측 KG 노드 박힘:
```
(:Project {name: 'auth-feature-2026-05-13'})
  -[:HAS_PHASE]-> (:SemanticAnchor {core_fields: ...})
  -[:HAS_PHASE]-> (:SemanticPyramid {atomic_spans: [...]})
  -[:HAS_PHASE]-> (:SemanticTwin {contracts: [...], tasks: [...]})
  -[:HAS_PHASE]-> (:SourceCodeWorld {commits: [...], pytest_pass: 12/12})
  -[:HAS_PHASE]-> (:MetaReview {lessons: [...], skill_patches: [...]})
  -[:HAS_PHASE]-> (:CleanupGate {package_principles_pass: 6/6})
```

각 phase 결과는 영구 retrievable. 추후 같은 패턴 재사용 가능.

---

## 5. ruflo 대비 차별점

| 측면 | ruflo | APT cycle (bhgman) |
|---|---|---|
| 시작 phase | "swarm init" (orchestration setup) | SemanticAnchor (objective + 5 core field) |
| 의미층 결정 | 없음 | SP recursive decomposition + Crystallization Frontier |
| 형식 검증 | none built-in | Lean 4 + Taliban LensSet + Cypher Gate Hook |
| TDD 강제 | 권장 | mandatory (RED→GREEN→REFACTOR 강제) |
| Feedback loop | SONA self-learning (Goodhart 무방비) | MetaReview symmetric pair + Lakatos audit |
| 종료 조건 | 사용자 stop | self_application_forbidden + max_depth=1 + delta=0 |

---

## 6. 자세히는

- [../02-concepts/airplane-man.md](../02-concepts/airplane-man.md) — 비행기맨 정의
- [../02-concepts/harness.md](../02-concepts/harness.md) — 4축 모델 (Inform/Constrain/Verify/Correct 가 APT 각 phase 의 내부 조직)
- [longinus-drift-audit.md](longinus-drift-audit.md) — Longinus 측 KG ref 박는 법
- [../05-papers/lakatos-1976.md](../05-papers/lakatos-1976.md) — progressive/degenerating verdict (MetaReview 측)
- [../05-papers/cherns-1976-sts.md](../05-papers/cherns-1976-sts.md) — Cleanup 측 package-level boundary
