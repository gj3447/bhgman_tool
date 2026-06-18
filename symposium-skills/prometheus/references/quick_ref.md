# prometheus — Quick Ref

> Parent: [`../SKILL.md`](../SKILL.md). Sibling: [`./theory.md`](./theory.md), [`./gates.md`](./gates.md).

## Decision Tree

```
"I need to..."
    |
    +-- "...research a topic" → /prom <N> <topic>
    +-- "...research a TOE-class problem" → /prom 64 <topic>
    +-- "...quick fact check" → /prom 4 <topic>
    +-- "...hot-fix urgently" → /prom <N> <topic> --hot-fix-mode
    +-- "...check past PROM cycles" → KG: MATCH (c:PrometheusCycle) ORDER BY c.started_at DESC
    +-- "...understand 9-step protocol" → references/theory.md §3
    +-- "...troubleshoot dispatch" → references/error_handling.md §3
```

## N Selection Cheat Sheet

| Topic Size | N Default | Examples |
|------------|-----------|----------|
| small | 4 | 단일 라이브러리 사용법 |
| medium | 8 | 기존 도메인 axis × sub_axis |
| large | 16 | 복합 도메인 (여러 axis) |
| TOE | 64-100 | Theory-of-Everything 급 |

`MethodologyConfig.prometheus_N_default_*` slot resolve.

## Hard Rules Index

| Rule | Mnemonic |
|------|----------|
| KG-first | thesis 먼저 (Hegel) |
| Hot-fix exception | latency-critical 만 KG-skip 허용 |
| Single-message multi-call | parallel dispatch 강제 |
| GH#29181 self-check | intent_N == actual_N |
| W3C PROV provenance | every finding traceable |
| FullFindingRecord schema | dedup_hash mandatory |
| G6.5 dispersion gate | KG↔fs drift 차단 |

## Common BLOCK Causes

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| KG unreachable | Neo4j down | server-status |
| dispatch 누락 | self-check skip | GH#29181 enforce |
| dedup all null | Step 3.3 skip | hash 강제 |
| Lakatos DEGENERATING | rescue 가설 | refactor topic |

# KG: ATOM_Skill_prometheus, fw-prometheus-references-apt-parity-2026-05-06
