from __future__ import annotations

from bx_lens import Lens, make_dict_lens


class TestDictLens:
    def test_get_put_law(self):
        lens = make_dict_lens("k")
        s = {"k": "a"}
        assert lens.verify_get_put(s) is True

    def test_put_get_law(self):
        lens = make_dict_lens("k")
        s = {"k": "a"}
        assert lens.verify_put_get(s, "b") is True

    def test_put_put_law(self):
        lens = make_dict_lens("k")
        s = {"k": "a"}
        assert lens.verify_put_put(s, "b", "c") is True

    def test_verify_all_clean(self):
        lens = make_dict_lens("k")
        result = lens.verify_all(s={"k": "x"}, v1="y", v2="z")
        assert result.get_put is True
        assert result.put_get is True
        assert result.put_put is True
        assert result.violations == []


class TestBuggyLens:
    def test_get_put_violation_detected(self):
        # buggy lens — put always sets v + "!" suffix
        def _get(s):
            return s["k"]

        def _put(s, v):
            new = dict(s)
            new["k"] = v + "!"
            return new

        bad = Lens(_get, _put)
        # put(s, get(s)) = s | {k: s["k"] + "!"} ≠ s
        s = {"k": "abc"}
        assert bad.verify_get_put(s) is False

    def test_put_get_violation_detected(self):
        # put records under a different key
        def _get(s):
            return s.get("k", "")

        def _put(s, v):
            new = dict(s)
            new["other"] = v
            return new

        bad = Lens(_get, _put)
        # get(put(s, v)) = "" ≠ v
        assert bad.verify_put_get({"k": ""}, "x") is False

    def test_put_put_violation_detected(self):
        # put appends instead of replaces
        def _get(s):
            return s["k"]

        def _put(s, v):
            new = dict(s)
            new["k"] = s.get("k", "") + v
            return new

        bad = Lens(_get, _put)
        # put(put(s,v1),v2) = s + v1 + v2;  put(s, v2) = s + v2 — not equal when v1 != ""
        assert bad.verify_put_put({"k": ""}, "a", "b") is False

    def test_verify_all_violations_collected(self):
        def _get(s):
            return s.get("k", "")

        def _put(s, v):
            new = dict(s)
            new["k"] = v + "!"
            return new

        bad = Lens(_get, _put)
        result = bad.verify_all(s={"k": "x"}, v1="y", v2="z")
        # GetPut, PutGet violations expected (put adds "!")
        assert result.get_put is False
        assert result.put_get is False
        assert len(result.violations) >= 2
