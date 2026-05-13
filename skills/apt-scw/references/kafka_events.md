# SCW Kafka Events — Specific Payloads (Phase-Specific)

> 일반 Kafka convention은 [_common/kafka_event_convention.md](../../_common/kafka_event_convention.md). 본 파일은 SCW가 *발행*하는 이벤트 specific payload.

---

## ContractMaterialized (Active → Fulfilled)

```json
{
  "event_type": "ContractMaterialized",
  "timestamp": "2026-05-11T14:30:00Z",
  "correlation_id": "uuid",
  "agent": "agent_scw_02",
  "branch": "feature/xxx",
  "payload": {
    "contract": "CT_xxx",
    "task": "TASK_xxx",
    "source_file": "src/xxx.py",
    "target_file": "src/xxx.py",
    "impact_tests": ["tests/test_xxx.py", "tests/test_xxx_convergence.py"],
    "baseline_results": {"tests/test_xxx.py": "PASS (12 tests, 0.3s)"},
    "post_results": {"tests/test_xxx.py": "PASS (18 tests, 0.5s)"},
    "new_tests_added": 6,
    "coverage": 0.87,
    "nfr_results": {
      "latency_p99_ms": 45.2,
      "latency_threshold_ms": 100,
      "accuracy_mean": 0.962,
      "accuracy_threshold": 0.95,
      "repetitions": 10
    },
    "lines": 187,
    "complexity_threshold": 500
  }
}
```

---

## FeedbackCreated (PH5 → PH3/PH4)

```json
{
  "event_type": "FeedbackCreated",
  "timestamp": "2026-05-11T14:35:00Z",
  "correlation_id": "uuid",
  "agent": "agent_scw_02",
  "payload": {
    "feedback": "FB_xxx_001",
    "discovery_type": "contract_gap",
    "category": "Missing",
    "target_phase": "PH4",
    "affected_span": "ATOM_xxx",
    "severity": "blocking"
  }
}
```

자세히: [ph6_feedback.md](ph6_feedback.md)

---

## GateCheckFailed (FulfillmentGate FAIL)

```json
{
  "event_type": "GateCheckFailed",
  "timestamp": "2026-05-11T14:32:00Z",
  "correlation_id": "uuid",
  "agent": "agent_scw_02",
  "payload": {
    "gate_name": "FulfillmentGate",
    "check_failed": 5,
    "check_name": "Complexity within threshold",
    "actual_value": 678,
    "threshold_value": 500,
    "threshold_source": "cfg.complexity_threshold",
    "action": "block_materialization",
    "remediation": "return to PH3 for decomposition"
  }
}
```

자세히: [fulfillment_gate.md](fulfillment_gate.md)

---

## AptTestRunCompleted (EDD)

```json
{
  "event_type": "AptTestRunCompleted",
  "timestamp": "2026-05-11T14:25:00Z",
  "correlation_id": "uuid",
  "agent": "agent_scw_02",
  "payload": {
    "test_run": "TR_CT_xxx_uuid",
    "contract": "CT_xxx",
    "environment": "agent_local",
    "total_tests": 18,
    "passed": 18,
    "failed": 0,
    "skipped": 0,
    "pass_rate": 1.0,
    "repetitions": 10,
    "mean_accuracy": 0.962,
    "ci_lower": 0.928,
    "ci_upper": 0.985,
    "wall_time_seconds": 12.3,
    "tokens_consumed": null,
    "gpu_hours": null
  }
}
```

---

## CIDivergenceDetected (Agent vs CI)

```json
{
  "event_type": "CIDivergenceDetected",
  "timestamp": "2026-05-11T14:40:00Z",
  "correlation_id": "uuid",
  "agent": "system_monitor",
  "payload": {
    "contract": "CT_xxx",
    "agent_pass_rate": 1.0,
    "ci_pass_rate": 0.85,
    "divergence": 0.15,
    "threshold": 0.05,
    "action": "flag_contract_for_review",
    "possible_cause": "environment_mismatch | random_seed | hardware_diff"
  }
}
```

자세히: [edd.md](edd.md) CI Divergence Query 절.

# KG: APT_SCW_KafkaEvents_canonical
