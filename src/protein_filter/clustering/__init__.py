"""聚类分析模块"""

try:
    from .clustering import (
        InterfaceClusteringFilter,
        filter_by_clustering,
    )
    __all__ = [
        "InterfaceClusteringFilter",
        "filter_by_clustering",
    ]
except ImportError:
    __all__ = []
