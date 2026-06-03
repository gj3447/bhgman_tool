"""Locks the UNGAMEABLE property of the Lean oracle (거기 test). Skips if no lean toolchain.

KG: project-apt-ultracode-roadmap-2026-06-02
"""

import pytest

from engine.efficacy.lean_oracle import evaluate, lean_available

pytestmark = pytest.mark.skipif(not lean_available(), reason="lean toolchain not installed")


def test_real_proof_is_proven():
    v = evaluate("t_real", "(n : Nat) : n + 0 = n", "by rfl")
    assert v.compiles and v.proven and not v.sorry_tainted


def test_sorry_compiles_but_not_proven():
    # the core ungameable guarantee: sorry compiles (warning) but taints axioms → NOT proven
    v = evaluate("t_sorry", "(n : Nat) : n + 0 = n", "by sorry")
    assert v.compiles and v.sorry_tainted and not v.proven


def test_wrong_proof_does_not_compile():
    v = evaluate("t_wrong", "(n : Nat) : 0 + n = n", "by rfl")  # rfl can't close 0 + n
    assert not v.compiles and not v.proven


def test_headroom_task_real_proof_proven():
    # a custom-def nonlinear property omega/simp don't one-shot, but a real induction proves
    v = evaluate(
        "t_gauss",
        "(n : Nat) : 2 * sumTo n = n * (n+1)",
        "by induction n with | zero => rfl | succ k ih => simp [sumTo, Nat.mul_succ, Nat.succ_mul] at * <;> omega",
        preamble="def sumTo : Nat -> Nat | 0 => 0 | (n+1) => (n+1) + sumTo n",
    )
    assert v.proven


def test_headroom_task_omega_alone_fails():
    v = evaluate(
        "t_gauss_omega",
        "(n : Nat) : 2 * sumTo n = n * (n+1)",
        "by omega",
        preamble="def sumTo : Nat -> Nat | 0 => 0 | (n+1) => (n+1) + sumTo n",
    )
    assert not v.proven  # confirms genuine headroom (not one-shot by omega)
