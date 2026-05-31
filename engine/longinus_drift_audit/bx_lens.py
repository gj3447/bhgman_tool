"""BX Lens Laws — Foster-Pierce-Walker POPL 2007.

Get : KG → Code  (조회)
Put : Code → KG  (갱신)

3 Laws:
  GetPut  put(s, get(s)) = s          — 조회 후 무변화 갱신 ⇒ KG 불변
  PutGet  get(put(s, v)) = v          — 갱신 후 조회 ⇒ 새 값
  PutPut  put(put(s,v1),v2) = put(s,v2) — 연속 갱신 ⇒ 마지막만 유효

SKILL.md §"BX Lens Laws" 1:1.
"""

from __future__ import annotations

from typing import Callable, Generic, TypeVar

from engine.longinus_drift_audit.models import LensVerification

S = TypeVar("S")
V = TypeVar("V")


class Lens(Generic[S, V]):
    """Reference Lens between KG state (s : S) and code value (v : V)."""

    def __init__(
        self,
        get: Callable[[S], V],
        put: Callable[[S, V], S],
    ):
        self.get = get
        self.put = put

    def verify_get_put(self, s: S) -> bool:
        """put(s, get(s)) = s."""
        return self.put(s, self.get(s)) == s

    def verify_put_get(self, s: S, v: V) -> bool:
        """get(put(s, v)) = v."""
        return self.get(self.put(s, v)) == v

    def verify_put_put(self, s: S, v1: V, v2: V) -> bool:
        """put(put(s,v1),v2) = put(s,v2)."""
        return self.put(self.put(s, v1), v2) == self.put(s, v2)

    def verify_all(self, *, s: S, v1: V, v2: V) -> LensVerification:
        out = LensVerification()
        if not self.verify_get_put(s):
            out.get_put = False
            out.violations.append("GetPut: put(s, get(s)) != s — Orphan-class drift")
        if not self.verify_put_get(s, v1):
            out.put_get = False
            out.violations.append("PutGet: get(put(s, v1)) != v1 — Missing/SigMismatch-class drift")
        if not self.verify_put_put(s, v1, v2):
            out.put_put = False
            out.violations.append(
                "PutPut: put(put(s,v1),v2) != put(s,v2) — PatternDiv/LabelRot-class drift"
            )
        return out


# ─── Concrete Lens: dict-as-KG ↔ string-value-as-code ────────────────────


def make_dict_lens(key: str) -> Lens:
    """A simple lens between `dict` KG state and string value at fixed `key`.

    GET: state[key]
    PUT: state | {key: v}  (immutable update)
    """

    def _get(s: dict) -> str:
        return s.get(key, "")

    def _put(s: dict, v: str) -> dict:
        new = dict(s)
        new[key] = v
        return new

    return Lens(_get, _put)
