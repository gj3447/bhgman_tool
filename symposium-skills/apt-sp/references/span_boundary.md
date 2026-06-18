# Span Boundary Enforcement (Phase-Specific)

> 각 AtomicSpan에 `allowed_paths`와 `forbidden_patterns` 명시. SCW Phase에서 pre-commit hook으로 위반 검증.

---

## allowed_paths / forbidden_patterns

```cypher
MATCH (atom:AtomicSpan {name: $atom})
SET atom.allowed_paths = $paths,           -- ['src/module_a/', 'tests/test_module_a.py']
    atom.forbidden_patterns = $patterns    -- ['import module_b', 'from module_c']
```

- **allowed_paths**: 이 Span이 *수정 가능*한 파일/디렉토리. 다른 경로 수정 시 SCW에서 차단.
- **forbidden_patterns**: 이 Span의 코드에서 *금지된 import/패턴*. 다른 모듈 침범 방지.

---

## 경계 결정 알고리즘

SP가 AtomicSpan 결정 시점에 boundary 자동 추론:

```cypher
// Span의 description + INFORMED_BY 링크에서 module/path 키워드 추출
MATCH (atom:AtomicSpan {name: $atom})-[:INFORMED_BY]->(k)
WITH atom, collect(k.name) AS info_nodes,
     [w IN split(atom.description, ' ') WHERE w =~ '[a-z_]+\\.[a-z]+'] AS path_hints
SET atom.allowed_paths = path_hints,
    atom.forbidden_patterns =
      [n IN info_nodes WHERE n CONTAINS 'OtherModule' | 'import ' + n]
RETURN atom.allowed_paths, atom.forbidden_patterns
```

자동 추론이 불완전하면 인간/에이전트가 수동 보강.

---

## SCW에서의 적용

SCW pre-commit hook이 commit 직전 검증:

```bash
# pre-commit hook 예시 (Python)
import sys
from neo4j_client import resolve_atom

atom_name = sys.argv[1]
atom = resolve_atom(atom_name)
changed_files = subprocess_check("git diff --cached --name-only").split('\n')

violations = []
for f in changed_files:
    if not any(f.startswith(p) for p in atom['allowed_paths']):
        violations.append(f"path violation: {f} not in allowed_paths")

with open(atom['target_file']) as fp:
    code = fp.read()
    for pattern in atom['forbidden_patterns']:
        if pattern in code:
            violations.append(f"forbidden pattern: {pattern}")

if violations:
    print('\n'.join(violations), file=sys.stderr)
    sys.exit(1)
```

---

## 검증 query

```cypher
-- V-SP-Boundary-1: AtomicSpan에 boundary 미설정
MATCH (atom:AtomicSpan) WHERE atom.status = 'crystallized'
WHERE atom.allowed_paths IS NULL OR size(atom.allowed_paths) = 0
RETURN 'V_SP_Boundary_NoAllowedPaths' AS validation,
       atom.name AS atom

-- V-SP-Boundary-2: forbidden_patterns에 자기 모듈 포함 (자기 차단)
MATCH (atom:AtomicSpan)
WHERE any(p IN atom.forbidden_patterns
          WHERE any(ap IN atom.allowed_paths WHERE p CONTAINS ap))
RETURN 'V_SP_Boundary_SelfBlock' AS validation,
       atom.name, atom.allowed_paths, atom.forbidden_patterns
```

---

## anti-pattern

### E-SP-Boundary-1: boundary 누락
**Context:** AtomicSpan에 allowed_paths 안 채우고 SCW로 핸드오프.
**Lesson:** SCW에서 boundary 없으면 임의 파일 수정 가능 → 다른 모듈 침범 위험.
**Guard:** SP → ST 핸드오프 cypher에 allowed_paths IS NOT NULL 확인.

### E-SP-Boundary-2: forbidden_patterns 과도
**Context:** "import any" 같은 너무 광범위한 forbidden_pattern. 실제 필요한 standard library import도 차단.
**Lesson:** forbidden_patterns는 *특정 모듈 침범*만 막아야. import 자체 금지는 과도.
**Guard:** forbidden_patterns 생성 시 cypher 패턴 검증 — wildcard 또는 `any` 단어 단독 차단.

### E-SP-Boundary-3: cross-module 자동 인식 실패
**Context:** AtomicSpan A의 description이 "B 모듈 데이터를 받아서..." 인데 forbidden_patterns에 `from module_b` 없음.
**Lesson:** A는 B의 *출력*을 받는 자리 — B를 직접 import하면 안 됨 (Ports-and-Adapters 위반).
**Guard:** SP boundary 추론 cypher에 INFORMED_BY 노드 중 다른 모듈 발견 시 자동 forbidden_pattern 추가.

# KG: APT_SP_SpanBoundary_canonical
