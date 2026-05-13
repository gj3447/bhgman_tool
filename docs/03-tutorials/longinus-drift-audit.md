# Tutorial — Longinus Drift Audit (실 코드 walkthrough)

> KG (knowledge graph) 와 source code 간 *참조 drift* 를 검출하는 실 도구. Pydantic v2 + 77 pytest PASS. 사용자가 실제로 돌릴 수 있는 시나리오.

---

## 0. 사전 준비

```bash
git clone https://github.com/gj3447/bhgman_tool.git
cd bhgman_tool/engine/longinus_drift_audit

# uv (권장) 또는 pip
uv run --with pytest pytest tests/ -q
# 기대: 77 passed in 0.41s
```

---

## 1. 핵심 객체 — ReferenceSite

ReferenceSite = "코드 어딘가에 박힌 KG 참조 한 점".

```python
from longinus_drift_audit import ReferenceSite, Confidence

# 기본 사용 — confidence default = EXTRACTED
rs = ReferenceSite(
    sourceId="lesson-foo-2026-05-13",       # Frege Sinn (의미 id)
    sourcePath="engine/longinus.py:42",      # Frege Bedeutung (위치)
)

print(rs.file)        # "engine/longinus.py"
print(rs.line_start)  # 42
print(rs.confidence)  # <Confidence.EXTRACTED: 'EXTRACTED'>
```

### 3-tier confidence (graphify 흡수)

```python
# EXTRACTED — 명시적 출처 (import / direct call / type)
rs_ex = ReferenceSite(
    sourceId="lesson-explicit",
    sourcePath="src/explicit.py:10",
    confidence=Confidence.EXTRACTED,
)

# INFERRED — 추론 (call-graph 2-pass / 공기)
rs_in = ReferenceSite(
    sourceId="lesson-inferred",
    sourcePath="src/inferred.py:20",
    confidence=Confidence.INFERRED,
)

# AMBIGUOUS — 불확실, human review 강제
rs_amb = ReferenceSite(
    sourceId="lesson-ambiguous",
    sourcePath="src/ambiguous.py:30",
    confidence=Confidence.AMBIGUOUS,
)

from longinus_drift_audit import requires_human_verdict, trust_level

# T1 Lean theorem: AMBIGUOUS = unique human-verdict gate
assert requires_human_verdict(rs_amb.confidence) is True
assert requires_human_verdict(rs_ex.confidence) is False
assert requires_human_verdict(rs_in.confidence) is False

# T3 Lean theorem: trust 순서
assert trust_level(Confidence.EXTRACTED) == 2
assert trust_level(Confidence.INFERRED) == 1
assert trust_level(Confidence.AMBIGUOUS) == 0
```

---

## 2. BX Lens 측 3 laws 검증 (Foster-Pierce-Walker 2007)

```python
from longinus_drift_audit import make_dict_lens

# dict 상태 ↔ key 값 변환의 lens
lens = make_dict_lens(key="lesson-foo")

# 3 laws 일괄 검증
result = lens.verify_all(s={"lesson-foo": "v0"}, v1="code-edit-A", v2="code-edit-B")

print(result.get_put)    # True  — put(s, get(s)) = s
print(result.put_get)    # True  — get(put(s, v1)) = v1
print(result.put_put)    # True  — put(put(s, v1), v2) = put(s, v2)
print(result.violations) # [] (모두 만족)
```

위반 시 :
```python
# 사용자 정의 잘못된 lens
from longinus_drift_audit import Lens

bad_lens = Lens(
    get=lambda s: s.get("x", ""),
    put=lambda s, v: {**s, "x": v + "_corrupted"},  # PutGet 위반
)

result = bad_lens.verify_all(s={}, v1="hello", v2="world")
print(result.put_get)    # False
print(result.violations) # ["PutGet: get(put(s, v1)) != v1 — Missing/SigMismatch-class drift"]
```

---

## 3. 5 Drift type 검출

5 drift 가 BX Lens 3 laws 위반에 **surjective** 매핑 (Longinus T3):

| Drift | 의미 | Lens 위반 |
|---|---|---|
| `MISSING` | 코드 존재 ∧ KG ref 부재 | PutGet |
| `ORPHAN` | KG ref 존재 ∧ 코드 부재 | GetPut |
| `SIG_MISMATCH` | ref ↔ signature 불일치 | PutGet |
| `PATTERN_DIV` | 동일 대상 ↔ 상충 refs | PutPut |
| `LABEL_ROT` | label/이름 변경 미반영 | PutPut |

```python
from longinus_drift_audit import DriftRecord, DriftType, ReferenceLayer

drift = DriftRecord(
    drift_type=DriftType.MISSING,
    sourceId="lesson-missing-ref",
    sourcePath="engine/foo.py:100",
    expected="lesson-missing-ref present in KG",
    actual="not found",
    layer_violated=ReferenceLayer.L4_SEMIOTIC,
    lens_law_violated="PutGet",
)

print(drift.drift_type)  # <DriftType.MISSING: 'Missing'>
```

---

