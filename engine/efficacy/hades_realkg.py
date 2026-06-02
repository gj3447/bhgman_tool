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


def extract_signatures(src: str) -> str:
    """impl 소스 → def/class 시그니처 + 첫 docstring 줄 (순수, ast). hades arm의 Contract 힌트."""
    import ast  # noqa: PLC0415

    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ""
    lines: list[str] = []
    for node in ast.walk(tree):
        doc = (ast.get_docstring(node) or "").split("\n")[0] if isinstance(
            node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ) else ""
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            lines.append(f"def {node.name}({ast.unparse(node.args)}): {doc}".rstrip())
        elif isinstance(node, ast.ClassDef):
            lines.append(f"class {node.name}: {doc}".rstrip())
    return "\n".join(lines)


def _regenerate_prompt(test_src: str, impl_path: str, contract: str = "") -> str:
    contract_block = (
        f"=== CONTRACT (the module's public interface — implement these) ===\n{contract}\n\n"
        if contract
        else ""
    )
    return (
        f"Implement the Python module `{impl_path}`. It must make the following test "
        f"suite pass exactly as written (do not change the tests). Output ONLY the complete "
        f"contents of `{impl_path}` as Python — no markdown fences, no prose.\n\n"
        f"{contract_block}"
        f"=== TEST SUITE (the spec / hidden oracle) ===\n{test_src}\n"
    )


