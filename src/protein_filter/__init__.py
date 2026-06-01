"""
Protein Filter Library

一个独立的蛋白质设计过滤和质量评估库。
专注于对预测结构的分析和过滤。
"""

from .core import ProteinFilter, FilterResult
from .config import FilterConfig, StructureRelaxerConfig, MetricConfig
from .design import Design
from .interfaces import (
    StructureRelaxer,
    MetricCalculator,
)

__version__ = "0.1.0"
__all__ = [
    "ProteinFilter",
    "FilterResult",
    "FilterConfig",
    "StructureRelaxerConfig",
    "MetricConfig",
    "Design",
    "StructureRelaxer",
    "MetricCalculator",
]

