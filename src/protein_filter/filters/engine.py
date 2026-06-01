"""
通用筛选引擎：根据指标与规则判断通过/失败。

支持单条 metrics 字典或 DataFrame 批量应用，
与 FilterConfig.filters 格式一致（threshold + operator）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import logging

logger = logging.getLogger(__name__)


def evaluate_operator(value: Any, threshold: Any, operator: str) -> bool:
    """单条条件判断。"""
    try:
        if operator == "<":
            return value < threshold
        if operator == "<=":
            return value <= threshold
        if operator == ">":
            return value > threshold
        if operator == ">=":
            return value >= threshold
        if operator in ("==", "="):
            return value == threshold
        if operator == "!=":
            return value != threshold
        logger.warning("Unknown operator %r, defaulting to False", operator)
        return False
    except (TypeError, ValueError) as e:
        logger.warning("Error evaluating filter: %s %s %s: %s", value, operator, threshold, e)
        return False


def evaluate_filters(
    metrics: Dict[str, Any],
    filters: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, bool], bool]:
    """
    对一条 metrics 应用多条规则，返回每条规则是否通过及是否全部通过。

    Args:
        metrics: 单条设计的指标字典
        filters: 规则字典，形如 { "metric_name": {"threshold": x, "operator": ">="} }

    Returns:
        (filter_results: 每条规则名 -> 是否通过, all_passed: 是否全部通过)
    """
    filter_results = {}
    if not filters:
        return {}, True

    for filter_name, filter_config in filters.items():
        if filter_name not in metrics:
            logger.warning("Filter %r not found in metrics, skipping", filter_name)
            filter_results[f"{filter_name}_filter"] = False
            continue
        metric_value = metrics[filter_name]
        threshold = filter_config.get("threshold") or filter_config.get("value")
        operator = filter_config.get("operator", ">=")
        passed = evaluate_operator(metric_value, threshold, operator)
        filter_results[f"{filter_name}_filter"] = passed

    all_passed = all(filter_results.values())
    return filter_results, all_passed


def apply_filters_to_dataframe(
    df: Any,
    filters: Dict[str, Dict[str, Any]],
    design_name_key: str = "design_name",
) -> Any:
    """
    对 DataFrame 按行应用规则，返回通过筛选的行。

    需要 pandas。列名与 filters 的 key 对应。
    """
    import pandas as pd

    if not filters:
        return df.copy()

    mask = pd.Series(True, index=df.index)
    for metric_name, filter_config in filters.items():
        if metric_name not in df.columns:
            logger.warning("Metric %r not in DataFrame, skipping filter", metric_name)
            continue
        threshold = filter_config.get("threshold") or filter_config.get("value")
        operator = filter_config.get("operator", ">=")
        col = df[metric_name]
        if operator == ">=":
            mask = mask & (col >= threshold)
        elif operator == ">":
            mask = mask & (col > threshold)
        elif operator == "<=":
            mask = mask & (col <= threshold)
        elif operator == "<":
            mask = mask & (col < threshold)
        elif operator in ("==", "="):
            mask = mask & (col == threshold)
        elif operator == "!=":
            mask = mask & (col != threshold)
        else:
            logger.warning("Unknown operator %r for %s", operator, metric_name)
    return df.loc[mask].copy()


def composite_score_row(
    row: Any,
    weights: Dict[str, float],
    default: float = 0.0,
) -> float:
    """按权重计算一行综合分（用于 Top-N 排序）。"""
    import pandas as pd

    score = 0.0
    for metric_name, weight in weights.items():
        if metric_name in row.index:
            val = row[metric_name]
            if pd.notna(val) and isinstance(val, (int, float)):
                score += weight * val
        else:
            score += default * weight
    return score
