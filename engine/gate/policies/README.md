# OPA Rego Policy Skeleton — APT v27 FUTURE

> **RFC**: `rfc-apt-v27-A7-gate-hook-fail-closed-4-layer-2026-04-30` Phase 4 (FUTURE)
> **ActionPlan**: `ap-prom16apt-opa-rego-skeleton` (8-12주, FUTURE → ACTION 전환은 Sprint 3 완료 후)
> **External canonical**: OPA/Gatekeeper CNCF graduate, 268 enterprises (Netflix/Goldman/Google/T-Mobile)

---

## 도입 단계 (4 Phase)

| Phase | 내용 | 기간 |
|---|---|---|
| **Phase 1** | Harness 4축 (Inform/Constrain/Verify/Correct) Rego policy skeleton | 2주 |
| **Phase 2** | Taliban 검증 렌즈 (constitutional 9 / mathematical 113) → Rego constraint | 3주 |
| **Phase 3** | Conftest CI/CD 파이프라인 + GitHub Actions 통합 | 2주 |
| **Phase 4** | KG Cypher ↔ OPA decision log sync | 1-2주 |

---

## 파일 구조

```
opa_rego_skeleton/
├── README.md                           ← 본 파일
├── policies/
│   ├── harness/
│   │   ├── inform.rego                 ← 정보 제공 axis
│   │   ├── constrain.rego              ← 제약 axis (gate hook 본체)
│   │   ├── verify.rego                 ← 검증 axis (Taliban 호출 분기)
│   │   └── correct.rego                ← 수정 axis (오답노트 → lesson)
│   ├── taliban/
│   │   ├── constitutional_9.rego       ← 9 lens 적대 검증
│   │   └── mathematical_113.rego       ← FUTURE (Phase 2 후반)
│   └── apt_phase_gates/
│       ├── sa_to_sp.rego               ← Phase 1→2 gate
│       ├── sp_to_st.rego               ← Phase 2→3 gate (LensSet completeness)
│       ├── st_to_scw.rego              ← Phase 3→4 gate (8 decision area)
│       └── scw_to_meta.rego            ← Phase 4→5 gate (FulfillmentGate 7 checks)
├── tests/
│   ├── harness_test.rego
│   ├── taliban_test.rego
│   └── gate_test.rego
├── conftest.toml                       ← Conftest CI/CD 설정
├── github-actions-workflow.yml         ← CI/CD 통합 예시
└── kg_sync/
    └── cypher_to_rego_translator.py    ← Phase 4 KG ↔ Rego sync
```

---

## Phase 1 — Harness 4축 (skeleton)

### `policies/harness/constrain.rego` (gate hook 본체 예시)

```rego
package apt.harness.constrain

import future.keywords.if
import future.keywords.in

# Default deny (fail-closed) — RFC A7 핵심 원칙
default allow := false

# Composition Root: KG MethodologyConfig 5 core field 필수
required_fields := {
  "vibe_coding_sweet_min",
  "vibe_coding_sweet_max",
  "lens_count_constitutional",
  "contract_default_fields",
  "st_decision_areas",
}

# 5 core field 모두 채워졌는지 검증
methodology_config_complete if {
  every f in required_fields {
    input.kg.methodology_config[f] != null
  }
}

# Constrain axis 통과 조건
allow if {
  methodology_config_complete
  not violates_break_glass_allowlist
  input.gate_decision.audit_id != ""
}

# Break-glass allowlist 위반 검사
violates_break_glass_allowlist if {
  input.gate_name in {"essential-infra-pod-bypass", "cluster-autoscaler-bypass"}
  not input.gate_decision.break_glass_token_valid
}

# Drift 탐지 (constrain 축 메트릭)
drift_detected if {
  input.kg.skill_md_inline_numbers_count > 0
  input.kg.cfg_orphan_field_count > 0
}
```

### `policies/harness/inform.rego` (정보 제공 axis 예시)

```rego
package apt.harness.inform

# Inform axis = SKILL.md + Lesson context 제공 검증
# default allow는 inform 축이 informational이라 true (constrain이 fail-closed)
default allow := true

# 단, KG에서 관련 Lesson 조회 가능해야 함
require_lesson_context if {
  count(input.kg.related_lessons) >= 1
}

deny[msg] if {
  not require_lesson_context
  msg := "Inform 축: 관련 Lesson context 없음. SKILL.md 진행 전 KG Lesson seed 필수."
}
```

---

## Phase 2 — Taliban constitutional 9 lens

### `policies/taliban/constitutional_9.rego` (skeleton)

```rego
package apt.taliban.constitutional

import future.keywords.if
import future.keywords.in

# 9 lens 정의 (각 lens는 별도 rego file 또는 inline rule)
lenses := {
  "evidence-backed",
  "non-rubber-stamp",
  "executor-not-equal-critic",
  "lensset-completeness",
  "min-findings-per-lens",
  "ground-truth-anchored",
  "post-gate-reflection",
  "longinus-binding-checked",
  "feedback-loop-instance",
}

# 만장일치 PASS 조건
default approve := false

approve if {
  every lens in lenses {
    input.lens_results[lens] == "PASS"
  }
}

# Anti-rubber-stamp: 모든 PASS verdict는 evidence 인용 필수
deny[msg] if {
  some lens in lenses
  input.lens_results[lens] == "PASS"
  not input.lens_results[lens].evidence_cited
  msg := sprintf("HR11 위반: lens '%s' PASS without evidence citation (RUBBER_STAMP)", [lens])
}

# 3-lens shortcut 차단 (lesson-taliban-shortcut-antipattern-2026-04-21)
deny[msg] if {
  count(input.lens_results) < 9
  msg := sprintf("3-lens shortcut: only %d/9 lenses run. RFC A6.1 LensSet completeness violation.", [count(input.lens_results)])
}
```

