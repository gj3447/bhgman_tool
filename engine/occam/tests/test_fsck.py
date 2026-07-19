"""오캄 fsck 불변식 테스트 — PROM 6 C8 (dangling/ambiguous 무덤 탐지).

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A3-2026-07-19
"""

from __future__ import annotations

from engine.occam.fsck import (
    _ARCHIVE_INTEGRITY_CYPHER,
    check_archive_integrity,
    IntegrityViolation,
)


class _Runner:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __call__(self, cypher, params):
        self.calls.append((cypher, params))
        return self.rows


def test_cypher_gates_on_archived_label_and_live_target():
    # 라벨 기준(canonical 마커) + live(비아카이브) 타겟만 카운트해야 한다.
    up = _ARCHIVE_INTEGRITY_CYPHER.upper()
    assert ":ARCHIVED" in up
    assert "NOT T:ARCHIVED" in up  # 타겟은 살아있어야 유효
    assert "LIVE_TARGETS <> 1" in up  # 0(dangling) 또는 >1(ambiguous) 위반


def test_clean_kg_has_no_violations():
    assert check_archive_integrity(_Runner([])) == []


def test_dangling_tomb_flagged():
    runner = _Runner([{"name": "x@bind", "source_path": "engine/x.py", "live_targets": 0}])
    v = check_archive_integrity(runner)
    assert len(v) == 1
    assert v[0].kind == "DANGLING"
    assert v[0].live_targets == 0
    assert v[0].source_path == "engine/x.py"


def test_ambiguous_multi_survivor_flagged():
    runner = _Runner([{"name": "y@bind", "source_path": "engine/y.py", "live_targets": 2}])
    v = check_archive_integrity(runner)
    assert v[0].kind == "AMBIGUOUS"
    assert v[0].live_targets == 2


def test_null_live_targets_coerced_to_dangling():
    # count(t) 가 NULL 로 오는 경우(방어) → 0 = DANGLING 으로 취급.
    v = check_archive_integrity(_Runner([{"name": "z", "source_path": None, "live_targets": None}]))
    assert v[0].kind == "DANGLING" and v[0].live_targets == 0


def test_readonly_no_write_tokens_in_cypher():
    up = _ARCHIVE_INTEGRITY_CYPHER.upper()
    for tok in ("DELETE", "DETACH", "REMOVE", "SET ", "MERGE", "CREATE"):
        assert tok not in up, f"fsck must be read-only, found {tok}"
