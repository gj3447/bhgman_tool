"""judge J-D — R2 가드의 정직 개방: 블랭킷 금지 → 능력 속성 게이트(R2′).

RED(main): --consume-dispatch + --apply + 비-local 은 무조건 rc=2 (정규화 가능한 규약
체크아웃에서도) — normalize_path 결함 잔존 중의 fail-closed 임시조치, 그리고 무테스트(F-D).

GREEN 기대: 정규화-가능 체크아웃(정본/워크트리)은 개방(rc≠2), 정규화-불가 체크아웃
(무규약 클론 시뮬레이션)은 여전히 rc=2 — 개방과 안전이 동시 실측.

metric r2_normalizable_allowed: 규약 체크아웃 시나리오가 게이트를 통과하면 1 (main=0).
novel r2_unnormalizable_refused: 무규약 시나리오가 여전히 거부되면 1 (안전 보존 축).

사용: .venv/bin/python verification/seam_integrity/judge_r2_release.py
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def _mk_args(ns_mod):
    return ns_mod.Namespace(
        verb="run",
        local=False,
        apply=True,
        consume_dispatch=True,
        scope=None,
        concept=None,
        topic=None,
        no_disk_scan=True,
        llm=False,
        no_ground=True,
        web=False,
    )


def _rc_with_root(root: Path) -> int:
    """cmd_legion 을 fake 러너 + 지정 root 로 호출 — 게이트 판정(rc)만 관측.

    fake 러너는 빈 rows 반환: 게이트 통과 시 legion 루프가 degraded 로 돌지만 rc 는
    2 가 아니게 된다 (관측 대상은 '게이트가 여는가/닫는가' 뿐)."""
    import argparse as ns_mod
    import contextlib
    import io

    from engine.cli import commands

    orig_root = commands._repo_root
    orig_runners = commands._resolve_kg_runners
    try:
        commands._repo_root = lambda: root

        def _fake_runners(_args):
            runner = lambda _c, _p=None: []  # noqa: E731
            return runner, runner, lambda: None

        commands._resolve_kg_runners = _fake_runners
        # 게이트 통과 시 legion 루프의 stage print 가 judge JSON 출력을 오염시키므로 격리.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return commands.cmd_legion(_mk_args(ns_mod))
    finally:
        commands._repo_root = orig_root
        commands._resolve_kg_runners = orig_runners


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--receipt",
        default=str(REPO / "verification" / "seam_integrity" / "r2_release_receipt.json"),
    )
    args = ap.parse_args()

    # 시나리오 1: 규약 체크아웃 (이 repo 의 실제 root — 정본이든 -wt-* 든).
    rc_convention = _rc_with_root(REPO)
    allowed = 1.0 if rc_convention != 2 else 0.0

    # 시나리오 2: 무규약 클론 (tmp 아래 임의 디렉터리명).
    with tempfile.TemporaryDirectory() as td:
        clone = Path(td) / "someclone"
        (clone / "engine").mkdir(parents=True)
        rc_clone = _rc_with_root(clone)
    refused = 1.0 if rc_clone == 2 else 0.0

    receipt = {
        "metric_name": "r2_normalizable_allowed",
        "metric_value": allowed,
        "r2_unnormalizable_refused": refused,
        "rc_convention_checkout": rc_convention,
        "rc_unconvention_clone": rc_clone,
        "checkout_root": str(REPO),
        "note": (
            "RED(main): 블랭킷 금지 — 규약 체크아웃도 rc=2 (allowed=0). "
            "GREEN: 규약=개방(rc≠2, allowed=1) ∧ 무규약=거부(rc=2, refused=1) 동시 성립."
        ),
    }
    out = Path(args.receipt)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
