---
name: apt-autoflow-guard
kg_ref: ATOM_Skill_apt_autoflow_guard
version: "0.1.0-scaffold"
channel: experimental
canonical_name: apt-autoflow-guard
description: >
  APT autoflow guarantee 책무 — KG-first check + AskUserQuestion 차단 + Span-MERGE-KG-paste guard.
  APT 는 monolithic auto-flow. 중간 결정 (gate dispatch, seed 우선순위, fix 방식) 은 시스템
  자율 처리, 사용자는 초기 input + 최종 산출물 + 비가역 리스크 검토만.
  lesson-apt-monolithic-autoflow-no-mid-questions-2026-04-17 enforce 본체.
  Scaffold 2026-05-22: 실행 layer = 3개 hook 묶음.
  Invoke when: APT 사이클 시작 시 marker touch, autoflow violation 진단.
  # KG: ATOM_Skill_apt_autoflow_guard, lesson-apt-monolithic-autoflow-no-mid-questions-2026-04-17, vr-apt-autonomy-drift-3-symptom-cluster-naesengmoon-3lens-2026-05-22
---

## 🚧 Scaffold Status (2026-05-22)

SRP 4-책무 분해 중 4번째. 본 책무 측 실행 layer 는 *이미 박혀 있음* — 3개 hook + apt-progress.md template.

## 실행 layer (이미 install)

| Hook | matcher | mode | symptom 직격 |
|------|---------|------|--------------|
| `~/.claude/hooks/pre_tool_apt_autoflow_guard.py` | `AskUserQuestion` | BLOCK_WHEN_CYCLE_ACTIVE | 자동 사이클 도중 질문 차단 |
| `~/.claude/hooks/pre_tool_apt_phase_gate_check.py` | `mcp__neo4j__write_neo4j_cypher` | BLOCK_NEW (legacy bypass `UNKNOWN_LEGACY`) | AptDecisionLog 측 lens/verdict/gate 누락 차단 |
| `~/.claude/hooks/pre_tool_apt_sa_kg_paste_check.py` | `mcp__neo4j__write_neo4j_cypher` | BLOCK on Span MERGE without apt-progress.md ## KG Snapshot ≥5 lines | KG-skip 창작 차단 |

## 사용법

APT 사이클 시작 시:
```bash
touch ~/.claude/hooks/state/apt_cycle_active.marker
# 또는 export APT_CYCLE_ACTIVE=1
```

종료 시:
```bash
rm ~/.claude/hooks/state/apt_cycle_active.marker
# 또는 unset APT_CYCLE_ACTIVE
```

Override (debug only):
- `APT_AUTOFLOW_GUARD=off` — autoflow guard 비활성
- `APT_SA_KG_PASTE=off` — KG paste check 비활성
- `APT_SA_KG_PASTE_BYPASS=1` — single bypass (seed Span)

## SKILL.md body migration status

apt/SKILL.md 본문 측 description L20 ("auto mode") + invoke condition 측 본 책무 측 *의도 선언*. enforcement 측 위 3 hook 측 실행.

**Migration deferred to**: APT meta-review cycle (next session). 본 scaffold 측 hook docs 측 *consolidate* 측 SKILL.md 측 분리.

# KG: scaffold-apt-skill-decomposition-2026-05-22, pre_tool_apt_autoflow_guard, pre_tool_apt_phase_gate_check, pre_tool_apt_sa_kg_paste_check
