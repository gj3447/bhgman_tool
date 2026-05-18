# Longinus Drift Audit Prototype

> **Skill**: `longinus v3.2` (`sv-longinus-v3.2.0`)
> **Pair**: APT `gate_endpoint_prototype/` + Prometheus `prom_cycle_runtime_prototype/` + 재배맨 `jaebaeman_sop_runtime_prototype/`.
> **Stack**: Python 3.11+ / Pydantic v2 / `neo4j` driver (optional) / `tenacity`.

---

## 무엇인가

롱기누스 v3.2 SKILL.md 의 **7-Layer Reference Model + BX Lens Laws (GetPut/PutGet/PutPut) + 5 drift types + GED quantification + Reverse Orphan Scan** 을 Python module 로 결정화.

목적: KG 의미 계층 ↔ source code 의 *양방향 추적* 자동화. drift 발생 시 5 유형 (Missing/Orphan/SigMismatch/PatternDiv/LabelRot) 으로 분류 + GED 정량 + reverse blind-spot 탐지.

본 prototype 은 SKILL.md 의 *기계 측 동등성* — KG node ↔ code symbol pair 위에서 동일 lens-law 의미를 보존한다.

---

## 7-Layer Reference Model → module map

| Layer | 책무 | module | 의미 |
|---|---|---|---|
| L1 Address Indirection | source path (file:line) | `code_scanner.py` | grep/LSP-equivalent 심볼 위치 |
| L2 Lifetime/Scope | 참조 유효 범위 | `reference_layers.py` | `pierced_at`/`drift_detected_at` |
| L3 Type Permission | Refinement type (ValidSourceRef) | `models.py` | branded type + Pydantic validator |
| L4 Semiotic Binding | Frege Sinn↔Bedeutung | `models.py::ReferenceSite` | sourceId=Sinn, sourcePath=Bedeutung |
| L5 Distributed Identity | KG MERGE consensus | `kg_client.py` | name PK idempotent |
| L6 Information Compression | `# KG: xxx` 1 line bundles 7 layers | `reference_layers.py::compress` | Kolmogorov 압축 |
| L7 Aesthetic/Intentional | 최소 침습으로 최대 추적 | `audit_runner.py` | pierce_rate metric |

---

## BX Lens Laws + 5 Drift Types

| Lens Law | 정의 | 위반 = drift 유형 |
|---|---|---|
| GetPut | `put(s, get(s)) = s` | **Orphan** — KG 에 ref 있으나 코드에 대응 없음 |
| PutGet | `get(put(s, v)) = v` | **Missing** — 코드 존재하나 KG 에 ref 없음 / **SigMismatch** — ref 있으나 시그니처 불일치 |
| PutPut | `put(put(s,v1),v2) = put(s,v2)` | **PatternDiv** — 동일 대상 상충 ref / **LabelRot** — 라벨/이름 변경 미반영 |

→ *Drift = Lens Law Violation*. 5 유형을 모두 lens 위반 사례로 재정의.

---

## API

```python
from audit_runner import LonginusAudit
from kg_client import MockKgClient

audit = LonginusAudit(
    kg=MockKgClient(),
    code_root="/path/to/src",
)

# 1. 양방향 scan
report = audit.run_full()

# report.drifts: {Missing: 3, Orphan: 1, SigMismatch: 0, PatternDiv: 0, LabelRot: 0}
# report.ged_drift_score: 0.04  (4% of nodes have drift)
# report.reverse_orphans: ["function_in_code_no_kg_ref_1.py:42", ...]
# report.layer_coverage: {L1: 100%, L2: 95%, L3: 98%, L4: 100%, L5: 100%, L6: 87%, L7: pierce_rate=0.93}
```

---

## 파일

```
longinus_drift_audit_prototype/
├── README.md
├── pyproject.toml
├── models.py               ← Pydantic v2 (ReferenceSite, DriftRecord, AuditReport)
├── kg_client.py            ← KgClient ABC + Mock + Neo4j (DIP)
├── code_scanner.py         ← grep-based code symbol/ref scanner (LSP fallback)
├── reference_layers.py     ← 7-Layer 의미 추출
├── bx_lens.py              ← GetPut/PutGet/PutPut law verifier
├── drift_detector.py       ← 5 drift type classifier
├── ged_metric.py           ← Graph Edit Distance (Sanfeliu-Fu 1983) + normalized score
├── reverse_orphan_scan.py  ← Code→KG blind-spot 탐지 (v3.1)
├── audit_runner.py         ← LonginusAudit orchestrator + CLI
└── tests/
    ├── test_models.py
    ├── test_code_scanner.py
    ├── test_reference_layers.py
    ├── test_bx_lens.py
    ├── test_drift_detector.py
    ├── test_ged_metric.py
    ├── test_reverse_orphan_scan.py
    └── test_e2e_audit.py
```

# KG: longinus-drift-audit-prototype-2026-05-12

---

## Parallelism (L1 + L2, 2026-05-18)

L1 = `code_scanner.scan_root` 파일 fan-out via `ProcessPoolExecutor`.
L2 = `LonginusAudit.run_full` post-barrier 5-phase fan-out via `ThreadPoolExecutor` (drift / reverse_orphan / forward_orphan / sha256_verify / GED).

### API

```python
# L1: scan only
syms, refs = code_scanner.scan_root(root, parallel=True, threshold=5000)

# L2: full audit
audit = LonginusAudit(kg=kg, code_root=root, parallel=True)
report = audit.run_full()
```

`threshold` (env `LONGINUS_PARALLEL_FILE_THRESHOLD`, default 5000) gates L1 — below it, sequential codepath runs.

### Empirical bench (`bench/bench_parallel.py`, M-series macOS, 2026-05-18)

| file_count | sequential | full_parallel | speedup |
|---|---|---|---|
| 100 | 12 ms | 35 ms | **0.34× (slower)** |
| 2000 | 464 ms | 421 ms | 1.10× |
| 5000 | 1404 ms | 1282 ms | 1.10× |
| 10000 | 5129 ms | 2588 ms | **1.98×** |
| real (bhgman_tool, 78 files) | 62 ms | 75 ms | 0.83× |

**Honest verdict**: at the current regex-only scanner, per-file work (~50μs) is so cheap that ProcessPool spawn + IPC pickle dominates until ~5000 files. Default `parallel=False` on `LonginusAudit` matches this — flip it on for repos ≥10000 files or after swapping the scanner for AST/tree-sitter (per-file CPU 100×, then parallel dominates by `ncpus`).

L2 ThreadPool fan-out also adds 10-30% overhead with Mock KG (in-memory). Real Neo4j (network-IO bound) should benefit — not yet measured.

Tests `test_parallel_invariant.py` enforce parallel-mode AuditReport ≡ sequential output (7 invariant tests + 120 baseline = 127 total).

# KG: longinus-parallel-scan-2026-05-18 (L1 PRELIMINARY)
# KG: longinus-parallel-fanout-2026-05-18 (L2 PRELIMINARY)
# KG: lesson-longinus-parallel-breakeven-2026-05-18
