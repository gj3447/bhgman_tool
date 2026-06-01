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
