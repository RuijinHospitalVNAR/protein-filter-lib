"""Configuration validation module for protein_filter_lib.

This module provides functionality to validate YAML configuration files
before running the pipeline, preventing errors early.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class ConfigValidator:
    """Validator for protein_filter configuration files."""

    REQUIRED_SECTIONS = {
        "part3": ["chains", "md", "mmpbsa"],
    }

    CHAIN_CONFIG_SCHEMA = {
        "target_chain": (str, None),
        "binder_chain": (str, None),
        "auto_detect": (dict, {
            "enabled": (bool, True),
            "strategy": (str, ["by_length", "by_interface", "by_sequence"]),
        }),
    }

    MD_CONFIG_SCHEMA = {
        "timestep_fs": (float, [1.0, 2.0, 2.5]),
        "production_ns": (int, None),
        "crash_recovery": (dict, {
            "enabled": (bool, False),
            "max_attempts": (int, [1, 2, 3, 5]),
            "auto_adjust_params": (bool, False),
        }),
    }

    MMPBSA_CONFIG_SCHEMA = {
        "receptor_residues": (str, None),
        "ligand_residues": (str, None),
        "verbose": (bool, False),
        "precheck_topology": (bool, False),
        "auto_detect": (bool, False),
    }

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_file(self, config_path: str) -> Tuple[bool, Dict]:
        """
        Validate a configuration file.

        Args:
            config_path: Path to YAML config file

        Returns:
            Tuple of (is_valid, result_dict)
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            try:
                config = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise ConfigValidationError(f"Invalid YAML: {e}")

        if config is None:
            raise ConfigValidationError("Config file is empty")

        return self.validate_config(config)

    def validate_config(self, config: Dict) -> Tuple[bool, Dict]:
        """
        Validate configuration dictionary.

        Args:
            config: Configuration dictionary

        Returns:
            Tuple of (is_valid, result_dict)
        """
        self.errors = []
        self.warnings = []

        self._validate_structure(config)
        self._validate_chains(config.get("part3", {}))
        self._validate_md(config.get("part3", {}).get("md", {}))
        self._validate_mmpbsa(config.get("part3", {}).get("mmpbsa", {}))

        result = {
            "valid": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
        }

        return result["valid"], result

    def _validate_structure(self, config: Dict):
        """Validate top-level structure."""
        if "part3" not in config:
            self.errors.append("Missing required section: part3")

    def _validate_chains(self, chains_config: Dict):
        """Validate chain configuration."""
        if not chains_config:
            self.warnings.append("No chain configuration found")
            return

        actual_chains = chains_config.get("chains", chains_config)

        if "auto_detect" in actual_chains:
            auto_detect = actual_chains["auto_detect"]
            if "enabled" in auto_detect and auto_detect["enabled"]:
                if "strategy" in auto_detect:
                    valid_strategies = ["by_length", "by_interface", "by_sequence"]
                    if auto_detect["strategy"] not in valid_strategies:
                        self.errors.append(
                            f"Invalid auto_detect strategy: {auto_detect['strategy']}"
                        )
            return

        if "target_chain" not in actual_chains and "binder_chain" not in actual_chains:
            if not actual_chains.get("auto_detect", {}).get("enabled", False):
                self.warnings.append(
                    "No explicit chain configuration and auto_detect not enabled"
                )

    def _validate_md(self, md_config: Dict):
        """Validate MD configuration."""
        if not md_config:
            return

        if "timestep_fs" in md_config:
            timestep = md_config["timestep_fs"]
            if timestep not in [1.0, 1.5, 2.0, 2.5]:
                self.warnings.append(
                    f"Unusual timestep value: {timestep}fs (recommended: 1-2fs)"
                )

        if "production_ns" in md_config:
            if md_config["production_ns"] < 10:
                self.warnings.append(
                    f"Short production time: {md_config['production_ns']}ns"
                )

        if "crash_recovery" in md_config:
            crash_rec = md_config["crash_recovery"]
            if crash_rec.get("max_attempts", 0) > 5:
                self.warnings.append(
                    f"High max_attempts: {crash_rec['max_attempts']} (may cause long waits)"
                )

    def _validate_mmpbsa(self, mmpbsa_config: Dict):
        """Validate MMPBSA configuration."""
        if not mmpbsa_config:
            return

        if mmpbsa_config.get("precheck_topology", False):
            if not mmpbsa_config.get("receptor_residues") and not mmpbsa_config.get("auto_detect", False):
                self.warnings.append(
                    "precheck_topology enabled but no residue ranges specified"
                )


def validate_config(config_path: str) -> Dict:
    """
    Convenience function to validate a config file.

    Args:
        config_path: Path to config file

    Returns:
        Validation result dict with keys: valid, errors, warnings

    Raises:
        FileNotFoundError: If config file doesn't exist
        ConfigValidationError: If YAML is invalid
    """
    validator = ConfigValidator()
    is_valid, result = validator.validate_file(config_path)
    return result


def validate_config_dict(config: Dict) -> Dict:
    """
    Convenience function to validate a config dict.

    Args:
        config: Configuration dictionary

    Returns:
        Validation result dict with keys: valid, errors, warnings
    """
    validator = ConfigValidator()
    is_valid, result = validator.validate_config(config)
    return result