#!/bin/bash

###############################################################################
# Stage 2 Metrics Computation Script
#
# 计算精细指标并保存到 parquet 文件（只对 Stage 1 通过的设计）
# 使用方法：修改下面的配置变量，然后运行：./scripts/part1/part1_compute_stage2_metrics.sh
###############################################################################

set -e

#######################################
# 配置变量（请根据需要修改）
#######################################

# 输入/输出路径
INPUT_DIR="/data/Tools/boltzgen/workbench/test_PI3K_BH_251225/final_ranked_designs_01/final_100_designs/"  # 输入目录（包含 PDB/CIF 和 JSON 文件）
STAGE1_PASSED="./stage1_filtered/stage1_passed_design_names.txt"  # Stage 1 通过的设计列表（.txt 或 .parquet）
OUTPUT_DIR="./stage2_metrics"                                    # 输出目录
METRICS_FILE="stage2_metrics.parquet"                            # 指标文件名

# 结构文件与链配置
PDB_PATTERN="*.{pdb,cif}"                                         # 结构文件匹配模式（支持 PDB 和 CIF）
TARGET_CHAIN="A"                                                  # 目标链 ID
BINDER_CHAIN="B"                                                  # 结合子链 ID
RELAXER="pyrosetta"                                               # 结构松弛器："none" 或 "pyrosetta"（精细指标建议用 "pyrosetta"）

# 精细指标配置
ENABLE_INTERFACE=true                                             # 启用界面分析（16个指标，需要 PyRosetta）
ENABLE_SAP=true                                                   # 启用 SAP 指标（需要 PyRosetta）
ENABLE_SECONDARY_STRUCTURE=true                                  # 启用二级结构指标（需要 PyRosetta）
ENABLE_A2BINDER=false                                            # 启用 A2binder 亲和力预测

# A2binder 配置（如果启用）
A2BINDER_MODEL_PATH=""                                            # A2binder 模型路径
A2BINDER_HEAVY_MODEL_DIR=""                                       # Heavy 模型目录
A2BINDER_LIGHT_MODEL_DIR=""                                       # Light 模型目录
A2BINDER_TOKENIZER_DIR=""                                         # Tokenizer 目录
A2BINDER_DEVICE="cuda"                                            # 设备："cuda" 或 "cpu"

# PyRosetta 配置（如果使用）
PYROSETTA_INIT=""                                                 # PyRosetta 初始化选项（留空使用默认）
PYROSETTA_PATH=""                                                 # PyRosetta 安装路径（用于设置 PYTHONPATH，如：/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360）

# Conda 环境配置（可选，推荐使用）
CONDA_ENV=""                                                      # Conda 环境名称（如：PyRosetta），如果设置，脚本会自动激活该环境

# Python 环境配置（可选，留空则自动检测）
PYTHON_CMD=""                                                     # 指定 Python 命令路径（如：/home/supervisor/anaconda3/envs/PyRosetta/bin/python3）
                                                                  # 注意：如果设置了 CONDA_ENV，会自动使用该环境的 Python，此选项会被忽略

# 日志配置
LOG_LEVEL="INFO"                                                  # 日志级别：DEBUG, INFO, WARNING, ERROR

###############################################################################
# 主流程（无需修改）
###############################################################################

# 验证输入
if [[ ! -d "$INPUT_DIR" ]]; then
    echo "Error: Input directory does not exist: $INPUT_DIR"
    echo "Please modify INPUT_DIR in the script configuration section"
    exit 1
fi

if [[ ! -f "$STAGE1_PASSED" ]]; then
    echo "Error: Stage1 passed file not found: $STAGE1_PASSED"
    echo "Please run part1_filter_stage1_metrics.sh first, or modify STAGE1_PASSED in the script"
    exit 1
fi

# 验证 A2binder 配置
if [[ "$ENABLE_A2BINDER" == true ]]; then
    if [[ -z "$A2BINDER_MODEL_PATH" ]]; then
        echo "Error: A2BINDER_MODEL_PATH is required when ENABLE_A2BINDER=true"
        echo "Please set A2BINDER_MODEL_PATH in the script configuration section"
        exit 1
    fi
fi

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 辅助函数：将 shell 布尔值转换为 Python 布尔值
shell_to_python_bool() {
    if [[ "$1" == "true" ]]; then
        echo "True"
    else
        echo "False"
    fi
}

