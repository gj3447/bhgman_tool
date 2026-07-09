"""오캄 end-to-end runner TDD — fetch → occam_pass → apply. dry-run 기본.

# KG: occam-pass-kg-wide-2026-05-27, occam-kam-canonical-2026-05-26
"""

from __future__ import annotations

from engine.occam.kg_adapter import fetch_cypher, parse_node_records
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


# fetch가 inbound_edges/recency를 실어오면 _pick_current가 그것으로 current를 고른다 (end-to-end).
_INBOUND_ROWS = [
    {
        "name": "big_lonely",
        "source_path": "bhgman_tool/x.py",
        "sha256": "a",
        "line_count": 999,
        "inbound_edges": 0,
    },
    {
        "name": "small_hub",
        "source_path": "bhgman_tool/x.py",
        "sha256": "b",
        "line_count": 10,
        "inbound_edges": 20,
    },
]


def test_run_occam_uses_inbound_edges_for_current_selection():
    res = run_occam(_Runner(_INBOUND_ROWS))
    assert res.report.superseded_count == 1
    cand = res.report.candidates[0]
    assert cand.current.name == "small_hub"  # 참조 많은 쪽이 현재 (line_count 휴리스틱 보강)
    assert cand.stale.name == "big_lonely"


# ─── σ seam: run_occam이 score_meta를 빌드해 occam_pass에 주입 (이전엔 dead) ───


def test_run_occam_attaches_sigma_and_verdict():
    # σ scoring이 production runner 경로에서 살아있어야 한다 (이전엔 score_meta 미주입 → dead).
    res = run_occam(_Runner(_DUP_ROWS))
    cand = res.report.candidates[0]
    assert cand.score is not None
    assert 0.0 <= cand.score <= 1.0
    assert cand.verdict in {"SUPERSEDE", "VERIFY", "KEEP", "PROTECTED", "FLAG_ONLY"}


def test_run_occam_no_usage_log_does_not_saturate_to_supersede():
    # 사용기록 부재(invocation None → deadness 0)라 부분중복 후보가 σ=1.0 SUPERSEDE로 잘못
    # 떠선 안 된다 (안전 회귀 방지). 10L vs 99L, 동일경로, 타임스탬프 없음 → redundancy 낮음.
    res = run_occam(_Runner(_DUP_ROWS))
    cand = res.report.candidates[0]
    assert cand.score < 0.7  # θ_supersede 밑 — 자동 SUPERSEDE 아님
    assert cand.verdict != "SUPERSEDE"


def test_run_occam_exact_duplicate_still_supersedes():
    # 동일 sha(완전중복) = redundancy 1.0 → deadness 부재여도 candidacy 포화 → σ 높음 → SUPERSEDE.
    rows = [
        {"name": "a", "source_path": "/abs/bhgman_tool/x.py", "sha256": "same", "line_count": 50},
        {"name": "b", "source_path": "bhgman_tool/x.py", "sha256": "same", "line_count": 50},
    ]
    res = run_occam(_Runner(rows))
    cand = res.report.candidates[0]
    assert cand.score is not None and cand.score >= 0.7
    assert cand.verdict == "SUPERSEDE"


def test_run_occam_apply_defers_uncertain_partial_dup():
    # σ-gate: 부분중복(σ=KEEP, MEDIUM, 비동일)은 apply=True여도 auto-write 안 함 → deferred.
    # 불확실한 건 escalation에 위임 (잘못 supersede로 KG 의미계층 왜곡 방지).
    read = _Runner(_DUP_ROWS)
    write = _Runner([{"superseded": "old", "current": "new"}])
    res = run_occam(read, write_cypher=write, apply=True)
    assert res.apply_result.applied_count == 0
    assert write.calls == []  # 불확실 → write 안 함
    assert "old" in res.apply_result.deferred


_EXACT_DUP_ROWS = [
    {"name": "a_abs", "source_path": "/abs/bhgman_tool/x.py", "sha256": "same", "line_count": 50},
    {"name": "b_rel", "source_path": "bhgman_tool/x.py", "sha256": "same", "line_count": 50},
]


def test_run_occam_apply_writes_confident_supersession():
    # 확신 케이스(완전중복 σ=SUPERSEDE, byte-동일)는 apply=True에서 실제 write.
    read = _Runner(_EXACT_DUP_ROWS)
    write = _Runner([{"superseded": "a_abs", "current": "b_rel"}])  # cypher matched a row
    res = run_occam(read, write_cypher=write, apply=True)
    assert res.apply_result.applied_count == 1
    assert len(write.calls) == 1
    assert res.apply_result.deferred == ()


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
    write = _Runner([{"superseded": "x", "current": "y"}])  # cypher matches a row
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


