#!/bin/bash

###############################################################################
# Run Full Two-Stage Pipeline (Metrics + Filtering)
#
# 一键运行完整的两阶段筛选流程（Part1 指标计算与筛选分离架构）。
# 若需跑完整 De novo（Part1+Part2+Part3），请使用 run_denovo_design.sh + config/full_pipeline.yaml。
# 使用方法：修改下面的配置变量，然后运行：./scripts/run_full_pipeline.sh
#
# 流程：
#   1) part1/part1_compute_stage1_metrics.sh   → stage1_metrics.parquet
#   2) part1/part1_filter_stage1_metrics.sh   → stage1_passed_design_names.txt
#   3) part1/part1_compute_stage2_metrics.sh   → stage2_metrics.parquet
#   4) part1/part1_filter_stage2_metrics.sh   → stage2_passed.parquet
#
# 注意：此脚本会自动同步配置到 scripts/part1/ 下各子脚本
###############################################################################

set -e

#######################################
# 全局配置（请根据需要修改）
#######################################

# 输入/输出路径
INPUT_DIR="./af3_predictions"              # 输入目录（包含 PDB/CIF 和 JSON 文件）
STAGE1_METRICS_DIR="./stage1_metrics"      # Stage 1 指标输出目录
STAGE1_FILTERED_DIR="./stage1_filtered"   # Stage 1 筛选结果目录
STAGE2_METRICS_DIR="./stage2_metrics"     # Stage 2 指标输出目录
STAGE2_FILTERED_DIR="./stage2_filtered"   # Stage 2 筛选结果目录

# PDB 与链配置
TARGET_CHAIN="A"                          # 目标链 ID
BINDER_CHAIN="B"                          # 结合子链 ID

#######################################
# Stage 1 筛选阈值（快速指标）
#######################################

STAGE1_PLDDT_THRESHOLD=0.7                # pLDDT 阈值（>=）
STAGE1_CLASHES_THRESHOLD=5                # 碰撞阈值（<）
STAGE1_PDOCKQ_THRESHOLD=0.2              # pDockQ 阈值（>=）
STAGE1_IPTM_THRESHOLD=0.0                 # iPTM 阈值（>=，0 表示不启用）
STAGE1_SAP_THRESHOLD=0.0                  # SAP 阈值（<，0 表示不启用）
STAGE1_IPSAE_THRESHOLD=0.0                # IPSAE 阈值（>=，0 表示不启用）
STAGE1_TOP_N=1000                         # 保留 top N 候选进入 Stage 2

#######################################
# Stage 2 筛选阈值（精细指标）
#######################################

STAGE2_INTERFACE_DG_THRESHOLD=-10.0       # 界面 dG 阈值（<）
STAGE2_INTERFACE_PACKSTAT_THRESHOLD=0.6   # 界面 packstat 阈值（>=）
STAGE2_INTERFACE_SC_THRESHOLD=0.0         # 界面形状互补性阈值（>=，0 表示不启用）
STAGE2_A2BINDER_THRESHOLD=0.0             # A2binder 亲和力阈值（>=，0 表示不启用）

#######################################
# 日志级别
#######################################

LOG_LEVEL="INFO"                          # 日志级别：DEBUG, INFO, WARNING, ERROR

###############################################################################
# 辅助函数：同步配置到子脚本
###############################################################################

sync_config_to_script() {
    local script_file="$1"
    local var_name="$2"
    local var_value="$3"
    
    # 检查脚本文件是否存在
    if [[ ! -f "$script_file" ]]; then
        echo "Warning: Script file not found: $script_file"
        return 1
    fi
    
    # 转义特殊字符用于sed
    local escaped_value
    escaped_value=$(printf '%s\n' "$var_value" | sed 's/[[\.*^$()+?{|]/\\&/g' | sed 's/"/\\"/g')
    
    # 使用 sed -i 进行原地替换（Linux/GNU sed）
    # 先尝试使用 -i.bak（GNU sed）
    if sed -i.bak "s|^${var_name}=.*|${var_name}=\"${escaped_value}\"|" "$script_file" 2>/dev/null; then
        rm -f "${script_file}.bak" 2>/dev/null || true
        return 0
    fi
    
    # 如果失败，尝试使用临时文件方式（更兼容）
    local temp_file
    temp_file=$(mktemp) || {
        echo "Error: Failed to create temporary file"
        return 1
    }
    
    if sed "s|^${var_name}=.*|${var_name}=\"${escaped_value}\"|" "$script_file" > "$temp_file" 2>/dev/null; then
        if mv "$temp_file" "$script_file" 2>/dev/null; then
            return 0
        else
            rm -f "$temp_file" 2>/dev/null || true
            return 1
        fi
    else
        rm -f "$temp_file" 2>/dev/null || true
        return 1
    fi
}

