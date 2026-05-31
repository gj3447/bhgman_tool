"""Tests for scip_adapter — SCIP (LSIF migration 2024) input adapter.

# KG: sa-longinus-scip-adapter-2026-05-19, wqi-longinus-scip-adapter-v3.3-2026-06-2026-05-19
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from engine.longinus_drift_audit import scip_adapter
from engine.longinus_drift_audit.models import CodeSymbol


class TestParseScipSymbol:
    def test_simple_typescript_moniker(self):
        moniker = "scip-typescript npm @types/node 20.0.0 `index.d.ts`/Buffer#"
        sym = scip_adapter.parse_scip_symbol(moniker)
        assert sym.scheme == "scip-typescript"
        assert sym.package == "npm/@types/node@20.0.0"
        assert sym.descriptor == "`index.d.ts`/Buffer#"
        assert sym.raw == moniker

    def test_method_descriptor(self):
        # Method (function suffix `().`), type (`#`), term (`.`), package (`/`).
        moniker = "scip-python python my-pkg 1.2.3 `mymod`/MyClass#method()."
        sym = scip_adapter.parse_scip_symbol(moniker)
        assert sym.scheme == "scip-python"
        assert sym.descriptor == "`mymod`/MyClass#method()."

    def test_field_descriptor(self):
        moniker = "scip-go go github.com/foo/bar 0.1.0 `pkg`/Cfg#timeout."
        sym = scip_adapter.parse_scip_symbol(moniker)
        assert sym.scheme == "scip-go"
        # field suffix `.` preserved
        assert sym.descriptor.endswith("timeout.")

    def test_reject_malformed_moniker(self):
        with pytest.raises(ValueError, match="malformed SCIP moniker"):
            scip_adapter.parse_scip_symbol("only-three tokens here")
        with pytest.raises(ValueError):
            scip_adapter.parse_scip_symbol("")
        with pytest.raises(ValueError):
            scip_adapter.parse_scip_symbol("   ")


class TestParseScipIndexJson:
    def test_empty_index(self):
        idx = scip_adapter.parse_scip_index_json('{"metadata": {}, "documents": []}')
        assert idx.metadata_version == 0
        assert idx.project_root == ""
        assert idx.documents == []

    def test_index_with_one_doc_three_occurrences(self):
        payload = {
            "metadata": {"version": 1, "projectRoot": "file:///proj"},
            "documents": [
                {
                    "relativePath": "src/lib.ts",
                    "language": "TypeScript",
                    "occurrences": [
                        {
                            "symbol": "scip-typescript npm pkg 1.0.0 `lib.ts`/A#",
                            "range": [0, 5, 0, 6],
                            "symbolRoles": 1,
                        },
                        {
                            "symbol": "scip-typescript npm pkg 1.0.0 `lib.ts`/B#",
                            "range": [3, 2, 7],  # 3-tuple short form
                            "symbolRoles": 8,
                        },
                        {
                            "symbol": "scip-typescript npm pkg 1.0.0 `lib.ts`/c().",
                            "range": [10, 0, 12, 3],
                            "symbolRoles": 0,
                        },
                    ],
                }
            ],
        }
        idx = scip_adapter.parse_scip_index_json(json.dumps(payload))
        assert idx.metadata_version == 1
        assert idx.project_root == "file:///proj"
        assert len(idx.documents) == 1
        doc = idx.documents[0]
        assert doc.relative_path == "src/lib.ts"
        assert doc.language == "TypeScript"
        assert len(doc.occurrences) == 3
        # 3-tuple range expansion
        b_occ = doc.occurrences[1]
        assert b_occ.range_start_line == 3
        assert b_occ.range_end_line == 3
        assert b_occ.range_end_char == 7
        assert b_occ.role == 8

    def test_reject_malformed_json(self):
        with pytest.raises(ValueError, match="malformed SCIP JSON"):
            scip_adapter.parse_scip_index_json("{not valid json")

    def test_reject_non_object_root(self):
        with pytest.raises(ValueError, match="SCIP root must be JSON object"):
            scip_adapter.parse_scip_index_json("[1, 2, 3]")

    def test_empty_document_handled_gracefully(self):
        payload = {
            "metadata": {"version": 0},
            "documents": [
                {"relativePath": "src/empty.py", "language": "Python", "occurrences": []}
            ],
        }
        idx = scip_adapter.parse_scip_index_json(json.dumps(payload))
        assert len(idx.documents) == 1
        assert idx.documents[0].occurrences == []


class TestScipToCodeSymbols:
    def test_roundtrip_parse_then_adapt(self):
        payload = {
            "metadata": {"version": 1, "projectRoot": "file:///proj"},
            "documents": [
                {
                    "relativePath": "src/lib.ts",
                    "language": "TypeScript",
                    "occurrences": [
                        {
                            "symbol": "scip-typescript npm pkg 1.0.0 `lib.ts`/MyClass#",
                            "range": [4, 0, 4, 7],
                            "symbolRoles": 1,
                        },
                        {
                            "symbol": "scip-typescript npm pkg 1.0.0 `lib.ts`/myFn().",
                            "range": [9, 0, 12, 1],
                            "symbolRoles": 1,
                        },
                    ],
                }
            ],
        }
        idx = scip_adapter.parse_scip_index_json(json.dumps(payload))
        syms = scip_adapter.scip_to_code_symbols(idx)
        assert len(syms) == 2
        # All are CodeSymbol
        for s in syms:
            assert isinstance(s, CodeSymbol)
        # 0-based → 1-based line conversion
        assert syms[0].sourcePath == "src/lib.ts:5"
        assert syms[0].name == "MyClass"
        assert syms[0].kind == "class"
        assert syms[1].sourcePath == "src/lib.ts:10"
        assert syms[1].name == "myFn"
        assert syms[1].kind == "function"
        # Signature preserves full moniker
        assert "scip-typescript" in syms[0].signature
        # No KG refs from SCIP (separate channel)
        assert syms[0].kg_refs == []

    def test_local_symbols_skipped(self):
        # `local 1` is a SCIP sentinel form that doesn't match the 5-token grammar.
        # Adapter must skip rather than abort.
        payload = {
            "metadata": {"version": 0},
            "documents": [
                {
                    "relativePath": "src/x.ts",
                    "language": "TypeScript",
                    "occurrences": [
                        {"symbol": "local 1", "range": [0, 0, 0, 5], "symbolRoles": 0},
                        {
                            "symbol": "scip-typescript npm p 0.1.0 `x.ts`/keep#",
                            "range": [1, 0, 1, 4],
                            "symbolRoles": 0,
                        },
                    ],
                }
            ],
        }
        idx = scip_adapter.parse_scip_index_json(json.dumps(payload))
        syms = scip_adapter.scip_to_code_symbols(idx)
        # Only the well-formed moniker becomes a CodeSymbol; local skipped.
        assert len(syms) == 1
        assert syms[0].name == "keep"

    def test_empty_index_yields_empty_symbols(self):
        idx = scip_adapter.parse_scip_index_json('{"metadata": {}, "documents": []}')
        assert scip_adapter.scip_to_code_symbols(idx) == []


class TestPydanticSerialization:
    def test_roundtrip_serialize_deserialize(self):
        sym = scip_adapter.ScipSymbol(
            scheme="scip-rust",
            package="cargo/serde@1.0.0",
            descriptor="`serde`/Serialize#",
            raw="scip-rust cargo serde 1.0.0 `serde`/Serialize#",
        )
        dumped = sym.model_dump_json()
        restored = scip_adapter.ScipSymbol.model_validate_json(dumped)
        assert restored == sym

        occ = scip_adapter.ScipOccurrence(
            symbol=sym.raw,
            range_start_line=1,
            range_start_char=2,
            range_end_line=3,
            range_end_char=4,
            role=1,
        )
        d_occ = occ.model_dump_json()
        restored_occ = scip_adapter.ScipOccurrence.model_validate_json(d_occ)
        assert restored_occ == occ


class TestRangeValidation:
    def test_invalid_range_end_before_start_line(self):
        with pytest.raises(ValidationError):
            scip_adapter.ScipOccurrence(
                symbol="scip-x m p 0 `f`/X#",
                range_start_line=5,
                range_start_char=0,
                range_end_line=3,  # < start
                range_end_char=0,
            )

    def test_invalid_range_3_tuple_via_json(self):
        # 2-tuple range is rejected
        payload = {
            "metadata": {},
            "documents": [
                {
                    "relativePath": "x.py",
                    "language": "Python",
                    "occurrences": [
                        {
                            "symbol": "scip-python python p 0 `x`/y.",
                            "range": [0, 0],  # too short
                        }
                    ],
                }
            ],
        }
        with pytest.raises(ValueError, match="3- or 4-tuple"):
            scip_adapter.parse_scip_index_json(json.dumps(payload))
