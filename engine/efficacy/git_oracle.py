"""git 히스토리 = 시스템이 저자가 될 수 없는 외부 효능 oracle (PROM 16 P0).

엔진이 라벨을 자기가 만들면 순환(occam σ A/B AUC 0.41 사례). git이 *물리적으로 기록한*
사건(삭제·rename·신규파일·`# KG:` 바인딩 변화·feature+test 동시커밋)은 군단장이 만들지
않은 ground truth → 비순환 hold-out 라벨. KG 엣지 타임스탬프는 사실상 0이라
(BELONGS_TO 0/107528 등) git이 *유일한 정직한 시간축*.

  occam(정리)   ← DELETE + RENAME (치워야 했던 것)
  eureka(창조)  ← ADD            (새로 만들어진 추상)
  hades(실현)   ← feature+test 동시커밋 (impl revert→재생성 SWE-bench식 task)
  longinus(연결) ← RENAME(stale path) + `# KG:` 참조 주석 추가/삭제

temporal split: cutoff T로 pre-T(관찰)·post-T(hold-out 정답) 분리. 슬라이딩 T로 N fold.
재현: (repo_sha, cutoff, n_events) 동결 → 2-run idempotence.

순수(parse_*: git 출력 텍스트→이벤트) + IO(mine_*: subprocess). 순수부만 unit-test.

# KG: efficacy-measurement-line-2026-06-01, project_bhgman_ab_falsifier_2026_05_30,
#     7cmd-measurement-driven-conditional-dispatch-2026-05-30, feedback_empirical_falsifier_before_grand_frame
"""

from __future__ import annotations

import subprocess
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# 이벤트 종류 (git diff status에서 파생).
ADD = "ADD"
DELETE = "DELETE"
RENAME = "RENAME"
MODIFY = "MODIFY"

# git log --name-status 헤더 prefix — 파일 status 줄과 충돌 안 나게 distinctive.
_HEADER = "__C__"
_LOG_FORMAT = _HEADER + "%H\t%cd"

# 군단장별 양성 라벨 = 어떤 git 사건이 "그 동사가 옳았다"의 외부 증거인가.
COMMANDER_POSITIVE_KINDS: dict[str, tuple[str, ...]] = {
    "occam": (DELETE, RENAME),
    "eureka": (ADD,),
    "hades": (ADD,),
    "longinus": (RENAME,),
}


@dataclass(frozen=True)
class GitEvent:
    """git 커밋 1개가 파일 1개에 가한 변화 1건."""

    commit: str
    date: str  # ISO 'YYYY-MM-DD' (committer date) — 문자열 비교로 temporal split 가능
    kind: str
    path: str
    old_path: str | None = None  # RENAME의 이전 경로


@dataclass(frozen=True)
class FeatureTestCommit:
    """impl(.py)과 test_*.py를 *함께* 건드린 커밋 = hades SWE-bench식 task 후보."""

    commit: str
    date: str
    impl_paths: tuple[str, ...]
    test_paths: tuple[str, ...]


@dataclass(frozen=True)
class OracleSnapshot:
    """재현 동결 튜플 — 같은 (repo_sha, cutoff)면 같은 라벨셋."""

    repo_sha: str
    cutoff: str
    n_events_before: int
    n_events_after: int


def _is_test_path(path: str) -> bool:
    """test_*.py / *_test.py / tests/ 하위 = 테스트 파일."""
    base = path.rsplit("/", 1)[-1]
    return base.startswith("test_") or base.endswith("_test.py") or "/tests/" in path


def parse_name_status(text: str) -> list[GitEvent]:
    """`git log --name-status --format=__C__%H\\t%cd` 출력 → GitEvent 리스트 (순수)."""
    events: list[GitEvent] = []
    sha: str | None = None
    date = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        if line.startswith(_HEADER):
            sha, _, date = line[len(_HEADER) :].partition("\t")
            continue
        if sha is None:
            continue
        ev = _parse_status_line(line, sha, date)
        if ev is not None:
            events.append(ev)
    return events


