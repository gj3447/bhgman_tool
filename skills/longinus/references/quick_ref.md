# longinus — Quick Ref

> Parent: [`../SKILL.md`](../SKILL.md).

## Decision Tree

```
"I need to..."
    |
    +-- "...bind Contract X to code" → /longinus forward <contract>
    +-- "...find KG-unmapped code symbols" → /longinus reverse <path>
    +-- "...detect drift now" → /longinus drift <target>
    +-- "...crate-level binding" → /longinus crate <Cargo.toml>
    +-- "...full audit" → /longinus audit <SemanticAnchor>
    +-- "...activate sha256 daemon" → launchctl bootstrap com.symposium.longinus-sha256-daemon
    +-- "...check drift trend" → KG: MATCH (dr:DriftReport) ...
```

## 7-Layer Cheat Sheet

| L | Field | Required when |
|---|-------|--------------|
| L1 | KG node identity | always |
| L2 | Contract | binding to Contract |
| L3 | code symbol | binding to fn/struct |
| L4 | file:line | always (mandatory) |
| L5 | line_range | multi-line region |
| L6 | sha256 | drift detection |
| L7 | crate/script | binary artifact |

## 5-Drift Kinds

| Kind | Symptom |
|------|---------|
| Missing | KG points to non-existent file/symbol |
| Orphan | code symbol unmapped in KG |
| SigMismatch | code sig ≠ contract.protocol |
| PatternDiv | pattern shifted (State → Strategy) |
| LabelRot | KG label drifted from canonical |

## BX Lens Laws

| Law | Means |
|-----|-------|
| GetPut | get(put(s,v)) = v |
| PutGet | put(s,get(s)) = s |
| PutPut | put(put(s,v1),v2) = put(s,v2) |

## Common BLOCK Causes

| Symptom | Cause | Fix |
|---------|-------|-----|
| ReferenceSite missing | LG_LongiusBindingMissing | TR12 enforce |
| sha256 stale > 7d | LG_SHA256Stale | daemon refresh |
| coverage < 0.8 | LG_DriftSilenced | SUSPENDED 처리 |
| L4 missing | LG_LayerInsufficient | file:line 강제 |

# KG: ATOM_Skill_longinus, fw-longinus-references-apt-parity-2026-05-06