# 辅助函数：激活 conda 环境
activate_conda_env() {
    local env_name="$1"
    
    if [[ -z "$env_name" ]]; then
        return 0
    fi
    
    # 初始化 conda（如果还没有）
    if [[ -z "$CONDA_DEFAULT_ENV" ]] || [[ "$CONDA_DEFAULT_ENV" != "$env_name" ]]; then
        # 尝试找到 conda
        if [[ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]]; then
            source "$HOME/anaconda3/etc/profile.d/conda.sh"
        elif [[ -f "/opt/conda/etc/profile.d/conda.sh" ]]; then
            source "/opt/conda/etc/profile.d/conda.sh"
        elif [[ -n "$CONDA_PREFIX" ]]; then
            # 如果已经在 conda 环境中，尝试使用 conda 命令
            if command -v conda &> /dev/null; then
                # conda 已可用
                :
            else
                echo "Warning: Cannot find conda initialization script"
                return 1
            fi
        else
            # 尝试从 PATH 中找到 conda
            local conda_path=$(command -v conda 2>/dev/null)
            if [[ -n "$conda_path" ]]; then
                # 尝试从 conda 路径推断初始化脚本位置
                local conda_base=$(dirname $(dirname "$conda_path"))
                if [[ -f "$conda_base/etc/profile.d/conda.sh" ]]; then
                    source "$conda_base/etc/profile.d/conda.sh"
                else
                    echo "Warning: Cannot find conda initialization script"
                    return 1
                fi
            else
                echo "Warning: conda command not found"
                return 1
            fi
        fi
        
        # 激活环境
        if conda env list | grep -q "^${env_name}\s"; then
            echo "Activating conda environment: $env_name"
            conda activate "$env_name"
            if [[ $? -eq 0 ]]; then
                echo "✅ Conda environment activated: $env_name"
                return 0
            else
                echo "❌ Failed to activate conda environment: $env_name"
                return 1
            fi
        else
            echo "❌ Conda environment not found: $env_name"
            echo "Available environments:"
            conda env list | grep -v "^#" | awk '{print "  - " $1}'
            return 1
        fi
    else
        echo "Conda environment already active: $env_name"
        return 0
    fi
}

# 创建 Python 脚本
cat > "$OUTPUT_DIR/compute_stage2_metrics.py" << PYTHON_SCRIPT
#!/usr/bin/env python3
"""
Stage 2 Metrics Computation Script
Computes slow/expensive metrics for stage1-passed designs.
"""

import sys
import logging
from pathlib import Path
import pandas as pd
from protein_filter import ProteinFilter, FilterConfig, Design, StructureRelaxerConfig, MetricConfig
from protein_filter.utils import (
    save_metrics_to_parquet,
    load_metrics_from_parquet,
)

