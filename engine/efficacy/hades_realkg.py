"""hades(실현) real-KG oracle — repo git에서 SWE-bench식 revert/regenerate task (PROM 16 H4).

hades 동사 = 추상 spec→구체 코드(TDD GREEN). 비순환 실행 oracle = *인간이 작성한* hidden
test가 통과하나. git_oracle.feature_test_commits(impl+test 동시커밋)에서 task 채굴:
  1. feature commit에서 impl을 parent로 revert(=기능 제거, test는 신버전 유지 → RED 기대).
  2. LLM에게 test(=spec)만 주고 impl 재생성.
  3. git worktree 격리(공유 working tree 불간섭) 안에서 pytest → pass@1.

비순환: test는 commit에 이미 박힌 인간 작성 oracle (모델/엔진이 만든 게 아님). 단 이 repo는
AI-authored 커밋이 많아 "human test" 외부성이 진짜 SWE-bench보다 약함 — residual confounder 공시.

순수(pick_tasks/strip_code_fence/pass_at_k) + IO(build_tasks/run_task: worktree+pytest).

# KG: efficacy-measurement-line-2026-06-01, project_bhgman_ab_falsifier_2026_05_30,
#     7cmd-measurement-driven-conditional-dispatch-2026-05-30 (hades 실현)
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass

from engine.efficacy.git_oracle import FeatureTestCommit


@dataclass(frozen=True)
class HadesTask:
    """revert/regenerate task 1건. parent = commit^ (기능 직전 상태)."""

    commit: str
    impl_path: str
    test_path: str

    @property
    def parent(self) -> str:
        return f"{self.commit}^"


@dataclass(frozen=True)
class TaskResult:
    task: HadesTask
    passed: bool  # 전체 GREEN (엄격 pass@1, SWE-bench 관례)
    detail: str  # pytest 요약 또는 에러
    tests_passed: int = 0  # 부분 통과 granularity
    tests_total: int = 0

    @property
    def test_pass_rate(self) -> float:
        return self.tests_passed / self.tests_total if self.tests_total else 0.0


def pick_tasks(
    fts: Sequence[FeatureTestCommit], n: int, scope_prefix: str = "engine/"
) -> list[HadesTask]:
    """impl 1 + test 1인 깔끔한 커밋만 골라 결정론 task로 (순수). commit 정렬, 앞 n."""
    tasks: list[HadesTask] = []
    for ft in sorted(fts, key=lambda f: f.commit):
        if len(ft.impl_paths) != 1 or len(ft.test_paths) != 1:
            continue
        impl, test = ft.impl_paths[0], ft.test_paths[0]
        if not impl.startswith(scope_prefix) or impl.endswith("__init__.py"):
            continue
        tasks.append(HadesTask(commit=ft.commit, impl_path=impl, test_path=test))
    return tasks[:n]


def strip_code_fence(text: str) -> str:
    """LLM 출력에서 ```python ... ``` 펜스 제거 (순수). 펜스 없으면 그대로."""
    lines = text.splitlines()
    if lines and lines[0].lstrip().startswith("```"):
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
    return "\n".join(lines).strip() + "\n"


def pass_at_1(results: Sequence[TaskResult]) -> float:
    """전체 GREEN task 비율 = 엄격 pass@1 (순수). 빈 입력이면 0.0."""
    return sum(1 for r in results if r.passed) / len(results) if results else 0.0


def parse_pytest_counts(text: str) -> tuple[int, int]:
    """pytest 요약 → (passed, total). total = passed+failed+error (skipped 제외). 순수."""
    import re  # noqa: PLC0415

    def _n(word: str) -> int:
        m = re.search(rf"(\d+) {word}", text)
        return int(m.group(1)) if m else 0

    passed = _n("passed")
    return passed, passed + _n("failed") + _n("error")


def mean_test_pass_rate(results: Sequence[TaskResult]) -> float:
    """task별 테스트 통과율의 평균 (순수). 엄격 pass@1보다 granular."""
    rated = [r for r in results if r.tests_total]
    return sum(r.test_pass_rate for r in rated) / len(rated) if rated else 0.0


# ── IO (git worktree + subprocess) ──


def _git(repo: str, args: list[str]) -> subprocess.CompletedProcess:  # pragma: no cover — IO
    return subprocess.run(  # noqa: S603
        ["git", "-C", repo, *args], capture_output=True, text=True, check=False
    )


def build_tasks(
    repo: str, cutoff: str, n: int, scope_prefix: str = "engine/"
) -> list[HadesTask]:  # pragma: no cover — IO
    """git_oracle를 소비해 task 채굴."""
    from engine.efficacy import git_oracle as go  # noqa: PLC0415

    fts = go.feature_test_commits(go.mine_events(repo, since=cutoff))
    return pick_tasks(fts, n, scope_prefix)


def _regenerate_prompt(test_src: str, impl_path: str) -> str:
    return (
        f"Implement the Python module `{impl_path}`. It must make the following test "
        f"suite pass exactly as written (do not change the tests). Output ONLY the complete "
        f"contents of `{impl_path}` as Python — no markdown fences, no prose.\n\n"
        f"=== TEST SUITE (the spec / hidden oracle) ===\n{test_src}\n"
    )


def run_task(
    repo: str, task: HadesTask, client, model: str = "local"
) -> TaskResult:  # pragma: no cover — IO (worktree + LLM + pytest)
    """worktree 격리: feature commit checkout → impl revert → LLM 재생성 → pytest pass@1.

    공유 working tree 불간섭(git worktree add 별도 디렉터리). finally에서 worktree 제거."""
    repo_abs = os.path.abspath(repo)
    py = os.path.join(repo_abs, ".venv/bin/python")
    with tempfile.TemporaryDirectory(prefix="hades_wt_") as wt:
        add = _git(repo_abs, ["worktree", "add", "--detach", wt, task.commit])
        if add.returncode != 0:
            return TaskResult(task, False, f"worktree add 실패: {add.stderr[:200]}")
        try:
            try:
                test_src = (open(os.path.join(wt, task.test_path), encoding="utf-8").read())  # noqa: SIM115,PTH123
                # impl을 parent로 revert (기능 제거). parent에 없으면 빈 파일(from-scratch).
                rev = _git(wt, ["checkout", task.parent, "--", task.impl_path])
                if rev.returncode != 0:
                    with open(os.path.join(wt, task.impl_path), "w", encoding="utf-8") as fh:  # noqa: PTH123
                        fh.write("")
                # LLM 재생성 (timeout/네트워크 오류는 그 task FAIL로 — batch 중단 금지)
                comp = client.complete(
                    system="You are an expert Python engineer. Output only code.",
                    user=_regenerate_prompt(test_src, task.impl_path),
                    model=model,
                    max_tokens=8192,
                )
                with open(os.path.join(wt, task.impl_path), "w", encoding="utf-8") as fh:  # noqa: PTH123
                    fh.write(strip_code_fence(comp.text))
                proc = subprocess.run(  # noqa: S603
                    [py, "-m", "pytest", task.test_path, "-q", "-x", "-p", "no:cacheprovider"],
                    cwd=wt, capture_output=True, text=True, check=False,
                )
                tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr[:150]
                passed_n, total_n = parse_pytest_counts(proc.stdout)
                return TaskResult(task, proc.returncode == 0, tail, passed_n, total_n)
            except Exception as exc:  # noqa: BLE001 — 한 task 실패가 batch를 죽이면 안 됨
                return TaskResult(task, False, f"{type(exc).__name__}: {str(exc)[:120]}")
        finally:
            _git(repo_abs, ["worktree", "remove", "--force", wt])


def main() -> int:  # pragma: no cover — IO 진입점
    import sys  # noqa: PLC0415

    repo = sys.argv[2] if len(sys.argv) > 2 else "."
    cutoff = sys.argv[3] if len(sys.argv) > 3 else "2026-05-25"
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    mode = sys.argv[1] if len(sys.argv) > 1 else "--list"
    tasks = build_tasks(repo, cutoff, n)
    if mode == "--list":
        print(f"hades real-KG tasks [{repo}] cutoff={cutoff} (clean impl+test commits):")
        for t in tasks:
            print(f"  {t.commit[:8]} {t.impl_path} <- {t.test_path}")
        print(f"  total selected: {len(tasks)}")
        return 0
    if mode == "--run":
        from engine.agents.client import AgentClient  # noqa: PLC0415

        client = AgentClient()
        results = [run_task(repo, t, client) for t in tasks]
        for r in results:
            mark = "PASS" if r.passed else "FAIL"
            frac = f"{r.tests_passed}/{r.tests_total}" if r.tests_total else "n/a"
            print(f"  [{mark}] {r.task.commit[:8]} {r.task.impl_path}: {frac} tests — {r.detail}")
        print(
            f"hades realization: strict pass@1={pass_at_1(results):.3f}  "
            f"mean test-pass-rate={mean_test_pass_rate(results):.3f}  (n={len(results)}, LLM=regenerate)"
        )
        print("  ※ 비순환: human-written hidden test oracle. residual: AI-authored 커밋 다수.")
        return 0
    print(f"unknown mode {mode} (use --list / --run)", file=sys.stderr)
    return 2


__all__ = [
    "HadesTask",
    "TaskResult",
    "build_tasks",
    "mean_test_pass_rate",
    "parse_pytest_counts",
    "pass_at_1",
    "pick_tasks",
    "run_task",
    "strip_code_fence",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