---

## Phase 3 — Conftest CI/CD

### `conftest.toml`

```toml
[parser]
yaml = "yaml"
json = "json"

[testing]
namespaces = [
  "apt.harness.constrain",
  "apt.harness.verify",
  "apt.taliban.constitutional",
  "apt.phase_gates.sp_to_st",
  "apt.phase_gates.st_to_scw",
]
```

### `github-actions-workflow.yml`

```yaml
name: APT Gate Policy Check

on:
  pull_request:
    paths:
      - "SKILLS/apt*/SKILL.md"
      - "THEORY/APT/**"

jobs:
  rego-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install OPA + Conftest
        run: |
          curl -L https://github.com/open-policy-agent/conftest/releases/latest/download/conftest_linux_x86_64.tar.gz | tar -xz
          sudo mv conftest /usr/local/bin/
      - name: Build gate decision input from KG
        run: |
          python kg_sync/cypher_to_rego_translator.py \
            --gate G3.5 \
            --cycle ${{ github.run_id }} \
            --output /tmp/gate-input.json
      - name: Conftest verify (Harness 4-axis)
        run: |
          conftest verify --policy policies/harness/ /tmp/gate-input.json
      - name: Conftest verify (Taliban 9 lens)
        run: |
          conftest verify --policy policies/taliban/ /tmp/gate-input.json
      - name: Phase gate validation
        run: |
          conftest verify --policy policies/apt_phase_gates/ /tmp/gate-input.json
```

---

## Phase 4 — KG ↔ Rego sync

### `kg_sync/cypher_to_rego_translator.py` (skeleton)

```python
"""KG Cypher → Rego JSON input 변환.

Rego policy가 KG decision을 평가하려면 input.json 표준 형식 필요.
이 변환기가 다리 역할.
"""

import json
import sys
from neo4j import GraphDatabase


CYPHER_GATE_INPUT = """
MATCH (g:Gate {name: $gate_name})
OPTIONAL MATCH (g)-[:HAS_LENS_RESULT]->(lr:LensResult)
OPTIONAL MATCH (g)-[:DECIDED_BY]->(audit:GateAuditEntry)
OPTIONAL MATCH (cfg:MethodologyConfig {name: 'MethodologyConfig_default_v27'})
RETURN g {.*} AS gate,
       collect(lr {.*}) AS lens_results,
       audit {.*} AS audit,
       cfg {.*} AS methodology_config
"""


def fetch_gate_input(gate_name: str, cycle_id: str) -> dict:
    driver = GraphDatabase.driver(...)
    with driver.session() as s:
        r = s.run(CYPHER_GATE_INPUT, gate_name=gate_name).single()
    return {
        "gate_name": gate_name,
        "cycle_id": cycle_id,
        "kg": {
            "methodology_config": dict(r["methodology_config"]),
            "related_lessons": [],  # 추가 query
            "skill_md_inline_numbers_count": 0,  # validator 결과
            "cfg_orphan_field_count": 0,
        },
        "lens_results": {
            lr["lens_name"]: {
                "verdict": lr["verdict"],
                "evidence_cited": lr.get("evidence_cited", False),
            }
            for lr in r["lens_results"]
        },
        "gate_decision": {
            "audit_id": r["audit"]["audit_id"],
            "break_glass_token_valid": False,
        },
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--gate", required=True)
    p.add_argument("--cycle", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    out = fetch_gate_input(args.gate, args.cycle)
    with open(args.output, "w") as f:
        json.dump(out, f, indent=2)
```

---

## 결정 기준 (Phase 1 Harness 적용 후 평가)

OPA 도입 후 측정:
1. **Gate decision latency**: shell `apt-gate-check.sh` 대비 OPA `eval` (예상: 비슷)
2. **Policy 가독성**: shell + Cypher 대비 Rego (예상: 명확 우위 — declarative)
3. **CI/CD 통합**: GitHub Actions Conftest (shell보다 표준화)
4. **Cross-domain reuse**: K8s admission, Terraform plan validation, API gateway에 동일 policy 재사용 가능 (shell 불가)

→ Phase 1 결과 *Rego 가독성 + reuse 우위* 명확 시 Phase 2-4 가속.

---

## ResumptionHook 갱신

```cypher
MATCH (rh:ResumptionHook {name: 'hook-apt-opa-rego-first-policy'})
SET rh.skeleton_ready = true,
    rh.skeleton_path = '/Users/lagyeongjun/CD/SYMPOSIUM/THEORY/APT/opa_rego_skeleton/',
    rh.next_action_status = 'SPRINT_3_COMPLETION_PENDING'
```

Sprint 3 (gate fail-closed HTTP endpoint) 완료 후 자동 promote → ACTION.

---

## 한 줄 결론

**OPA Rego skeleton 4 phase로 8-12주. Phase 1(Harness 4축) 우선 + Phase 2(Taliban 9 lens) 후 Conftest CI/CD + KG sync. CNCF 표준 + 268 enterprises 채택 + Cross-domain reuse 우위 → Sprint 3 완료 후 가속.**
