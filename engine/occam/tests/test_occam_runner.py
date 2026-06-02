"""오캄 end-to-end runner TDD — fetch → occam_pass → apply. dry-run 기본.

# KG: occam-pass-kg-wide-2026-05-27, occam-kam-canonical-2026-05-26
"""

from __future__ import annotations

from engine.occam.occam_runner import run_occam, scan_disk_paths


class _Runner:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def __call__(self, cypher, params):
        self.calls.append((cypher, params))
        return self.rows


_DUP_ROWS = [
    {"name": "old", "source_path": "bhgman_tool/x.py", "sha256": "o", "line_count": 10},
    {"name": "new", "source_path": "bhgman_tool/x.py", "sha256": "n", "line_count": 99},
]
_CLEAN_ROWS = [
    {"name": "solo", "source_path": "bhgman_tool/solo.py", "sha256": "s", "line_count": 50},
]


def test_run_occam_dry_run_detects_but_does_not_write():
    read = _Runner(_DUP_ROWS)
    write = _Runner()
    res = run_occam(read, write_cypher=write)  # apply defaults False
    assert res.report.superseded_count == 1
    assert res.apply_result.dry_run is True
    assert write.calls == []  # covenant


def test_run_occam_apply_writes_supersession():
    read = _Runner(_DUP_ROWS)
    write = _Runner()
    res = run_occam(read, write_cypher=write, apply=True)
    assert res.apply_result.applied_count == 1
    assert len(write.calls) == 1


# name은 schema상 required 아님(sourcePath/sha256/lineCount만 필수). name=None 노드도
# supersede 식별·표시가 깨지면 안 된다 (regression: 옛 name-키 → None join CLI crash +
# {name:null} MATCH 무발견 silent persistence miss).
# # KG: challenge-occam-supersede-name-key-not-required-nullable-2026-06-02
_NONAME_DUP_ROWS = [
    {"name": None, "source_path": "/abs/bhgman_tool/x.py", "sha256": "z", "line_count": 10},
    {"name": None, "source_path": "bhgman_tool/x.py", "sha256": "z", "line_count": 10},
]


def test_run_occam_apply_nameless_nodes_no_crash_path_fallback():
    read = _Runner(_NONAME_DUP_ROWS)
    write = _Runner()
    res = run_occam(read, write_cypher=write, apply=True)
    assert res.apply_result.applied_count == 1
    # 표시 식별자가 None이 아니라 sourcePath로 폴백 (CLI join crash 차단)
    assert all(s is not None for s in res.apply_result.superseded)
    assert res.apply_result.superseded[0].endswith("x.py")
    # 매칭 키 = 복합 (sourcePath, sha256) — write params에 둘 다 존재
    _cy, params = write.calls[0]
    assert params["stale_path"] and params["stale_sha"]
    assert params["current_path"] and params["current_sha"]


def test_run_occam_clean_kg_no_candidates_no_write_even_with_apply():
    read = _Runner(_CLEAN_ROWS)
    write = _Runner()
    res = run_occam(read, write_cypher=write, apply=True)
    assert res.report.superseded_count == 0
    assert write.calls == []  # twin 없으면 손 안 댐 (GUARD)


def test_run_occam_scope_passed_to_fetch():
    read = _Runner(_CLEAN_ROWS)
    run_occam(read, scope="engine/occam")
    assert read.calls[0][1] == {"scope": "engine/occam"}


# ─── disk-aware (mode-2/3) ───

_MOVED_ROWS = [
    {
        "name": "old-ged",
        "source_path": "bhgman_tool/engine/longinus_l8_induction/ged.py",
        "sha256": "samesha",
        "line_count": 157,
    },
    {
        "name": "new-ged",
        "source_path": "bhgman_tool/engine/longinus_drift/ged.py",
        "sha256": "samesha",
        "line_count": 157,
    },
]


def test_scan_disk_paths_normalizes_and_skips_caches(tmp_path):
    (tmp_path / "bhgman_tool" / "engine").mkdir(parents=True)
    (tmp_path / "bhgman_tool" / "engine" / "live.py").write_text("x=1\n")
    (tmp_path / "bhgman_tool" / "engine" / "__pycache__").mkdir()
    (tmp_path / "bhgman_tool" / "engine" / "__pycache__" / "live.cpython.pyc").write_text("z")
    paths = scan_disk_paths(tmp_path)
    assert "engine/live.py" in paths
    assert not any("__pycache__" in p for p in paths)


def test_scan_disk_paths_follows_symlinked_dirs(tmp_path):
    # bhgman_tool/skills/* = SYMPOSIUM/SKILLS 심링크 (정전). followlinks 없으면 false-orphan.
    real = tmp_path / "real_skills" / "harness"
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("# harness\n")
    repo = tmp_path / "bhgman_tool"
    (repo).mkdir()
    (repo / "skills").symlink_to(tmp_path / "real_skills")
    paths = scan_disk_paths(repo)
    assert "skills/harness/SKILL.md" in paths  # 심링크 통해 발견돼야


def test_scan_disk_paths_symlink_and_real_dir_coexist(tmp_path):
    # 정전 패턴: bhgman_tool/symposium-skills/* (실디렉터리) + bhgman_tool/skills/* → symposium-skills/* (심링크).
    # 양쪽 모두 ROOT 하위 → realpath cycle guard가 한 쪽을 통째 skip하면 KG가 그 symbolic
    # path를 저장한 경우 false-orphan 폭증 (self-dogfood 2026-05-28: 83 file false-orphan).
    repo = tmp_path / "bhgman_tool"
    real = repo / "symposium-skills" / "harness"
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("# harness\n")
    (repo / "skills").symlink_to(repo / "symposium-skills")
    paths = scan_disk_paths(repo)
    assert "symposium-skills/harness/SKILL.md" in paths
    assert "skills/harness/SKILL.md" in paths  # symbolic alias도 walk돼야 (alias 0건 회귀)


def test_scan_disk_paths_depth_guard_blocks_symlink_cycle(tmp_path):
    # 자기 자신을 가리키는 심링크 = 무한 cycle. depth 가드(>50)가 폭주 차단.
    repo = tmp_path / "bhgman_tool"
    repo.mkdir()
    (repo / "live.py").write_text("x=1\n")
    (repo / "loop").symlink_to(repo)  # repo/loop/loop/loop/... 무한
    paths = scan_disk_paths(repo)
    assert "live.py" in paths  # 정상 파일은 잡힘
    # 폭주 없이 return됐다는 사실 자체가 가드 동작 증거 (timeout 없이 통과)


def test_run_occam_disk_aware_supersedes_moved_node(monkeypatch):
    from engine.occam import occam_runner

    # 옛 경로는 디스크에 없고 새 경로만 살아있다고 위장.
    monkeypatch.setattr(
        occam_runner, "scan_disk_paths", lambda _root: frozenset({"engine/longinus_drift/ged.py"})
    )
    read = _Runner(_MOVED_ROWS)
    write = _Runner()
    res = run_occam(read, write_cypher=write, apply=True, repo_root="/fake")
    assert res.report.superseded_count == 1
    cand = res.report.candidates[0]
    assert cand.stale.name == "old-ged"
    assert cand.current.name == "new-ged"
    assert len(write.calls) == 1


def test_run_occam_no_repo_root_is_disk_unaware(monkeypatch):
    read = _Runner(_MOVED_ROWS)
    res = run_occam(read)  # repo_root=None → mode-1만, 다른 경로라 후보 0
    assert res.report.superseded_count == 0
