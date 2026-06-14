"""나생문 truth-렌즈 검증 — axiom-audit(결정론) + falsifiability(routing).

axiom-audit: 공리 vs 정리 위상, 전이적 taint, 비판 자체 실측. falsifiability: 주장 라우팅.

# KG: 외부 리뷰 tension #1 + #4
"""

from __future__ import annotations

from pathlib import Path

from engine.naesengmoon.axiom_audit import audit_lean_dir, check_claim
from engine.naesengmoon.falsifiability import classify


# ── axiom-audit (합성 lean 디렉터리) ─────────────────────────────────────────
def _write(d: Path, name: str, body: str) -> None:
    (d / name).write_text(body, encoding="utf-8")


def test_axiom_audit_taints_transitively(tmp_path):
    _write(tmp_path, "Base.lean", "axiom FOO : Type\ntheorem t1 : True := trivial\n")
    _write(
        tmp_path, "Mid.lean", "import Base\ntheorem t2 : True := trivial\n"
    )  # tainted via import
    _write(tmp_path, "Free.lean", "theorem t3 : True := trivial\nlemma l1 : True := trivial\n")
    r = audit_lean_dir(tmp_path)
    assert r.total_axioms == 1
    assert r.total_theorems == 4
    # Base(1) + Mid(1) rest on FOO; Free(2) axiom-free
    assert r.axiom_resting_theorems == 2
    assert r.axiom_free_theorems == 2
    assert "FOO" in r.summary


def test_axiom_audit_detects_proof_sorry(tmp_path):
    _write(
        tmp_path, "S.lean", "theorem t : True := by sorry\n-- sorry in a comment does not count\n"
    )
    r = audit_lean_dir(tmp_path)
    assert r.total_sorry == 1  # proof-position only


def test_check_claim_flags_overstatement(tmp_path):
    _write(tmp_path, "Base.lean", "axiom FOO : Type\ntheorem t1 : True := trivial\n")
    _write(tmp_path, "Free.lean", "theorem t2 : True := trivial\n")
    r = audit_lean_dir(tmp_path)
    assert "OVERSTATED" in check_claim(r, claimed_resting=2)  # claimed 2, actual 1
    assert "CONFIRMED" in check_claim(r, claimed_resting=1)


def test_axiom_audit_on_real_repo_lean():
    """실제 repo lean/: axiom CHU 1개, ~5 정리가 그 위 (리뷰어 'all 71' 과장 실측)."""
    lean = Path(__file__).resolve().parents[3] / "lean"
    if not lean.is_dir():
        return  # repo lean/ 부재 환경 skip
    r = audit_lean_dir(lean)
    assert r.total_axioms == 1  # CHU
    # total_theorems 는 repo 성장에 따라 늘어남 — 정확값 박으면 새 lean 추가마다 stale.
    # auditor 가 알려진 집합 이상을 센다는 것만 lower-bound 로 확인 (89 as of 2026-06-01).
    assert r.total_theorems >= 79
    assert (
        r.axiom_resting_theorems < r.total_theorems
    )  # NOT all (강조: 더 많아져도 axiom-resting 그대로)
    assert (
        r.axiom_resting_theorems == 5
    )  # Harness_LawvereFixedPoint only (load-bearing 불변량 — 정확값)


# ── falsifiability routing ───────────────────────────────────────────────────
def test_classify_consistency_only():
    c = classify("This theorem type-checks and is internally consistent")
    assert c.claim_class == "consistency-only" and c.truth_apt is False


def test_classify_efficacy_routes_to_ab():
    c = classify("APT improves work quality better than baseline")
    assert c.claim_class == "efficacy" and c.truth_apt is True
    assert "A/B" in c.oracle


def test_classify_unfalsifiable_demoted():
    c = classify("axiom CHU is the foundation and should be adopted")
    assert c.claim_class == "unfalsifiable" and c.truth_apt is False
    assert "not truth-apt" in c.cheapest_falsifier


def test_classify_empirical_default_routes_external():
    c = classify("LangGraph is a tier-2 instance of the harness model")
    assert c.truth_apt is True
    assert "referent" in c.oracle.lower() or "reproduction" in c.oracle.lower()


def test_axiom_audit_taints_through_dotted_import(tmp_path):
    """W3-E: a namespaced `import Foo.Bar.Base` must propagate taint by its final segment."""
    _write(tmp_path, "Base.lean", "axiom FOO : Type\ntheorem t1 : True := trivial\n")
    _write(tmp_path, "Mid.lean", "import Foo.Bar.Base\ntheorem t2 : True := trivial\n")
    r = audit_lean_dir(tmp_path)
    assert r.axiom_resting_theorems == 2  # Base + Mid (dotted import resolved to stem Base)
