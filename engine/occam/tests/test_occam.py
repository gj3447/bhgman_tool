"""오캄 코어 TDD — 2026-05-27 손으로 한 pass의 케이스를 spec으로 고정.

# KG: occam-pass-bhgman_tool-2026-05-27, lesson-occam-must-query-kg-node-dedup-...-2026-05-27
"""

from __future__ import annotations

from engine.occam.occam import normalize_path, occam_pass
from engine.occam.occam_models import Confidence, NodeRecord
from engine.occam.scoring import EntrenchmentTier, NodeScoreMeta


def test_normalize_unifies_abs_and_rel_lineage():
    abs_p = "/Users/x/CD/bhgman_tool/engine/foo.py"
    rel_p = "bhgman_tool/engine/foo.py"
    assert normalize_path(abs_p) == normalize_path(rel_p) == "engine/foo.py"


def test_no_dup_single_node_yields_no_candidate():
    nodes = [NodeRecord("solo.py", "bhgman_tool/engine/solo.py", "sha1", 50)]
    report = occam_pass(nodes)
    assert report.superseded_count == 0
    assert report.scanned_nodes == 1


def test_conftest_case_disk_confirms_current_HIGH():
    # 실제 l8 케이스: rel(8L) vs abs(18L) 같은 파일, disk가 abs를 확정
    rel = NodeRecord("l8ind-tests-conftest.py", "bhgman_tool/engine/l8/tests/conftest.py", "aaa", 8)
    abs_ = NodeRecord("conftest.py", "/Users/x/bhgman_tool/engine/l8/tests/conftest.py", "bbb", 18)
    disk = {"engine/l8/tests/conftest.py": "bbb"}
    report = occam_pass([rel, abs_], disk_truth=disk)
    assert report.superseded_count == 1
    cand = report.candidates[0]
    assert cand.stale.name == "l8ind-tests-conftest.py"
    assert cand.current.name == "conftest.py"
    assert cand.confidence is Confidence.HIGH
    assert cand.action == "SUPERSEDED_BY"


def test_amie3_stub_superseded_by_impl_no_disk_MEDIUM():
    # 실제 amie3: stub(23L) vs impl(180L), 둘 다 rel-path, disk 진실 부재 → max line_count=impl
    stub = NodeRecord("l8ind-amie3.py", "bhgman_tool/engine/l8/amie3.py", "stub", 23)
    impl = NodeRecord("l8ind-amie3-impl.py", "bhgman_tool/engine/l8/amie3.py", "impl", 180)
    report = occam_pass([stub, impl])
    assert report.superseded_count == 1
    cand = report.candidates[0]
    assert cand.stale.name == "l8ind-amie3.py"
    assert cand.current.name == "l8ind-amie3-impl.py"
    assert cand.confidence is Confidence.MEDIUM


def test_exact_duplicate_detected():
    # 실제 urdna2015: 같은 name/path/sha/line 완전중복 2개
    a = NodeRecord("urdna.py", "/Users/x/bhgman_tool/engine/urdna.py", "same", 190)
    b = NodeRecord("urdna.py", "/Users/x/bhgman_tool/engine/urdna.py", "same", 190)
    report = occam_pass([a, b])
    assert report.superseded_count == 1
    assert "exact duplicate" in report.candidates[0].reason


def test_covenant_no_delete_only_supersede():
    # OccamReport에 delete 필드 부재 + 모든 action=SUPERSEDED_BY (삭제 금지 covenant)
    stub = NodeRecord("old.py", "bhgman_tool/x.py", "o", 10)
    new = NodeRecord("new.py", "bhgman_tool/x.py", "n", 99)
    report = occam_pass([stub, new])
    assert not hasattr(report, "deleted")
    assert all(c.action == "SUPERSEDED_BY" for c in report.candidates)


