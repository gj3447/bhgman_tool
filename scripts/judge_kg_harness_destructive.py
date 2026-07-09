#!/usr/bin/env python3
"""judge — kg_harness delete-blind 실측 (LakatosTree_BhgmanSeamIntegrity_20260708/kgh_destructive_rule).

metric: destructive_allowed_plus_benign_refused
  = (파괴 corpus 중 validate_write 가 ALLOWED 로 통과시킨 수)      ← delete-blind 축
  + (정상 corpus 중 validate_write 가 ERROR 로 거부한 수)          ← revert-proof counter 축
양축 합산이라 "전부 거부" 치팅(가드를 무조건 refuse 로 만들기)도 벌점이다. 목표 0.

verdict 는 손입력이 아니라 이 스크립트가 live import 한 production validate_write 실행에서
도출된다. 영수증: verification/kgh_destructive_receipt.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine.kg_harness.write_guard import (  # noqa: E402
    supersede_node,
    upsert_node,
    validate_write,
)

DESTRUCTIVE = [
    "MATCH (n:Concept {name:'x'}) DETACH DELETE n",
    "MATCH (n:Concept {name:'x'}) DELETE n",
    "DROP CONSTRAINT kgh_Concept_name_unique IF EXISTS",
    "MATCH (n:Concept {name:'x'}) REMOVE n.summary",
    "MATCH (a:Concept),(b:Concept) CALL apoc.refactor.mergeNodes([a,b],{}) YIELD node RETURN node",
    "MATCH (n:Concept {status:'dead'}) CALL apoc.nodes.delete(n, 100)",
    'CALL apoc.periodic.iterate("MATCH (n:Concept) RETURN n", "DETACH DELETE n", {batchSize:100})',
    "CREATE /* sneaky */ (n:Concept {name:'evil'})",  # comment-evasion (NAKED_CREATE 우회)
    "MATCH (n:Concept) DETACH /* c */ DELETE n",  # comment-evasion (파괴)
    "MERGE (n:Ref {id:$id}) SET n.url = 'http://e.test/x' DETACH DELETE n",  # 문자열 뒤 파괴
]

BENIGN = [
    upsert_node("Concept", "name", "x", {"summary": "s"})[0],
    supersede_node("Concept", "name", "old", "new", "dup")[0],
    "MERGE (n:Concept {name:$name}) SET n += $props",
    "MERGE (n:Ref {id:$id}) SET n.url = 'http://e.test/x'",
    "MATCH (n:Concept {id:$i}) // note: never DETACH DELETE here\nSET n.y = $y",
]


def main() -> None:
    destructive_allowed = [c for c in DESTRUCTIVE if validate_write(c).ok]
    benign_refused = [c for c in BENIGN if not validate_write(c).ok]
    value = len(destructive_allowed) + len(benign_refused)
    receipt = {
        "tree": "LakatosTree_BhgmanSeamIntegrity_20260708",
        "node": "kgh_destructive_rule",
        "metric": "destructive_allowed_plus_benign_refused",
        "value": value,
        "destructive_corpus": len(DESTRUCTIVE),
        "destructive_allowed": destructive_allowed,
        "benign_corpus": len(BENIGN),
        "benign_refused": benign_refused,
    }
    out = REPO / "verification" / "kgh_destructive_receipt.json"
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
