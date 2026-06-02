# efficacy — A/B falsification 실험 (결과 + 하네스)

방법론/군단장이 실제로 뭘 *더하는지* 외부 baseline 대비 falsifiable 측정. **결과 = `SWEEP_RESULTS.md`.**

핵심 결론 (2026-05-30): 도구예산 통제 후 base-LLM 대비 **cognitive 우위 ≈ 0**. 가치는 operational(scale·재현성·audit)뿐.

- `falsifier.py` / `harness.py` — 실험 하네스
- `longinus_ab_experiment.py` — longinus drift 엔진 ON/OFF 반사실
- `drift_oracle.py` / `mutation_oracle.py` — 비순환 oracle
- `scale_curve.py` — 스케일 커브
- `run_all_commanders.py` / `run_kg_efficacy.py` — 러너
- `metrics.py` / `scoring_bridge.py` — 지표

> 심장 = preflight 3-falsifier 게이트 (순환성/신호부재/신호역전). 효능 주장 전 통과 필수
> (`project_efficacy_measurement_line_2026_06_01`).
