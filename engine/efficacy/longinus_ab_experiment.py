"""#1 longinus injected-mutation ON/OFF — 첫 비순환 반사실 효능 실험.

ap-effmeas-noncircular-2026-06-01 의 p1. 샌드박스에 *알려진* drift 손상을 주입(=ground
truth, 우리가 만들었으니 비순환) → longinus 탐지(ON) vs 순진한 same-path sha-compare(OFF).

핵심 falsifier 질문 (bitter lesson): longinus 엔진이 5줄 sha-비교를 *이기나*?
  · 둘 다 잡는 것: content edit(같은 경로 sha 변경) — 순진한 비교로 충분.
  · longinus만 잡는 것: **file move**(내용 동일·경로 이동) = sha-twin 매칭으로 MOVED 분류.
    순진한 비교는 MISSING으로 오분류 → *false-kill 위험*(살아있는 내용 archive). 이게 lift.
  · 둘 다 놓치는 것: move+edit(이동+내용변경, sha 불일치) — longinus도 ORPHAN 오분류(정직).

oracle = 주입 ledger(각 노드 true class). 독립: longinus 판정과 무관하게 우리가 주입.
metric = detection recall + classification accuracy + false-positive(clean 오탐). paired.

순수 함수만 (random sandbox 구성은 seed 주입 결정론). KG/IO 없음.

# KG: efficacy-longinus-2026-06-01, ap-effmeas-noncircular-2026-06-01 (p1),
#     consensus-effmeas-2026-06-01, project_bhgman_ab_falsifier_2026_05_30
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from engine.efficacy.git_oracle import GitEvent


class TrueKind(str, Enum):
    CLEAN = "CLEAN"  # 손상 없음 (disk sha == recorded)
    EDIT = "EDIT"  # 같은 경로, 내용 변경 → DRIFT 가 정답
    MOVE = "MOVE"  # 경로 이동, 내용 동일 → MOVED 가 정답
    DELETE = "DELETE"  # 삭제, twin 없음 → ORPHAN 이 정답
    MOVE_EDIT = "MOVE_EDIT"  # 이동+내용변경 → MOVED 가 정답(내용 살아있음), 둘 다 어려움


class Verdict(str, Enum):
    CLEAN = "CLEAN"
    DRIFT = "DRIFT"
    MOVED = "MOVED"
    ORPHAN = "ORPHAN"
    MISSING = "MISSING"  # 순진한 baseline 전용 (move/delete 구분 못 함)


# true kind → 정답 verdict (정확 분류 기준)
_CORRECT: dict[TrueKind, Verdict] = {
    TrueKind.CLEAN: Verdict.CLEAN,
    TrueKind.EDIT: Verdict.DRIFT,
    TrueKind.MOVE: Verdict.MOVED,
    TrueKind.DELETE: Verdict.ORPHAN,
    TrueKind.MOVE_EDIT: Verdict.MOVED,  # 내용이 이동지(변형됐어도) → archive 하면 false-kill
}


@dataclass(frozen=True)
class Node:
    name: str
    path: str
    recorded_sha: str  # KG 기록 baseline


@dataclass(frozen=True)
class Sandbox:
    nodes: tuple[Node, ...]  # KG 기록 상태 (손상 전)
    disk: dict[str, str]  # 현재 디스크 {path: sha} (손상 후)
    ledger: dict[str, TrueKind]  # node.name → 주입한 true kind (oracle)


def build_sandbox(n_clean: int, n_edit: int, n_move: int, n_delete: int, n_move_edit: int, seed: int) -> Sandbox:
    """결정론 샌드박스(seed). recorded 노드 + 손상된 disk 상태 + ledger."""
    rng = random.Random(seed)
    nodes: list[Node] = []
    disk: dict[str, str] = {}
    ledger: dict[str, TrueKind] = {}
    plan = (
        [TrueKind.CLEAN] * n_clean + [TrueKind.EDIT] * n_edit + [TrueKind.MOVE] * n_move
        + [TrueKind.DELETE] * n_delete + [TrueKind.MOVE_EDIT] * n_move_edit
    )
    rng.shuffle(plan)
    for i, kind in enumerate(plan):
        path = f"engine/m{i}.py"
        sha = f"sha{i:04d}"
        nodes.append(Node(name=f"n{i}", path=path, recorded_sha=sha))
        ledger[f"n{i}"] = kind
        if kind is TrueKind.CLEAN:
            disk[path] = sha  # 그대로
        elif kind is TrueKind.EDIT:
            disk[path] = f"sha{i:04d}X"  # 같은 경로, 새 sha
        elif kind is TrueKind.MOVE:
            disk[f"engine/moved/m{i}.py"] = sha  # 새 경로, 같은 sha (P 경로는 사라짐)
        elif kind is TrueKind.DELETE:
            pass  # 디스크에서 사라짐, twin 없음
        elif kind is TrueKind.MOVE_EDIT:
            disk[f"engine/moved/m{i}.py"] = f"sha{i:04d}Y"  # 새 경로 + 새 sha
    return Sandbox(nodes=tuple(nodes), disk=disk, ledger=ledger)


def assemble_git_sandbox(
    recorded_blobs: dict[str, str],
    disk_blobs: dict[str, str],
    net_events: Sequence[GitEvent],
    scope_prefix: str = "",
) -> Sandbox:
    """실 git 데이터로 Sandbox 조립 (순수). 합성 build_sandbox의 real-KG 대체.

    recorded_blobs = base(pre-T) {path: sha}, disk_blobs = HEAD {path: sha},
    net_events = `git diff -M base HEAD`(git의 rename 탐지 = longinus와 독립 → 비순환 ledger).
    ledger true-kind는 *git이* 판정한 R/D/M (longinus sha-twin 아님)."""
    renamed_from = {e.old_path: e.path for e in net_events if e.kind == "RENAME" and e.old_path}
    deleted = {e.path for e in net_events if e.kind == "DELETE"}
    modified = {e.path for e in net_events if e.kind == "MODIFY"}
    disk = {p: s for p, s in disk_blobs.items() if p.endswith(".py")}
    nodes: list[Node] = []
    ledger: dict[str, TrueKind] = {}
    for path, sha in recorded_blobs.items():
        if not path.endswith(".py") or not path.startswith(scope_prefix):
            continue
        nodes.append(Node(name=path, path=path, recorded_sha=sha))
        ledger[path] = _git_true_kind(path, sha, renamed_from, deleted, modified, disk)
    return Sandbox(nodes=tuple(nodes), disk=disk, ledger=ledger)


def _git_true_kind(
    path: str,
    sha: str,
    renamed_from: dict[str, str],
    deleted: set[str],
    modified: set[str],
    disk: dict[str, str],
) -> TrueKind:
    """git net status → TrueKind. rename은 disk sha 동일성으로 MOVE vs MOVE_EDIT 구분."""
    if path in renamed_from:
        return TrueKind.MOVE if disk.get(renamed_from[path]) == sha else TrueKind.MOVE_EDIT
    if path in deleted:
        return TrueKind.DELETE
    if path in modified:
        return TrueKind.EDIT
    return TrueKind.CLEAN


def longinus_detect(sandbox: Sandbox) -> dict[str, Verdict]:
    """ON: longinus 엔진. drift(sha≠) + move(sha-twin at 타 경로) + orphan(twin 없음)."""
    disk = sandbox.disk
    sha_to_paths: dict[str, list[str]] = {}
    for p, s in disk.items():
        sha_to_paths.setdefault(s, []).append(p)
    out: dict[str, Verdict] = {}
    for n in sandbox.nodes:
        if n.path in disk:
            out[n.name] = Verdict.CLEAN if disk[n.path] == n.recorded_sha else Verdict.DRIFT
        elif n.recorded_sha in sha_to_paths:  # 경로 사라졌지만 같은 내용이 다른 곳에 살아있음
            out[n.name] = Verdict.MOVED
        else:  # 경로 없음 + 내용 twin 없음
            out[n.name] = Verdict.ORPHAN
    return out


def naive_detect(sandbox: Sandbox) -> dict[str, Verdict]:
    """OFF: 순진한 same-path sha-compare. move/delete 구분 못 함(MISSING)."""
    disk = sandbox.disk
    out: dict[str, Verdict] = {}
    for n in sandbox.nodes:
        if n.path in disk:
            out[n.name] = Verdict.CLEAN if disk[n.path] == n.recorded_sha else Verdict.DRIFT
        else:
            out[n.name] = Verdict.MISSING
    return out


@dataclass(frozen=True)
class ArmScore:
    detection_recall: float  # 손상 노드 중 non-CLEAN 으로 잡은 비율
    classification_accuracy: float  # 전체 노드 중 정답 verdict 일치 비율
    false_positive_rate: float  # clean 노드를 non-CLEAN 으로 오탐한 비율
    false_kill_rate: float  # MOVE/MOVE_EDIT(내용 살아있음)을 ORPHAN/MISSING으로 분류 = 위험


def score_arm(detected: dict[str, Verdict], ledger: dict[str, TrueKind]) -> ArmScore:
    total = len(ledger)
    corrupted = [k for k, v in ledger.items() if v is not TrueKind.CLEAN]
    cleans = [k for k, v in ledger.items() if v is TrueKind.CLEAN]
    alive_moves = [k for k, v in ledger.items() if v in (TrueKind.MOVE, TrueKind.MOVE_EDIT)]

    detected_corrupt = sum(1 for k in corrupted if detected[k] is not Verdict.CLEAN)
    correct = sum(1 for k, v in ledger.items() if detected[k] == _CORRECT[v])
    fp = sum(1 for k in cleans if detected[k] is not Verdict.CLEAN)
    # false-kill: 내용이 살아있는데(MOVE/MOVE_EDIT) ORPHAN/MISSING(=archive 대상)으로 본 것
    false_kill = sum(1 for k in alive_moves if detected[k] in (Verdict.ORPHAN, Verdict.MISSING))
    return ArmScore(
        detection_recall=detected_corrupt / len(corrupted) if corrupted else 0.0,
        classification_accuracy=correct / total if total else 0.0,
        false_positive_rate=fp / len(cleans) if cleans else 0.0,
        false_kill_rate=false_kill / len(alive_moves) if alive_moves else 0.0,
    )


def serialize_task(sandbox: Sandbox) -> str:
    """OFF-base-LLM arm용 task 텍스트. longinus와 *동일한* sha 데이터만 제공(budget-matched).

    LLM은 도구 없이 추론으로 각 노드를 CLEAN/DRIFT/MOVED/ORPHAN 분류해야 한다.
    move 판별 = recorded sha가 disk의 *다른 경로*에 살아있는지 sha 매칭 (longinus가 하는 일)."""
    recorded = "\n".join(f"  {n.name}: path={n.path} sha={n.recorded_sha}" for n in sandbox.nodes)
    disk = "\n".join(f"  {p} sha={s}" for p, s in sorted(sandbox.disk.items()))
    return (
        "You are auditing KG↔disk drift. For EACH recorded node decide its status by "
        "comparing the recorded (path,sha) against the CURRENT disk state.\n\n"
        "Rules:\n"
        "- CLEAN: node.path exists on disk AND disk sha == recorded sha.\n"
        "- DRIFT: node.path exists on disk BUT disk sha != recorded sha (content changed).\n"
        "- MOVED: node.path is NOT on disk, BUT the node's recorded sha appears at a DIFFERENT "
        "disk path (same content relocated — do NOT treat as deleted).\n"
        "- ORPHAN: node.path is NOT on disk AND its recorded sha does not appear anywhere on disk.\n\n"
        f"RECORDED nodes:\n{recorded}\n\n"
        f"CURRENT disk (path sha):\n{disk}\n\n"
        "Return ONLY a JSON object mapping each node name to its verdict, e.g. "
        '{"n0":"CLEAN","n1":"MOVED",...}. No prose.'
    )


@dataclass(frozen=True)
class ABResult:
    n_seeds: int
    on_classification: float  # longinus 평균 classification accuracy
    off_classification: float  # naive 평균
    on_false_kill: float  # longinus 평균 false-kill rate
    off_false_kill: float  # naive 평균
    delta_classification: float  # ON − OFF (양수 = longinus 우위)
    delta_false_kill: float  # OFF − ON (양수 = longinus가 위험 더 줄임)
    perm_p_classification: float  # sign-flip permutation p (delta_classification)
    on_detection_recall: float
    off_detection_recall: float

    @property
    def summary(self) -> str:
        return (
            f"longinus ON vs naive OFF (n={self.n_seeds} seeds): "
            f"classification ON={self.on_classification:.3f} OFF={self.off_classification:.3f} "
            f"Δ={self.delta_classification:+.3f} (perm p={self.perm_p_classification:.4f}); "
            f"false-kill ON={self.on_false_kill:.3f} OFF={self.off_false_kill:.3f}; "
            f"detection-recall ON={self.on_detection_recall:.3f} OFF={self.off_detection_recall:.3f}"
        )


def _signflip_p(deltas: list[float], n_resamples: int = 20000, seed: int = 0) -> float:
    """paired sign-flip permutation p (양측). 관측 |mean| 이상 비율. 결정론(seed)."""
    obs = abs(sum(deltas) / len(deltas)) if deltas else 0.0
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_resamples):
        m = sum(d if rng.random() < 0.5 else -d for d in deltas) / len(deltas)
        if abs(m) >= obs - 1e-12:
            hits += 1
    return hits / n_resamples


def run_experiment(
    n_seeds: int = 20,
    composition: tuple[int, int, int, int, int] = (50, 12, 12, 8, 6),
    base_seed: int = 1000,
) -> ABResult:
    """multi-seed paired ON/OFF. composition=(clean,edit,move,delete,move_edit). 결정론."""
    on_cls, off_cls, on_fk, off_fk, on_rec, off_rec, deltas = [], [], [], [], [], [], []
    for s in range(n_seeds):
        sb = build_sandbox(*composition, seed=base_seed + s)
        on = score_arm(longinus_detect(sb), sb.ledger)
        off = score_arm(naive_detect(sb), sb.ledger)
        on_cls.append(on.classification_accuracy)
        off_cls.append(off.classification_accuracy)
        on_fk.append(on.false_kill_rate)
        off_fk.append(off.false_kill_rate)
        on_rec.append(on.detection_recall)
        off_rec.append(off.detection_recall)
        deltas.append(on.classification_accuracy - off.classification_accuracy)
    mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
    return ABResult(
        n_seeds=n_seeds,
        on_classification=mean(on_cls), off_classification=mean(off_cls),
        on_false_kill=mean(on_fk), off_false_kill=mean(off_fk),
        delta_classification=mean(on_cls) - mean(off_cls),
        delta_false_kill=mean(off_fk) - mean(on_fk),
        perm_p_classification=_signflip_p(deltas),
        on_detection_recall=mean(on_rec), off_detection_recall=mean(off_rec),
    )


def build_sandbox_from_git(
    repo: str, cutoff: str, scope_prefix: str = "engine/"
) -> Sandbox:  # pragma: no cover — IO
    """git_oracle를 소비해 실 git 데이터로 Sandbox 조립 (합성 sandbox의 real-KG 대체)."""
    from engine.efficacy import git_oracle as go  # noqa: PLC0415

    base = go.cutoff_commit(repo, cutoff)
    recorded = go.tree_blobs(repo, base)
    disk = go.tree_blobs(repo, "HEAD")
    net = go.net_status(repo, base, "HEAD")
    return assemble_git_sandbox(recorded, disk, net, scope_prefix)


def run_experiment_real_kg(
    repo: str, cutoff: str, scope_prefix: str = "engine/"
) -> tuple[Sandbox, ArmScore, ArmScore]:  # pragma: no cover — IO
    """실 git drift 위 longinus(ON) vs naive(OFF) 단일 표본. ground truth=git -M rename."""
    sb = build_sandbox_from_git(repo, cutoff, scope_prefix)
    on = score_arm(longinus_detect(sb), sb.ledger)
    off = score_arm(naive_detect(sb), sb.ledger)
    return sb, on, off


def main() -> int:  # pragma: no cover — 진입점
    import sys  # noqa: PLC0415

    if len(sys.argv) > 1 and sys.argv[1] == "--real":
        repo = sys.argv[2] if len(sys.argv) > 2 else "."
        cutoff = sys.argv[3] if len(sys.argv) > 3 else "2026-05-25"
        sb, on, off = run_experiment_real_kg(repo, cutoff)
        corrupted = sum(1 for v in sb.ledger.values() if v is not TrueKind.CLEAN)
        dist: dict[str, int] = {}
        for v in sb.ledger.values():
            dist[v.value] = dist.get(v.value, 0) + 1
        print(f"longinus real-KG drift [{repo}] cutoff={cutoff} (ground truth = git -M rename):")
        print(f"  nodes={len(sb.nodes)} corrupted={corrupted} true-kinds={dist}")
        print(
            f"  ON (longinus): class={on.classification_accuracy:.3f} "
            f"recall={on.detection_recall:.3f} false-kill={on.false_kill_rate:.3f} "
            f"fp={on.false_positive_rate:.3f}"
        )
        print(
            f"  OFF (naive):   class={off.classification_accuracy:.3f} "
            f"recall={off.detection_recall:.3f} false-kill={off.false_kill_rate:.3f} "
            f"fp={off.false_positive_rate:.3f}"
        )
        print(
            f"  Δclass={on.classification_accuracy - off.classification_accuracy:+.3f}  "
            f"Δfalse-kill(OFF−ON)={off.false_kill_rate - on.false_kill_rate:+.3f}  "
            "※ single real sample, non-circular (git rename ⊥ longinus sha-twin)"
        )
        return 0
    res = run_experiment()
    print(res.summary)
    return 0


__all__ = [
    "ABResult",
    "ArmScore",
    "Node",
    "Sandbox",
    "TrueKind",
    "Verdict",
    "assemble_git_sandbox",
    "build_sandbox",
    "build_sandbox_from_git",
    "longinus_detect",
    "naive_detect",
    "run_experiment",
    "run_experiment_real_kg",
    "score_arm",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
