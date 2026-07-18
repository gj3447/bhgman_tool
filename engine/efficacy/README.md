# efficacy — A/B falsification 실험 (결과 + 하네스)

방법론/군단장이 실제로 뭘 *더하는지* 외부 baseline 대비 falsifiable 측정. **결과 = `SWEEP_RESULTS.md`.**

핵심 결론 (2026-05-30): 도구예산 통제 후 base-LLM 대비 **cognitive 우위 ≈ 0**. 가치는 operational(scale·재현성·audit)뿐.

- `falsifier.py` / `harness.py` — 실험 하네스
- `longinus_ab_experiment.py` — longinus drift 엔진 ON/OFF 반사실
- `drift_oracle.py` / `mutation_oracle.py` — 비순환 oracle
- `scale_curve.py` — 스케일 커브
- `run_all_commanders.py` / `run_kg_efficacy.py` — 러너
- `metrics.py` / `scoring_bridge.py` — 지표

## Diagnostic-repair v3 harness

새 diagnostic loop의 구현 정확성과 인과효능을 분리해 검증하는 `L_RT`
하네스:

- `diagnostic_repair_harness.py` — 정확히 6개 arm
  (`single`, `bestN`, `legacy_repair`, `pi_repair`, `pi_decoy`,
  `plain_baseline`)을 실행한다. `pi_repair`/`pi_decoy`는
  `engine.legion.diagnostic_repair.diagnostic_repair`를 직접 호출한다.
- `analyze_diagnostic_repair_harness.py` — schema/hash/conservation 검증 후
  모든 proof를 frozen oracle boundary에서 재실행한다. 안전한 proof와 decoy
  setup은 sandbox에서, 명백한 command payload는 canonical pre-sandbox
  rejection으로 재현하고 exact verdict와 diagnostic을 대조한 뒤,
  per-run·per-task exact sign test, paired Student-t
  TOST, live-task compute parity, comparator별 matched-token 결과, power와
  concentration을 계산한다.
- `diagnostic_repair_harness_manifest.v3.json` — claim-bearing run의 코드·oracle·
  task·contract SHA-256과 threshold authority.
- `DIAGNOSTIC_REPAIR_PREREGISTRATION_V3.md` — 6-arm 정의와 B1/P1–P5 사전등록.
- `diagnostic_repair_harness_contract.json` — Harness `L_RT` control contract.
- `diagnostic_repair_harness_fsm.json` +
  `diagnostic_repair_harness_fsm_traces.json` — arm lifecycle 정본과 추상 trace.
- `lean_sandbox_runner_macos.py` — host fallback 없이 Lean을 격리 실행하는
  hash-frozen macOS reference sandbox. `lean/lean-toolchain`, 전체 버전 문자열,
  Lean 실행파일 SHA-256까지 함께 고정한다.

기존 `lean_headroom_run.py`는 historical/frozen 구현으로 보존한다. 기존
`8W/2T/0L`은 신규 PI 엔진의 결과로 소급 귀속하지 않는다.

```bash
export BHGMAN_LLM_BASE_URL="<32b-openai-compatible-endpoint>"
export BHGMAN_LLM_MODEL="qwen2.5:32b-instruct"
export LEAN_TEMP="0.8"
export LEAN_MAX_TOKENS="3072"

uv run python -m engine.efficacy.diagnostic_repair_harness \
  --k 4 --replications 10 --seed-step 10 \
  --execute-frozen-run \
  --out-dir verification/diagnostic-repair-v3-32b

uv run python -m engine.efficacy.analyze_diagnostic_repair_harness \
  --json verification/diagnostic-repair-v3-32b
```

하네스·manifest·사전등록이 먼저 clean commit되어야 P5가 PASS한다. dirty
worktree, redacted payload, hidden token usage, hash drift는 결과가 좋아도
`CONFIRM`을 만들 수 없다. sandbox 누락/변조, 정확한 32B run-design 불일치,
seed/feedback chain, 실제 JSONL 실행 순서, PI lifecycle 지문, attempt별 출력
상한, 실제 응답 model ID, decoy setup 인과체인, sandbox replay 불일치,
commit-before-run 시각 불일치도 model 호출 전에 또는 analyzer에서
fail-closed된다. Lean child output은 64,000 bytes에서 process group이
종료되고, 임시 sandbox 경로는 deterministic diagnostic replay를 위해
정규화된다.

Loop contract의 publication/checkpoint control plane은 목표 설계이며 현재
runner 구현이 아니다. 현재 구현은 local fresh-file + per-record flush이고
resume/atomic rename/outbox가 없으며, FSM도 실행 reducer가 아닌 reference
model이다.

> 심장 = preflight 3-falsifier 게이트 (순환성/신호부재/신호역전). 효능 주장 전 통과 필수
> (`project_efficacy_measurement_line_2026_06_01`).