# Configure logging
logging.basicConfig(
    level=logging.${LOG_LEVEL},
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
INPUT_DIR = Path("${INPUT_DIR}")
STAGE1_PASSED = Path("${STAGE1_PASSED}")
OUTPUT_DIR = Path("${OUTPUT_DIR}")
METRICS_FILE = Path("${OUTPUT_DIR}") / "${METRICS_FILE}"
TARGET_CHAIN = "${TARGET_CHAIN}"
BINDER_CHAIN = "${BINDER_CHAIN}"
RELAXER = "${RELAXER}"
PDB_PATTERN = "${PDB_PATTERN}"

# PyRosetta initialization options
PYROSETTA_INIT = "${PYROSETTA_INIT}" if "${PYROSETTA_INIT}" else None

# Slow metrics to enable
ENABLED_METRICS = []

if $(shell_to_python_bool "${ENABLE_INTERFACE}"):
    # Interface analysis metrics (require PyRosetta)
    ENABLED_METRICS.extend([
        "interface_dG", "interface_dSASA", "interface_packstat",
        "interface_sc", "interface_hbonds", "interface_hydrophobicity",
        "binder_score", "surface_hydrophobicity"
    ])

if $(shell_to_python_bool "${ENABLE_SAP}"):
    # SAP metrics (require PyRosetta)
    ENABLED_METRICS.extend(["sap_score", "cdr_sap", "hydrophobic_patches_binder"])

if $(shell_to_python_bool "${ENABLE_SECONDARY_STRUCTURE}"):
    # Secondary structure metrics (require PyRosetta)
    ENABLED_METRICS.extend(["alpha_all", "beta_all", "loops_all"])

if $(shell_to_python_bool "${ENABLE_A2BINDER}"):
    ENABLED_METRICS.append("a2binder_affinity")

# A2binder config
A2BINDER_CONFIG = None
if $(shell_to_python_bool "${ENABLE_A2BINDER}"):
    A2BINDER_CONFIG = {
        "model_path": "${A2BINDER_MODEL_PATH}",
        "heavy_model_dir": "${A2BINDER_HEAVY_MODEL_DIR}",
        "light_model_dir": "${A2BINDER_LIGHT_MODEL_DIR}",
        "antibody_tokenizer_dir": "${A2BINDER_TOKENIZER_DIR}",
        "device": "${A2BINDER_DEVICE}",
        "use_light_chain": False,  # For VNAR/nanobodies
        "nanobody_model": True,
    }

# Create filter configuration (no filters, only metrics)
config = FilterConfig(
    structure_relaxer=StructureRelaxerConfig(
        name=RELAXER,
        pyrosetta_init=PYROSETTA_INIT,
    ),
    metrics=MetricConfig(
        enabled=ENABLED_METRICS,
        a2binder_config=A2BINDER_CONFIG,
    ),
    filters={},  # No filters, only compute metrics
    output_dir=str(OUTPUT_DIR),
)

def load_stage1_passed_designs() -> list:
    """Load design names from stage1 passed file"""
    design_names = []
    
    if STAGE1_PASSED.suffix == '.parquet':
        # Load from parquet
        df = load_metrics_from_parquet(STAGE1_PASSED)
        if 'design_name' in df.columns:
            design_names = df['design_name'].tolist()
        else:
            logger.error("'design_name' column not found in parquet file")
            return []
    elif STAGE1_PASSED.suffix == '.txt':
        # Load from text file (one design name per line)
        with open(STAGE1_PASSED, 'r') as f:
            design_names = [line.strip() for line in f if line.strip()]
    else:
        raise ValueError(f"Unsupported file format: {STAGE1_PASSED.suffix}")
    
    logger.info(f"Loaded {len(design_names)} design names from {STAGE1_PASSED}")
    return design_names

def load_designs(design_names: list) -> list:
    """Load designs from input directory"""
    designs = []
    
    for design_name in design_names:
        # Try to find structure file (PDB or CIF)
        pdb_file = INPUT_DIR / f"{design_name}.pdb"
        if not pdb_file.exists():
            pdb_file = INPUT_DIR / f"{design_name}.cif"
        if not pdb_file.exists():
            # Try with pattern (handle different naming)
            matches = list(INPUT_DIR.glob(f"{design_name}.pdb")) + list(INPUT_DIR.glob(f"{design_name}.cif"))
            if matches:
                pdb_file = matches[0]
            else:
                logger.warning(f"Structure file not found for {design_name}, skipping")
                continue
        
        try:
            sequence = "MKLLVL..."  # TODO: Extract from PDB or provide separately
            design = Design(
                sequence=sequence,
                pdb_path=str(pdb_file),
                target_chain=TARGET_CHAIN,
                binder_chain=BINDER_CHAIN,
                design_name=design_name,
            )
            designs.append(design)
        except Exception as e:
            logger.warning(f"Error loading {design_name}: {e}")
            continue
    
    return designs

def compute_metrics(designs: list) -> list:
    """Compute metrics for all designs"""
    filter_system = ProteinFilter(config)
    metrics_list = []
    
    total = len(designs)
    for i, design in enumerate(designs):
        if (i + 1) % 10 == 0:
            logger.info(f"Processing {i + 1}/{total} designs...")
        
        try:
            result = filter_system.filter(design)
            
            # Extract metrics and add design_name
            metrics = result.metrics.copy()
            metrics["design_name"] = design.design_name
            metrics["pdb_path"] = design.pdb_path
            
            metrics_list.append(metrics)
        except Exception as e:
            logger.error(f"Error computing metrics for {design.design_name}: {e}")
            # Still add entry with design_name for tracking
            metrics_list.append({
                "design_name": design.design_name,
                "pdb_path": design.pdb_path if 'design' in locals() else "",
                "error": str(e),
            })
    
    return metrics_list

def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("Stage 2 Metrics Computation")
    logger.info("=" * 60)
    logger.info(f"Input directory: {INPUT_DIR}")
    logger.info(f"Stage1 passed file: {STAGE1_PASSED}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info(f"Metrics file: {METRICS_FILE}")
    logger.info(f"Enabled metrics: {ENABLED_METRICS}")
    logger.info(f"Relaxer: {RELAXER}")
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load stage1 passed designs
    design_names = load_stage1_passed_designs()
    if not design_names:
        logger.error("No designs found in stage1 passed file!")
        return 1
    
    # Load designs
    designs = load_designs(design_names)
    if not designs:
        logger.error("No designs loaded!")
        return 1
    
    logger.info(f"Computing metrics for {len(designs)} designs...")
    
    # Compute metrics
    metrics_list = compute_metrics(designs)
    
    # Save to parquet
    logger.info(f"Saving metrics to {METRICS_FILE}...")
    save_metrics_to_parquet(metrics_list, METRICS_FILE)
    
    logger.info("=" * 60)
    logger.info("Stage 2 metrics computation complete!")
    logger.info(f"Metrics saved to: {METRICS_FILE}")
    logger.info(f"Total designs processed: {len(metrics_list)}")
    logger.info("=" * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
PYTHON_SCRIPT

chmod +x "$OUTPUT_DIR/compute_stage2_metrics.py"

# 运行 Python 脚本
echo "=========================================="
echo "Stage 2 Metrics Computation"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Input directory: $INPUT_DIR"
echo "  Stage1 passed file: $STAGE1_PASSED"
echo "  Output directory: $OUTPUT_DIR"
echo "  Metrics file: $METRICS_FILE"
echo "  Relaxer: $RELAXER"
if [[ -n "$CONDA_ENV" ]]; then
    echo "  Conda environment: $CONDA_ENV (will be activated)"
fi
if [[ -n "$PYROSETTA_PATH" ]]; then
    echo "  PyRosetta path: $PYROSETTA_PATH"
fi
echo ""
echo "Enabled metrics:"
if ${ENABLE_INTERFACE}; then
    echo "  - Interface analysis (requires PyRosetta)"
fi
if ${ENABLE_SAP}; then
    echo "  - SAP metrics (requires PyRosetta)"
fi
if ${ENABLE_SECONDARY_STRUCTURE}; then
    echo "  - Secondary structure (requires PyRosetta)"
fi
if ${ENABLE_A2BINDER}; then
    echo "  - A2binder affinity"
fi
echo ""

# 激活 conda 环境（如果指定）
if [[ -n "$CONDA_ENV" ]]; then
    if ! activate_conda_env "$CONDA_ENV"; then
        echo ""
        echo "Error: Failed to activate conda environment: $CONDA_ENV"
        echo "Please check the environment name or install it first"
        exit 1
    fi
    # 环境激活后，使用该环境的 Python
    PYTHON_CMD="python3"
    echo "Using Python from conda environment: $CONDA_ENV"
fi

# 检测 Python 命令
if [[ -n "$PYTHON_CMD" ]]; then
    # 使用指定的 Python 命令
    if [[ ! -f "$PYTHON_CMD" ]] && ! command -v "$PYTHON_CMD" &> /dev/null; then
        echo "Error: Specified Python command not found: $PYTHON_CMD"
        exit 1
    fi
    if [[ -z "$CONDA_ENV" ]]; then
        echo "Using specified Python: $PYTHON_CMD"
    fi
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found. Please install Python 3.7+"
    exit 1
fi

# 设置 PYTHONPATH（如果指定了 PyRosetta 路径）
if [[ -n "$PYROSETTA_PATH" ]]; then
    if [[ -d "$PYROSETTA_PATH" ]]; then
        export PYTHONPATH="$PYROSETTA_PATH:$PYTHONPATH"
        echo "Set PYTHONPATH to include: $PYROSETTA_PATH"
    else
        echo "Warning: PyRosetta path does not exist: $PYROSETTA_PATH"
    fi
fi

# 检查 PyRosetta（如果启用需要 PyRosetta 的指标）
if ${ENABLE_INTERFACE} || ${ENABLE_SAP} || ${ENABLE_SECONDARY_STRUCTURE}; then
    if [[ "$RELAXER" == "pyrosetta" ]] || ${ENABLE_INTERFACE} || ${ENABLE_SAP} || ${ENABLE_SECONDARY_STRUCTURE}; then
        echo "Checking PyRosetta availability..."
        if ! $PYTHON_CMD -c "import pyrosetta" 2>/dev/null; then
            echo ""
            echo "⚠️  WARNING: PyRosetta is not available!"
            echo "   Some metrics will not be calculated:"
            if ${ENABLE_INTERFACE}; then
                echo "     - Interface analysis metrics"
            fi
            if ${ENABLE_SAP}; then
                echo "     - SAP metrics"
            fi
            if ${ENABLE_SECONDARY_STRUCTURE}; then
                echo "     - Secondary structure metrics"
            fi
            echo ""
            echo "   The script will continue but these metrics will be missing."
            echo "   To install PyRosetta, visit: https://www.pyrosetta.org/"
            echo ""
            read -p "Continue anyway? (y/n) " -n 1 -r
            echo ""
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo "Aborted."
                exit 1
            fi
        else
            echo "✅ PyRosetta is available"
        fi
    fi
fi

echo "Running metrics computation..."
echo ""

$PYTHON_CMD "$OUTPUT_DIR/compute_stage2_metrics.py" 2>&1 | tee "$OUTPUT_DIR/compute_stage2_metrics.log"

EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    echo ""
    echo "=========================================="
    echo "Stage 2 metrics computation completed!"
    echo "=========================================="
    echo "Metrics saved to: $OUTPUT_DIR/$METRICS_FILE"
    echo ""
    echo "Next step: Run part1_filter_stage2_metrics.sh to filter based on thresholds"
else
    echo ""
    echo "=========================================="
    echo "Stage 2 metrics computation failed!"
    echo "=========================================="
    exit $EXIT_CODE
fi
