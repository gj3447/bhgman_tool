"""오캄 수렴(fixpoint) 테스트 — PROM 6 C2.

occam(occam(G)) == occam(G): 아카이브(=stale 제거) 후 재실행하면 같은 그룹에서 신규
후보가 0이어야 한다. 이번 세션의 무덤-재검출 버그(brittle status-string 필터)의
falsifier — 필터가 다시 tombstone 을 후보로 흘리면 이 테스트가 RED.

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A2-2026-07-19,
#     lesson-occam-refetch-archived-status-exact-match-2026-07-19
"""

from __future__ import annotations

from engine.occam.occam import occam_pass
from engine.occam.occam_models import NodeRecord


def _key(n: NodeRecord) -> tuple[str, str]:
    return (n.source_path, n.sha256)


def _remove_stale(nodes: list[NodeRecord], report) -> list[NodeRecord]:
    """supersede 된 stale 노드를 live 집합에서 제거 = 아카이브(fetch 필터가 :ARCHIVED 제외)의
    순수-함수 아날로그."""
    stale = {_key(c.stale) for c in report.candidates}
    return [n for n in nodes if _key(n) not in stale]


def test_occam_pass_reaches_fixpoint_in_one_step():
    nodes = [
        NodeRecord("old", "bhgman_tool/x.py", "sha_old", 10),
        NodeRecord("new", "bhgman_tool/x.py", "sha_new", 99),
    ]
    r1 = occam_pass(nodes)
    assert r1.candidates, "pass 1 이 중복을 잡아야 한다"

    survivors = _remove_stale(nodes, r1)
    r2 = occam_pass(survivors)
    assert len(r2.candidates) == 0, "수렴 실패: 아카이브 후 재실행이 tombstone 을 재검출"


def test_idempotent_on_already_deduped_corpus():
    # 이미 유일한 노드만 남은 코퍼스는 어떤 후보도 만들지 않는다 (재flag 없음).
    nodes = [
        NodeRecord("a", "bhgman_tool/a.py", "sa", 10),
        NodeRecord("b", "bhgman_tool/b.py", "sb", 20),
    ]
    r = occam_pass(nodes)
    assert len(r.candidates) == 0


def test_multi_group_converges():
    nodes = [
        NodeRecord("x_old", "bhgman_tool/x.py", "xo", 10),
        NodeRecord("x_new", "bhgman_tool/x.py", "xn", 40),
        NodeRecord("y_old", "bhgman_tool/y.py", "yo", 5),
        NodeRecord("y_new", "bhgman_tool/y.py", "yn", 30),
    ]
    r1 = occam_pass(nodes)
    assert len(r1.candidates) >= 2
    r2 = occam_pass(_remove_stale(nodes, r1))
    assert len(r2.candidates) == 0
