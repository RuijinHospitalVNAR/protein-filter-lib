"""Pytest configuration and fixtures for protein_filter_lib tests."""

import pytest
import sys
from pathlib import Path

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


@pytest.fixture
def fixtures_dir():
    """Return the path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_two_chain_pdb(fixtures_dir):
    """Return path to sample two-chain PDB file."""
    return fixtures_dir / "sample_two_chain.pdb"


@pytest.fixture
def sample_single_chain_pdb(fixtures_dir):
    """Return path to sample single-chain PDB file."""
    return fixtures_dir / "sample_single_chain.pdb"


@pytest.fixture
def sample_config_yaml(fixtures_dir):
    """Return path to sample config YAML file."""
    return fixtures_dir / "sample_config.yaml"


@pytest.fixture
def config_dir():
    """Return path to config directory."""
    return Path(__file__).parent.parent / "config"


@pytest.fixture
def part3_config(config_dir):
    """Return path to part3.yaml config."""
    return config_dir / "part3.yaml"