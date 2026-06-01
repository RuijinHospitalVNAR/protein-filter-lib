#!/bin/bash

###############################################################################
# Stage 1 Filtering Script
#
# 基于已保存的 stage1_metrics.parquet 进行筛选
# 使用方法：修改下面的配置变量，然后运行：./scripts/part1/part1_filter_stage1_metrics.sh
###############################################################################

set -e

#######################################
# 配置变量（请根据需要修改）
#######################################

# 输入/输出路径
METRICS_FILE="./stage1_metrics/stage1_metrics.parquet"  # Stage 1 指标文件路径
OUTPUT_DIR="./stage1_filtered"                          # 输出目录

# 筛选阈值
PLDDT_THRESHOLD=0.7                                     # pLDDT 阈值（>=）
CLASHES_THRESHOLD=5                                     # 碰撞阈值（<）
IPTM_THRESHOLD=0.0                                      # iPTM 阈值（>=，0 表示不启用）
PDOCKQ_THRESHOLD=0.2                                    # pDockQ 阈值（>=）
SAP_THRESHOLD=0.0                                       # SAP 阈值（<，0 表示不启用，SAP 越高越差）
IPSAE_THRESHOLD=0.0                                     # IPSAE 阈值（>=，0 表示不启用）

# Top-N 配置
TOP_N=1000                                              # 保留 top N 候选（0 表示保留所有通过的设计）

# 综合评分权重（用于 top-n 排序，如果 TOP_N > 0）
SCORE_WEIGHT_PLDDT=0.3                                  # pLDDT 权重
SCORE_WEIGHT_IPTM=0.2                                   # iPTM 权重
SCORE_WEIGHT_PDOCKQ=0.2                                 # pDockQ 权重
SCORE_WEIGHT_IPSAE=0.2                                  # IPSAE 权重
SCORE_PENALTY_CLASHES=0.1                               # 碰撞惩罚（负权重）

# 日志配置
LOG_LEVEL="INFO"                                        # 日志级别：DEBUG, INFO, WARNING, ERROR

###############################################################################
# 主流程（无需修改）
###############################################################################

# 验证指标文件
if [[ ! -f "$METRICS_FILE" ]]; then
    echo "Error: Metrics file not found: $METRICS_FILE"
    echo "Please run part1_compute_stage1_metrics.sh first, or modify METRICS_FILE in the script"
    exit 1
fi

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 创建 Python 脚本
cat > "$OUTPUT_DIR/filter_stage1.py" << PYTHON_SCRIPT
#!/usr/bin/env python3
"""
Stage 1 Filtering Script
Filters designs based on pre-computed metrics.
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
TOP_N = ${TOP_N}

# Filter thresholds
FILTERS = {
    "external_plddt": {"threshold": ${PLDDT_THRESHOLD}, "operator": ">="},
    "clashes": {"threshold": ${CLASHES_THRESHOLD}, "operator": "<"},
}

if ${IPTM_THRESHOLD} > 0:
    FILTERS["external_iptm"] = {"threshold": ${IPTM_THRESHOLD}, "operator": ">="}

if ${PDOCKQ_THRESHOLD} > 0:
    FILTERS["pdockq"] = {"threshold": ${PDOCKQ_THRESHOLD}, "operator": ">="}

if ${SAP_THRESHOLD} > 0:
    FILTERS["sap_score"] = {"threshold": ${SAP_THRESHOLD}, "operator": "<"}

if ${IPSAE_THRESHOLD} > 0:
    FILTERS["ipsae"] = {"threshold": ${IPSAE_THRESHOLD}, "operator": ">="}

# Scoring weights
SCORE_WEIGHTS = {
    "external_plddt": ${SCORE_WEIGHT_PLDDT},
    "external_iptm": ${SCORE_WEIGHT_IPTM},
    "pdockq": ${SCORE_WEIGHT_PDOCKQ},
    "ipsae": ${SCORE_WEIGHT_IPSAE},
    "clashes": -${SCORE_PENALTY_CLASHES},  # Negative weight (penalty)
}

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

def calculate_composite_score(row: pd.Series) -> float:
    """Calculate composite score for ranking"""
    score = 0.0
    
    for metric_name, weight in SCORE_WEIGHTS.items():
        if metric_name in row.index:
            value = row[metric_name]
            if pd.notna(value) and isinstance(value, (int, float)):
                score += weight * value
    
    # Bonus for pDockQ2 if available
    if "pdockq2" in row.index and pd.notna(row["pdockq2"]):
        score += 0.1 * row["pdockq2"]
    
    return score

def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("Stage 1 Filtering")
    logger.info("=" * 60)
    logger.info(f"Metrics file: {METRICS_FILE}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info(f"Filters: {FILTERS}")
    logger.info(f"Top N: {TOP_N if TOP_N > 0 else 'All passing designs'}")
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load metrics
    logger.info(f"Loading metrics from {METRICS_FILE}...")
    df = load_metrics_from_parquet(METRICS_FILE)
    
    logger.info(f"Loaded {len(df)} designs")
    
    # Apply filters
    logger.info("Applying filters...")
    filtered_df = apply_filters(df)
    
    logger.info(f"After filtering: {len(filtered_df)} designs passed")
    
    # Calculate composite scores if top-n is specified
    if TOP_N > 0 and len(filtered_df) > TOP_N:
        logger.info(f"Calculating composite scores for ranking...")
        filtered_df["composite_score"] = filtered_df.apply(calculate_composite_score, axis=1)
        filtered_df = filtered_df.sort_values("composite_score", ascending=False)
        filtered_df = filtered_df.head(TOP_N)
        logger.info(f"Selected top {TOP_N} designs based on composite score")
    
    # Save results
    passed_file = OUTPUT_DIR / "stage1_passed.parquet"
    save_metrics_to_parquet(
        filtered_df.to_dict('records'),
        passed_file
    )
    
    # Save design names list for stage 2
    design_names_file = OUTPUT_DIR / "stage1_passed_design_names.txt"
    with open(design_names_file, 'w') as f:
        for design_name in filtered_df['design_name']:
            f.write(f"{design_name}\n")
    
    # Summary
    logger.info("=" * 60)
    logger.info("Stage 1 filtering complete!")
    logger.info(f"Total designs loaded: {len(df)}")
    logger.info(f"Designs passed filters: {len(filtered_df)}")
    logger.info(f"Results saved to: {passed_file}")
    logger.info(f"Design names list: {design_names_file}")
    logger.info("=" * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
PYTHON_SCRIPT

chmod +x "$OUTPUT_DIR/filter_stage1.py"

# 运行 Python 脚本
echo "=========================================="
echo "Stage 1 Filtering"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Metrics file: $METRICS_FILE"
echo "  Output directory: $OUTPUT_DIR"
echo "  Top N: ${TOP_N:-All passing}"
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

$PYTHON_CMD "$OUTPUT_DIR/filter_stage1.py" 2>&1 | tee "$OUTPUT_DIR/filter_stage1.log"

EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    echo ""
    echo "=========================================="
    echo "Stage 1 filtering completed!"
    echo "=========================================="
    echo "Results saved to: $OUTPUT_DIR/stage1_passed.parquet"
    echo "Design names list: $OUTPUT_DIR/stage1_passed_design_names.txt"
    echo ""
    echo "Next step: Run part1_compute_stage2_metrics.sh for selected designs"
else
    echo ""
    echo "=========================================="
    echo "Stage 1 filtering failed!"
    echo "=========================================="
    exit $EXIT_CODE
fi
