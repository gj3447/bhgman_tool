"""프로메테우스 엔진 × 로컬 KG backend — gap-scan read + :ResearchFinding ingest write.

neo4j 없이 풀 파이프라인: 로컬 store의 OpenQuestion 읽어 gap 도출 → StaticFetcher →
:ResearchFinding upsert. idempotent(findingId 키) 확인.

# KG: project-legion-unification-kg-engine-2026-06-01, bhgman-local-kg-backend-2026-05-28
"""

from __future__ import annotations

from engine.kg_local.runner import make_local_runner
from engine.kg_local.store import LocalKgStore
from engine.prometheus import FetchedDoc, StaticFetcher, run_acquire


def _store_with_gaps(tmp_path):
    store = LocalKgStore(tmp_path / "kg.json")
    store.merge_node("OpenQuestion", "name", "q-koide", {"question": "Is Koide numerology"})
    store.merge_node("VerdictPending", "name", "v-eureka", {"question": "eureka span 7"})
    return store


def test_gap_scan_route_reads_local_questions(tmp_path):
    runner = make_local_runner(_store_with_gaps(tmp_path), autosave=False)
    report = run_acquire(runner)  # fetcher 없음 → gap+query surface
    ids = {g.id for g in report.gaps}
    assert ids == {"q-koide", "v-eureka"}


def test_research_finding_ingest_writes_to_local_store(tmp_path):
    store = _store_with_gaps(tmp_path)
    runner = make_local_runner(store, autosave=False)
    corpus = {
        "Is Koide numerology": [
            FetchedDoc(
                "https://phys/koide", "Koide ratio holds to high precision empirically here."
            )
        ],
        "eureka span 7 evidence resolution": [
            FetchedDoc(
                "https://kg/eureka", "Seven commanders close the verb space deterministically."
            )
        ],
    }
    report = run_acquire(
        runner, fetcher=StaticFetcher(corpus), write_cypher=runner, apply=True, cycle_id="cyc-l"
    )
    assert report.dry_run is False
    assert report.ingested == len(report.findings) >= 2
    persisted = [n for n in store.nodes if "ResearchFinding" in n["labels"]]
    assert len(persisted) == len(report.findings)
    assert persisted[0]["props"]["cycleId"] == "cyc-l"
    assert persisted[0]["props"]["citation_url"].startswith("https://")


def test_ingest_is_idempotent_on_local_store(tmp_path):
    store = _store_with_gaps(tmp_path)
    runner = make_local_runner(store, autosave=False)
    corpus = {
        "Is Koide numerology": [
            FetchedDoc("https://phys/koide", "A stable claim sentence long enough to pass filter.")
        ]
    }
    fetcher = StaticFetcher(corpus)
    run_acquire(runner, fetcher=fetcher, write_cypher=runner, apply=True, cycle_id="cyc-i")
    before = len([n for n in store.nodes if "ResearchFinding" in n["labels"]])
    run_acquire(runner, fetcher=fetcher, write_cypher=runner, apply=True, cycle_id="cyc-i")
    after = len([n for n in store.nodes if "ResearchFinding" in n["labels"]])
    assert before == after  # 재실행해도 노드 안 늚 (findingId MERGE)