def _parse_status_line(line: str, sha: str, date: str) -> GitEvent | None:
    """status\\tpath[\\tnewpath] 한 줄 → GitEvent. 알 수 없으면 None."""
    parts = line.split("\t")
    status = parts[0]
    if (status.startswith("R") or status.startswith("C")) and len(parts) >= 3:
        return GitEvent(sha, date, RENAME, path=parts[2], old_path=parts[1])
    simple = {"A": ADD, "D": DELETE, "M": MODIFY}.get(status)
    if simple and len(parts) >= 2:
        return GitEvent(sha, date, simple, path=parts[1])
    return None


def parse_ref_comment_patch(patch_text: str) -> list[GitEvent]:
    """`git log -p` unified diff → `# KG:` 바인딩 추가/삭제 이벤트 (longinus, 순수).

    `+...# KG:` = 바인딩 추가(ADD), `-...# KG:` = 바인딩 삭제(DELETE). 헤더 ±는 제외."""
    events: list[GitEvent] = []
    sha = ""
    date = ""
    path = ""
    for raw in patch_text.splitlines():
        if raw.startswith(_HEADER):
            sha, _, date = raw[len(_HEADER) :].partition("\t")
        elif raw.startswith("+++ b/"):
            path = raw[len("+++ b/") :]
        elif raw.startswith(("+++", "---")):
            continue
        elif raw.startswith("+") and "# KG:" in raw:
            events.append(GitEvent(sha, date, ADD, path=path, old_path=None))
        elif raw.startswith("-") and "# KG:" in raw:
            events.append(GitEvent(sha, date, DELETE, path=path, old_path=None))
    return events


def parse_diff_status(text: str) -> list[GitEvent]:
    """`git diff --name-status -M base head` 출력(커밋 헤더 없음) → GitEvent (순수).

    net 변화(base→head)를 종류별로. commit/date는 비움(단일 비교라 무의미)."""
    events: list[GitEvent] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        ev = _parse_status_line(line, "", "")
        if ev is not None:
            events.append(ev)
    return events


def feature_test_commits(events: Iterable[GitEvent]) -> list[FeatureTestCommit]:
    """impl .py와 test_*.py를 함께 건드린 커밋 추출 (순수). date는 첫 이벤트."""
    by_commit: dict[str, list[GitEvent]] = defaultdict(list)
    for e in events:
        by_commit[e.commit].append(e)
    out: list[FeatureTestCommit] = []
    for sha, evs in by_commit.items():
        py = [e.path for e in evs if e.path.endswith(".py")]
        impls = tuple(p for p in py if not _is_test_path(p))
        tests = tuple(p for p in py if _is_test_path(p))
        if impls and tests:
            out.append(FeatureTestCommit(sha, evs[0].date, impls, tests))
    return out


def split_by_cutoff(
    events: Sequence[GitEvent], cutoff: str
) -> tuple[list[GitEvent], list[GitEvent]]:
    """cutoff(ISO date) 기준 (pre-T 관찰, post-T hold-out) 분리. ISO라 문자열 비교 OK."""
    before = [e for e in events if e.date < cutoff]
    after = [e for e in events if e.date >= cutoff]
    return before, after


def positive_paths(events: Iterable[GitEvent], commander: str) -> set[str]:
    """군단장의 양성 라벨 경로 = COMMANDER_POSITIVE_KINDS 종류의 사건이 일어난 path."""
    kinds = COMMANDER_POSITIVE_KINDS.get(commander, ())
    return {e.path for e in events if e.kind in kinds}


# ── IO (subprocess) — 순수부는 위에서 끝, 아래는 pragma no cover ──


def _git(repo: str, args: list[str]) -> str:  # pragma: no cover — subprocess
    proc = subprocess.run(  # noqa: S603
        ["git", "-C", repo, *args], capture_output=True, text=True, check=True
    )
    return proc.stdout


