#!/bin/bash

###############################################################################
# Stage 2 Filtering Script
#
# 基于已保存的 stage2_metrics.parquet 进行筛选（只使用 Stage 2 指标）
# 使用方法：修改下面的配置变量，然后运行：./scripts/part1/part1_filter_stage2_metrics.sh
###############################################################################

set -e

#######################################
# 配置变量（请根据需要修改）
#######################################

# 输入/输出路径
METRICS_FILE="./stage2_metrics/stage2_metrics.parquet"  # Stage 2 指标文件路径
OUTPUT_DIR="./stage2_filtered"                           # 输出目录

# 筛选阈值（Stage 2 指标，只基于 stage2_metrics.parquet）
INTERFACE_DG_THRESHOLD=-10.0                            # 界面 dG 阈值（<，越负越好）
INTERFACE_PACKSTAT_THRESHOLD=0.6                        # 界面 packstat 阈值（>=）
INTERFACE_SC_THRESHOLD=0.0                              # 界面形状互补性阈值（>=，0 表示不启用）
A2BINDER_THRESHOLD=0.0                                  # A2binder 亲和力阈值（>=，0 表示不启用）

# 日志配置
LOG_LEVEL="INFO"                                         # 日志级别：DEBUG, INFO, WARNING, ERROR

###############################################################################
# 主流程（无需修改）
###############################################################################

# 验证指标文件
if [[ ! -f "$METRICS_FILE" ]]; then
    echo "Error: Metrics file not found: $METRICS_FILE"
    echo "Please run part1_compute_stage2_metrics.sh first, or modify METRICS_FILE in the script"
    exit 1
fi

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 创建 Python 脚本
cat > "$OUTPUT_DIR/filter_stage2.py" << PYTHON_SCRIPT
#!/usr/bin/env python3
"""
Stage 2 Filtering Script
Filters designs based on pre-computed stage2 metrics only.
"""

import sys
import logging
from pathlib import Path
import pandas as pd
from protein_filter.utils import load_metrics_from_parquet, save_metrics_to_parquet

# Configure logging
logging.basicConfig(
    level=logging.${LOG_LEVEL},
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
METRICS_FILE = Path("${METRICS_FILE}")
OUTPUT_DIR = Path("${OUTPUT_DIR}")

# Filter thresholds (Stage 2 metrics only)
FILTERS = {}

if ${INTERFACE_DG_THRESHOLD} < 0:
    FILTERS["interface_dG"] = {"threshold": ${INTERFACE_DG_THRESHOLD}, "operator": "<"}

if ${INTERFACE_PACKSTAT_THRESHOLD} > 0:
    FILTERS["interface_packstat"] = {"threshold": ${INTERFACE_PACKSTAT_THRESHOLD}, "operator": ">="}

if ${INTERFACE_SC_THRESHOLD} > 0:
    FILTERS["interface_sc"] = {"threshold": ${INTERFACE_SC_THRESHOLD}, "operator": ">="}

if ${A2BINDER_THRESHOLD} > 0:
    FILTERS["a2binder_affinity"] = {"threshold": ${A2BINDER_THRESHOLD}, "operator": ">="}

def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Apply filters to DataFrame"""
    filtered_df = df.copy()
    
    for metric_name, filter_config in FILTERS.items():
        if metric_name not in filtered_df.columns:
            logger.warning(f"Metric '{metric_name}' not found in metrics file, skipping filter")
            continue
        
        threshold = filter_config["threshold"]
        operator = filter_config["operator"]
        
        if operator == ">=":
            mask = filtered_df[metric_name] >= threshold
        elif operator == ">":
            mask = filtered_df[metric_name] > threshold
        elif operator == "<=":
            mask = filtered_df[metric_name] <= threshold
        elif operator == "<":
            mask = filtered_df[metric_name] < threshold
        elif operator == "==":
            mask = filtered_df[metric_name] == threshold
        else:
            logger.warning(f"Unknown operator '{operator}' for {metric_name}, skipping")
            continue
        
        before = len(filtered_df)
        filtered_df = filtered_df[mask]
        after = len(filtered_df)
        logger.info(f"Filter {metric_name} {operator} {threshold}: {before} -> {after} designs")
    
    return filtered_df

def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("Stage 2 Filtering")
    logger.info("=" * 60)
    logger.info(f"Metrics file: {METRICS_FILE}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info(f"Filters (Stage 2 metrics only): {FILTERS}")
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load metrics
    logger.info(f"Loading metrics from {METRICS_FILE}...")
    df = load_metrics_from_parquet(METRICS_FILE)
    
    logger.info(f"Loaded {len(df)} designs")
    
    # Apply filters
    if FILTERS:
        logger.info("Applying filters...")
        filtered_df = apply_filters(df)
    else:
        logger.warning("No filters specified, returning all designs")
        filtered_df = df
    
    logger.info(f"After filtering: {len(filtered_df)} designs passed")
    
    # Save results
    passed_file = OUTPUT_DIR / "stage2_passed.parquet"
    save_metrics_to_parquet(
        filtered_df.to_dict('records'),
        passed_file
    )
    
    # Save design names list
    design_names_file = OUTPUT_DIR / "stage2_passed_design_names.txt"
    with open(design_names_file, 'w') as f:
        for design_name in filtered_df['design_name']:
            f.write(f"{design_name}\n")
    
    # Summary
    logger.info("=" * 60)
    logger.info("Stage 2 filtering complete!")
    logger.info(f"Total designs loaded: {len(df)}")
    logger.info(f"Designs passed filters: {len(filtered_df)}")
    logger.info(f"Results saved to: {passed_file}")
    logger.info(f"Design names list: {design_names_file}")
    logger.info("=" * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
PYTHON_SCRIPT

chmod +x "$OUTPUT_DIR/filter_stage2.py"

# 运行 Python 脚本
echo "=========================================="
echo "Stage 2 Filtering"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Metrics file: $METRICS_FILE"
echo "  Output directory: $OUTPUT_DIR"
echo ""

# 检测 Python 命令
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found. Please install Python 3.7+"
    exit 1
fi

echo "Running filter..."
echo ""

$PYTHON_CMD "$OUTPUT_DIR/filter_stage2.py" 2>&1 | tee "$OUTPUT_DIR/filter_stage2.log"

EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    echo ""
    echo "=========================================="
    echo "Stage 2 filtering completed!"
    echo "=========================================="
    echo "Results saved to: $OUTPUT_DIR/stage2_passed.parquet"
    echo "Design names list: $OUTPUT_DIR/stage2_passed_design_names.txt"
else
    echo ""
    echo "=========================================="
    echo "Stage 2 filtering failed!"
    echo "=========================================="
    exit $EXIT_CODE
fi
