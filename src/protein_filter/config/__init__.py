"""Configuration module for protein_filter_lib.

This module provides both config classes and validation.
"""

import sys
import os

def _load_config_classes():
    """Load config classes from config.py."""
    import importlib.util
    config_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(config_dir, "..", "config.py")
    config_path = os.path.normpath(config_path)
    spec = importlib.util.spec_from_file_location("config", config_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["protein_filter.config"] = module
    spec.loader.exec_module(module)
    return module

config_module = _load_config_classes()

FilterConfig = config_module.FilterConfig
StructureRelaxerConfig = config_module.StructureRelaxerConfig
MetricConfig = config_module.MetricConfig

def __getattr__(name):
    """Lazy load validator to avoid circular import."""
    if name in ("ConfigValidator", "validate_config", "validate_config_dict", "ConfigValidationError"):
        from protein_filter.utils.config_validator import (
            ConfigValidator,
            validate_config,
            validate_config_dict,
            ConfigValidationError,
        )
        globals()["ConfigValidator"] = ConfigValidator
        globals()["validate_config"] = validate_config
        globals()["validate_config_dict"] = validate_config_dict
        globals()["ConfigValidationError"] = ConfigValidationError
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "FilterConfig",
    "StructureRelaxerConfig",
    "MetricConfig",
    "ConfigValidator",
    "validate_config", 
    "validate_config_dict",
    "ConfigValidationError",
]