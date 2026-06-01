# Quickstart

## 0. 요구 사항

- **Python 3.11+** (engine/ runtime)
- **uv** (권장) 또는 pip
- **Claude Code** ≥2.0 (skill/plugin 사용 시)
- **Lean 4** (≥4.29, 선택, formal verification 재현 시)

```bash
# uv 설치 (한 번)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 1. Clone + engine 실행 (3분)

```bash
git clone https://github.com/gj3447/bhgman_tool.git
cd bhgman_tool/engine/longinus_drift_audit

# 319 pytest PASS 검증 (longinus_drift_audit engine subset)
uv run --with pytest pytest tests/ -q
# 기대 출력: 77 passed in 0.41s
```

이걸로 Longinus drift audit (참조 바인딩 검증 도구) 가 작동한다. 5무기 중 한 instance 의 실 코드.

---

## 2. Claude Code 측 skill 사용 (5분)

```bash
# 1) Claude Code 설치 후
# 2) skill 디렉토리에 bhgman_tool/skills 의 21 SKILL.md 복사
cp -R bhgman_tool/skills/* ~/.claude/skills/

# 3) Claude Code 재시작 후 사용
```

이제 chat 에서:
```
/apt        — APT cycle 시작 (forward methodology: SA→SP→ST→SCW)
/prom 16    — Prometheus cycle (지식-행동 spiral, axis 16개 parallel)
/tpa <path> — TPA cycle (reverse engineering: TCW→ST→SP→TA)
/tlb <target> — Naesengmoon adversarial validation
/longinus   — Longinus 참조 바인딩 (KG↔code drift audit)
/jaebaeman  — 재배맨 SOP (subagent orchestration)
/harness    — Harness 4축 agent scaffolding 진단
```

각 skill 의 정전 + 절차는 [02-concepts/harness.md](02-concepts/harness.md) (Harness 본문) 참고. 다른 무기 (Longinus / Prometheus / Naesengmoon / 재배맨) 본문은 SYMPOSIUM 측 정전.

---

## 3. APT cycle 첫 사용 (10분)

가장 흔한 진입점은 새 프로젝트/feature 결정화. Claude Code 에 무엇을 만들지 발화 후:

```
/apt
```

→ AI 가 SA (Semantic Anchor) phase 진입:
1. **SA**: project identity + objective + 5 core field 설정
2. **SP**: recursive Span decomposition (DAG 노드)
3. **ST**: Crystallization Frontier — Contract + Task + 8 decision area
4. **SCW**: TDD implementation (Contract → RED test → GREEN code → REFACTOR)
5. **meta-review**: lesson + skill 패치 (피드백 루프)

각 phase 사이에 Gate Check Hook 가 Cypher 로 강제: LensSet 완전성 + Naesengmoon adversarial validation + Lean 형식화 (해당시).

상세는 [03-tutorials/apt-cycle.md](03-tutorials/apt-cycle.md).

---

## 4. Lean 형식 검증 재현 (선택, 5분)

```bash
cd bhgman_tool/lean
lean Longinus_ConfidenceSchema_GraphifyAbsorbed.lean
# exit 0 = 7 theorem PASS, 0 sorry
```

14 standalone Lean 4 파일, 총 89 theorem (Harness 24 + Longinus 21 + Measurement 26 + Occam 10 + Seed 8, Mathlib-free, Lean 4.29+ 검증; +16 Mathlib-sister → 트리 105).

---

## 5. Plugin 형태 install (alpha, planned)

```bash
# 1) Claude Code plugin marketplace 측 (예정)
/plugin marketplace add gj3447/bhgman_tool
/plugin install bhgman-harness@bhgman_tool
```

→ skill + engine + MCP server 한 번에. `bhgman_tool/plugins/.claude-plugin/plugin.json` 설정 참고.

---

## 다음 단계

- **비행기맨 본질**: [02-concepts/airplane-man.md](02-concepts/airplane-man.md) — #4 사도 정의
- **Harness 도구**: [02-concepts/harness.md](02-concepts/harness.md) — 본 repo 중심
- **실 코드 tutorial**: 03-tutorials/ (다음 sprint 작성 예정)
- **인용**: [04-references/citations.md](04-references/citations.md) — 17 axes external grounding
- **ruflo / LangGraph 와 차이**: [04-references/related-work.md](04-references/related-work.md)
- **철학적 함의**: [06-philosophy/](06-philosophy/) — *왜* 도구 사용자가 알면 좋은가
- **본질 / 메타휴모토닉 hint**: [07-metahumotonic-trace.md](07-metahumotonic-trace.md)
