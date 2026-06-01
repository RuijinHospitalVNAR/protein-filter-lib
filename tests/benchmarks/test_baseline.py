"""Benchmarks for protein_filter_lib performance testing.

This module provides performance benchmarking for key functions.
Requires pytest-benchmark: pip install pytest-benchmark
"""

import pytest
import sys
import time
from pathlib import Path

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


pytest_plugins = []

try:
    import pytest_benchmark
    pytest_plugins.append("pytest_benchmark")
except ImportError:
    pass


def pytest_configure(config):
    """Configure pytest for benchmarks."""
    if "pytest_benchmark" not in config.getoption("plugins", ""):
        pytest.skip("pytest-benchmark not installed", allow_module_level=True)


class TestPDBParsePerformance:
    """Performance tests for PDB parsing."""

    def test_parse_single_structure(self, benchmark, sample_two_chain_pdb):
        """Benchmark parsing a single PDB structure."""
        from protein_filter.utils.chain_detection import parse_chains_from_pdb
        
        result = benchmark(parse_chains_from_pdb, str(sample_two_chain_pdb))
        assert result is not None

    def test_parse_with_cache(self, benchmark, sample_two_chain_pdb):
        """Benchmark parsing with cache enabled."""
        from protein_filter.cache import clear_structure_cache, get_cached_structure
        
        clear_structure_cache()
        
        result = benchmark(get_cached_structure, str(sample_two_chain_pdb))
        assert result is not None

    def test_cache_hit_performance(self, benchmark, sample_two_chain_pdb):
        """Benchmark cache hit performance."""
        from protein_filter.cache import get_cached_structure, clear_structure_cache
        
        clear_structure_cache()
        get_cached_structure(str(sample_two_chain_pdb))
        
        result = benchmark(get_cached_structure, str(sample_two_chain_pdb))
        assert result is not None


class TestChainDetectionPerformance:
    """Performance tests for chain detection."""

    def test_auto_detect_chains(self, benchmark, sample_two_chain_pdb):
        """Benchmark chain auto-detection."""
        from protein_filter.utils.chain_detection import auto_detect_chains
        
        result = benchmark(auto_detect_chains, str(sample_two_chain_pdb))
        assert result is not None

    def test_interface_area_calculation(self, benchmark, sample_two_chain_pdb):
        """Benchmark interface area calculation."""
        from protein_filter.utils.chain_detection import calculate_interface_area
        
        result = benchmark(
            calculate_interface_area,
            str(sample_two_chain_pdb),
            "A",
            "B",
            8.0
        )
        assert result >= 0


class TestConfigValidationPerformance:
    """Performance tests for config validation."""

    def test_validate_small_config(self, benchmark):
        """Benchmark validating a small config."""
        from protein_filter.utils.config_validator import validate_config_dict
        
        config = {
            "part3": {
                "chains": {"target_chain": "A", "binder_chain": "B"},
                "md": {"timestep_fs": 2.0, "production_ns": 100},
                "mmpbsa": {}
            }
        }
        
        result = benchmark(validate_config_dict, config)
        assert result is not None


class TestTopologyCheckPerformance:
    """Performance tests for topology checking."""

    def test_pdb_residue_count(self, benchmark, sample_two_chain_pdb):
        """Benchmark PDB residue counting."""
        from protein_filter.utils.topology_check import read_pdb_residue_count
        
        result = benchmark(read_pdb_residue_count, str(sample_two_chain_pdb))
        assert result > 0

    def test_chain_order_check(self, benchmark, sample_two_chain_pdb):
        """Benchmark chain order checking."""
        from protein_filter.utils.topology_check import check_chain_order
        
        result = benchmark(check_chain_order, str(sample_two_chain_pdb))
        assert "chains" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])