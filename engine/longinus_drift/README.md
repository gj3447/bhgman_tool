# longinus_drift — drift 감지부 (작은 조각)

⚠ **`longinus_drift_audit/`와 다름.** 헷갈리지 말 것.

- 이것 = eureka에서 분리돼 나온 **drift 감지 조각** (`ged_drift_detector` / `nightly_drift_check`).
  eureka-l8-rectification split (2026-05-27). pyproject에서 root-scan 대상.
- `longinus_drift_audit/` = 프로덕션 7-layer 감사 러너 (정본 구현, 자체 README).

파일:
- `ged_drift_detector.py` — GED 기반 drift 탐지
- `nightly_drift_check.py` — 야간 배치 체크
