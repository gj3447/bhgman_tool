# TPA Hard Rules (TR1-TR15) — APT v24 역분석 매핑

> # KG: ATOM_Skill_tpa_orchestrator_v10, TPA_methodology_v10

## APT ↔ TPA 거울 매핑

| TPA Rule | APT 원본 | 역방향 적용 |
|---|---|---|
| TR1 | HR1 (Adversarial at every gate) | 동일 — 매 phase gate에 Naesengmoon |
| TR2 | HR11 (Evidence-backed verdict) | 동일 — APPROVED에 증거 필수 |
| TR3 | HR7 (Gate transition logged) | 역순: TCW→ST→SP→TA 순서 강제 |
| TR4 | (신규) | AST 파서 필수 — grep 단독은 false positive |
| TR5 | (신규) | skipped_files = 0 — 사각지대 방지 |
| TR6 | HR5 (KG density) | Unknown → ResearchProvider 자동 |
| TR7 | HR7 (KG logging) | 동일 — 모든 전환 기록 |
| TR8 | HR12 (2-Tier Naesengmoon) | 동일 — artifact vs methodology 분리 |
| TR9 | HR14 (Post-gate reflection) | 동일 — reflection 필수 |
| TR10 | (신규) | Lesson 즉시 생성 — 피드백 루프 핵심 |
| TR11 | HR2+HR3 (executor ≠ reviewer) | 동일 — D20 원칙 |
| TR12 | (Longinus) | 결과물에 KG 바인딩 필수 |
| TR13 | (treasure_coverage) | MIC slot 활용 최소 0.9 |
| TR14 | (신규) | 대형 repo 재배맨 병렬 필수 |
| TR15 | HR13 (Essential ✗) | 역분석의 본질적 한계 인정 |

## Essential ✗ (TR15 상세)

역분석에서 **절대 "고칠 수 없는" 본질적 한계**:

1. **Information Loss** (Gödel) — 컴파일된 코드에서 원저자 의도 100% 복원 불가
2. **Naming Drift** — 원저자의 네이밍 의도와 TPA 추출 이름의 괴리
3. **Dead Code Blindness** — 실행 경로 없이 dead code 완전 식별 불가
4. **Implicit Convention** — 암묵적 관행(coding convention) 완전 포착 불가
5. **Temporal Context** — 왜 그 시점에 그 결정을 했는지 git history만으로 부족

이들은 **버그가 아니라 설계 제약**. "고쳤다"고 주장하면 rubber-stamp 위반.
