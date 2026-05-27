"""오캄 코어 TDD — 2026-05-27 손으로 한 pass의 케이스를 spec으로 고정.

# KG: occam-pass-bhgman_tool-2026-05-27, lesson-occam-must-query-kg-node-dedup-...-2026-05-27
"""

from __future__ import annotations

from occam import normalize_path, occam_pass
from occam_models import Confidence, NodeRecord


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