def test_three_node_lineage_supersedes_two_toward_disk_current():
    # 같은 파일에 3 노드, disk가 가운데 것 확정 → 나머지 2개 superseded
    n1 = NodeRecord("v1", "bhgman_tool/engine/g.py", "s1", 10)
    n2 = NodeRecord("v2", "/Users/x/bhgman_tool/engine/g.py", "s2", 50)
    n3 = NodeRecord("v3", "bhgman_tool/engine/g.py", "s3", 30)
    report = occam_pass([n1, n2, n3], disk_truth={"engine/g.py": "s2"})
    assert report.superseded_count == 2
    assert all(c.current.name == "v2" for c in report.candidates)
    assert all(c.confidence is Confidence.HIGH for c in report.candidates)


# ─── mode-2: sha-이동 (challenge-occam-pass-...-missed-own-domain-stale-nodes) ───


def test_sha_move_supersedes_orphan_toward_live_twin_HIGH():
    # 실제 ged_drift_detector.py 케이스: longinus_l8_induction/(디스크 삭제) vs
    # longinus_drift/(생존), 동일 sha → 옛 경로 노드를 살아있는 twin으로 supersede.
    old = NodeRecord(
        "ged_drift_detector.py",
        "/Users/x/bhgman_tool/engine/longinus_l8_induction/ged_drift_detector.py",
        "4465964fad4d",
        157,
    )
    new = NodeRecord(
        "l8ind-ged_drift_detector.py",
        "bhgman_tool/engine/longinus_drift/ged_drift_detector.py",
        "4465964fad4d",
        157,
    )
    disk = frozenset({"engine/longinus_drift/ged_drift_detector.py"})  # 옛 경로는 없음
    report = occam_pass([old, new], disk_paths=disk)
    assert report.superseded_count == 1
    cand = report.candidates[0]
    assert cand.stale.name == "ged_drift_detector.py"
    assert cand.current.name == "l8ind-ged_drift_detector.py"
    assert cand.confidence is Confidence.HIGH
    assert "moved" in cand.reason and "absent on disk" in cand.reason
    assert report.orphan_count == 0  # live twin 있으니 orphan 아님


def test_sha_move_skipped_without_disk_paths():
    # disk_paths=None → mode-1만. 다른 경로라 same-path 그룹도 안 묶임 → 후보 0.
    old = NodeRecord("a", "bhgman_tool/engine/old/x.py", "samesha", 10)
    new = NodeRecord("b", "bhgman_tool/engine/new/x.py", "samesha", 10)
    report = occam_pass([old, new])
    assert report.superseded_count == 0
    assert report.orphan_count == 0


def test_both_paths_live_not_superseded():
    # 동일 sha지만 둘 다 디스크 존재 = 의도적 사본(보존). supersede 안 함.
    a = NodeRecord("a", "bhgman_tool/engine/p/x.py", "s", 10)
    b = NodeRecord("b", "bhgman_tool/engine/q/x.py", "s", 10)
    disk = frozenset({"engine/p/x.py", "engine/q/x.py"})
    report = occam_pass([a, b], disk_paths=disk)
    assert report.superseded_count == 0
    assert report.orphan_count == 0


# ─── mode-3: disk-orphan flag-only (machloket 보존) ───


def test_disk_orphan_no_twin_flagged_not_superseded():
    # 경로가 디스크에 없고 동일-sha live twin도 없음 → orphans에 flag, supersede 안 함.
    dead = NodeRecord(
        "l8ind-next-session.md",
        "bhgman_tool/engine/longinus_l8_induction/NEXT_SESSION.md",
        "deadsha",
        200,
    )
    live = NodeRecord("other.py", "bhgman_tool/engine/longinus_drift/other.py", "othersha", 30)
    disk = frozenset({"engine/longinus_drift/other.py"})
    report = occam_pass([dead, live], disk_paths=disk)
    assert report.superseded_count == 0  # supersede 안 함 (machloket)
    assert report.orphan_count == 1
    assert report.orphans[0].name == "l8ind-next-session.md"


