"""longinus injected-mutation ON/OFF 실험 테스트 — 손상 분류 정확도."""

from __future__ import annotations

from engine.efficacy.longinus_ab_experiment import (
    TrueKind,
    Verdict,
    build_sandbox,
    longinus_detect,
    naive_detect,
    run_experiment,
    score_arm,
)


def test_sandbox_ledger_counts():
    sb = build_sandbox(n_clean=5, n_edit=3, n_move=2, n_delete=2, n_move_edit=1, seed=1)
    assert len(sb.nodes) == 13
    kinds = list(sb.ledger.values())
    assert kinds.count(TrueKind.CLEAN) == 5
    assert kinds.count(TrueKind.MOVE) == 2


def test_longinus_classifies_move_naive_misses():
    # 핵심: longinus는 MOVE를 MOVED로, naive는 MISSING으로 (오분류)
    sb = build_sandbox(n_clean=0, n_edit=0, n_move=3, n_delete=0, n_move_edit=0, seed=7)
    lon = longinus_detect(sb)
    nai = naive_detect(sb)
    assert all(v is Verdict.MOVED for v in lon.values())  # longinus 정답
    assert all(v is Verdict.MISSING for v in nai.values())  # naive 오분류


def test_both_catch_edit():
    sb = build_sandbox(n_clean=0, n_edit=4, n_move=0, n_delete=0, n_move_edit=0, seed=3)
    assert all(v is Verdict.DRIFT for v in longinus_detect(sb).values())
    assert all(v is Verdict.DRIFT for v in naive_detect(sb).values())


def test_longinus_orphan_on_delete():
    sb = build_sandbox(n_clean=0, n_edit=0, n_move=0, n_delete=3, n_move_edit=0, seed=5)
    assert all(v is Verdict.ORPHAN for v in longinus_detect(sb).values())


def test_clean_no_false_positive():
    sb = build_sandbox(n_clean=10, n_edit=0, n_move=0, n_delete=0, n_move_edit=0, seed=2)
    lon = score_arm(longinus_detect(sb), sb.ledger)
    nai = score_arm(naive_detect(sb), sb.ledger)
    assert lon.false_positive_rate == 0.0
    assert nai.false_positive_rate == 0.0


def test_move_edit_hard_for_both():
    # 이동+내용변경: sha 불일치라 longinus도 ORPHAN 오분류 (정직 — magic 아님)
    sb = build_sandbox(n_clean=0, n_edit=0, n_move=0, n_delete=0, n_move_edit=3, seed=9)
    lon = longinus_detect(sb)
    assert all(v is Verdict.ORPHAN for v in lon.values())  # 정답은 MOVED인데 놓침


def test_false_kill_naive_higher_on_alive_moves():
    sb = build_sandbox(n_clean=0, n_edit=0, n_move=5, n_delete=0, n_move_edit=0, seed=11)
    lon = score_arm(longinus_detect(sb), sb.ledger)
    nai = score_arm(naive_detect(sb), sb.ledger)
    # MOVE는 내용 살아있음 → naive(MISSING=archive대상)는 false-kill, longinus(MOVED)는 안전
    assert nai.false_kill_rate == 1.0
    assert lon.false_kill_rate == 0.0


def test_run_experiment_longinus_beats_naive_on_classification():
    res = run_experiment(n_seeds=10)
    assert res.on_classification > res.off_classification  # longinus 우위
    assert 0.0 <= res.perm_p_classification <= 1.0


def test_run_experiment_detection_recall_similar():
    # 탐지 recall(non-CLEAN 잡기)은 둘 다 높음 — lift는 분류에 있지 탐지에 있지 않음
    res = run_experiment(n_seeds=10)
    assert res.on_detection_recall == res.off_detection_recall  # 둘 다 모든 손상 flag


def test_serialize_task_contains_rules_and_nodes():
    from engine.efficacy.longinus_ab_experiment import serialize_task

    sb = build_sandbox(n_clean=2, n_edit=1, n_move=1, n_delete=0, n_move_edit=0, seed=1)
    txt = serialize_task(sb)
    assert "MOVED" in txt and "ORPHAN" in txt and "DRIFT" in txt
    assert "RECORDED nodes:" in txt and "CURRENT disk" in txt
    assert all(n.name in txt for n in sb.nodes)  # 모든 노드 포함


def test_assemble_git_sandbox_maps_git_status_to_truekind():
    """git -M net status → TrueKind (ground truth는 git, longinus 아님)."""
    from engine.efficacy.git_oracle import ADD, DELETE, MODIFY, RENAME, GitEvent
    from engine.efficacy.longinus_ab_experiment import assemble_git_sandbox

    recorded = {  # base(pre-T) {path: sha}
        "engine/clean.py": "s0",
        "engine/edited.py": "s1",
        "engine/moved.py": "s2",  # 순수 이동 (sha 유지)
        "engine/moved_edited.py": "s3",  # 이동+변경
        "engine/gone.py": "s4",
        "engine/skip.txt": "sx",  # .py 아님 → 제외
    }
    disk = {  # HEAD {path: sha}
        "engine/clean.py": "s0",
        "engine/edited.py": "s1NEW",
        "engine/sub/moved.py": "s2",  # 같은 sha, 새 경로
        "engine/sub/moved_edited.py": "s3NEW",  # 새 경로 + 새 sha
    }
    net = [
        GitEvent("", "", MODIFY, "engine/edited.py"),
        GitEvent("", "", RENAME, "engine/sub/moved.py", old_path="engine/moved.py"),
        GitEvent("", "", RENAME, "engine/sub/moved_edited.py", old_path="engine/moved_edited.py"),
        GitEvent("", "", DELETE, "engine/gone.py"),
        GitEvent("", "", ADD, "engine/sub/moved.py"),
    ]
    sb = assemble_git_sandbox(recorded, disk, net, scope_prefix="engine/")
    assert sb.ledger["engine/clean.py"] is TrueKind.CLEAN
    assert sb.ledger["engine/edited.py"] is TrueKind.EDIT
    assert sb.ledger["engine/moved.py"] is TrueKind.MOVE  # disk new-path sha 동일
    assert sb.ledger["engine/moved_edited.py"] is TrueKind.MOVE_EDIT  # sha 다름
    assert sb.ledger["engine/gone.py"] is TrueKind.DELETE
    assert "engine/skip.txt" not in sb.ledger  # .py 아닌 것 제외


def test_assemble_git_sandbox_longinus_detects_real_move():
    """조립된 실 sandbox에서 longinus가 MOVE를 MOVED로(naive는 MISSING) — lift 재현."""
    from engine.efficacy.git_oracle import RENAME, GitEvent
    from engine.efficacy.longinus_ab_experiment import (
        Verdict,
        assemble_git_sandbox,
        longinus_detect,
        naive_detect,
    )

    recorded = {"engine/a.py": "sha_a"}
    disk = {"engine/b.py": "sha_a"}  # 같은 내용이 새 경로에
    net = [GitEvent("", "", RENAME, "engine/b.py", old_path="engine/a.py")]
    sb = assemble_git_sandbox(recorded, disk, net, "engine/")
    assert longinus_detect(sb)["engine/a.py"] is Verdict.MOVED  # twin 매칭
    assert naive_detect(sb)["engine/a.py"] is Verdict.MISSING  # 경로만 봄
