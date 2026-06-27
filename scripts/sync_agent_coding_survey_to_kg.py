#!/usr/bin/env python3
"""--verify / --apply: agent-coding 지식 코퍼스 → 로컬 KG (GENERATED mirror, method B).

라이브 neo4j 는 agent-coding-kg-load.cypher(idempotent MERGE) 로 적재. 로컬 KG 는 이 스크립트로
(runner.py _ROUTES 화이트리스트 우회 — LocalKgStore 직접 호출). SoT = agent_coding_survey.json.

예:
  python scripts/sync_agent_coding_survey_to_kg.py --verify        # drift 검사(변이 없음)
  python scripts/sync_agent_coding_survey_to_kg.py --apply         # 멱등 적재
  BHGMAN_KG_PATH=/tmp/kg.json python scripts/...py --apply         # 대상 store 지정

# KG: agent-coding-survey-local-ingest-2026-06-27
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root → engine 패키지

from engine.kg_local.store import LocalKgStore  # noqa: E402
from engine.kg_local.survey_sync import apply_sot, load_sot, verify_sot  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="agent-coding survey → local KG GENERATED mirror")
    ap.add_argument("--sot", default=str(Path(__file__).with_name("agent_coding_survey.json")))
    ap.add_argument("--kg", default=None, help="LocalKgStore 경로 (기본 BHGMAN_KG_PATH/~/.bhgman/kg.json)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--verify", action="store_true", help="drift 검사만 (MISSING 보고, 변이 없음)")
    g.add_argument("--apply", action="store_true", help="멱등 적재 후 저장")
    a = ap.parse_args(argv)

    sot = load_sot(a.sot)
    store = LocalKgStore(path=a.kg)

    if a.verify:
        missing = verify_sot(store, sot)
        if missing:
            print(f"DRIFT: {len(missing)} missing")
            for m in missing:
                print(f"  - {m}")
            return 1
        print(f"clean: {len(sot['nodes'])} nodes / {len(sot['edges'])} edges present")
        return 0

    stats = apply_sot(store, sot)
    store.save()
    print(f"applied: {stats['nodes']} nodes, {stats['edges_added']} new edges → {store.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