def mine_events(repo: str, since: str | None = None) -> list[GitEvent]:  # pragma: no cover — IO
    """repo의 git log을 name-status로 채굴 → GitEvent. since='YYYY-MM-DD'로 범위 제한."""
    args = ["log", "--name-status", "--date=short", f"--format={_LOG_FORMAT}"]
    if since:
        args += ["--since", since]
    return parse_name_status(_git(repo, args))


def mine_ref_comment_events(
    repo: str, since: str | None = None
) -> list[GitEvent]:  # pragma: no cover — IO
    """`# KG:` 바인딩 변화만 채굴 (longinus). -G로 해당 diff만 끌어 비용 절감."""
    args = ["log", "-p", "-G", "# KG:", "--date=short", f"--format={_LOG_FORMAT}", "--", "*.py"]
    if since:
        args += ["--since", since]
    return parse_ref_comment_patch(_git(repo, args))


def cutoff_commit(repo: str, date: str) -> str:  # pragma: no cover — IO
    """date(ISO) 직전 마지막 커밋 sha = temporal split의 base(pre-T 상태)."""
    return _git(repo, ["rev-list", "-1", f"--before={date}", "HEAD"]).strip()


def tree_blobs(repo: str, ref: str) -> dict[str, str]:  # pragma: no cover — IO
    """ref 시점 {path: blob_sha} = 그 시점 KG-recorded/disk 상태의 진짜 sha."""
    blobs: dict[str, str] = {}
    for line in _git(repo, ["ls-tree", "-r", ref]).splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) >= 3 and parts[1] == "blob":
            blobs[path] = parts[2]
    return blobs


def net_status(repo: str, base: str, head: str = "HEAD") -> list[GitEvent]:  # pragma: no cover — IO
    """base→head net 변화 (git -M rename 탐지 = longinus와 독립 메커니즘 → 비순환 oracle)."""
    return parse_diff_status(_git(repo, ["diff", "--name-status", "-M", base, head]))


def freeze(repo: str, cutoff: str, since: str | None = None) -> OracleSnapshot:  # pragma: no cover
    """재현 동결 튜플 생성 — (HEAD sha, cutoff, pre/post 이벤트 수)."""
    head = _git(repo, ["rev-parse", "HEAD"]).strip()
    before, after = split_by_cutoff(mine_events(repo, since), cutoff)
    return OracleSnapshot(head, cutoff, len(before), len(after))


def main() -> int:  # pragma: no cover — IO 진입점
    import sys  # noqa: PLC0415

    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    cutoff = sys.argv[2] if len(sys.argv) > 2 else "2026-05-25"
    events = mine_events(repo)
    before, after = split_by_cutoff(events, cutoff)
    by_kind: dict[str, int] = defaultdict(int)
    for e in events:
        by_kind[e.kind] += 1
    ft = feature_test_commits(events)
    snap = freeze(repo, cutoff)
    print(f"git_oracle [{repo}] HEAD={snap.repo_sha[:10]} cutoff={cutoff}")
    print(f"  events: {dict(by_kind)} (total {len(events)})")
    print(f"  temporal split: pre-T={len(before)}  post-T(hold-out)={len(after)}")
    print(f"  feature+test commits (hades tasks): {len(ft)}")
    for cmd in COMMANDER_POSITIVE_KINDS:
        pos_after = positive_paths(after, cmd)
        print(f"  {cmd:<9} post-T positive paths: {len(pos_after)}")
    return 0


__all__ = [
    "ADD",
    "COMMANDER_POSITIVE_KINDS",
    "DELETE",
    "MODIFY",
    "RENAME",
    "FeatureTestCommit",
    "GitEvent",
    "OracleSnapshot",
    "cutoff_commit",
    "feature_test_commits",
    "freeze",
    "mine_events",
    "mine_ref_comment_events",
    "net_status",
    "parse_diff_status",
    "parse_name_status",
    "parse_ref_comment_patch",
    "positive_paths",
    "split_by_cutoff",
    "tree_blobs",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
