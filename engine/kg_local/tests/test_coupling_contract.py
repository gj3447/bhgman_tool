"""kg_local↔engine 결합 계약 가드 — 나생문 AC-bhgman-kglocal-implicit-coupling (2026-05-28).

make_local_runner의 dispatch는 엔진이 emit하는 cypher 템플릿 substring에 묶여있다. test_runner.py는
*복사한* 문자열을 쓰므로 엔진 drift를 못 잡는다. 이 테스트는 occam/eureka의 *실제 cypher 빌더*를
import해 그 출력이 로컬 runner로 라우팅됨을 확인 — 엔진이 템플릿을 바꾸면 여기서 UnsupportedLocalQuery로
실패해 동시갱신을 강제한다(암묵 결합 → 명시 계약).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

_ENG = pathlib.Path(__file__).parents[2]
for _d in ("occam", "eureka"):
    _p = str(_ENG / _d)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from engine.kg_local.runner import UnsupportedLocalQuery, make_local_runner  # noqa: E402
from engine.kg_local.store import LocalKgStore  # noqa: E402


def _runner(tmp_path):
    return make_local_runner(LocalKgStore(tmp_path / "k.json"))


def test_occam_real_fetch_templates_routed(tmp_path):
    from engine.occam import kg_adapter  # occam의 실제 cypher 빌더

    run = _runner(tmp_path)
    run(*kg_adapter.fetch_cypher(None))  # _FETCH_ALL — raise 없으면 routing OK
    run(*kg_adapter.fetch_cypher("engine/x"))  # _FETCH_SCOPED


def test_hades_real_fetch_templates_routed(tmp_path):
    # both hades fetch variants must route through the local backend. The all-concepts form
    # routed; the single-concept _FETCH_ONE interpolates `(a:AbstractClass {name: $concept})`,
    # so the bare "(a:AbstractClass)" route predicate missed it → `hades --concept X --local`
    # crashed with UnsupportedLocalQuery (handler already supported concept-filtering).
    from engine.hades.hades_runner import fetch_accepted_cypher

    run = _runner(tmp_path)
    run(*fetch_accepted_cypher(None))  # _FETCH_ALL — already routed
    run(*fetch_accepted_cypher("some_concept"))  # _FETCH_ONE — was UnsupportedLocalQuery (RED)


def test_hades_single_concept_fetch_filters_to_requested(tmp_path):
    # routing + filtering: with two ACCEPTED AbstractClasses, single-concept fetch returns only one.
    from engine.hades.hades_runner import fetch_accepted_cypher

    store = LocalKgStore(tmp_path / "k.json")
    store.nodes.append({"labels": ["AbstractClass"], "props": {"name": "alpha", "verdictStatus": "ACCEPTED", "extent": ["a"]}})
    store.nodes.append({"labels": ["AbstractClass"], "props": {"name": "beta", "verdictStatus": "ACCEPTED", "extent": ["b"]}})
    run = make_local_runner(store, autosave=False)
    rows = run(*fetch_accepted_cypher("alpha"))
    assert [r["concept"] for r in rows] == ["alpha"]
    assert len(run(*fetch_accepted_cypher(None))) == 2  # all-concepts still returns both


def test_occam_real_supersede_template_routed(tmp_path):
    from engine.occam import kg_adapter
    from engine.occam.occam_models import Confidence, NodeRecord, SupersessionCandidate

    cand = SupersessionCandidate(
        stale=NodeRecord("o", "p", "s1", 1),
        current=NodeRecord("n", "p", "s2", 2),
        normalized_path="p",
        reason="r",
        confidence=Confidence.MEDIUM,
    )
    cy, params = kg_adapter.build_supersede(cand)
    _runner(tmp_path)(cy, params)  # _SUPERSEDE_CYPHER 라우팅 (노드 부재 → [] but no raise)


def test_eureka_real_extraction_template_routed(tmp_path):
    from engine.eureka.formal_context_builder import FormalContextConfig, build_extraction_cypher

    cy, params = build_extraction_cypher(FormalContextConfig())
    rows = _runner(tmp_path)(cy, params)  # facet read 라우팅
    assert rows == []  # 빈 store → 빈 결과 (raise 안 함이 핵심)


def test_drift_sentinel_unrouted_raises(tmp_path):
    # 계약 반대편: 라우트에 없는 임의 cypher는 조용히 빈 결과가 아니라 명시 실패.
    with pytest.raises(UnsupportedLocalQuery):
        _runner(tmp_path)("MATCH (n:NovelLabel) RETURN n", {})
