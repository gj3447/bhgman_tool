"""7군단장 효능 sweep 진입점 — 실 KG에 대해 전원 honest verdict 한 방.

각 군단장 spec(commanders.COMMANDERS)을 같은 3-falsifier 게이트에 통과시켜
MEASURED / BELOW_CHANCE / UNMEASURABLE 을 한 표로 찍는다. label_cypher=None 인
군단장은 oracle 미구축이므로 UNMEASURABLE(no-oracle)이 정직한 현재값.

occam 은 두 줄로 보고한다:
  · occam(registry)  — KG status 라벨(73% occam-생성) = 순환 → UNMEASURABLE 예상.
  · occam(disk)      — run_kg_efficacy 의 disk_present 독립 oracle = 비순환 → MEASURED.

수치 날조 금지: 게이트 실패는 실패로, no-oracle 은 no-oracle 로 보고.

# KG: efficacy-measurement-line-2026-06-01, 7cmd-measurement-driven-conditional-dispatch-2026-05-30
"""

from __future__ import annotations

import sys
from dataclasses import replace

from engine.efficacy.commanders import COMMANDERS
from engine.efficacy.harness import run_efficacy
from engine.efficacy.models import EfficacyResult, LabeledItem
from engine.efficacy.run_kg_efficacy import _FETCH as OCCAM_DISK_FETCH
from engine.efficacy.run_kg_efficacy import OCCAM_DISK_SPEC, rows_to_items


def _items_from_rows(rows: list[dict]) -> list[LabeledItem]:
    """registry cypher row(item_id/is_positive/signal/provenance) → LabeledItem."""
    items: list[LabeledItem] = []
    for r in rows:
        sig = r.get("signal")
        items.append(
            LabeledItem(
                item_id=str(r["item_id"]),
                is_positive=bool(r["is_positive"]),
                signal=None if sig is None else float(sig),
                provenance=str(r.get("provenance") or ""),
            )
        )
    return items


def main() -> int:  # pragma: no cover — IO 진입점
    from engine.cli.runtime import make_kg_runners  # noqa: PLC0415

    runners = make_kg_runners()
    if runners is None:
        print("neo4j 미연결 (NEO4J_PASSWORD?) — bolt 직결 필요", file=sys.stderr)
        return 2
    run_cypher, _write, close = runners

    results: list[EfficacyResult] = []
    try:
        # 1) occam disk-oracle (비순환) — 라인의 reference 측정.
        disk_rows = run_cypher(OCCAM_DISK_FETCH, {})
        disk_res = run_efficacy(OCCAM_DISK_SPEC, rows_to_items(disk_rows))
        results.append(replace(disk_res, commander="occam(disk)"))

        # 2) registry 7군단장 전원.
        for spec in COMMANDERS:
            if spec.label_cypher is None:
                results.append(run_efficacy(spec, []))  # no-oracle → UNMEASURABLE
                continue
            rows = run_cypher(spec.label_cypher, {})
            res = run_efficacy(spec, _items_from_rows(rows))
            if spec.commander == "occam":
                res = replace(res, commander="occam(registry)")
            results.append(res)
    finally:
        close()

    # 정직 표 출력.
    print(f"\n{'commander':<18} {'verdict':<13} {'AUC':>6}  {'pos/neg':>9}  reason")
    print("-" * 92)
    for r in results:
        auc = f"{r.auc:.3f}" if r.auc is not None else "  n/a"
        pn = f"{r.n_positive}/{r.n_negative}"
        print(f"{r.commander:<18} {r.verdict.value:<13} {auc:>6}  {pn:>9}  {r.reason}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
