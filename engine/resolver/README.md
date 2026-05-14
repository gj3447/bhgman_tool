# APT v27 Pre-Prompt Resolver (bhgman_tool engine/resolver)

> **Absorbed**: 2026-05-14 Wave 7 P3-H from SYMPOSIUM/THEORY/APT/resolver_prototype/
> **Original verification**: 9/9 pytest PASS on dgx (Python 3.12 aarch64 Ubuntu 24.04)
> **RFC**: `rfc-apt-v26-A6-resolver-path-A-pre-prompt-hook-2026-04-30` ACCEPTED
> **Sprint**: 1 (3주 estimate, apt-sa 먼저)
> **Stack**: Python 3.11+ / `python-frontmatter` / `Jinja2` (SandboxedEnvironment) / `neo4j` driver

## CLI entry

```bash
bhgman-tool resolver render   --input <SKILL.md> --output <resolved.md>
bhgman-tool resolver validate <SKILL.md>
# or module mode:
python -m engine.resolver.resolver render   --input <SKILL.md> --output <resolved.md>
python -m engine.resolver.resolver validate <SKILL.md>
```

---

## Original prototype documentation (path references relative to SYMPOSIUM)

---

## 목적

SKILL.md를 *static prompt*로 두지 않고 *KG metadata + runtime interpolation*로 양층 분리. v26 A6 directive ("magic number 본문 박지 말고 KG slot resolve")의 실제 작동 구현.

```
SKILL.md (frontmatter + body with {{cfg.X}} markers)
        │
        ▼
    [resolver.py]
    1. python-frontmatter로 frontmatter parse
    2. Jinja2 SandboxedEnvironment로 {{cfg.X}} 마커 발견
    3. neo4j driver로 KG Cypher 쿼리 → MethodologyConfig 노드에서 X 값 추출
    4. .render() → resolved prompt
        │
        ▼
    Final prompt (Claude Code dispatch)
```

## 파일 구조

```
resolver_prototype/
├── README.md                    ← 본 파일
├── pyproject.toml               ← 의존성
├── resolver.py                  ← 메인 entry
├── frontmatter_parser.py        ← python-frontmatter wrapper
├── cypher_kg_client.py          ← neo4j driver + Cypher 쿼리
├── jinja_env.py                 ← SandboxedEnvironment 설정
├── example_skill.md             ← 테스트용 SKILL.md
└── tests/
    ├── test_resolver.py
    ├── test_drift_detection.py
    └── fixtures/
        └── mock_kg.cypher       ← 로컬 mock KG seed
```

## 의존성

```toml
# pyproject.toml
[project]
name = "apt-resolver"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "python-frontmatter>=1.1.0",
  "Jinja2>=3.1.4",
  "neo4j>=5.20.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]
```

## 사용법

```bash
# Setup
cd THEORY/APT/resolver_prototype
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Resolve (Cypher KG 연결 가정)
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="..."
python resolver.py --input ../../../SKILLS/apt-sa/SKILL.md --output /tmp/apt-sa-resolved.md

# Validate (drift detection: KG ↔ SKILL.md 일관성)
python resolver.py --validate ../../../SKILLS/apt-sa/SKILL.md
# → 0 errors expected after Sprint 2b 변환 완료
```

## 명세 (Sprint 2b 의존)

resolver는 SKILL.md `body`에서 `{{cfg.X}}` 마커 발견 시:

1. KG `MethodologyConfig_default_v27` 노드에서 `cfg.X` 필드 조회
2. *값 미존재* → ERROR (`MissingConfigError`) + drift 보고
3. *값 존재* → Jinja2 SandboxedEnv로 안전 렌더링
4. 결과 = resolved prompt (Claude Code skill loader가 사용)

## Composition Root 정책 (eager validation)

resolver 시작 시:
1. KG 연결 health check
2. `MethodologyConfig_default_v27` 5 core field 모두 존재 검증
3. SandboxedEnv 보안 정책 확인 (no `__getattr__`, no `__import__`)
4. Cypher 쿼리 cache (TTL 60s)

→ 1-3 중 하나라도 실패 시 startup exception. SKILL.md 절대 부분-resolved 상태로 출력 안 함.

## Drift Detection (Sprint 2b 후 활성)

```
python resolver.py --validate <SKILL.md>
```

검사 항목:
1. SKILL.md `{{cfg.X}}` 마커 모두 KG에 존재
2. 본문 inline 숫자 (200/500/9 등)가 *괄호 안 reader-facing 안내*만 (e.g. "(현재 200)"). 그 외 위치 발견 시 ERROR
3. KG cfg field 중 *어디서도 참조 안 됨* 검사 (orphan)

## 보안 (LangChain CVE-2025-68664 대응)

- Jinja2 SandboxedEnvironment 강제 (`autoescape=True`, `__getattr__` 차단)
- `lc` key 검증 (LangChain serialization injection 회피)
- KG 응답에 untrusted code 포함 시 raise (whitelist field 만 통과)
- MCP server-side error message sterilization (만약 MCP wrapper 추가 시)

## 후속 sprint 의존

| Sprint | 의존 | 내용 |
|---|---|---|
| **2b** | Sprint 1 완료 | apt-sp/st/scw 본문 5 core magic → `{{cfg.X}}` 변환 |
| **3** | (병렬) | gate fail-closed HTTP endpoint 구축 |
| **4a/4b** | (병렬) | Neo4j DispatchHyperedge 정형화 → TypeDB POC |

## 상태

- [x] README + 명세 작성 (본 파일)
- [x] pyproject.toml
- [x] resolver.py 골격 + interface
- [x] frontmatter_parser.py
- [x] cypher_kg_client.py
- [x] jinja_env.py
- [x] example_skill.md
- [ ] tests/ (Sprint 1 sub-task — 후속)
- [ ] apt-sa SKILL.md *실제 적용* (Sprint 1 마지막 단계)