## 4. AMBIGUOUS contagion (Lean T6)

여러 ReferenceSite 측 1개라도 AMBIGUOUS 이면 aggregate 가 PRELIMINARY 표기 강제:

```python
from longinus_drift_audit import any_ambiguous

sites = [
    ReferenceSite(sourceId="a", sourcePath="x.py:1", confidence=Confidence.EXTRACTED),
    ReferenceSite(sourceId="b", sourcePath="x.py:2", confidence=Confidence.AMBIGUOUS),
    ReferenceSite(sourceId="c", sourcePath="x.py:3", confidence=Confidence.INFERRED),
]

assert any_ambiguous(sites) is True
# → 이 aggregate 결과는 PRELIMINARY 라벨 + user_verdict_trigger_required=true
```

---

## 5. AuditReport 측 전체 결과

```python
from longinus_drift_audit import AuditReport, LayerCoverage, LensVerification, GedReport

report = AuditReport(
    audit_id="audit-2026-05-13-001",
    drifts_by_type={"Missing": 2, "Orphan": 1},
    drift_records=[],  # 위 DriftRecord list
    reverse_orphans=["AbandonedSymbol"],  # 코드에 없으나 KG에 ref
    layer_coverage=LayerCoverage(
        L1_address=1.0, L2_lifetime=0.9, L3_type=1.0, L4_semiotic=0.85,
        L5_distributed=1.0, L6_compression=1.0, L7_aesthetic_pierce_rate=0.7,
    ),
    lens_verification=LensVerification(get_put=True, put_get=False, violations=["..."]),
    ged_report=GedReport(
        kg_node_count=100, code_node_count=98,
        insertions=2, deletions=0, relabels=1,
        ged_total=3, normalized_score=0.97,
    ),
)

print(report.total_drifts)  # 3
print(report.is_clean)      # False (drifts > 0 or reverse_orphans > 0)
```

---

## 6. Pydantic v2 측 round-trip (KG Cypher write 호환)

```python
# 직렬화 (KG 측 property write 가능)
data = rs.model_dump()
# {'sourceId': 'lesson-foo-2026-05-13', 'sourcePath': 'engine/longinus.py:42',
#  'pierced_at': '2026-05-13T...', 'drift_detected_at': None, 'drift_score': 0.0,
#  'confidence': 'EXTRACTED'}

# 역직렬화
rs2 = ReferenceSite.model_validate(data)
assert rs.confidence == rs2.confidence
```

---

## 7. 실 사용 시나리오 — 자기 repo 측 drift audit

```python
# pseudocode (full implementation: audit_runner.py)
from longinus_drift_audit import LonginusAudit

audit = LonginusAudit(
    code_root="src/",
    kg_endpoint="bolt://localhost:7687",  # Neo4j
    confidence_threshold=Confidence.INFERRED,  # AMBIGUOUS 만 human review
)

report = audit.run()

if report.is_clean:
    print("✓ All references aligned. No drift.")
else:
    print(f"⚠ {report.total_drifts} drift(s) detected.")
    for d in report.drift_records:
        print(f"  - {d.drift_type.value} @ {d.sourcePath}: {d.expected} != {d.actual}")
```

---

## 8. Lean 4 형식 검증 재현

각 Python 측 행동은 Lean theorem 으로 형식 검증됨:

```bash
cd bhgman_tool/lean
lean Longinus_ConfidenceSchema_GraphifyAbsorbed.lean
# exit 0, 0 sorry
# 7 theorem PASS:
#   T1 ambiguous_unique_human_gate    ← requires_human_verdict() 의 형식 보장
#   T2 sinn_bedeutung_non_collapse    ← sourceId ↔ sourcePath 비-collapse
#   T3 trust_strict_order             ← trust_level() 순서 보장
#   T4 bx_getput                      ← Foster-Pierce-Walker GetPut
#   T5 bx_putget                      ← Foster-Pierce-Walker PutGet
#   T6 ambiguous_in_list_forces_preliminary  ← any_ambiguous() contagion
#   T7 goodhart_safeguard_confidence_not_scalar  ← scalar collapse 거부
```

---

## 9. Skill 측 호출 (Claude Code)

```bash
cp -R bhgman_tool/skills/longinus ~/.claude/skills/
# Claude Code 재시작
```

chat 에서:
```
/longinus   — KG ↔ code 참조 바인딩 audit
```

→ AI 가 *자동으로* repo 측 drift audit 실행 + 결과 보고.

---

## 자세히는

- [../02-concepts/harness.md](../02-concepts/harness.md) §Longinus reference layer
- [../05-papers/foster-pierce-walker-2007-bx-lens.md](../05-papers/foster-pierce-walker-2007-bx-lens.md) — BX Lens 정전
- [../05-papers/frege-1892-sense-reference.md](../05-papers/frege-1892-sense-reference.md) — Sinn ↔ Bedeutung 형이상학
- [../04-references/lean-theorems.md](../04-references/lean-theorems.md) — 50 theorem list
- `engine/longinus_drift_audit/README.md` — 측 자체 docs (예정)