def test_external_node_not_flagged_as_orphan():
    # repo 밖 노드(bhgman_tool/ 마커 없음)는 이 repo 디스크로 판정 불가 → orphan/move 평가 제외.
    # (실측 회귀: SYMPOSIUM/THEORY/*BHGMAN* 노드가 false-orphan으로 잡히던 버그.)
    external = NodeRecord(
        "finding.json",
        "/Users/x/CD/SYMPOSIUM/THEORY/PROM_16_BHGMAN_APPLICATION/finding.json",
        "ext",
        45,
    )
    disk = frozenset({"engine/live.py"})
    report = occam_pass([external], disk_paths=disk)
    assert report.orphan_count == 0
    assert report.superseded_count == 0


def test_orphan_survivor_after_samepath_dedup_still_flagged():
    # 같은 죽은 경로에 2 노드(abs 18L / rel 8L): mode-1이 8L를 18L로 supersede,
    # 그 18L survivor는 disk-orphan(경로 없음+live twin 없음)으로 flag.
    abs_ = NodeRecord(
        "conftest.py",
        "/Users/x/bhgman_tool/engine/longinus_l8_induction/tests/conftest.py",
        "bbb",
        18,
    )
    rel = NodeRecord(
        "l8ind-tests-conftest.py",
        "bhgman_tool/engine/longinus_l8_induction/tests/conftest.py",
        "aaa",
        8,
    )
    disk = frozenset({"engine/longinus_drift/tests/conftest.py"})  # l8 경로 없음
    report = occam_pass([abs_, rel], disk_paths=disk)
    assert report.superseded_count == 1  # 8L → 18L
    assert report.candidates[0].stale.name == "l8ind-tests-conftest.py"
    assert report.orphan_count == 1  # 18L survivor는 orphan
    assert report.orphans[0].name == "conftest.py"


# ─── scoring 통합: score_meta 주입 시 후보에 σ + verdict 부착 ───


def test_score_meta_absent_leaves_score_none():
    # 기존 동작 불변: score_meta 없으면 score/verdict = None
    stub = NodeRecord("old.py", "bhgman_tool/x.py", "o", 10)
    new = NodeRecord("new.py", "bhgman_tool/x.py", "n", 99)
    report = occam_pass([stub, new])
    assert report.superseded_count == 1
    assert report.candidates[0].score is None
    assert report.candidates[0].verdict is None


def test_exact_dup_old_unused_scores_supersede():
    # 완전중복(같은 sha) + 오래됨 + 미사용 → redundancy=1.0 occam이 권위 → σ≈1 SUPERSEDE
    a = NodeRecord("dup.py", "/Users/x/bhgman_tool/dup.py", "same", 50)
    b = NodeRecord("dup.py", "/Users/x/bhgman_tool/dup.py", "same", 50)
    meta = {
        "dup.py": NodeScoreMeta(
            redundancy=0.0,  # occam이 _redundancy로 1.0 override
            age_days=3650,
            invocation_count=0,
            tier=EntrenchmentTier.PLAIN,
        )
    }
    report = occam_pass([a, b], score_meta=meta)
    assert report.superseded_count == 1
    cand = report.candidates[0]
    assert cand.score is not None and cand.score >= 0.7
    assert cand.verdict == "SUPERSEDE"


def test_score_meta_redundancy_overridden_by_occam_dedup():
    # stub(10L) vs impl(100L) 다른 sha → occam redundancy = 10/100 = 0.1 (caller 값 무시)
    stub = NodeRecord("s.py", "bhgman_tool/m.py", "s", 10)
    impl = NodeRecord("i.py", "bhgman_tool/m.py", "i", 100)
    meta = {
        "s.py": NodeScoreMeta(
            redundancy=0.99,
            age_days=1.0,
            invocation_count=100,
            tier=EntrenchmentTier.PLAIN,
        )
    }
    report = occam_pass([stub, impl], score_meta=meta)
    cand = report.candidates[0]
    # 신선+많이쓰임+낮은redundancy → σ 낮음 → KEEP (caller의 0.99가 반영됐다면 높았을 것)
    assert cand.score is not None and cand.score < 0.3
    assert cand.verdict == "KEEP"