def run_task(
    repo: str, task: HadesTask, client, model: str = "local", use_contract: bool = False
) -> TaskResult:  # pragma: no cover — IO (worktree + LLM + pytest)
    """worktree 격리: feature commit checkout → impl revert → LLM 재생성 → pytest pass@1.

    use_contract=True (hades arm): revert 전 reference impl의 시그니처를 Contract로 주입.
    False (base arm): test만. 공유 working tree 불간섭. finally에서 worktree 제거."""
    repo_abs = os.path.abspath(repo)
    py = os.path.join(repo_abs, ".venv/bin/python")
    with tempfile.TemporaryDirectory(prefix="hades_wt_") as wt:
        add = _git(repo_abs, ["worktree", "add", "--detach", wt, task.commit])
        if add.returncode != 0:
            return TaskResult(task, False, f"worktree add 실패: {add.stderr[:200]}")
        try:
            try:
                test_src = (open(os.path.join(wt, task.test_path), encoding="utf-8").read())  # noqa: SIM115,PTH123
                # hades arm: revert 전 feature impl 시그니처 추출 (Contract).
                contract = ""
                if use_contract:
                    ref = open(os.path.join(wt, task.impl_path), encoding="utf-8").read()  # noqa: SIM115,PTH123
                    contract = extract_signatures(ref)
                # impl을 parent로 revert (기능 제거). parent에 없으면 빈 파일(from-scratch).
                rev = _git(wt, ["checkout", task.parent, "--", task.impl_path])
                if rev.returncode != 0:
                    with open(os.path.join(wt, task.impl_path), "w", encoding="utf-8") as fh:  # noqa: PTH123
                        fh.write("")
                # LLM 재생성 (timeout/네트워크 오류는 그 task FAIL로 — batch 중단 금지)
                comp = client.complete(
                    system="You are an expert Python engineer. Output only code.",
                    user=_regenerate_prompt(test_src, task.impl_path, contract),
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


@dataclass(frozen=True)
class Candidate:
    """best-of-N 후보 1개: 생성 코드 + 실제 hidden-test 통과 여부."""

    code: str
    passed: bool


def _normalize_code(code: str) -> str:
    """majority 투표용 정규화 — 공백/빈줄 제거 (텍스트 self-consistency, oracle 미사용)."""
    return "\n".join(ln.rstrip() for ln in code.splitlines() if ln.strip())


def select_pass_at_1(cands: Sequence[Candidate]) -> bool:
    """블라인드 floor: 첫 샘플을 그냥 ship (= 단일패스 pass@1). 순수."""
    return bool(cands) and cands[0].passed


def select_majority_at_n(cands: Sequence[Candidate]) -> bool:
    """텍스트 self-consistency: 가장 흔한 코드(정규화)를 ship. oracle 미사용. 순수.

    동수면 먼저 등장한 군. base 모델의 '오라클 없는 N-선택' = 정직한 baseline."""
    from collections import Counter  # noqa: PLC0415

    if not cands:
        return False
    counts = Counter(_normalize_code(c.code) for c in cands)
    top_norm = max(counts, key=lambda k: (counts[k], -[_normalize_code(c.code) for c in cands].index(k)))
    rep = next(c for c in cands if _normalize_code(c.code) == top_norm)
    return rep.passed


def select_pass_at_n(cands: Sequence[Candidate]) -> bool:
    """oracle-rerank: N 중 hidden-test 통과하는 게 하나라도 있으면 ship (= bhgman 완벽-oracle). 순수."""
    return any(c.passed for c in cands)


def run_bestofn_task(
    repo: str, task: HadesTask, client, n: int = 5, model: str = "local",
    temperature: float | None = 1.0,
) -> list[Candidate]:  # pragma: no cover — IO (worktree + N×LLM + N×pytest)
    """한 task에서 N개 후보 생성·각각 테스트. 같은 worktree 재사용, 매 후보 impl revert→생성→pytest.

    동일 생성예산(N) 아래 selector만 바꿔 비교하려는 raw 재료. oracle은 토큰 0(실행만)."""
    repo_abs = os.path.abspath(repo)
    py = os.path.join(repo_abs, ".venv/bin/python")
    cands: list[Candidate] = []
    with tempfile.TemporaryDirectory(prefix="hades_bon_") as wt:
        if _git(repo_abs, ["worktree", "add", "--detach", wt, task.commit]).returncode != 0:
            return []
        try:
            test_src = open(os.path.join(wt, task.test_path), encoding="utf-8").read()  # noqa: SIM115,PTH123
            # 후보별 접근 변주 — outcome 다양성 유도(temperature 노브 부재 우회). pass@k headroom 전제.
            variants = [
                "", "Take a minimal, direct approach.", "Take a defensive, edge-case-first approach.",
                "Prefer standard-library idioms and explicit types.", "Optimize for readability over cleverness.",
                "Consider an alternative data structure or control flow.",
            ]
            for i in range(n):
                try:
                    rev = _git(wt, ["checkout", task.parent, "--", task.impl_path])
                    if rev.returncode != 0:
                        open(os.path.join(wt, task.impl_path), "w").close()  # noqa: SIM115,PTH123
                    hint = variants[i % len(variants)]
                    comp = client.complete(
                        system="You are an expert Python engineer. Output only code.",
                        user=_regenerate_prompt(test_src, task.impl_path) + (f"\n\n[Variant {i}] {hint}" if hint else ""),
                        model=model,
                        max_tokens=8192,
                        temperature=temperature,
                    )
                    code = strip_code_fence(comp.text)
                    with open(os.path.join(wt, task.impl_path), "w", encoding="utf-8") as fh:  # noqa: PTH123
                        fh.write(code)
                    proc = subprocess.run(  # noqa: S603
                        [py, "-m", "pytest", task.test_path, "-q", "-x", "-p", "no:cacheprovider"],
                        cwd=wt, capture_output=True, text=True, check=False,
                    )
                    cands.append(Candidate(code=code, passed=proc.returncode == 0))
                except Exception:  # noqa: BLE001 — 후보 1개 실패는 FAIL 후보로 계속
                    cands.append(Candidate(code="", passed=False))
        finally:
            _git(repo_abs, ["worktree", "remove", "--force", wt])
    return cands


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
    if mode == "--ab":
        from engine.agents.client import AgentClient  # noqa: PLC0415

        client = AgentClient()
        base = [run_task(repo, t, client, use_contract=False) for t in tasks]
        hades = [run_task(repo, t, client, use_contract=True) for t in tasks]
        print(f"hades A/B (Contract 힌트 효과) [{repo}] cutoff={cutoff} n={len(tasks)}:")
        print(
            f"  base  (tests only):       pass@1={pass_at_1(base):.3f}  "
            f"mean-test={mean_test_pass_rate(base):.3f}"
        )
        print(
            f"  hades (tests+Contract):   pass@1={pass_at_1(hades):.3f}  "
            f"mean-test={mean_test_pass_rate(hades):.3f}"
        )
        print(
            f"  Δpass@1(hades−base)={pass_at_1(hades) - pass_at_1(base):+.3f}  "
            f"Δmean-test={mean_test_pass_rate(hades) - mean_test_pass_rate(base):+.3f}  "
            "※ 동일 모델, Contract 시그니처 힌트만 차이"
        )
        return 0
    if mode == "--bestofn":
        from engine.agents.client import AgentClient  # noqa: PLC0415

        n_cand = int(sys.argv[5]) if len(sys.argv) > 5 else 5
        temp = float(sys.argv[6]) if len(sys.argv) > 6 else 1.0
        client = AgentClient()
        per_task = [run_bestofn_task(repo, t, client, n_cand, temperature=temp) for t in tasks]
        per_task = [c for c in per_task if c]  # 빈(worktree 실패) task 제외
        nt = len(per_task)
        p1 = sum(select_pass_at_1(c) for c in per_task) / nt if nt else 0.0
        maj = sum(select_majority_at_n(c) for c in per_task) / nt if nt else 0.0
        pn = sum(select_pass_at_n(c) for c in per_task) / nt if nt else 0.0
        # medium-band = 한 task 안에서 일부만 통과(0<통과<N) = best-of-N이 고를 다양성 존재.
        band = [c for c in per_task if 0 < sum(x.passed for x in c) < len(c)]
        nb = len(band)
        maj_b = sum(select_majority_at_n(c) for c in band) / nb if nb else 0.0
        pn_b = sum(select_pass_at_n(c) for c in band) / nb if nb else 0.0
        dist = sorted(sum(x.passed for x in c) for c in per_task)  # task별 통과 후보 수
        print(f"hades best-of-N (N={n_cand}, temp={temp}, oracle=토큰0) [{repo}] tasks={nt}:")
        print(f"  pass@1={p1:.3f}  majority@N={maj:.3f}  oracle-rerank@N={pn:.3f}")
        print(f"  ▶ 전체 cognitive lift = oracle−majority = {pn - maj:+.3f}  (headroom pass@N−pass@1 = {pn - p1:+.3f})")
        print(f"  task별 통과후보수 분포(0~{n_cand}): {dist}")
        print(f"  medium-band(0<통과<N) tasks = {nb}/{nt}  → 이 band lift = oracle−majority = {pn_b - maj_b:+.3f} (maj {maj_b:.3f} vs oracle {pn_b:.3f})")
        print("  ※ medium-band가 0이면 다양성/난이도 문제(=selector 무관). >0인데 lift>0이면 oracle이 진짜 이김.")
        return 0
    print(f"unknown mode {mode} (use --list / --run / --ab / --bestofn)", file=sys.stderr)
    return 2


__all__ = [
    "Candidate",
    "HadesTask",
    "TaskResult",
    "build_tasks",
    "extract_signatures",
    "mean_test_pass_rate",
    "parse_pytest_counts",
    "pass_at_1",
    "pick_tasks",
    "run_bestofn_task",
    "run_task",
    "select_majority_at_n",
    "select_pass_at_1",
    "select_pass_at_n",
    "strip_code_fence",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
