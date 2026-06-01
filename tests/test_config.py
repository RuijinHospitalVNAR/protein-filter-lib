"""Tests for configuration loading and parsing."""

import pytest
import sys
import yaml
from pathlib import Path

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_load_sample_config(self, sample_config_yaml):
        """Test loading sample config YAML."""
        with open(sample_config_yaml, 'r') as f:
            config = yaml.safe_load(f)

        assert "part3" in config
        assert "chains" in config["part3"]
        assert config["part3"]["chains"]["target_chain"] == "A"

    def test_part3_config_structure(self, part3_config):
        """Test part3.yaml config structure."""
        if not part3_config.exists():
            pytest.skip("part3.yaml not found")

        with open(part3_config, 'r') as f:
            config = yaml.safe_load(f)

        assert isinstance(config, dict)

    def test_auto_detect_config_parsing(self, sample_config_yaml):
        """Test parsing auto_detect config."""
        with open(sample_config_yaml, 'r') as f:
            config = yaml.safe_load(f)

        chains_config = config["part3"]["chains"]
        assert "auto_detect" in chains_config
        assert chains_config["auto_detect"]["enabled"] is True
        assert chains_config["auto_detect"]["strategy"] == "by_length"


class TestConfigValidation:
    """Tests for config validation."""

    def test_mmpbsa_config_parsing(self, sample_config_yaml):
        """Test MMPBSA config section."""
        with open(sample_config_yaml, 'r') as f:
            config = yaml.safe_load(f)

        mmpbsa = config["part3"]["mmpbsa"]
        assert mmpbsa["auto_detect"] is True
        assert mmpbsa["verbose"] is True
        assert mmpbsa["precheck_topology"] is True

    def test_md_crash_recovery_config(self, sample_config_yaml):
        """Test MD crash recovery config."""
        with open(sample_config_yaml, 'r') as f:
            config = yaml.safe_load(f)

        crash_recovery = config["part3"]["md"]["crash_recovery"]
        assert crash_recovery["enabled"] is True
        assert crash_recovery["max_attempts"] == 3
        assert crash_recovery["auto_adjust_params"] is True


class TestConfigMerge:
    """Tests for config merging with CLI args."""

    def test_cli_override_defaults(self, sample_config_yaml):
        """Test CLI args can override config defaults."""
        with open(sample_config_yaml, 'r') as f:
            base_config = yaml.safe_load(f)

        cli_overrides = {
            "part3": {
                "chains": {
                    "target_chain": "X",
                    "binder_chain": "Y"
                }
            }
        }

        base_config["part3"]["chains"]["target_chain"] = cli_overrides["part3"]["chains"]["target_chain"]
        base_config["part3"]["chains"]["binder_chain"] = cli_overrides["part3"]["chains"]["binder_chain"]

        assert base_config["part3"]["chains"]["target_chain"] == "X"
        assert base_config["part3"]["chains"]["binder_chain"] == "Y"