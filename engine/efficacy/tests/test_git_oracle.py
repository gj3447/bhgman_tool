"""git_oracle 순수부 — git 출력 파싱 + temporal split + 군단장 라벨."""

from __future__ import annotations

from engine.efficacy.git_oracle import (
    ADD,
    DELETE,
    RENAME,
    feature_test_commits,
    parse_diff_status,
    parse_name_status,
    parse_ref_comment_patch,
    positive_paths,
    split_by_cutoff,
)

# `git log --name-status --format=__C__%H\t%cd` 형태 fixture.
_LOG = "\n".join(
    [
        "__C__abc123\t2026-05-30",
        "A\tengine/new_feature.py",
        "D\tengine/old_dead.py",
        "R100\tengine/moved_from.py\tengine/moved_to.py",
        "",
        "__C__def456\t2026-05-20",
        "M\tengine/edited.py",
        "A\tengine/feat.py",
        "A\tengine/tests/test_feat.py",
    ]
)


def test_parse_add_delete_rename():
    events = parse_name_status(_LOG)
    kinds = {(e.kind, e.path) for e in events}
    assert (ADD, "engine/new_feature.py") in kinds
    assert (DELETE, "engine/old_dead.py") in kinds
    rename = next(e for e in events if e.kind == RENAME)
    assert rename.path == "engine/moved_to.py"
    assert rename.old_path == "engine/moved_from.py"


def test_parse_attaches_commit_and_date():
    events = parse_name_status(_LOG)
    abc = [e for e in events if e.commit == "abc123"]
    assert all(e.date == "2026-05-30" for e in abc)
    assert len(abc) == 3


def test_rename_keeps_old_path_as_moved():
    # R100 = a genuine move: source IS stale (old_path set)
    events = parse_diff_status("R100\told/a.py\tnew/a.py")
    assert len(events) == 1
    assert events[0].kind == RENAME
    assert events[0].path == "new/a.py" and events[0].old_path == "old/a.py"


def test_copy_is_add_not_move():
    """W2-D: a copy (C…) leaves the source in place — it must NOT be labeled a move
    (old_path would falsely flag the source as stale/moved-away)."""
    events = parse_diff_status("C075\tx.py\ty.py")
    assert len(events) == 1
    assert events[0].kind == ADD
    assert events[0].path == "y.py"
    assert events[0].old_path is None  # source x.py is NOT moved


def test_unknown_status_skipped():
    events = parse_name_status("__C__x\t2026-01-01\n??\tjunk\nA\tok.py")
    assert [e.path for e in events] == ["ok.py"]


def test_no_events_before_first_header():
    assert parse_name_status("A\torphan.py") == []


def test_split_by_cutoff_iso_string_compare():
    events = parse_name_status(_LOG)
    before, after = split_by_cutoff(events, "2026-05-25")
    assert all(e.date < "2026-05-25" for e in before)
    assert all(e.date >= "2026-05-25" for e in after)
    assert len(before) + len(after) == len(events)
    # def456(05-20) → before, abc123(05-30) → after
    assert {e.commit for e in before} == {"def456"}
    assert {e.commit for e in after} == {"abc123"}


def test_positive_paths_per_commander():
    events = parse_name_status(_LOG)
    # occam = DELETE + RENAME
    assert positive_paths(events, "occam") == {"engine/old_dead.py", "engine/moved_to.py"}
    # eureka = ADD
    assert "engine/new_feature.py" in positive_paths(events, "eureka")
    # 미정의 군단장 → 빈셋
    assert positive_paths(events, "unknown") == set()


def test_feature_test_commits():
    fts = feature_test_commits(parse_name_status(_LOG))
    # def456이 feat.py(impl) + test_feat.py(test) 동시 → 후보. abc123은 test 없음.
    assert len(fts) == 1
    ft = fts[0]
    assert ft.commit == "def456"
    assert "engine/feat.py" in ft.impl_paths
    assert "engine/tests/test_feat.py" in ft.test_paths
    assert "engine/tests/test_feat.py" not in ft.impl_paths  # test가 impl로 안 샘


_PATCH = "\n".join(
    [
        "__C__sha789\t2026-05-29",
        "diff --git a/engine/m.py b/engine/m.py",
        "--- a/engine/m.py",
        "+++ b/engine/m.py",
        "+    # KG: new-binding-node",
        "+    x = 1",
        "-    # KG: removed-binding",
    ]
)


def test_parse_ref_comment_patch_add_and_remove():
    events = parse_ref_comment_patch(_PATCH)
    kinds = [(e.kind, e.path) for e in events]
    assert (ADD, "engine/m.py") in kinds  # 바인딩 추가
    assert (DELETE, "engine/m.py") in kinds  # 바인딩 삭제
    # `+    x = 1`은 # KG: 없으니 무시
    assert len(events) == 2
    assert all(e.commit == "sha789" for e in events)


def test_ref_comment_ignores_header_plus_lines():
    # '+++ b/...' 헤더는 # KG: 없으니 자연히 제외 — path만 세팅
    events = parse_ref_comment_patch("__C__s\t2026-01-01\n+++ b/a.py\n+ code # KG: z")
    assert len(events) == 1
    assert events[0].path == "a.py" and events[0].kind == ADD
