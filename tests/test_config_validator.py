"""Tests for config validator module."""

import pytest
import sys
import tempfile
import yaml
from pathlib import Path

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from protein_filter.utils.config_validator import (
    ConfigValidator,
    validate_config,
    validate_config_dict,
    ConfigValidationError,
)


class TestConfigValidator:
    """Tests for ConfigValidator class."""

    def test_validate_valid_config(self):
        """Test validating a valid config."""
        config = {
            "part3": {
                "chains": {
                    "target_chain": "A",
                    "binder_chain": "B",
                    "auto_detect": {
                        "enabled": True,
                        "strategy": "by_length"
                    }
                },
                "md": {
                    "timestep_fs": 2.0,
                    "production_ns": 100,
                    "crash_recovery": {
                        "enabled": True,
                        "max_attempts": 3
                    }
                },
                "mmpbsa": {
                    "verbose": True
                }
            }
        }

        validator = ConfigValidator()
        is_valid, result = validator.validate_config(config)
        assert is_valid is True
        assert len(result["errors"]) == 0

    def test_validate_missing_part3(self):
        """Test validation fails when part3 section is missing."""
        config = {"other": "data"}

        validator = ConfigValidator()
        is_valid, result = validator.validate_config(config)
        assert is_valid is False
        assert "part3" in result["errors"][0]

    def test_validate_invalid_strategy(self):
        """Test validation fails for invalid auto_detect strategy."""
        config = {
            "part3": {
                "chains": {
                    "auto_detect": {
                        "enabled": True,
                        "strategy": "invalid_strategy"
                    }
                },
                "md": {},
                "mmpbsa": {}
            }
        }

        validator = ConfigValidator()
        is_valid, result = validator.validate_config(config)
        assert is_valid is False

    def test_validate_unusual_timestep_warning(self):
        """Test warning for unusual timestep."""
        config = {
            "part3": {
                "chains": {"target_chain": "A", "binder_chain": "B"},
                "md": {"timestep_fs": 5.0},
                "mmpbsa": {}
            }
        }

        validator = ConfigValidator()
        is_valid, result = validator.validate_config(config)
        assert is_valid is True
        assert len(result["warnings"]) > 0


class TestValidateConfigFile:
    """Tests for validate_config function."""

    def test_validate_nonexistent_file(self):
        """Test validation of non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            validate_config("/nonexistent/config.yaml")

    def test_validate_invalid_yaml(self):
        """Test validation of invalid YAML raises error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content:")
            f.flush()
            config_path = f.name

        try:
            with pytest.raises(ConfigValidationError):
                validate_config(config_path)
        finally:
            Path(config_path).unlink()

    def test_validate_empty_yaml(self):
        """Test validation of empty YAML raises error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            f.flush()
            config_path = f.name

        try:
            with pytest.raises(ConfigValidationError):
                validate_config(config_path)
        finally:
            Path(config_path).unlink()


class TestValidateConfigDict:
    """Tests for validate_config_dict function."""

    def test_validate_dict_valid(self):
        """Test validating a valid config dict."""
        config = {
            "part3": {
                "chains": {"target_chain": "A", "binder_chain": "B"},
                "md": {"timestep_fs": 2.0},
                "mmpbsa": {}
            }
        }

        result = validate_config_dict(config)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_dict_with_warnings(self):
        """Test config with warnings."""
        config = {
            "part3": {
                "chains": {},
                "md": {"timestep_fs": 0.5},
                "mmpbsa": {}
            }
        }

        result = validate_config_dict(config)
        assert result["valid"] is True
        assert len(result["warnings"]) > 0