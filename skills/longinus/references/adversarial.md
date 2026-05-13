# longinus — Adversarial

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## 1. Binding Adversarial Surface

Longinus 의 binding 은 *passive* 검증이지만 *active* attack 가능:
- ReferenceSite 가 진짜 file:line 가리키는가? (parser 검증)
- SHA256 baseline 가 stale 가? (timestamp 검증)
- Drift coverage_ratio 가 over-reported 인가? (재계산)
- Reverse orphan 이 진짜 missing 인가? (수동 확인)

## 2. Anti-Bypass for Longinus

| # | Bypass | 검출 | 처방 |
|---|--------|------|------|
| 1 | grep으로 symbol harvest | parsed_with field | TR4 강제 |
| 2 | manifest skip | union vs manifest assertion | TR5 강제 |
| 3 | sha256 baseline 거짓 (stale) | baseline_at age | daemon refresh |
| 4 | DRIFT 검출 후 status SUSPENDED 안 함 | V9 audit | TR/HR 강제 |
| 5 | BX PutPut 자동 머지 | violation log | sigma_oracle |
| 6 | L4 file:line 누락 | layer_completeness bitmask | G4 강제 |
| 7 | reverse orphan 무시 | total ratio | Lesson |

## 3. Taliban --lens longinus 통합

LensSet `longinus` 가 Tier1 binding 검증 전용:

```cypher
MERGE (ls:LensSet {name: 'longinus'})
SET ls.lensCount = 9,
    ls.lenses = [
      'reference_site_completeness',
      'sha256_freshness',
      'bx_law_compliance',
      'drift_coverage_threshold',
      'reverse_orphan_management',
      'parser_ground_truth',
      'manifest_assertion',
      'layer_completeness_audit',
      'crate_script_binding'
    ],
    ls.scope = 'longinus binding integrity',
    ls.deprecated = false
```

## 4. Critic Input Context

Taliban critic 가 받는 컨텍스트 (--lens longinus):
- ReferenceSite list (with layer_completeness)
- SHA256 baseline + current (drift evidence)
- BX law violation list
- 5-drift report
- ReverseOrphan list
- Parser output stats (parsed_with, symbol_count vs wc -l ground truth)

## 5. Lakatos 측 Progressive 입증

7-Layer Reference Model 은 *progressive* hypothesis (4-Layer 보다 정밀):

| Test | 4-Layer (이전) | 7-Layer (v3) |
|------|---------------|---------------|
| theory_laden_anomaly | drift 검출 가능 | drift kind 분류 가능 |
| independent_testable_consequence | sha256 만 | + line_range / crate-script |
| excess_empirical_content | 코드 위치 | + 코드 변화 history (sha256 timeline) |
| principled_grounding | BX 2-law (Get/Put) | BX 3-law (+ PutPut) |

→ 7-Layer 가 PROGRESSIVE.

## 6. Adversarial Mode in Daemon

`longinus_sha256_daemon.py` (production launchd 1h interval):
- 모든 ReferenceSite SHA256 검증
- DRIFT detected → push notification webhook
- HIGH severity Lesson 5+ 누적 → 사용자 verdict 게이트
- daemon health log (last_run timestamp)

→ continuous adversarial layer (cron-driven).

## 7. The Human as Meta-Discriminator

자동 drift detection 도 false positive 가능 (예: refactor 가 의도된 변경):
- sigma_oracle 가 DRIFT 의도성 결정
- `lesson-longinus-intentional-refactor` 같은 카테고리 logging
- daemon 자체 false positive 패턴 학습 (Lesson 후보)

# KG: ATOM_Skill_longinus, fw-longinus-references-apt-parity-2026-05-06
