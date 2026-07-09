"""R2′ 속성 게이트 계약 — --consume-dispatch + --apply 의 공유 KG 개방 조건.

역사: R2 블랭킷 가드(PR#65, "--local 에서만")는 normalize_path 워크트리 결함이 main 에
잔존하는 동안의 fail-closed 임시조치였고 *무테스트*였다(F-D). 결함 착지(seam-integrity
2026-07-10)로 전제가 소멸 — 가드는 '능력 속성' 체크로 치환된다: 체크아웃 경로가 KG 키로
정규화되면 개방, 아니면(무규약 클론) 여전히 거부. 미래에 체크아웃 규약이 깨지면 자동 재폐쇄.

# KG: LakatosTree_BhgmanSeamIntegrity_20260708/seam_r2_release
"""

from __future__ import annotations

import argparse

from engine.cli import commands
from engine.cli.commands import _consume_pathkey_selftest, cmd_legion


def _args(**over) -> argparse.Namespace:
    base = dict(
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
    base.update(over)
    return argparse.Namespace(**base)


def test_selftest_passes_in_convention_checkout():
    """이 repo 체크아웃(정본이든 -wt-* 워크트리든)은 selftest 를 통과해야 — 통과 자체가
    normalize_path 워크트리 수리의 살아있는 증거다 (이 테스트는 워크트리 CI 에서도 돈다)."""
    assert _consume_pathkey_selftest() is True


def test_unnormalizable_checkout_is_refused(monkeypatch, tmp_path):
    """무규약 클론(~/clones/foo 류) 시뮬레이션: selftest 실패 → 공유 KG apply 소비 rc=2.

    주의(적대검증 정정): 게이트는 러너 *해석 후*에 선다 — fake 러너는 게이트 앞 단계가
    2 이외의 사유로 조기 종료하지 않게 하는 비계일 뿐, 순서 고정 장치가 아니다. 거부가
    러너-불가(rc=2 동일값)가 아니라 게이트에서 남을 stderr 문구로 판별한다."""
    import contextlib
    import io

    clone = tmp_path / "someclone"
    (clone / "engine").mkdir(parents=True)
    monkeypatch.setattr(commands, "_repo_root", lambda: clone)

    def _fake_runners(_args):
        runner = lambda _c, _p=None: []  # noqa: E731
        return runner, runner, lambda: None

    monkeypatch.setattr(commands, "_resolve_kg_runners", _fake_runners)

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rc = cmd_legion(_args())
    assert rc == 2, "정규화 불가 체크아웃의 공유 KG apply 소비는 거부돼야 (R2′)"
    assert "정규화 불가" in err.getvalue(), "rc=2 의 출처가 R2′ 게이트임을 문구로 판별"


def test_local_mode_needs_no_selftest(monkeypatch, tmp_path):
    """--local 은 ephemeral 라 게이트 무관 — selftest 실패 체크아웃에서도 rc=2 가 아니어야
    (블랭킷 시절과 동일한 개방면 보존).

    ⚠BHGMAN_KG_PATH 격리 필수: --local 의 기본 store 는 ~/.bhgman/kg.json(사용자 홈,
    autosave=True) — 격리 없이 돌리면 테스트가 실행마다 :JaebaemanRun 을 홈 KG 에
    영속시켜 타 테스트(레코드 정확-1 assert)를 오염시킨다 (2026-07-10 실사고)."""
    monkeypatch.setenv("BHGMAN_KG_PATH", str(tmp_path / "kg.json"))
    clone = tmp_path / "someclone"
    (clone / "engine").mkdir(parents=True)
    monkeypatch.setattr(commands, "_repo_root", lambda: clone)
    rc = cmd_legion(_args(local=True, no_disk_scan=True))
    assert rc != 2, "--local 경로는 R2′ 게이트 대상이 아님"