# ─── invocation_count (deadness) wiring: oracle_backfill → fetch → scoring ───
# lesson-occam-needs-invocation-log-2026-05-28: usage-based deadness. oracle_backfill writes
# s.invocation_count to the KG, but the runner never read it (cypher/parse/score_meta all
# dropped it) → the load-bearing signal was permanently dead.


def test_fetch_cypher_selects_invocation_count():
    cypher, _ = fetch_cypher(None)
    assert "invocation_count" in cypher  # the backfilled usage signal must be fetched


def test_parse_node_records_keeps_invocation_count():
    rows = [
        {"name": "n", "source_path": "p.py", "sha256": "s", "line_count": 5, "invocation_count": 0},
        {"name": "m", "source_path": "q.py", "sha256": "t", "line_count": 5},  # absent → None
    ]
    recs = parse_node_records(rows)
    assert recs[0].invocation_count == 0  # measured-dead survives into the NodeRecord
    assert recs[1].invocation_count is None  # absent stays None (no-false-dead preserved)


_DUP_ROWS_MEASURED_DEAD = [
    # same path + different sha as _DUP_ROWS, but the stale "old" is measured-DEAD (0 calls).
    {
        "name": "old",
        "source_path": "bhgman_tool/x.py",
        "sha256": "o",
        "line_count": 10,
        "invocation_count": 0,
    },
    {
        "name": "new",
        "source_path": "bhgman_tool/x.py",
        "sha256": "n",
        "line_count": 99,
        "invocation_count": 20,
    },
]


def test_summarize_occam_result_exposes_candidate_sigma_verdict():
    # occam.py attaches a continuous σ + per-candidate verdict to every candidate, but
    # summarize_occam_result (the MCP/legion surface) dropped it — the safety value was invisible.
    from engine.occam_engine import summarize_occam_result

    res = run_occam(_Runner(_DUP_ROWS))
    summary = summarize_occam_result(res)
    assert "candidates" in summary
    c0 = summary["candidates"][0]
    assert c0["sigma"] is not None and 0.0 <= c0["sigma"] <= 1.0
    assert c0["verdict"] in {"SUPERSEDE", "VERIFY", "KEEP", "PROTECTED", "FLAG_ONLY"}
    assert c0["stale"] and c0["current"]


def test_run_occam_reads_backfilled_invocation_count():
    # The backfilled deadness (stale measured-dead) must RAISE σ vs the no-usage baseline —
    # currently identical because invocation_count is dropped before scoring = RED.
    measured = run_occam(_Runner(_DUP_ROWS_MEASURED_DEAD)).report.candidates[0]
    baseline = run_occam(_Runner(_DUP_ROWS)).report.candidates[0]
    assert measured.score is not None and baseline.score is not None
    assert measured.score > baseline.score  # the live, load-bearing usage signal
    # crosses θ_supersede the no-usage baseline never reaches (the verdict flip the audit
    # verified: σ 0.3 VERIFY → 1.0 SUPERSEDE), while the baseline keeps the no-false-dead floor.
    assert measured.verdict == "SUPERSEDE"
    assert baseline.verdict != "SUPERSEDE"


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


def test_run_occam_computes_disk_truth_from_repo_root(tmp_path):
    """W3-B: repo_root now builds disk_truth → the disk-sha node wins (HIGH), not the
    bigger-line-count heuristic. The HIGH path was dead (disk_truth never built)."""
    import hashlib

    from engine.occam.occam_models import Confidence

    f = tmp_path / "engine" / "x.py"
    f.parent.mkdir(parents=True)
    f.write_text("real disk content\n")
    disk_sha = hashlib.sha256(f.read_bytes()).hexdigest()
    rows = [
        {"name": "x_disk", "source_path": "engine/x.py", "sha256": disk_sha, "line_count": 5},
        {"name": "x_old", "source_path": "engine/x.py", "sha256": "OLDSHA", "line_count": 999},
    ]
    res = run_occam(_Runner(rows), repo_root=tmp_path)
    cand = res.report.candidates[0]
    assert cand.current.sha256 == disk_sha  # disk truth beats the line-count heuristic
    assert cand.stale.sha256 == "OLDSHA"
    assert cand.confidence is Confidence.HIGH


# ─── seam-integrity 2026-07-10 적대검증 봉합: 워크트리 실존-면제 + disk-truth 결정론 ───


