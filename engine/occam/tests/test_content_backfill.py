"""오캄 content 임베딩 backfill 테스트 — PROM 6 P2 / A1 정밀화 (소스 내용 임베딩).

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A1-2026-07-19
"""

from __future__ import annotations

from engine.occam.embed_backfill import ContentBackfillReport, content_backfill, content_spec


class _Reg:
    """fake RepoRegistry — repo_relpath → tmp 파일 매핑."""

    def __init__(self, root):
        self.root = root

    def locate(self, repo_id, relpath):
        return self.root / relpath


class _Runner:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __call__(self, cypher, params=None):
        self.calls.append((cypher, params))
        if "codeEmb IS NULL" in cypher:
            return self.rows
        return []


def _embed(texts):
    return [[0.1, 0.2, 0.3] for _ in texts]


def test_content_spec_uses_codeemb_prop():
    spec = content_spec(3)
    assert spec.embedding_prop == "codeEmb"
    assert spec.index_name == "sourcecodenode_content_emb"


def test_resolves_content_from_registry(tmp_path):
    (tmp_path / "engine").mkdir()
    (tmp_path / "engine" / "a.py").write_text("def f(): return 1\n")
    rows = [{"id": "a@bind", "repo_id": "gh/x", "relpath": "engine/a.py"}]
    rep = content_backfill(_Runner(rows), _embed, registry=_Reg(tmp_path), apply=False)
    assert rep.resolved == 1 and rep.unresolved == 0
    assert rep.written == 0  # PROPOSE 기본 — write 없음


def test_missing_file_counts_unresolved_no_fabrication(tmp_path):
    # 디스크에 없는 파일 → 유령 임베딩 날조 금지, unresolved 로 정직 집계.
    rows = [{"id": "gone@bind", "repo_id": "gh/x", "relpath": "engine/gone.py"}]
    rep = content_backfill(_Runner(rows), _embed, registry=_Reg(tmp_path), apply=False)
    assert rep.resolved == 0 and rep.unresolved == 1


def test_apply_writes_via_vector_proc(tmp_path):
    (tmp_path / "b.py").write_text("x = 1\n")
    rows = [{"id": "b@bind", "repo_id": "gh/x", "relpath": "b.py"}]
    runner = _Runner(rows)
    rep = content_backfill(runner, _embed, registry=_Reg(tmp_path), apply=True)
    assert rep.written == 1
    writes = [c for c, _ in runner.calls if "setNodeVectorProperty" in c]
    assert writes and "codeEmb" in writes[0]


def test_content_bounded_by_max_chars(tmp_path):
    (tmp_path / "big.py").write_text("x" * 20000)
    rows = [{"id": "big@bind", "repo_id": "gh/x", "relpath": "big.py"}]
    captured = []

    def embed(texts):
        captured.extend(texts)
        return [[0.0] * 3 for _ in texts]

    content_backfill(_Runner(rows), embed, registry=_Reg(tmp_path), max_chars=100, apply=True)
    # captured[0]은 dim probe("probe") — 실제 콘텐츠는 마지막 배치에 있음.
    assert captured and len(captured[-1]) == 100  # bound 준수


def test_report_summary_shape():
    rep = ContentBackfillReport(resolved=2, written=0, unresolved=1)
    assert "resolved=2" in rep.summary and "unresolved=1" in rep.summary