###############################################################################
# 主流程
###############################################################################

main() {
    # 获取脚本所在目录，确保路径正确
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    echo "=========================================="
    echo "Run Full Two-Stage Pipeline"
    echo "=========================================="
    echo ""
    echo "Input directory:        $INPUT_DIR"
    echo "Stage1 metrics dir:     $STAGE1_METRICS_DIR"
    echo "Stage1 filtered dir:    $STAGE1_FILTERED_DIR"
    echo "Stage2 metrics dir:     $STAGE2_METRICS_DIR"
    echo "Stage2 filtered dir:    $STAGE2_FILTERED_DIR"
    echo ""
    echo "Stage1 thresholds:"
    echo "  pLDDT   >= $STAGE1_PLDDT_THRESHOLD"
    echo "  clashes <  $STAGE1_CLASHES_THRESHOLD"
    echo "  pDockQ  >= $STAGE1_PDOCKQ_THRESHOLD"
    echo "  top-n   =  $STAGE1_TOP_N"
    echo ""
    echo "Stage2 thresholds:"
    echo "  interface_dG        <  $STAGE2_INTERFACE_DG_THRESHOLD"
    echo "  interface_packstat  >= $STAGE2_INTERFACE_PACKSTAT_THRESHOLD"
    echo ""

    # 验证输入目录
    if [[ ! -d "$INPUT_DIR" ]]; then
        echo "Error: Input directory does not exist: $INPUT_DIR"
        echo "Please modify INPUT_DIR in the script configuration section"
        exit 1
    fi

    # 同步配置到各个子脚本
    echo "Synchronizing configuration to sub-scripts..."
    
    # 同步到 part1_compute_stage1_metrics.sh
    sync_config_to_script "$SCRIPT_DIR/part1/part1_compute_stage1_metrics.sh" "INPUT_DIR" "$INPUT_DIR"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_compute_stage1_metrics.sh" "OUTPUT_DIR" "$STAGE1_METRICS_DIR"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_compute_stage1_metrics.sh" "TARGET_CHAIN" "$TARGET_CHAIN"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_compute_stage1_metrics.sh" "BINDER_CHAIN" "$BINDER_CHAIN"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_compute_stage1_metrics.sh" "LOG_LEVEL" "$LOG_LEVEL"
    
    # 同步到 part1_filter_stage1_metrics.sh
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage1_metrics.sh" "METRICS_FILE" "$STAGE1_METRICS_DIR/stage1_metrics.parquet"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage1_metrics.sh" "OUTPUT_DIR" "$STAGE1_FILTERED_DIR"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage1_metrics.sh" "PLDDT_THRESHOLD" "$STAGE1_PLDDT_THRESHOLD"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage1_metrics.sh" "CLASHES_THRESHOLD" "$STAGE1_CLASHES_THRESHOLD"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage1_metrics.sh" "PDOCKQ_THRESHOLD" "$STAGE1_PDOCKQ_THRESHOLD"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage1_metrics.sh" "IPTM_THRESHOLD" "$STAGE1_IPTM_THRESHOLD"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage1_metrics.sh" "SAP_THRESHOLD" "$STAGE1_SAP_THRESHOLD"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage1_metrics.sh" "IPSAE_THRESHOLD" "$STAGE1_IPSAE_THRESHOLD"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage1_metrics.sh" "TOP_N" "$STAGE1_TOP_N"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage1_metrics.sh" "LOG_LEVEL" "$LOG_LEVEL"
    
    # 同步到 part1_compute_stage2_metrics.sh
    sync_config_to_script "$SCRIPT_DIR/part1/part1_compute_stage2_metrics.sh" "INPUT_DIR" "$INPUT_DIR"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_compute_stage2_metrics.sh" "STAGE1_PASSED" "$STAGE1_FILTERED_DIR/stage1_passed_design_names.txt"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_compute_stage2_metrics.sh" "OUTPUT_DIR" "$STAGE2_METRICS_DIR"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_compute_stage2_metrics.sh" "TARGET_CHAIN" "$TARGET_CHAIN"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_compute_stage2_metrics.sh" "BINDER_CHAIN" "$BINDER_CHAIN"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_compute_stage2_metrics.sh" "LOG_LEVEL" "$LOG_LEVEL"
    
    # 同步到 part1_filter_stage2_metrics.sh
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage2_metrics.sh" "METRICS_FILE" "$STAGE2_METRICS_DIR/stage2_metrics.parquet"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage2_metrics.sh" "OUTPUT_DIR" "$STAGE2_FILTERED_DIR"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage2_metrics.sh" "INTERFACE_DG_THRESHOLD" "$STAGE2_INTERFACE_DG_THRESHOLD"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage2_metrics.sh" "INTERFACE_PACKSTAT_THRESHOLD" "$STAGE2_INTERFACE_PACKSTAT_THRESHOLD"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage2_metrics.sh" "INTERFACE_SC_THRESHOLD" "$STAGE2_INTERFACE_SC_THRESHOLD"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage2_metrics.sh" "A2BINDER_THRESHOLD" "$STAGE2_A2BINDER_THRESHOLD"
    sync_config_to_script "$SCRIPT_DIR/part1/part1_filter_stage2_metrics.sh" "LOG_LEVEL" "$LOG_LEVEL"
    
    echo "Configuration synchronized."
    echo ""

    ###################################
    # 1. 计算 Stage 1 指标
    ###################################
    echo "[1/4] Computing Stage 1 metrics..."
    echo ""
    
    "$SCRIPT_DIR/part1/part1_compute_stage1_metrics.sh" || {
        echo "Error: Stage 1 metrics computation failed!"
        exit 1
    }

    ###################################
    # 2. 筛选 Stage 1
    ###################################
    echo ""
    echo "[2/4] Filtering Stage 1 metrics..."
    echo ""
    
    STAGE1_METRICS_FILE="$STAGE1_METRICS_DIR/stage1_metrics.parquet"
    if [[ ! -f "$STAGE1_METRICS_FILE" ]]; then
        echo "Error: Stage1 metrics file not found: $STAGE1_METRICS_FILE"
        exit 1
    fi
    
    "$SCRIPT_DIR/part1/part1_filter_stage1_metrics.sh" || {
        echo "Error: Stage 1 filtering failed!"
        exit 1
    }

    STAGE1_PASSED_LIST="$STAGE1_FILTERED_DIR/stage1_passed_design_names.txt"
    if [[ ! -f "$STAGE1_PASSED_LIST" ]]; then
        echo "Error: Stage1 passed design list not found: $STAGE1_PASSED_LIST"
        exit 1
    fi

    ###################################
    # 3. 计算 Stage 2 指标
    ###################################
    echo ""
    echo "[3/4] Computing Stage 2 metrics..."
    echo ""
    
    "$SCRIPT_DIR/part1/part1_compute_stage2_metrics.sh" || {
        echo "Error: Stage 2 metrics computation failed!"
        exit 1
    }

    ###################################
    # 4. 筛选 Stage 2
    ###################################
    echo ""
    echo "[4/4] Filtering Stage 2 metrics..."
    echo ""
    
    STAGE2_METRICS_FILE="$STAGE2_METRICS_DIR/stage2_metrics.parquet"
    if [[ ! -f "$STAGE2_METRICS_FILE" ]]; then
        echo "Error: Stage2 metrics file not found: $STAGE2_METRICS_FILE"
        exit 1
    fi
    
    "$SCRIPT_DIR/part1/part1_filter_stage2_metrics.sh" || {
        echo "Error: Stage 2 filtering failed!"
        exit 1
    }

    echo ""
    echo "=========================================="
    echo "Full pipeline completed successfully!"
    echo "=========================================="
    echo "Stage1 metrics:   $STAGE1_METRICS_DIR/stage1_metrics.parquet"
    echo "Stage1 passed:   $STAGE1_FILTERED_DIR/stage1_passed.parquet"
    echo "Stage2 metrics:  $STAGE2_METRICS_DIR/stage2_metrics.parquet"
    echo "Stage2 passed:   $STAGE2_FILTERED_DIR/stage2_passed.parquet"
    echo ""
    echo "Final results:   $STAGE2_FILTERED_DIR/stage2_passed_design_names.txt"
    echo "=========================================="
}

main "$@"
