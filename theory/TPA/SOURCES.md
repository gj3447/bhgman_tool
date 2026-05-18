# TPA (Target Protocol Analysis) — 자료집

> **한 줄 정의:** 코드→설계 복원 방법론 v1.0. APT의 *역분석 거울*. TCW→TT→TP→TA 역순 사이클. 5대 본질 MIC 참조. 외부/레거시 코드를 KG로 끌어올리는 리버스 엔지니어링 프로토콜.

---

## 핵심 주장 (논문 골격용)

1. **APT의 거울**: APT가 SA→SP→ST→SCW로 **창조**한다면, TPA는 그 역순으로 **복원**한다.
   - TCW (TargetCodeWorld) ← SCW
   - TT (TargetTwin) ← ST
   - TP (TargetPyramid) ← SP
   - TA (TargetAnchor) ← SA
2. **5대 본질 공유 (MIC)**: APT와 TPA 모두 같은 MIC slots를 USES — Prometheus(unknown 리서치), Naesengmoon(phase gate), 88-Naesengmoon(메타검증), Longinus(코드↔KG 양방향), 재배맨(병렬 subagent), Harness(4축 제약).
3. **Pattern Library 매칭** (TP): 51 DesignPattern 노드 중 confidence ≥0.7 → INSTANCE_OF, <0.7 → RESEMBLES.
4. **카테고리별 검증 전략**: Distributed→MetaVerifier(수학 lens), Structural→AST, Behavioral→call graph, Creational→grep, PL→ResearchProvider.
5. **5종 Drift 측정** (TA): Missing / Orphan / SigMismatch / PatternDiv / LabelRot. coverage_ratio < 0.8 → status='SUSPENDED' 강제.
6. **AptContract vs ConventionalContract** (TT): 명시(interface/trait) vs 암묵(시그니처) 분리 라벨. LOC>100 giant method는 TP로 위임.
7. **오답노트 피드백 루프 내장.** Gate Check Hook 강제 — TCW Gate 미통과 시 TT 진입 불가.

---

## 1차 소스 (Orchestrator + Phases)

| 경로 | 내용 |
|---|---|
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/tpa/SKILL.md` | **정본 v1.0 orchestrator.** 역순 사이클, MIC 참조, 오답노트 피드백 |
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/tpa-tcw/SKILL.md` | TCW (Phase 1/4) — pub 심볼 추출, AST |
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/tpa-tt/SKILL.md` | TT (Phase 2/4) — Contract 추출, Apt vs Conventional |
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/tpa-tp/SKILL.md` | TP (Phase 3/4) — Pattern Library 매칭 |
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/tpa-ta/SKILL.md` | TA (Phase 4/4) — SemanticAnchor 라우팅, drift, 최종 Naesengmoon gate |

## 1차 소스 (신화 명단)

| 경로 | 내용 |
|---|---|
| `/Users/lagyeongjun/CD/MIND/metahumotonic/나는야_ice_orca_dragon.md` | 명단 시 (TPA 직접 명시는 아니지만 APT 개발론과 같은 계열) |

## 핵심 인용

SKILL.md (orchestrator):
> TPA v1.0 orchestrator — APT v24 역분석 기반 역순 사이클.
> 코드→설계 복원 (TCW→TT→TP→TA). 5대 본질 MIC 참조.
> 오답노트 피드백 루프 내장. Gate Check Hook 강제.

> **본질이 업데이트되면 TPA도 자동 진화한다.**
> 아래 slot의 `currentConcrete`가 바뀌면 TPA 전체가 새 구현체를 사용. SKILL.md 본문 수정 불필요 (DIP 원칙).

| 무기 | MIC Slot | TPA 역할 |
|---|---|---|
| Prometheus | ResearchProvider | unknown 리서치, 패턴 탐색 |
| Naesengmoon | AdversarialValidator | 각 phase gate 검증 |
| 88-Naesengmoon | MetaVerifier | TPA 방법론 자체 메타검증 |
| Longinus | KgCodeBinder | 코드↔KG 양방향 바인딩 |
| 재배맨 | SubagentSeeder | 병렬 subagent 분산 |
| Harness | (구조적 제약) | 4축 제약 모델 |

## 논문 작성 시 발전 가능 축

- **(a) 정방향 vs 역방향 동치성**: APT 결과를 TPA로 다시 분해하면 원본 SA가 나오는가 (BX Lens GetPut/PutGet 적용).
- **(b) 코드→설계의 정보손실**: 컴파일이 lossy하듯, TCW→TT→TP→TA는 어디서 손실하는가. Drift 5종이 그 손실의 측정.
- **(c) Pattern Library 51개의 분류학**: GoF + DDD + Distributed + PL — 각 카테고리의 검증 전략이 다른 이유.
- **(d) 외부/레거시 코드의 KG 흡수**: 본 방법론의 실용 가치 — 인수합병, 오픈소스 도입, 디지털 고고학.
- **(e) Drift 5종의 의미**: Missing/Orphan/SigMismatch/PatternDiv/LabelRot이 코드-KG 정합성의 어떤 차원인가.
- **(f) APT-TPA 듀얼**: MIC를 공유하는 두 방법론. 5대 무기가 양쪽에서 같은 역할을 한다는 것의 형식적 의미.
- **(g) 12사도와 무관**: APT/TPA 모두 도구. 사도 아님.
