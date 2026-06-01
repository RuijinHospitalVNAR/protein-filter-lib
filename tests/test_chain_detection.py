"""Tests for chain_detection module."""

import pytest
import sys
from pathlib import Path

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from protein_filter.utils.chain_detection import (
    parse_chains_from_pdb,
    extract_sequence,
    calculate_interface_area,
    auto_detect_chains,
    get_mmpbsa_masks,
    generate_auto_config,
)


class TestParseChainsFromPdb:
    """Tests for parse_chains_from_pdb function."""

    def test_parse_two_chain_pdb(self, sample_two_chain_pdb):
        """Test parsing PDB with two chains."""
        chains = parse_chains_from_pdb(str(sample_two_chain_pdb))

        assert len(chains) == 2
        assert "A" in chains
        assert "B" in chains
        assert chains["A"]["length"] > 0
        assert chains["B"]["length"] > 0
        assert "min_res" in chains["A"]
        assert "max_res" in chains["A"]
        assert "residues" in chains["A"]

    def test_parse_single_chain_pdb(self, sample_single_chain_pdb):
        """Test parsing PDB with single chain."""
        chains = parse_chains_from_pdb(str(sample_single_chain_pdb))

        assert len(chains) == 1
        assert "A" in chains
        assert chains["A"]["length"] == 4

    def test_parse_nonexistent_file(self):
        """Test parsing non-existent file raises error."""
        with pytest.raises((RuntimeError, FileNotFoundError)):
            parse_chains_from_pdb("/nonexistent/file.pdb")


class TestAutoDetectChains:
    """Tests for auto_detect_chains function."""

    def test_auto_detect_by_length(self, sample_two_chain_pdb):
        """Test auto-detect by length - longest chain should be target."""
        target, binder = auto_detect_chains(
            str(sample_two_chain_pdb), strategy="by_length"
        )

        assert target in ["A", "B"]
        assert binder in ["A", "B"]
        assert target != binder

    def test_auto_detect_single_chain_raises(self, sample_single_chain_pdb):
        """Test auto-detect on single chain raises ValueError."""
        with pytest.raises(ValueError, match="Need at least 2 protein chains"):
            auto_detect_chains(str(sample_single_chain_pdb), strategy="by_length")

    def test_auto_detect_default_strategy(self, sample_two_chain_pdb):
        """Test default strategy is by_length."""
        target, binder = auto_detect_chains(str(sample_two_chain_pdb))
        assert target is not None
        assert binder is not None


class TestGetMmpbsaMasks:
    """Tests for get_mmpbsa_masks function."""

    def test_get_mmpbsa_masks_valid(self, sample_two_chain_pdb):
        """Test generating MMPBSA masks for valid chains."""
        receptor_mask, ligand_mask = get_mmpbsa_masks(
            str(sample_two_chain_pdb), "A", "B"
        )

        assert isinstance(receptor_mask, str)
        assert isinstance(ligand_mask, str)
        assert ":" in receptor_mask
        assert ":" in ligand_mask

    def test_get_mmpbsa_masks_invalid_chain(self, sample_two_chain_pdb):
        """Test invalid chain raises error."""
        with pytest.raises(ValueError, match="Chain not found"):
            get_mmpbsa_masks(str(sample_two_chain_pdb), "A", "C")


class TestExtractSequence:
    """Tests for extract_sequence function."""

    def test_extract_sequence_valid(self, sample_two_chain_pdb):
        """Test extracting sequence from valid chain."""
        seq = extract_sequence(str(sample_two_chain_pdb), "A")
        assert isinstance(seq, str)
        assert len(seq) > 0

    def test_extract_sequence_single_letter(self, sample_two_chain_pdb):
        """Test extracted sequence uses single letter codes."""
        seq = extract_sequence(str(sample_two_chain_pdb), "A")
        valid_amino_acids = set("ACDEFGHIKLMNPQRSTVWY")
        for char in seq:
            assert char in valid_amino_acids or char == "-"


class TestCalculateInterfaceArea:
    """Tests for calculate_interface_area function."""

    def test_calculate_interface_area_valid(self, sample_two_chain_pdb):
        """Test calculating interface area between two chains."""
        area = calculate_interface_area(str(sample_two_chain_pdb), "A", "B")
        assert area >= 0
        assert hasattr(area, '__int__') or hasattr(area, '__float__')

    def test_calculate_interface_area_same_chain(self, sample_two_chain_pdb):
        """Test interface area between same chain returns non-negative value."""
        area = calculate_interface_area(str(sample_two_chain_pdb), "A", "A")
        assert area >= 0


class TestGenerateAutoConfig:
    """Tests for generate_auto_config function."""

    def test_generate_auto_config_two_chains(self, sample_two_chain_pdb):
        """Test generating auto config for two-chain PDB."""
        config = generate_auto_config(str(sample_two_chain_pdb))

        assert "chains" in config
        assert "auto_detect" in config["chains"]
        assert config["chains"]["auto_detect"]["enabled"] is True
        assert config["chains"]["auto_detect"]["strategy"] == "by_length"
        assert "target_chain" in config["chains"]
        assert "binder_chain" in config["chains"]

    def test_generate_auto_config_single_chain_raises(self, sample_single_chain_pdb):
        """Test generating auto config for single chain raises error."""
        with pytest.raises(ValueError, match="Cannot auto-detect"):
            generate_auto_config(str(sample_single_chain_pdb))