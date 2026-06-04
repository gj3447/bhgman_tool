"""Lean proving task set for the 거기 (headroom) composition test.

Each task FIXES the statement (model supplies only the proof → statement-fidelity by construction).
`headroom` tasks use a custom recursive def + a property that `omega`/`simp` do NOT one-shot (verified
2026-06-03), so a strong-ish model must CONSTRUCT a multi-step induction proof — genuine headroom.
`easy` tasks are omega/simp-closable saturation baselines. `reference_proof` is a verified real proof
(for the harness's own sanity check; it is NEVER shown to the model).

# KG: project-apt-ultracode-roadmap-2026-06-02
"""

from __future__ import annotations

from dataclasses import dataclass

_SUMTO = "def sumTo : Nat -> Nat | 0 => 0 | (n+1) => (n+1) + sumTo n"


@dataclass(frozen=True)
class LeanTask:
    name: str
    preamble: str
    signature: str
    difficulty: str  # "easy" | "headroom"
    reference_proof: str


TASKS = [
    LeanTask("zero_add", "", "(n : Nat) : 0 + n = n", "easy", "by omega"),
    LeanTask("app_nil", "", "(l : List Nat) : l ++ [] = l", "easy", "by simp"),
    LeanTask(
        "gauss",
        _SUMTO,
        "(n : Nat) : 2 * sumTo n = n * (n+1)",
        "headroom",
        "by induction n with | zero => rfl | succ k ih => simp [sumTo, Nat.mul_succ, Nat.succ_mul] at * <;> omega",
    ),
    LeanTask(
        "double",
        "def dbl : Nat -> Nat | 0 => 0 | (n+1) => dbl n + 2",
        "(n : Nat) : dbl n = 2 * n",
        "headroom",
        "by induction n with | zero => rfl | succ k ih => simp [dbl, ih] <;> omega",
    ),
    LeanTask(
        "cnt_len",
        "def cnt : List Nat -> Nat | [] => 0 | (_ :: t) => cnt t + 1",
        "(l : List Nat) : cnt l = l.length",
        "headroom",
        "by induction l with | nil => rfl | cons h t ih => simp [cnt, ih]",
    ),
    LeanTask(
        "sumto_mono",
        _SUMTO,
        "(n : Nat) : sumTo n <= sumTo (n+1)",
        "headroom",
        "by simp [sumTo] <;> omega",
    ),
    # ── band enrichment 2026-06-05 (powered re-test): 6 more custom-def headroom tasks ──
    LeanTask(
        "sumlist_app",
        "def sumL : List Nat -> Nat | [] => 0 | h::t => h + sumL t",
        "(l1 l2 : List Nat) : sumL (l1 ++ l2) = sumL l1 + sumL l2",
        "headroom",
        "by induction l1 with | nil => simp [sumL] | cons h t ih => simp [sumL, ih] <;> omega",
    ),
    LeanTask(
        "addone_len",
        "def addOne : List Nat -> List Nat | [] => [] | h::t => (h+1) :: addOne t",
        "(l : List Nat) : (addOne l).length = l.length",
        "headroom",
        "by induction l with | nil => rfl | cons h t ih => simp [addOne, ih]",
    ),
    LeanTask(
        "repl_len",
        "def repl : Nat -> List Nat | 0 => [] | (n+1) => 0 :: repl n",
        "(n : Nat) : (repl n).length = n",
        "headroom",
        "by induction n with | zero => rfl | succ k ih => simp [repl, ih]",
    ),
    LeanTask(
        "pow2_pos",
        "def pow2 : Nat -> Nat | 0 => 1 | (n+1) => 2 * pow2 n",
        "(n : Nat) : 1 <= pow2 n",
        "headroom",
        "by induction n with | zero => simp [pow2] | succ k ih => simp [pow2] <;> omega",
    ),
    LeanTask(
        "le_sumto",
        _SUMTO,
        "(n : Nat) : n <= sumTo n",
        "headroom",
        "by induction n with | zero => simp [sumTo] | succ k ih => simp [sumTo] <;> omega",
    ),
    LeanTask(
        "dbl_ge",
        "def dbl : Nat -> Nat | 0 => 0 | (n+1) => dbl n + 2",
        "(n : Nat) : n <= dbl n",
        "headroom",
        "by induction n with | zero => simp | succ k ih => simp [dbl] <;> omega",
    ),
]

__all__ = ["LeanTask", "TASKS"]
