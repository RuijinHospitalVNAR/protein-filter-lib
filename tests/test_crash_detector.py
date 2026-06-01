"""Tests for MD crash detection module."""

import pytest
import sys
import os
import tempfile
from pathlib import Path

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from protein_filter.md.crash_detector import (
    CrashType,
    parse_md_log,
    detect_crash_type,
    get_crash_suggestion,
    generate_crash_report,
    apply_recovery_params,
)


class TestParseMdLog:
    """Tests for parse_md_log function."""

    def test_parse_nonexistent_file(self):
        """Test parsing non-existent log file."""
        result = parse_md_log("/nonexistent/log.txt")
        assert result["exists"] is False

    def test_parse_empty_file(self):
        """Test parsing empty log file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            log_path = f.name

        try:
            result = parse_md_log(log_path)
            assert result["exists"] is True
            assert result["completed"] is False
        finally:
            os.unlink(log_path)

    def test_parse_successful_log(self):
        """Test parsing successful completion log."""
        log_content = """
Running MD simulation
Step 1000: ENERGY = -50000.5
Step 2000: ENERGY = -52000.2
Normal termination
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(log_content)
            log_path = f.name

        try:
            result = parse_md_log(log_path)
            assert result["completed"] is True
        finally:
            os.unlink(log_path)


class TestDetectCrashType:
    """Tests for detect_crash_type function."""

    def test_detect_energy_explosion(self):
        """Test detecting energy explosion crash."""
        log_content = "ERROR: Energy explosion detected\nFinal energy: 1e15"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(log_content)
            log_path = f.name

        try:
            crash_type, desc = detect_crash_type(log_path)
            assert crash_type == CrashType.ENERGY_EXPLOSION
        finally:
            os.unlink(log_path)

    def test_detect_nan(self):
        """Test detecting NaN crash."""
        log_content = "Energy = NaN\nNot a number detected"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(log_content)
            log_path = f.name

        try:
            crash_type, desc = detect_crash_type(log_path)
            assert crash_type == CrashType.NAN
        finally:
            os.unlink(log_path)

    def test_detect_success(self):
        """Test detecting successful completion."""
        log_content = "Step 1000: Energy = -50000\nNormal termination"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(log_content)
            log_path = f.name

        try:
            crash_type, desc = detect_crash_type(log_path)
            assert crash_type == CrashType.SUCCESS
        finally:
            os.unlink(log_path)

    def test_detect_unknown(self):
        """Test detecting unknown crash type."""
        log_content = "Some error occurred\nCheck the logs"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write(log_content)
            log_path = f.name

        try:
            crash_type, desc = detect_crash_type(log_path)
            assert crash_type == CrashType.UNKNOWN
        finally:
            os.unlink(log_path)


class TestGetCrashSuggestion:
    """Tests for get_crash_suggestion function."""

    def test_energy_explosion_suggestion(self):
        """Test getting suggestion for energy explosion."""
        suggestion = get_crash_suggestion(CrashType.ENERGY_EXPLOSION)
        assert suggestion["recovery_possible"] is True
        assert len(suggestion["suggestions"]) > 0
        assert "timestep" in suggestion["params_to_adjust"]

    def test_segfault_suggestion(self):
        """Test getting suggestion for segfault."""
        suggestion = get_crash_suggestion(CrashType.SEGFAULT)
        assert suggestion["recovery_possible"] is False
        assert len(suggestion["params_to_adjust"]) == 0


class TestApplyRecoveryParams:
    """Tests for apply_recovery_params function."""

    def test_apply_timestep_change(self):
        """Test applying timestep recovery parameter."""
        config = {
            "md": {
                "timestep_fs": 2,
                "production_ns": 100
            }
        }
        recovery = {
            "params_to_adjust": {
                "timestep": 1
            }
        }

        result = apply_recovery_params(config, recovery)
        assert result["md"]["timestep_fs"] == 1

    def test_apply_production_change(self):
        """Test applying production time recovery parameter."""
        config = {
            "md": {
                "production_ns": 100
            }
        }
        recovery = {
            "params_to_adjust": {
                "production_ns": 50
            }
        }

        result = apply_recovery_params(config, recovery)
        assert result["md"]["production_ns"] == 50