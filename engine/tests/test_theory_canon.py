"""theory/ 정본 무결성 oracle (jbm-s7, gap G7 of audit wf_376c327b-8f3 — 레포-와이드 패스).

RED-first 배경: theory/ 아래 심링크 12개(재배맨 2 · APT 3 · CHU 2 · PROMETHEUS 2 · TPA 1 ·
LONGINUS 1 · 00_공통 1)가 홈 박스 SYMPOSIUM 정본을 가리키다 타깃 부재로 전부 파손돼 있었고,
나생문 INDEX 는 이 박스에 없는 파일 ~12개를 실재처럼 지도에 올려 두고 있었다. 2026-07-03
패스에서 파손 심링크를 prune 하고 홈 박스 정본 위치를 명시한 정직 스텁으로 교체했다.

이 oracle 이 고정하는 계약:
  (a) theory/ 아래 깨진 심링크 0 — 심링크 재도입으로 조용히 되돌아가지 못한다
      (복원은 vendor 실복사만).
  (b) theory/<dir>/INDEX.md 의 레포-로컬 마크다운 링크는 전수 실존 — 유령 참조를
      링크로 위장하지 못한다(미보유 목록은 링크 아닌 plain text 로만).

judge(scripts/judge_theory_canon.py)가 이 모듈의 헬퍼를 import 해 같은 오라클로 채점한다
(테스트↔judge drift 불가).

# KG: LakatosTree_BhgmanJaebaeman_20260702/jbm_s7_theory_canon
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
THEORY = REPO / "theory"

_MD_LINK = re.compile(r"\]\(([^)#\s]+)\)")


def broken_symlinks(root: Path) -> list[Path]:
    """root 아래 타깃이 실존하지 않는 심링크 전수."""
    return [p for p in root.rglob("*") if p.is_symlink() and not p.exists()]


def missing_index_refs(index_md: Path) -> list[str]:
    """INDEX.md 의 레포-로컬 마크다운 링크 중 실존하지 않는 타깃 (../·절대·URL 은 대상 외)."""
    out: list[str] = []
    for target in _MD_LINK.findall(index_md.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://", "../", "/")):
            continue
        if not (index_md.parent / target).exists():
            out.append(target)
    return out


def test_no_broken_symlinks_under_theory():
    """(a) 파손 심링크 0 — prune 이전엔 12개였다."""
    broken = broken_symlinks(THEORY)
    assert not broken, f"theory/ 에 파손 심링크 재발: {[str(p) for p in broken]}"


def test_subdir_index_local_refs_all_exist():
    """(b) 각 하위 폴더 INDEX.md 의 레포-로컬 링크 전수 실존 — 유령 참조 금지."""
    indexes = sorted(THEORY.glob("*/INDEX.md"))
    assert indexes, "theory/*/INDEX.md 가 하나도 없다 — 스텁 소실?"
    ghosts = {str(ix.relative_to(REPO)): missing_index_refs(ix) for ix in indexes}
    ghosts = {k: v for k, v in ghosts.items() if v}
    assert not ghosts, f"INDEX 유령 참조: {ghosts}"


def test_every_theory_dir_has_index_stub():
    """모든 theory 하위 폴더는 (스텁이라도) INDEX.md 를 지닌다 — 실재/미보유 공시 의무."""
    for d in sorted(p for p in THEORY.iterdir() if p.is_dir()):
        assert (d / "INDEX.md").is_file(), f"{d.name}/ 에 INDEX.md 없음 (정직 스텁 의무)"