def test_true_orphan_still_detected_from_worktree_root(tmp_path):
    """양성 대조(적대검증: J-A1 은 false-orphan=0 만 봐서 orphan 평가 전체를 죽여도
    green) — 디스크에 없는 정본-lineage 노드는 워크트리명 root 에서도 여전히 orphan."""
    wt_root = tmp_path / "bhgman_tool-wt-probe"
    (wt_root / "engine").mkdir(parents=True)
    (wt_root / "engine" / "alive.py").write_text("x=1\n")
    rows = [
        {
            "name": "alive",
            "source_path": "bhgman_tool/engine/alive.py",
            "sha256": "s1",
            "line_count": 1,
        },
        {
            "name": "ghost",
            "source_path": "bhgman_tool/engine/ghost.py",
            "sha256": "s2",
            "line_count": 9,
        },
    ]
    res = run_occam(_Runner(rows), repo_root=wt_root)
    orphan_names = {o.name for o in res.report.orphans}
    assert "ghost" in orphan_names, "실제 orphan 탐지는 살아 있어야 (평가 전멸=위조 green)"
    assert "alive" not in orphan_names


def test_worktree_lineage_exempt_from_move_and_orphan(tmp_path):
    """병렬-세션 보호(적대검증 high): -wt- lineage 노드는 이 체크아웃 디스크로 실존을
    판정하지 않는다 — mode-2 sha-move 의 orphan 측도, mode-3 disk-orphan 도 금지.
    (미머지 rename/신규 파일이 타 체크아웃 janitor 에 아카이브/노이즈 되는 사고 차단)"""
    root = tmp_path / "bhgman_tool"
    (root / "engine").mkdir(parents=True)
    (root / "engine" / "kept.py").write_text("same content\n")
    import hashlib as _h

    sha = _h.sha256((root / "engine" / "kept.py").read_bytes()).hexdigest()
    rows = [
        # 정본 lineage: 디스크 실재 (live twin)
        {
            "name": "kept",
            "source_path": "bhgman_tool/engine/kept.py",
            "sha256": sha,
            "line_count": 1,
        },
        # 병렬 워크트리의 미머지 rename 기록: 같은 sha, 이 체크아웃 디스크엔 없음
        {
            "name": "renamed",
            "source_path": "/x/bhgman_tool-wt-other/engine/renamed.py",
            "sha256": sha,
            "line_count": 1,
        },
        # 병렬 워크트리 전용 신규 파일 기록: 이 체크아웃 디스크엔 없음
        {
            "name": "newfile",
            "source_path": "/x/bhgman_tool-wt-other/engine/newfile.py",
            "sha256": "zz",
            "line_count": 5,
        },
    ]
    res = run_occam(_Runner(rows), repo_root=root)
    stale_names = {c.stale.name for c in res.report.candidates}
    orphan_names = {o.name for o in res.report.orphans}
    assert "renamed" not in stale_names, "-wt- 노드가 mode-2 로 아카이브 후보가 되면 병렬 작업 파괴"
    assert "renamed" not in orphan_names and "newfile" not in orphan_names, (
        "-wt- 노드는 mode-3 orphan 노이즈로도 흐르면 안 됨"
    )


def test_disk_truth_is_order_deterministic_and_root_anchored(tmp_path):
    """disk-truth 결정론(적대검증 high): 같은 정규화 키의 노드 순서가 바뀌어도, 그리고
    형제 체크아웃에 divergent 파일이 실재해도 — disk truth 는 *실행 root* 파일의 sha."""
    import hashlib as _h

    main_root = tmp_path / "bhgman_tool"
    sibling = tmp_path / "bhgman_tool-wt-sib"
    for r, body in ((main_root, "main body\n"), (sibling, "sibling WIP body\n")):
        (r / "engine").mkdir(parents=True)
        (r / "engine" / "f.py").write_text(body)
    main_sha = _h.sha256((main_root / "engine" / "f.py").read_bytes()).hexdigest()

    from engine.occam.occam_runner import _compute_disk_truth
    from engine.occam.occam_models import NodeRecord

    n_main = NodeRecord("m", str(main_root / "engine" / "f.py"), "a" * 64, 1)
    n_sib = NodeRecord("s", str(sibling / "engine" / "f.py"), "b" * 64, 1)
    for order in ([n_main, n_sib], [n_sib, n_main]):
        dt = _compute_disk_truth(main_root, order)
        assert dt.get("engine/f.py") == main_sha, (
            f"order={[''.join(n.name) for n in order]}: 실행 root 의 sha 여야 "
            "(형제 워크트리 WIP 탈출/last-wins 비결정 금지)"
        )
