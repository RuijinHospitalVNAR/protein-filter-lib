"""
Metrics I/O utilities for saving and loading computed metrics.

This module provides functions to save metrics to parquet/csv files
and load them for filtering, enabling separation of metric computation
and filtering steps.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

try:
    import pandas as pd
    import pyarrow
except ImportError:
    raise ImportError(
        "pandas and pyarrow are required for metrics I/O. "
        "Install with: pip install pandas pyarrow"
    )

logger = logging.getLogger(__name__)


def save_metrics_to_parquet(
    metrics_list: List[Dict[str, Any]],
    output_path: Union[str, Path],
    design_name_key: str = "design_name",
) -> Path:
    """
    Save a list of metrics dictionaries to a parquet file.
    
    Args:
        metrics_list: List of dictionaries, each containing metrics for one design
        output_path: Path to save the parquet file
        design_name_key: Key in each dict that contains the design name/ID
    
    Returns:
        Path to the saved file
    
    Example:
        >>> metrics = [
        ...     {"design_name": "design_001", "external_plddt": 0.85, "pdockq": 0.45},
        ...     {"design_name": "design_002", "external_plddt": 0.72, "pdockq": 0.38},
        ... ]
        >>> save_metrics_to_parquet(metrics, "stage1_metrics.parquet")
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not metrics_list:
        logger.warning("Empty metrics list, creating empty DataFrame")
        df = pd.DataFrame()
    else:
        # Convert to DataFrame
        df = pd.DataFrame(metrics_list)
        
        # Ensure design_name is the first column if present
        if design_name_key in df.columns:
            cols = [design_name_key] + [c for c in df.columns if c != design_name_key]
            df = df[cols]
    
    # Save to parquet
    df.to_parquet(output_path, index=False, engine='pyarrow')
    logger.info(f"Saved {len(df)} designs' metrics to {output_path}")
    
    return output_path


def load_metrics_from_parquet(
    input_path: Union[str, Path],
    design_names: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Load metrics from a parquet file.
    
    Args:
        input_path: Path to the parquet file
        design_names: Optional list of design names to filter (if None, load all)
    
    Returns:
        DataFrame with metrics
    """
    input_path = Path(input_path)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Metrics file not found: {input_path}")
    
    df = pd.read_parquet(input_path, engine='pyarrow')
    
    if design_names is not None:
        if 'design_name' in df.columns:
            df = df[df['design_name'].isin(design_names)]
        else:
            logger.warning("design_names provided but 'design_name' column not found")
    
    logger.info(f"Loaded {len(df)} designs' metrics from {input_path}")
    return df


def save_metrics_to_json(
    metrics_list: List[Dict[str, Any]],
    output_path: Union[str, Path],
) -> Path:
    """
    Save metrics to JSON file (alternative to parquet, for smaller datasets).
    
    Args:
        metrics_list: List of metrics dictionaries
        output_path: Path to save JSON file
    
    Returns:
        Path to saved file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(metrics_list, f, indent=2)
    
    logger.info(f"Saved {len(metrics_list)} designs' metrics to {output_path}")
    return output_path


def load_metrics_from_json(
    input_path: Union[str, Path],
) -> List[Dict[str, Any]]:
    """
    Load metrics from JSON file.
    
    Args:
        input_path: Path to JSON file
    
    Returns:
        List of metrics dictionaries
    """
    input_path = Path(input_path)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Metrics file not found: {input_path}")
    
    with open(input_path, 'r') as f:
        metrics_list = json.load(f)
    
    logger.info(f"Loaded {len(metrics_list)} designs' metrics from {input_path}")
    return metrics_list


def merge_metrics_files(
    file_paths: List[Union[str, Path]],
    output_path: Union[str, Path],
    on: str = "design_name",
) -> Path:
    """
    Merge multiple metrics files (e.g., stage1 and stage2) into one.
    
    Args:
        file_paths: List of paths to metrics files (parquet or JSON)
        output_path: Path to save merged metrics
        on: Column name to merge on (default: "design_name")
    
    Returns:
        Path to merged file
    """
    dfs = []
    
    for file_path in file_paths:
        file_path = Path(file_path)
        if file_path.suffix == '.parquet':
            df = pd.read_parquet(file_path, engine='pyarrow')
        elif file_path.suffix == '.json':
            metrics_list = load_metrics_from_json(file_path)
            df = pd.DataFrame(metrics_list)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        dfs.append(df)
    
    # Merge all DataFrames
    merged_df = dfs[0]
    for df in dfs[1:]:
        merged_df = merged_df.merge(df, on=on, how='outer', suffixes=('', '_dup'))
        # Remove duplicate columns (keep first occurrence)
        merged_df = merged_df.loc[:, ~merged_df.columns.str.endswith('_dup')]
    
    # Save merged result
    output_path = Path(output_path)
    if output_path.suffix == '.parquet':
        merged_df.to_parquet(output_path, index=False, engine='pyarrow')
    elif output_path.suffix == '.json':
        save_metrics_to_json(merged_df.to_dict('records'), output_path)
    else:
        raise ValueError(f"Unsupported output format: {output_path.suffix}")
    
    logger.info(f"Merged {len(file_paths)} metrics files into {output_path} ({len(merged_df)} designs)")
    return output_path
