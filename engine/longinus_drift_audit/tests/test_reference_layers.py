from __future__ import annotations

import reference_layers
from models import LayerCoverage, ReferenceSite


class TestPierceRate:
    def test_zero_symbols(self):
        assert reference_layers.make_pierce_rate(total_code_symbols=0, total_kg_refs=0) == 0.0

    def test_half_coverage(self):
        r = reference_layers.make_pierce_rate(total_code_symbols=10, total_kg_refs=5)
        assert r == 0.5

    def test_capped_at_one(self):
        r = reference_layers.make_pierce_rate(total_code_symbols=5, total_kg_refs=100)
        assert r == 1.0


class TestLayerCoverage:
    def test_empty_sites(self):
        cov = reference_layers.layer_coverage(sites=[], total_kg_refs=0, pierce_rate=0.0)
        assert isinstance(cov, LayerCoverage)
        assert cov.L1_address == 1.0

    def test_with_sites(self):
        sites = [
            ReferenceSite(sourceId="lesson-x", sourcePath="x.py:1"),
            ReferenceSite(sourceId="lesson-y", sourcePath="y.py:2"),
        ]
        cov = reference_layers.layer_coverage(sites=sites, total_kg_refs=2, pierce_rate=0.8)
        assert cov.L1_address == 1.0  # all have sourcePath
        assert cov.L4_semiotic == 1.0
        assert cov.L7_aesthetic_pierce_rate == 0.8


class TestCompressKgRef:
    def test_format(self):
        result = reference_layers.compress_kg_ref(
            sourceId="lesson-foo", sourcePath="src/foo.py:42"
        )
        assert "# KG: lesson-foo" in result
        assert "src/foo.py:42" in result
