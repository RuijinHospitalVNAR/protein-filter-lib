"""Tests for topology_check module."""

import pytest
import sys
import os
from pathlib import Path

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from protein_filter.utils.topology_check import (
    read_pdb_residue_count,
    check_prmtop_pdb_consistency,
    check_chain_order,
    generate_diagnostic_report,
    validate_mmpbsa_inputs,
    TopologyError,
)


class TestReadPdbResidueCount:
    """Tests for read_pdb_residue_count function."""

    def test_read_two_chain_pdb(self, sample_two_chain_pdb):
        """Test reading residue count from two-chain PDB."""
        count = read_pdb_residue_count(str(sample_two_chain_pdb))
        assert count > 0
        assert count >= 4

    def test_read_single_chain_pdb(self, sample_single_chain_pdb):
        """Test reading residue count from single-chain PDB."""
        count = read_pdb_residue_count(str(sample_single_chain_pdb))
        assert count == 4

    def test_read_nonexistent_file(self):
        """Test reading non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            read_pdb_residue_count("/nonexistent/file.pdb")


class TestCheckChainOrder:
    """Tests for check_chain_order function."""

    def test_check_two_chain_order(self, sample_two_chain_pdb):
        """Test checking chain order in two-chain PDB."""
        result = check_chain_order(str(sample_two_chain_pdb))
        assert "A" in result["chains"]
        assert "B" in result["chains"]

    def test_check_with_expected_order(self, sample_two_chain_pdb):
        """Test checking with expected first chain."""
        result = check_chain_order(str(sample_two_chain_pdb), expected_first="A")
        assert result["chains"][0] == "A"

    def test_check_invalid_chain(self):
        """Test checking non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            check_chain_order("/nonexistent.pdb")


class TestGenerateDiagnosticReport:
    """Tests for generate_diagnostic_report function."""

    def test_generate_report_for_fixtures(self, fixtures_dir):
        """Test generating report for fixtures directory."""
        report = generate_diagnostic_report(str(fixtures_dir))
        assert "directory" in report
        assert "files" in report

    def test_generate_report_nonexistent_dir(self):
        """Test generating report for non-existent directory."""
        with pytest.raises(FileNotFoundError):
            generate_diagnostic_report("/nonexistent/directory")


class TestValidateMmpbsaInputs:
    """Tests for validate_mmpbsa_inputs function."""

    def test_validate_missing_prmtop(self):
        """Test validation with missing prmtop file."""
        result = validate_mmpbsa_inputs(
            prmtop_path="/nonexistent.prmtop",
            trajectory_path="/nonexistent.nc"
        )
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_validate_missing_trajectory(self):
        """Test validation with missing trajectory file."""
        result = validate_mmpbsa_inputs(
            prmtop_path="/nonexistent.prmtop",
            trajectory_path="/nonexistent.nc"
        )
        assert result["valid"] is False