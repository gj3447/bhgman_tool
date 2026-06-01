"""drift_oracle 순수부 테스트 — sha-sync 독립 oracle."""

from __future__ import annotations

from pathlib import Path

from engine.efficacy.drift_oracle import compute_sync, hash_file, sync_accuracy


def test_compute_sync_matches_and_mismatches():
    nodes = [
        {"name": "a", "sourcePath": "bhgman_tool/engine/a.py", "sha256": "AAA"},
        {"name": "b", "sourcePath": "/Users/x/bhgman_tool/engine/b.py", "sha256": "OLD"},
        {"name": "gone", "sourcePath": "bhgman_tool/engine/gone.py", "sha256": "X"},
    ]
    disk = {"engine/a.py": "AAA", "engine/b.py": "NEW"}  # gone은 디스크에 없음
    rows = compute_sync(nodes, disk)
    by = {r["name"]: r for r in rows}
    assert by["a"]["in_sync"] is True
    assert by["b"]["in_sync"] is False  # OLD != NEW = longinus가 놓친 drift
    assert "gone" not in by  # 디스크 없음 → orphan(occam 영역), skip


def test_compute_sync_excludes_external():
    nodes = [{"name": "ext", "sourcePath": "/Users/x/SYMPOSIUM/x.md", "sha256": "Z"}]
    assert compute_sync(nodes, {"x.md": "Z"}) == []


def test_sync_accuracy():
    rows = [{"in_sync": True}, {"in_sync": True}, {"in_sync": False}]
    insync, total, ratio = sync_accuracy(rows)
    assert (insync, total) == (2, 3)
    assert abs(ratio - 2 / 3) < 1e-9


def test_sync_accuracy_empty():
    assert sync_accuracy([]) == (0, 0, 0.0)


def test_hash_file_roundtrip(tmp_path: Path):
    f = tmp_path / "x.txt"
    f.write_bytes(b"hello occam")
    import hashlib

    assert hash_file(f) == hashlib.sha256(b"hello occam").hexdigest()


def test_hash_file_missing_returns_none(tmp_path: Path):
    assert hash_file(tmp_path / "nope.txt") is None
