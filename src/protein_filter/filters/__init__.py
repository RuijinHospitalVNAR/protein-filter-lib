"""
筛选模块：基于指标与阈值的通用筛选引擎。

与 FilterConfig.filters 格式一致，可用于 Stage1/Stage2 的 parquet 筛选。
"""

from .engine import (
    evaluate_operator,
    evaluate_filters,
    apply_filters_to_dataframe,
    composite_score_row,
)

__all__ = [
    "evaluate_operator",
    "evaluate_filters",
    "apply_filters_to_dataframe",
    "composite_score_row",
]
