# EDD — Evidence-Driven Development (Phase-Specific)

> "예외 없음" 대신 *구체적 threshold + repetition + cost*. 확률적 시스템에도 적용 가능.

---

## 5 Criteria

| # | Criterion | 설명 |
|---|---|---|
| 1 | **Threshold per test** | 모든 테스트에 명시적 pass/fail 임계값. 결정적: 정확한 일치 (`abs(result - expected) < 1e-6`). 확률적: 통계적 경계 ("95% 신뢰도에서 accuracy ≥ 0.95") |
| 2 | **Repetition count** | 결정적: `repetitions = 1`. 확률적: `cfg.stochastic_repetitions` (기본 10) |
| 3 | **Baseline regression** | `regression(t) = baseline.pass_rate - current.pass_rate > cfg.regression_tolerance`. 결정적: 0.0, 확률적: 0.05 |
| 4 | **Cost tracking** | wall-clock, 토큰, GPU-hours, API calls 기록 → AptTestRun |
| 5 | **CI mandatory** | ContractMaterialized → CI 파이프라인 trigger → CI가 impact_tests 독립 재실행. agent vs CI 5% 이상 발산 시 review flag |

---

## Stochastic Repetition 통계

| True accuracy | P(all pass in 10 runs) | P(all pass in 20 runs) |
|:-:|:-:|:-:|
| 1.00 | 1.000 | 1.000 |
| 0.95 | 0.599 | 0.358 |
| 0.90 | 0.349 | 0.122 |
| 0.85 | 0.197 | 0.039 |
| 0.80 | 0.107 | 0.012 |

실용적으로 EDD는 all-pass가 아닌 **threshold 기반**:

```
pass_rate = count(PASS) / repetitions
ASSERT pass_rate >= threshold    # e.g., 0.9
confidence_interval = wilson_score(pass_rate, repetitions, alpha=0.05)
ASSERT confidence_interval.lower >= threshold - margin
```

---

## AptTestRun 스키마

```cypher
CREATE (run:AptTestRun {
  name:              'TR_' + $contract + '_' + $run_id,
  contract:          $contract_name,
  test_file:         $test_file_path,
  environment:       $env,               -- 'agent_local' | 'ci_linux' | 'ci_gpu'
  trigger:           $trigger,           -- 'implementation' | 'regression' | 'ci_scheduled'
  timestamp:         datetime(),
  total_tests:       $total,
  passed:            $passed,
  failed:            $failed,
  skipped:           $skipped,
  pass_rate:         toFloat($passed) / $total,
  repetitions:       $reps,
  mean_metric:       $mean,
  std_metric:        $std,
  ci_lower:          $ci_lower,
  ci_upper:          $ci_upper,
  wall_time_seconds: $time,
  tokens_consumed:   $tokens,
  gpu_hours:         $gpu,
  is_regression:     $is_regression,
  baseline_pass_rate: $baseline_rate,
  regression_delta:  $delta
})
WITH run
MATCH (ct:AptContract {name: $contract_name})
MERGE (ct)<-[:TESTS]-(run)
```

---

## CI Divergence Query

```cypher
MATCH (ct:AptContract)<-[:TESTS]-(agent_run:AptTestRun {environment: 'agent_local'})
MATCH (ct)<-[:TESTS]-(ci_run:AptTestRun {environment: 'ci_linux'})
WHERE agent_run.timestamp > datetime() - duration({hours: 24})
  AND ci_run.timestamp    > datetime() - duration({hours: 24})
  AND abs(agent_run.pass_rate - ci_run.pass_rate) > 0.05
RETURN ct.name AS contract,
       agent_run.pass_rate AS agent_rate,
       ci_run.pass_rate AS ci_rate,
       abs(agent_run.pass_rate - ci_run.pass_rate) AS divergence
ORDER BY divergence DESC
```

`divergence > 5%` 시 → "works on my machine" 위험 → review flag.

# KG: APT_SCW_EDD_canonical
