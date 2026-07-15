"""Regression: 라이브 full-KG 실측(2026-07-15)이 드러낸 occam 2버그.

1) 심볼-레벨 SourceCodeNode 의 sourcePath `file.py:250` (파일:시작줄)이 disk_paths 조인 시
   `:N` 앵커 때문에 절대 매치 안 돼 전부 false disk-orphan (60샘플 59실존, precision 1.7%).
2) recency_key 가 Neo4j DateTime(비-str)을 그대로 돌려줘 _current_rank 의 tuple `>` 비교가
   str↔DateTime 혼재로 크래시 (full-KG 스캔 사망 '> not supported between str and DateTime').
"""

from __future__ import annotations

from engine.occam.occam import _disk_key, normalize_path, occam_pass
from engine.occam.occam_models import NodeRecord


def _node(path: str, sha: str = "s", lc: int = 10, **kw) -> NodeRecord:
    return NodeRecord(name=path, source_path=path, sha256=sha, line_count=lc, **kw)


def test_disk_key_strips_line_anchor_but_normalize_keeps_symbol_identity() -> None:
    # 디스크 조인 키는 앵커를 벗지만…
    assert _disk_key("bhgman_tool/engine/cli/commands.py:250") == "engine/cli/commands.py"
    # …정체성(grouping)은 앵커를 유지 → 같은 파일의 서로 다른 심볼은 별개 노드로 남는다.
    assert normalize_path("bhgman_tool/engine/cli/commands.py:250") == "engine/cli/commands.py:250"
    assert normalize_path("x.py:250") != normalize_path("x.py:818")


def test_symbol_node_not_false_orphan_when_base_file_lives() -> None:
    # commands.py 는 디스크에 있다 → 심볼노드 commands.py:250 은 orphan 아님 (fix #3).
    disk = frozenset({"engine/cli/commands.py"})
    rep = occam_pass([_node("bhgman_tool/engine/cli/commands.py:250")], disk_paths=disk)
    assert rep.orphan_count == 0


def test_truly_absent_symbol_still_flagged_no_false_negative() -> None:
    # 파일 자체가 없으면 여전히 flag (fix #3 이 진짜 orphan 을 숨기지 않는다).
    disk = frozenset({"engine/cli/commands.py"})
    rep = occam_pass([_node("bhgman_tool/engine/gone/deleted.py:5")], disk_paths=disk)
    assert rep.orphan_count == 1


def test_recency_key_is_always_str() -> None:
    n = _node("bhgman_tool/a.py", last_validated=12345)  # type: ignore[arg-type]  # 비-str 타임스탬프
    assert isinstance(n.recency_key, str)
    assert n.recency_key == "12345"


def test_dup_group_mixed_timestamp_types_does_not_crash() -> None:
    class _DT:  # neo4j.time.DateTime 스탠드인 — str 과 `>` 비교 불가한 타입
        def __str__(self) -> str:
            return "2026-07-15T00:00:00+00:00"

    n1 = _node("bhgman_tool/a.py", sha="s1", lc=10, last_validated=_DT())  # type: ignore[arg-type]
    n2 = _node("bhgman_tool/a.py", sha="s2", lc=20, last_validated="")
    # 동일 정규화경로 → dup group → _pick_current 가 max(recency tuple) 비교. 크래시 없어야.
    rep = occam_pass([n1, n2])
    assert rep.groups_with_dups == 1
