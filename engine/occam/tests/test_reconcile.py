"""오캄 reconcile 테스트 — cross-KG-store content-address set-diff (PROM 6 P3).

fake runner 주입, 결정론, no network/DB.

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A4-2026-07-19
"""

from __future__ import annotations

import dataclasses

import pytest

from engine.occam.reconcile import (
    KEYS_CYPHER,
    DriftEntry,
    MissingEntry,
    ReconcileReport,
    diff_stores,
    fetch_keys,
    reconcile,
)


class _Runner:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __call__(self, cypher, params):
        self.calls.append((cypher, params))
        return self.rows


def _row(rid="repo1", rel="engine/x.py", sha="aaa", name="x@bind"):
    return {"repo_id": rid, "repo_relpath": rel, "sha256": sha, "name": name}


# ── KEYS_CYPHER 계약 ─────────────────────────────────────────────────────────


def test_keys_cypher_gates_on_archived_label_via_views():
    # 라벨 게이트는 views.current_only 단일 진실원 경유 (NOT n:ARCHIVED).
    up = KEYS_CYPHER.upper()
    assert "NOT N:ARCHIVED" in up


def test_keys_cypher_requires_full_content_address_key():
    up = KEYS_CYPHER.upper()
    for prop in ("N.REPO_ID", "N.REPO_RELPATH", "N.SHA256"):
        assert f"{prop} IS NOT NULL" in up


def test_keys_cypher_readonly_no_write_tokens():
    up = KEYS_CYPHER.upper()
    for tok in ("DELETE", "DETACH", "REMOVE", "SET ", "MERGE", "CREATE"):
        assert tok not in up, f"reconcile must be read-only, found {tok}"


def test_keys_cypher_deterministic_order_by():
    assert "ORDER BY" in KEYS_CYPHER.upper()


# ── fetch_keys ───────────────────────────────────────────────────────────────


def test_fetch_keys_runs_keys_cypher_and_passes_rows_through():
    runner = _Runner([_row()])
    rows = fetch_keys(runner)
    assert rows == [_row()]
    assert runner.calls == [(KEYS_CYPHER, {})]


def test_fetch_keys_skips_rows_missing_required_key_fields():
    runner = _Runner(
        [
            _row(),
            {"repo_id": None, "repo_relpath": "a.py", "sha256": "x", "name": "n"},
            {"repo_id": "r", "repo_relpath": None, "sha256": "x", "name": "n"},
            {"repo_id": "r", "repo_relpath": "a.py", "sha256": None, "name": "n"},
        ]
    )
    assert fetch_keys(runner) == [_row()]


def test_fetch_keys_tolerates_none_result():
    assert fetch_keys(_Runner(None)) == []


def test_fetch_keys_keeps_null_name_rows():
    # name 은 표시용일 뿐 identity 아님 — NULL 이어도 키가 완전하면 유지.
    row = _row(name=None)
    assert fetch_keys(_Runner([row])) == [row]


# ── diff_stores: 집합 연산 분류 ──────────────────────────────────────────────


def test_identical_stores_are_in_sync():
    a = [_row(), _row(rel="engine/y.py", sha="bbb", name="y@bind")]
    rep = diff_stores(a, list(a))
    assert rep.identical == 2
    assert rep.missing_in_b == () and rep.missing_in_a == () and rep.content_drift == ()
    assert rep.in_sync is True


def test_missing_in_b_when_path_absent_from_b():
    rep = diff_stores([_row()], [])
    assert rep.missing_in_a == () and rep.content_drift == () and rep.identical == 0
    assert rep.missing_in_b == (
        MissingEntry("repo1", "engine/x.py", "aaa", ("x@bind",)),
    )
    assert rep.in_sync is False


def test_missing_in_a_is_reverse():
    rep = diff_stores([], [_row()])
    assert rep.missing_in_b == () and rep.missing_in_a == (
        MissingEntry("repo1", "engine/x.py", "aaa", ("x@bind",)),
    )


def test_content_drift_same_path_different_sha_reports_both_shas():
    rep = diff_stores([_row(sha="aaa")], [_row(sha="bbb", name="x@bind-airo")])
    assert rep.content_drift == (
        DriftEntry(
            repo_id="repo1",
            repo_relpath="engine/x.py",
            sha256_a=("aaa",),
            sha256_b=("bbb",),
            names_a=("x@bind",),
            names_b=("x@bind-airo",),
        ),
    )
    # 드리프트 쌍은 missing 리스트에 중복 집계되지 않는다 (버전 차이 ≠ 부재).
    assert rep.missing_in_b == () and rep.missing_in_a == ()
    assert rep.identical == 0


