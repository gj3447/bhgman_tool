# apt-cleanup — 4-Tool Ratchet 사용법

> **Lazy-load reference** — read when 도구 호출 시.
> Parent: [`../SKILL.md`](../SKILL.md).

---

## Tool 매핑

| Tool | 측정 | install | 정책 |
|---|---|---|---|
| **tach** | folder import cycle (ADP) | `pip install tach` | 0 cycles HARD |
| **complexipy** | function cyclomatic complexity | `pip install complexipy` | `--ratchet` mode |
| **lizard** | function LOC + CCN + parameters | `pip install lizard` | LOC ≤ 50, CCN ≤ 10 |
| **vulture** | unused code (dead) | `pip install vulture` | new dead = BLOCK |
| **deptry** | unused/missing/transitive deps | `pip install deptry` | 0 issues HARD |

---

## tach — Folder Cycle (ADP enforcement)

### 1. tach.toml 정의 (folder boundary)

```toml
[[modules]]
path = "user"
depends_on = ["shared"]

[[modules]]
path = "order"
depends_on = ["user", "shared"]

[[modules]]
path = "shared"
depends_on = []
```

→ `order` → `user` → `shared` (DAG). `shared` → `user` 추가하면 *cycle 검출 + 에러*.

### 2. CI / Phase 6 호출

```bash
tach check
# Exit 0 = no cycles. Non-zero = ADP violation.
```

### 3. Cypher 결과 기록

```cypher
MERGE (cr:CleanupRun {name: 'cleanup-' + $cycle})
SET cr.tach_cycles = $cycle_count, cr.tach_violations = $violations
```

---

## complexipy --ratchet — Cyclomatic Complexity

### 사용법

```bash
# baseline 저장 (첫 cycle)
complexipy . --ratchet --baseline=.cleanup/complexipy.json

# 다음 cycle 비교
complexipy . --ratchet --check
# 함수당 complexity > baseline → 에러 (ratchet down only)
```

### 정책

- 새 함수 max complexity ≤ 이전 max complexity (ratchet down)
- 사이클별 max 감소 또는 동일 → PASS
- 증가 → BLOCK + refactor 권고

---

## lizard — Function LOC + CCN

### 사용법

```bash
lizard --CCN 10 --length 50 --warnings_only .
# CCN > 10 또는 LOC > 50 함수 출력
```

### 통합 (lizard + jq)

```bash
lizard . -X | jq '.[] | select(.cyclomatic_complexity > 10 or .nloc > 50) | {name, file, nloc, ccn: .cyclomatic_complexity}'
```

### Phase 6 metric 추출

```python
import subprocess, json
result = subprocess.run(['lizard', '.', '-X'], capture_output=True, text=True)
data = json.loads(result.stdout)
fat_funcs = [f for f in data if f['nloc'] > 50 or f['cyclomatic_complexity'] > 10]
metric = {
    'lizard_loc_max': max(f['nloc'] for f in data),
    'lizard_ccn_max': max(f['cyclomatic_complexity'] for f in data),
    'fat_func_count': len(fat_funcs),
}
```

---

## vulture — Dead Code

### 사용법

```bash
vulture . --min-confidence 80 --exclude tests/
# 80% 이상 confident 한 unused 코드만 출력
```

### 정책

- 신규 dead code (delta) > 0 → BLOCK
- 기존 dead code 유지 OK (점진 정리)

### 통합

```bash
vulture . --min-confidence 80 | wc -l > .cleanup/vulture.count
diff_count=$(($(cat .cleanup/vulture.count) - $(cat .cleanup/vulture.count.prev)))
[ "$diff_count" -gt 0 ] && echo "BLOCK: new dead code $diff_count" && exit 1
```

---

## deptry — Dependency Hygiene

### 사용법

```bash
deptry .
# 4종 issue 검출:
#   DEP001: missing (import 했으나 dependency 부재)
#   DEP002: unused (선언했으나 import 안 함)
#   DEP003: transitive (간접 의존, 직접 declare 안 함)
#   DEP004: misplaced (dev-deps 인데 prod 사용)
```

### 정책

- 0 issues HARD (any 발견 시 BLOCK)

---

## CleanupRun KG 기록 (통합)

```cypher
MERGE (cr:AbstractNode:CleanupRun {name: 'cleanup-' + $cycle_id})
SET cr.cycle_id = $cycle_id,
    cr.tach_cycles = $tach_cycles,
    cr.complexipy_max = $complexipy_max,
    cr.complexipy_ratchet_passed = $complexipy_ratchet,
    cr.lizard_loc_max = $lizard_loc_max,
    cr.lizard_ccn_max = $lizard_ccn_max,
    cr.fat_func_count = $fat_func_count,
    cr.vulture_dead_count = $vulture_count,
    cr.vulture_delta = $vulture_delta,
    cr.deptry_issues = $deptry_count,
    cr.gate_passed = $all_pass,
    cr.completed_at = datetime()
```

---

## 자동화 script (`bin/apt-cleanup-run.sh` 후보)

```bash
#!/bin/bash
# apt-cleanup Phase 6 Gate runner
# Usage: apt-cleanup-run.sh <cycle_id>
set -e
CYCLE_ID=$1

# 1. tach
tach check > .cleanup/tach.log 2>&1
TACH_CYCLES=$(grep -c "cycle" .cleanup/tach.log || echo 0)

# 2. complexipy
complexipy . --ratchet --check > .cleanup/complexipy.log 2>&1
COMPLEXIPY_MAX=$(grep -oE 'max=[0-9]+' .cleanup/complexipy.log | grep -oE '[0-9]+' | sort -n | tail -1)

# 3. lizard
lizard . -X > .cleanup/lizard.json
LIZARD_LOC=$(jq '[.[] | .nloc] | max' .cleanup/lizard.json)
LIZARD_CCN=$(jq '[.[] | .cyclomatic_complexity] | max' .cleanup/lizard.json)
FAT_FUNC=$(jq '[.[] | select(.nloc > 50 or .cyclomatic_complexity > 10)] | length' .cleanup/lizard.json)

# 4. vulture
VULTURE=$(vulture . --min-confidence 80 | wc -l)

# 5. deptry
DEPTRY=$(deptry . | wc -l)

# 6. KG write (Cypher via mcp/cypher-shell)
cat <<CYPHER | cypher-shell
MERGE (cr:CleanupRun {name: 'cleanup-$CYCLE_ID'})
SET cr.tach_cycles = $TACH_CYCLES,
    cr.lizard_loc_max = $LIZARD_LOC, cr.lizard_ccn_max = $LIZARD_CCN,
    cr.fat_func_count = $FAT_FUNC, cr.vulture_dead_count = $VULTURE,
    cr.deptry_issues = $DEPTRY, cr.completed_at = datetime()
CYPHER

# Gate decision
[ "$TACH_CYCLES" -eq 0 ] && [ "$DEPTRY" -eq 0 ] && exit 0 || exit 1
```

---

# KG: lesson-apt-phase6-cleanup-missing-2026-04-28
