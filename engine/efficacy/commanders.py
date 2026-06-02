"""7군단장 효능 측정 명세 registry.

각 군단장의 (동사/task/metric/oracle/필요신호/기대방향/순환성keyword)를 한 곳에.
label_cypher 있는 것만 실 KG 측정 시도; None은 oracle 미구축(UNMEASURABLE no-oracle).

정직 현황(2026-06-02): label_cypher(AUC sweep용)이 있는 건 occam·longinus 둘 뿐이고 그조차
순환성 위험. 나머지는 별도 독립-oracle 러너로 측정 — naesengmoon=mutation_oracle,
jaebaeman=dispatch_telemetry, hades=hades_oracle(test-reachability+pytest, realization 0.839),
prometheus=prometheus_oracle(verifiability 0.931)+prometheus_novelty(recall-delta 0.933, control_acc 1.0),
eureka=eureka_oracle(planted recovery lift +1.000 + 실 KG reuse-breadth 7추상/319노드 cover).
전원 측정값 보유하되 honesty tier 상이(cognitive/operational/capability) → 통합표=SWEEP_RESULTS.md.

# KG: efficacy-occam-sigma-ab-2026-06-01, 7cmd-measurement-driven-conditional-dispatch-2026-05-30,
#     bihaenggiman-legioncommanders-2026-05-26
"""

from __future__ import annotations

from engine.efficacy.models import CommanderEfficacySpec, Direction

# 오캄: 이미 superseded vs active 라벨 존재. signal=redundancy(sha-twin). 순환+역전 알려짐.
_OCCAM_CYPHER = (
    "MATCH (s:SourceCodeNode) WHERE s.status IN ['SUPERSEDED','superseded','active','ACTIVE'] "
    "AND s.sha256 IS NOT NULL "
    "OPTIONAL MATCH (t:SourceCodeNode) WHERE t.sha256=s.sha256 AND t<>s "
    "WITH s, count(t) AS twins, (s.status IN ['SUPERSEDED','superseded']) AS pos "
    "RETURN s.name AS item_id, pos AS is_positive, "
    "toFloat(CASE WHEN twins>0 THEN 1 ELSE 0 END) AS signal, "
    "coalesce(s.supersededReason, s.occam_archive_reason, '') AS provenance"
)

# 롱기누스: drift 라벨. signal=disk sha≠baseline. drift_reason/boundBy provenance — 순환 위험.
_LONGINUS_CYPHER = (
    "MATCH (s:SourceCodeNode) WHERE s.sha256_baseline IS NOT NULL "
    "WITH s, (s.drift_detected = true OR s.sha_disk_mismatch = true) AS pos "
    "RETURN s.name AS item_id, pos AS is_positive, "
    "toFloat(CASE WHEN s.sha256 <> s.sha256_baseline THEN 1 ELSE 0 END) AS signal, "
    "coalesce(s.drift_reason, s.boundBy, '') AS provenance"
)


COMMANDERS: tuple[CommanderEfficacySpec, ...] = (
    CommanderEfficacySpec(
        commander="occam",
        verb="정리",
        task="stale/중복 노드를 active와 구분해 supersession 후보화",
        metric="AUC(superseded vs active)",
        oracle_source="KG status 라벨 (※ 73% occam-생성 = 순환)",
        required_signal="redundancy(sha-twin), age(created_at), invocation",
        expected_direction=Direction.HIGHER,
        circularity_keywords=("occam", "dup", "duplicate", "redundant", "supersed", "moved"),
        label_cypher=_OCCAM_CYPHER,
        known_falsifier="라벨 순환 + active created_at=0 + invocation 부재 + twin율 역전(41<59)",
    ),
    CommanderEfficacySpec(
        commander="longinus",
        verb="연결",
        task="code↔KG drift 탐지 (sha256 vs baseline)",
        metric="AUC(drifted vs clean)",
        oracle_source="KG sha256_baseline (※ longinus-자체 산출 = 순환 위험)",
        required_signal="sha256, sha256_baseline",
        expected_direction=Direction.HIGHER,
        circularity_keywords=("longinus", "drift", "rebind", "rebound"),
        label_cypher=_LONGINUS_CYPHER,
        known_falsifier="drift 라벨도 longinus 자신이 찍음 + 독립 disk-change 진실 부재",
    ),
    CommanderEfficacySpec(
        commander="prometheus",
        verb="획득",
        task="외부 지식 ingest의 신규성/정확성 (base-LLM 회상 대비)",
        metric="finding novelty / precision",
        oracle_source="held-out 외부 사실셋 (미구축)",
        required_signal="ResearchFinding verified + 외부 정답 라벨",
        expected_direction=Direction.HIGHER,
        circularity_keywords=("prometheus", "prom"),
        label_cypher=None,
        known_falsifier="self-citation loop (project_bhgman_self_critique). 외부 held-out 필요",
    ),
    CommanderEfficacySpec(
        commander="eureka",
        verb="발견·창조",
        task="반복 패턴→추상 추출의 재사용률 (사람/baseline 대비)",
        metric="abstraction reuse rate",
        oracle_source="반복-패턴 코퍼스 + 사후 재사용 측정 (미구축)",
        required_signal="추상노드↔재사용 site 엣지 + 시계열",
        expected_direction=Direction.HIGHER,
        circularity_keywords=("eureka", "colimit"),
        label_cypher=None,
        known_falsifier="metaphor-not-algebraic dual. 재사용 시계열 데이터 미수집",
    ),
    CommanderEfficacySpec(
        commander="naesengmoon",
        verb="검증",
        task="적대적 결함 탐지율 (주입/기지 결함 대비)",
        metric="defect catch rate / precision",
        oracle_source="주입 결함셋(mutation/known-bug) (미구축)",
        required_signal="ValidationResult ↔ 결함 ground-truth",
        expected_direction=Direction.HIGHER,
        circularity_keywords=("naesengmoon", "taliban"),
        label_cypher=None,
        known_falsifier="critic 자체 oracle-reading drift. 독립 결함 라벨 필요",
    ),
    CommanderEfficacySpec(
        commander="jaebaeman",
        verb="출격",
        task="병렬 분해 충실도 (의도 N == 실제 dispatch N, GH#29181)",
        metric="dispatch fidelity (correctness, not AUC)",
        oracle_source="dispatch 의도 vs 실측 (telemetry 신설중)",
        required_signal="DispatchHyperedge intent_n / actual_n",
        expected_direction=Direction.HIGHER,
        circularity_keywords=("jaebaeman", "재배맨"),
        label_cypher=None,
        known_falsifier="효능≠AUC(분해정확도). telemetry 라인 별도 metric 필요",
    ),
    CommanderEfficacySpec(
        commander="hades",
        verb="실현",
        task="추상 spec→구체 코드 TDD GREEN 도달률",
        metric="test-pass rate (contract suite)",
        oracle_source="contract 테스트셋 통과 (미수집)",
        required_signal="Contract ↔ test suite 결과",
        expected_direction=Direction.HIGHER,
        circularity_keywords=("hades", "harness"),
        label_cypher=None,
        known_falsifier="실현 결과 테스트셋 KG 미적재",
    ),
)


def get_commander(name: str) -> CommanderEfficacySpec | None:
    return next((c for c in COMMANDERS if c.commander == name), None)


__all__ = ["COMMANDERS", "get_commander"]
