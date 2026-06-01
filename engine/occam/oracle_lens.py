"""나생문 oracle 렌즈 — occam 측 재export (정본은 engine/naesengmoon/oracle_lens.py).

primitive(OracleLens/OracleVerdict/run_oracle_gate)는 occam·eureka 2 commander 에 중복돼
있었고 정본 나생문 패키지로 추출됨 (오캄 dedup 2026-06-01,
wqi-extract-shared-naesengmoon-oracle-primitive-2026-05-27). 본 모듈은 기존 import 경로
(`engine.occam.oracle_lens`) back-compat 용 thin re-export — 정의 없음, drift 불가.

# KG: naesengmoon-compiler-family-2026-05-27, naesengmoon-tdd-connection-2026-05-27
"""

from __future__ import annotations

from engine.naesengmoon.oracle_lens import (
    CommandRunner,
    OracleLens,
    OracleVerdict,
    run_oracle_gate,
    subprocess_runner,
)

__all__ = [
    "CommandRunner",
    "OracleLens",
    "OracleVerdict",
    "run_oracle_gate",
    "subprocess_runner",
]
