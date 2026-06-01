"""
Implementation classes for structure relaxers.
"""

from .relaxers import PyRosettaRelaxer, NoOpRelaxer
from ..config import StructureRelaxerConfig
from ..interfaces import StructureRelaxer


def get_relaxer(config: StructureRelaxerConfig) -> StructureRelaxer:
    """Get structure relaxer based on configuration."""
    if config.name.lower() == "pyrosetta":
        return PyRosettaRelaxer(config)
    elif config.name.lower() == "none":
        return NoOpRelaxer()
    else:
        raise ValueError(f"Unknown relaxer: {config.name}. Use 'pyrosetta' or 'none'")


__all__ = [
    "PyRosettaRelaxer",
    "NoOpRelaxer",
    "get_relaxer",
]