def test_drift_pair_with_common_sha_counts_identical_and_reports_only_uniques():
    # 한 store 안에 같은 경로의 sha 가 복수인 경우 — 공통은 identical, 고유만 드리프트.
    a = [_row(sha="aaa", name="old"), _row(sha="ccc", name="shared")]
    b = [_row(sha="ccc", name="shared")]
    rep = diff_stores(a, b)
    assert rep.identical == 1
    assert rep.content_drift == (
        DriftEntry(
            repo_id="repo1",
            repo_relpath="engine/x.py",
            sha256_a=("aaa",),
            sha256_b=(),
            names_a=("old",),
            names_b=(),
        ),
    )


def test_repo_id_distinguishes_same_relpath():
    # 다른 repo 의 같은 relpath 는 다른 키 — 드리프트 아님.
    rep = diff_stores([_row(rid="repo1")], [_row(rid="repo2")])
    assert rep.content_drift == ()
    assert [e.repo_id for e in rep.missing_in_b] == ["repo1"]
    assert [e.repo_id for e in rep.missing_in_a] == ["repo2"]


def test_names_aggregated_sorted_for_duplicate_key_nodes():
    # 같은 삼중키를 가진 노드 여럿(store 내 중복 바인딩) → names 로 전부 추적.
    a = [_row(name="z@dup"), _row(name="a@dup")]
    rep = diff_stores(a, [])
    assert rep.missing_in_b[0].names == ("a@dup", "z@dup")


def test_null_name_falls_back_to_relpath():
    rep = diff_stores([_row(name=None)], [])
    assert rep.missing_in_b[0].names == ("engine/x.py",)


def test_diff_ignores_rows_with_incomplete_keys():
    rep = diff_stores([{"repo_id": "r", "repo_relpath": None, "sha256": "x", "name": "n"}], [])
    assert rep == ReconcileReport()


# ── 결정론적 정렬 ────────────────────────────────────────────────────────────


def test_outputs_sorted_regardless_of_input_order():
    a = [
        _row(rid="r2", rel="b.py", sha="s2", name="n2"),
        _row(rid="r1", rel="z.py", sha="s9", name="n9"),
        _row(rid="r1", rel="a.py", sha="s1", name="n1"),
    ]
    rep1 = diff_stores(a, [])
    rep2 = diff_stores(list(reversed(a)), [])
    assert rep1 == rep2
    assert [(e.repo_id, e.repo_relpath) for e in rep1.missing_in_b] == [
        ("r1", "a.py"),
        ("r1", "z.py"),
        ("r2", "b.py"),
    ]


def test_drift_entries_sorted_by_pair():
    a = [_row(rel="z.py", sha="a1"), _row(rel="a.py", sha="a2")]
    b = [_row(rel="z.py", sha="b1"), _row(rel="a.py", sha="b2")]
    rep = diff_stores(a, b)
    assert [d.repo_relpath for d in rep.content_drift] == ["a.py", "z.py"]


# ── ReconcileReport value object ─────────────────────────────────────────────


def test_report_is_frozen():
    rep = diff_stores([], [])
    with pytest.raises(dataclasses.FrozenInstanceError):
        rep.identical = 99


def test_summary_korean_counts():
    rep = diff_stores(
        [_row(), _row(rel="d.py", sha="v1")],
        [_row(), _row(rel="d.py", sha="v2"), _row(rel="only-b.py", sha="q")],
    )
    s = rep.summary
    assert "드리프트 감지" in s
    assert "동일 1" in s
    assert "내용 드리프트 1" in s
    assert "a에만 0" in s
    assert "b에만 1" in s


def test_summary_in_sync():
    assert "동기화됨" in diff_stores([_row()], [_row()]).summary


# ── reconcile wrapper ────────────────────────────────────────────────────────


def test_reconcile_fetches_both_stores_and_diffs():
    ra = _Runner([_row(sha="aaa")])
    rb = _Runner([_row(sha="bbb")])
    rep = reconcile(ra, rb)
    assert ra.calls == [(KEYS_CYPHER, {})]
    assert rb.calls == [(KEYS_CYPHER, {})]
    assert len(rep.content_drift) == 1
    assert rep.content_drift[0].sha256_a == ("aaa",)
    assert rep.content_drift[0].sha256_b == ("bbb",)
