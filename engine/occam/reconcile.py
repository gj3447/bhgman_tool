"""오캄 reconcile — cross-KG-store 콘텐츠 주소 set-diff 조정 (reconciliation).

PROM 6 P3 (rf-occam-adv-A4): SourceCodeNode 바인딩이 두 store(예: 홈 정본 KG vs airo
참조 KG)에 존재할 때 수동 복사로 드리프트한다. identity 가 content-address 키
``(repo_id, repo_relpath, sha256)`` 이므로 두 store 의 차이는 **집합 연산**이지
fuzzy matching 이 아니다:

  - ``missing_in_b``  : a 에만 있는 키 (경로 자체가 b 에 없음)
  - ``missing_in_a``  : 역방향
  - ``content_drift`` : 같은 ``(repo_id, repo_relpath)`` 가 양쪽에 있으나 sha256 이
                        다름 — 양쪽 sha 를 모두 보고 (어느 쪽이 낡았는지는 판정 안 함)
  - ``identical``     : 양쪽에 동일 삼중키로 존재하는 수

read-only 검사 — 차이를 리포트할 뿐 수정하지 않는다(수정은 occam supersede / longinus
재바인딩 경로). 순수 core + cypher 빌더 + 주입식 CypherRunner (kg_adapter 와 동일 IO
경계). 라벨 게이트는 views.current_only 단일 진실원(C1) 경유.

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A4-2026-07-19,
#     occam-kam-canonical-2026-05-26, lesson-occam-refetch-archived-status-exact-match-2026-07-19
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from engine.occam.views import current_only

CypherRunner = Callable[[str, "dict"], "list[dict]"]

# content-address 삼중키가 완전한 live 노드만 — 키 결손 노드는 조정 불가(집합 원소 아님).
# 라벨 게이트는 current_only (NOT n:ARCHIVED 를 손으로 쓰지 않는다, views C1).
KEYS_CYPHER = (
    f"MATCH (n:SourceCodeNode) WHERE {current_only('n')} "
    "AND n.repo_id IS NOT NULL AND n.repo_relpath IS NOT NULL AND n.sha256 IS NOT NULL "
    "RETURN n.name AS name, n.repo_id AS repo_id, "
    "n.repo_relpath AS repo_relpath, n.sha256 AS sha256 "
    "ORDER BY repo_id, repo_relpath, sha256, name"
)


def fetch_keys(run_cypher: CypherRunner) -> list[dict]:
    """한 store 에서 content-address 키 row 들을 가져온다.

    row shape = ``{name, repo_id, repo_relpath, sha256}``. 필수 키(repo_id/repo_relpath/
    sha256) 결손 row 는 방어적 skip (kg_adapter.parse_node_records 와 동일 규율).
    name 은 nullable — 표시용일 뿐 identity 가 아니다.
    """
    rows = run_cypher(KEYS_CYPHER, {}) or []
    return [
        r
        for r in rows
        if r.get("repo_id") is not None
        and r.get("repo_relpath") is not None
        and r.get("sha256") is not None
    ]


# ── 순수 core (no IO) ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class MissingEntry:
    """한쪽 store 에만 존재하는 content-address 키 하나.

    names = 그 store 에서 이 키를 가진 노드 name 들 (정렬, 추적성).
    name 이 NULL 인 노드는 repo_relpath 로 폴백 (kg_adapter._ident 와 동일 규율).
    """

    repo_id: str
    repo_relpath: str
    sha256: str
    names: tuple[str, ...]


@dataclass(frozen=True)
class DriftEntry:
    """같은 ``(repo_id, repo_relpath)`` 가 양쪽에 있으나 sha256 이 다른 경우.

    sha256_a/sha256_b = 각 store *에만* 있는 sha 들 (정렬 tuple — 한 store 안에
    같은 경로의 sha 가 복수일 수 있으므로 단수 가정 안 함; 통상 각 1개).
    양쪽에 공통인 sha 는 identical 로 집계되고 여기엔 안 나온다.
    """

    repo_id: str
    repo_relpath: str
    sha256_a: tuple[str, ...]
    sha256_b: tuple[str, ...]
    names_a: tuple[str, ...]
    names_b: tuple[str, ...]


@dataclass(frozen=True)
class ReconcileReport:
    """두 store 의 set-diff 결과. read-only value object — 판정/수정은 하지 않는다."""

    missing_in_b: tuple[MissingEntry, ...] = ()
    missing_in_a: tuple[MissingEntry, ...] = ()
    content_drift: tuple[DriftEntry, ...] = ()
    identical: int = 0

    @property
    def in_sync(self) -> bool:
        """차이 0 = 두 store 가 content-address 상 동일."""
        return not (self.missing_in_b or self.missing_in_a or self.content_drift)

    @property
    def summary(self) -> str:
        """한 줄 요약 (한국어)."""
        status = "동기화됨" if self.in_sync else "드리프트 감지"
        return (
            f"reconcile: {status} — 동일 {self.identical} | "
            f"내용 드리프트 {len(self.content_drift)} | "
            f"a에만 {len(self.missing_in_b)} | b에만 {len(self.missing_in_a)}"
        )


def _display_name(row: dict) -> str:
    """표시용 식별자 (never None). name 없으면 repo_relpath 폴백."""
    return row.get("name") or row["repo_relpath"]


def _index(rows: list[dict]) -> dict[tuple[str, str], dict[str, list[str]]]:
    """rows → {(repo_id, repo_relpath): {sha256: [names...]}}. 키 결손 row 는 skip."""
    idx: dict[tuple[str, str], dict[str, list[str]]] = {}
    for r in rows:
        rid = r.get("repo_id")
        rel = r.get("repo_relpath")
        sha = r.get("sha256")
        if rid is None or rel is None or sha is None:
            continue
        idx.setdefault((rid, rel), {}).setdefault(sha, []).append(_display_name(r))
    return idx


def diff_stores(a: list[dict], b: list[dict]) -> ReconcileReport:
    """두 store 의 키 row 리스트를 set-diff 한다 (순수 함수, 결정론적 정렬).

    분류 규칙 (경로 쌍 ``(repo_id, repo_relpath)`` 기준):
      - 쌍이 a 에만 → 그 쌍의 각 sha 가 ``missing_in_b`` 항목
      - 쌍이 b 에만 → ``missing_in_a``
      - 쌍이 양쪽에: 공통 sha 수만큼 ``identical`` 집계, sha 집합이 다르면
        ``content_drift`` 항목 1개 (양쪽 고유 sha 모두 보고). 드리프트 쌍은
        missing 리스트에 **중복 집계하지 않는다** (같은 파일의 버전 차이 ≠ 부재).
    """
    ia, ib = _index(a), _index(b)

    missing_in_b: list[MissingEntry] = []
    missing_in_a: list[MissingEntry] = []
    drift: list[DriftEntry] = []
    identical = 0

    for pair in set(ia) | set(ib):
        rid, rel = pair
        shas_a = ia.get(pair, {})
        shas_b = ib.get(pair, {})
        if not shas_b:
            missing_in_b.extend(
                MissingEntry(rid, rel, sha, tuple(sorted(names)))
                for sha, names in shas_a.items()
            )
            continue
        if not shas_a:
            missing_in_a.extend(
                MissingEntry(rid, rel, sha, tuple(sorted(names)))
                for sha, names in shas_b.items()
            )
            continue
        common = set(shas_a) & set(shas_b)
        identical += len(common)
        only_a = sorted(set(shas_a) - common)
        only_b = sorted(set(shas_b) - common)
        if only_a or only_b:
            drift.append(
                DriftEntry(
                    repo_id=rid,
                    repo_relpath=rel,
                    sha256_a=tuple(only_a),
                    sha256_b=tuple(only_b),
                    names_a=tuple(sorted(n for s in only_a for n in shas_a[s])),
                    names_b=tuple(sorted(n for s in only_b for n in shas_b[s])),
                )
            )

    def _mkey(e: MissingEntry) -> tuple[str, str, str]:
        return (e.repo_id, e.repo_relpath, e.sha256)

    return ReconcileReport(
        missing_in_b=tuple(sorted(missing_in_b, key=_mkey)),
        missing_in_a=tuple(sorted(missing_in_a, key=_mkey)),
        content_drift=tuple(sorted(drift, key=lambda d: (d.repo_id, d.repo_relpath))),
        identical=identical,
    )


def reconcile(run_cypher_a: CypherRunner, run_cypher_b: CypherRunner) -> ReconcileReport:
    """두 store 를 각각 fetch 하여 diff (편의 wrapper). read-only — 절대 write 안 함."""
    return diff_stores(fetch_keys(run_cypher_a), fetch_keys(run_cypher_b))


__all__ = [
    "KEYS_CYPHER",
    "CypherRunner",
    "DriftEntry",
    "MissingEntry",
    "ReconcileReport",
    "diff_stores",
    "fetch_keys",
    "reconcile",
]
