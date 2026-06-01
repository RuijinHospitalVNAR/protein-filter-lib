#!/bin/bash

###############################################################################
# Stage 1 Metrics Computation Script
#
# 计算快速指标并保存到 parquet 文件
# 使用方法：修改下面的配置变量，然后运行：./scripts/part1/part1_compute_stage1_metrics.sh
###############################################################################

set -e

#######################################
# 配置变量（请根据需要修改）
#######################################

# 输入/输出路径
INPUT_DIR="/data/Tools/boltzgen/workbench/test_PI3K_BHSH3_260116/final_ranked_designs/final_100_designs"              # 输入目录（包含 PDB/CIF 和 JSON 文件）
OUTPUT_DIR="/data/Tools/boltzgen/workbench/test_PI3K_BHSH3_260116/final_ranked_designs/stage1_metrics"               # 输出目录
METRICS_FILE="stage1_metrics.parquet"      # 指标文件名

# 结构文件与链配置
PDB_PATTERN="*.{pdb,cif}"                   # 结构文件匹配模式（支持 PDB 和 CIF）
TARGET_CHAIN="B"                            # 目标链 ID（VNAR 抗体）
BINDER_CHAIN="A"                            # 结合子链 ID（PI3K 抗原）
RELAXER="none"                              # 结构松弛器："none" 或 "pyrosetta"（快速指标建议用 "none"）

# 聚类筛选配置（在计算指标前先进行聚类筛选）
# 抗原-抗体互作位置聚类分析
# 功能：将符合目的结合界面的结构抓取出来，只对这些结构进行后续的stage1分析
ENABLE_CLUSTERING=true                      # 是否启用聚类筛选（true/false）
                                            # 推荐：对于大量结构，建议启用聚类筛选以聚焦到目标结合界面
CLUSTERING_METHOD="kmeans"                  # 聚类方法：hdbscan（推荐，自动参数估计）, kmeans, dbscan
                                            # 注意：如果 hdbscan 不可用，会自动切换到 kmeans
CLUSTERING_MIN_CLUSTER_SIZE=5               # 最小簇大小（用于HDBSCAN，0表示自动估计）
CLUSTERING_MIN_SAMPLES=3                    # 最小样本数（用于HDBSCAN/DBSCAN，0表示自动估计）
CLUSTERING_TARGET_CLUSTER=""                # 目标簇ID（空字符串表示选择最大的簇，通常是最主要的结合模式）
CLUSTERING_CONTACT_CUTOFF=5.0               # 接触距离阈值（Å），用于判断抗原-抗体接触
CLUSTERING_INTERFACE_CUTOFF=8.0             # 界面原子识别距离阈值（Å），用于识别界面残基
ENABLE_CLUSTERING_VISUALIZATION=true        # 是否生成聚类可视化图表（true/false）

# 快速指标配置（仅聚类分析时禁用）
ENABLE_CLASHES=false                        # 启用碰撞检测
ENABLE_PDOCKQ=false                         # 启用 pDockQ 系列指标
ENABLE_SECONDARY_STRUCTURE=false            # 启用二级结构分析
ENABLE_SAP=false                            # 启用 SAP 评分（已移至快速指标）
ENABLE_IPSAE=false                          # 启用 IPSAE 评分（默认启用，脚本在 scripts/ 目录中）

# IPSAE 配置
IPSAE_PAE_CUTOFF=5.0                        # IPSAE PAE 截断值
IPSAE_DISTANCE_CUTOFF=5.0                   # IPSAE 距离截断值
# 注意：IPSAE 脚本路径自动检测（scripts/ipsae.py），无需设置
# 注意：只输出 IPSAE 特有参数（ipsae, ipsae_d0chn, ipsae_d0dom），不包含重复指标

# 日志配置
LOG_LEVEL="INFO"                            # 日志级别：DEBUG, INFO, WARNING, ERROR

###############################################################################
# 主流程（无需修改）
###############################################################################

# 验证输入目录
if [[ ! -d "$INPUT_DIR" ]]; then
    echo "Error: Input directory does not exist: $INPUT_DIR"
    echo "Please modify INPUT_DIR in the script configuration section"
    exit 1
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

# 如果启用聚类筛选，先执行聚类
if [[ "$ENABLE_CLUSTERING" == "true" ]]; then
    echo "=========================================="
    echo "Step 1: Antigen-Antibody Interface Clustering Filter"
    echo "=========================================="
    echo ""
    echo "抗原-抗体互作位置聚类分析"
    echo "功能：筛选出符合目的结合界面的结构，只对这些结构进行后续分析"
    echo ""
    echo "配置信息："
    echo "  - 聚类方法: $CLUSTERING_METHOD"
    echo "  - 目标链 (抗体/受体): $TARGET_CHAIN"
    echo "  - 抗原链: $BINDER_CHAIN"
    echo "  - 接触距离阈值: ${CLUSTERING_CONTACT_CUTOFF} Å"
    echo "  - 界面识别阈值: ${CLUSTERING_INTERFACE_CUTOFF} Å"
    echo ""
    echo "Performing clustering to filter structures with target binding interface..."
    echo ""
    
    # 创建临时Python脚本进行聚类
    cat > "$OUTPUT_DIR/clustering_filter.py" << CLUSTERING_SCRIPT
#!/usr/bin/env python3
"""
Interface Clustering Filter
Filters structures based on antigen-antibody interaction interface clustering.
"""

import sys
import logging
from pathlib import Path
from protein_filter.clustering import filter_by_clustering
from protein_filter.clustering.clustering import InterfaceClusteringFilter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PDB_DIR = Path("${INPUT_DIR}")
OUTPUT_DIR = Path("${OUTPUT_DIR}")
CHAIN_A = "${TARGET_CHAIN}"
ANTIGEN_CHAINS = "${BINDER_CHAIN}".split(',') if "${BINDER_CHAIN}" else ['B']
CLUSTERING_METHOD = "${CLUSTERING_METHOD}"
MIN_CLUSTER_SIZE = ${CLUSTERING_MIN_CLUSTER_SIZE}
MIN_SAMPLES = ${CLUSTERING_MIN_SAMPLES}
TARGET_CLUSTER = None if "${CLUSTERING_TARGET_CLUSTER}" == "" else int("${CLUSTERING_TARGET_CLUSTER}")
CONTACT_CUTOFF = ${CLUSTERING_CONTACT_CUTOFF}
INTERFACE_CUTOFF = ${CLUSTERING_INTERFACE_CUTOFF}
ENABLE_VISUALIZATION = $(shell_to_python_bool "${ENABLE_CLUSTERING_VISUALIZATION}")

def main():
    logger.info("Starting interface clustering filter...")
    logger.info(f"PDB directory: {PDB_DIR}")
    logger.info(f"Chain configuration: chainA={CHAIN_A}, antigen_chains={ANTIGEN_CHAINS}")
    logger.info(f"Clustering method: {CLUSTERING_METHOD}")
    
    # 创建聚类过滤器对象
    filter_obj = InterfaceClusteringFilter(
        pdb_dir=str(PDB_DIR),
        chainA=CHAIN_A,
        antigen_chains=ANTIGEN_CHAINS,
        contact_cutoff=CONTACT_CUTOFF,
        interface_cutoff=INTERFACE_CUTOFF,
        clustering_method=CLUSTERING_METHOD,
        min_cluster_size=MIN_CLUSTER_SIZE,
        min_samples=MIN_SAMPLES,
        target_cluster_id=TARGET_CLUSTER,
    )
    
    # 执行聚类
    clustering_results = filter_obj.perform_clustering()
    
    # 保存筛选后的文件列表
    if OUTPUT_DIR:
        output_path = Path(OUTPUT_DIR)
        output_path.mkdir(parents=True, exist_ok=True)
        selected_files_path = output_path / "clustering_selected_files.txt"
        with open(selected_files_path, 'w') as f:
            for filename in filter_obj.selected_file_names:
                f.write(f"{filename}\n")
        logger.info(f"Selected files list saved to: {selected_files_path}")
    
    # 生成可视化图表
    if ENABLE_VISUALIZATION and clustering_results.get('n_clusters', 0) > 0:
        logger.info("Generating clustering visualization...")
        try:
            viz_path = OUTPUT_DIR / "clustering_visualization.png"
            filter_obj.analyzer.visualize_results(
                save_path=str(viz_path),
                show_plot=False,
                clustering_type="coarse"
            )
            logger.info(f"Clustering visualization saved to: {viz_path}")
            
            # 导出单独的图表和数据
            try:
                filter_obj.analyzer._export_individual_plots(
                    str(viz_path),
                    clustering_type="coarse"
                )
                logger.info("Individual plots and data exported successfully")
            except Exception as e:
                logger.warning(f"Failed to export individual plots: {e}")
            
            # 尝试生成径向树图
            try:
                radial_path = OUTPUT_DIR / "clustering_radial_tree.svg"
                filter_obj.analyzer.plot_cluster_radial_tree(
                    save_path=str(radial_path),
                    show_plot=False,
                    use_coarse_labels=True
                )
                logger.info(f"Radial tree plot saved to: {radial_path}")
            except Exception as e:
                logger.warning(f"Failed to generate radial tree plot: {e}")
        except Exception as e:
            logger.warning(f"Failed to generate visualization: {e}")
    
    if clustering_results.get('n_clusters', 0) > 0:
        logger.info(f"Clustering completed: {clustering_results.get('n_clusters', 0)} clusters found")
        logger.info(f"Selected cluster: {clustering_results.get('selected_cluster', 'N/A')}")
        logger.info(f"Selected structures: {len(filter_obj.selected_file_names)}")
        return 0
    else:
        logger.warning("Clustering was not enabled or failed, using all files")
        return 0

if __name__ == "__main__":
    sys.exit(main())
CLUSTERING_SCRIPT

    chmod +x "$OUTPUT_DIR/clustering_filter.py"
    
    # 运行聚类脚本
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo "Error: Python not found. Please install Python 3.7+"
        exit 1
    fi
    
    $PYTHON_CMD "$OUTPUT_DIR/clustering_filter.py" 2>&1 | tee "$OUTPUT_DIR/clustering_filter.log"
    
    CLUSTERING_EXIT_CODE=$?
    if [[ $CLUSTERING_EXIT_CODE -ne 0 ]]; then
        echo ""
        echo "⚠️  Warning: Clustering filter failed (exit code: $CLUSTERING_EXIT_CODE)"
        echo "   Check the log file for details: $OUTPUT_DIR/clustering_filter.log"
        echo ""
        exit $CLUSTERING_EXIT_CODE
    else
        echo ""
        echo "✓ Clustering analysis completed successfully"
        echo "  Clustering results saved to: $OUTPUT_DIR"
        echo "  Selected structures saved to: $OUTPUT_DIR/clustering_selected_files.txt"
        echo ""
        echo "=========================================="
        echo "Clustering analysis complete!"
        echo "=========================================="
        echo "Results are available in: $OUTPUT_DIR"
        echo ""
        # 如果只进行聚类分析，不计算指标，则退出
        if [[ "$ENABLE_CLASHES" == "false" && "$ENABLE_PDOCKQ" == "false" && "$ENABLE_SECONDARY_STRUCTURE" == "false" && "$ENABLE_SAP" == "false" && "$ENABLE_IPSAE" == "false" ]]; then
            echo "Only clustering analysis was requested. Exiting."
            exit 0
        fi
        echo "  Only these structures will be used for stage1 metrics computation"
        echo ""
    fi
fi

# 辅助函数：将 shell 布尔值转换为 Python 布尔值
shell_to_python_bool() {
    if [[ "$1" == "true" ]]; then
        echo "True"
    else
        echo "False"
    fi
}

# 创建 Python 脚本
cat > "$OUTPUT_DIR/compute_stage1_metrics.py" << PYTHON_SCRIPT
#!/usr/bin/env python3
"""
Stage 1 Metrics Computation Script
Computes fast metrics and saves to parquet file.
"""

import sys
import logging
from pathlib import Path
from protein_filter import ProteinFilter, FilterConfig, Design, StructureRelaxerConfig, MetricConfig
from protein_filter.utils import save_metrics_to_parquet

# Configure logging
logging.basicConfig(
    level=logging.${LOG_LEVEL},
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
INPUT_DIR = Path("${INPUT_DIR}")
OUTPUT_DIR = Path("${OUTPUT_DIR}")
METRICS_FILE = Path("${OUTPUT_DIR}") / "${METRICS_FILE}"
TARGET_CHAIN = "${TARGET_CHAIN}"
BINDER_CHAIN = "${BINDER_CHAIN}"
RELAXER = "${RELAXER}"
PDB_PATTERN = "${PDB_PATTERN}"

# Fast metrics to enable
ENABLED_METRICS = ["plddt"]  # Always enable prediction confidence

if $(shell_to_python_bool "${ENABLE_CLASHES}"):
    ENABLED_METRICS.append("clashes")

if $(shell_to_python_bool "${ENABLE_PDOCKQ}"):
    ENABLED_METRICS.extend(["pdockq", "pdockq2", "lis", "lia"])

if $(shell_to_python_bool "${ENABLE_SECONDARY_STRUCTURE}"):
    ENABLED_METRICS.extend(["alpha_all", "beta_all", "loops_all"])

if $(shell_to_python_bool "${ENABLE_SAP}"):
    ENABLED_METRICS.append("sap_score")

if $(shell_to_python_bool "${ENABLE_IPSAE}"):
    ENABLED_METRICS.append("ipsae")

# Create filter configuration (no filters, only metrics)
# IPSAE 配置：只输出特有参数（ipsae, ipsae_d0chn, ipsae_d0dom），不包含重复指标
config = FilterConfig(
    structure_relaxer=StructureRelaxerConfig(name=RELAXER),
    metrics=MetricConfig(
        enabled=ENABLED_METRICS,
        ipsae_include_duplicate_metrics=False,  # 只输出 IPSAE 特有参数
        ipsae_pae_cutoff=${IPSAE_PAE_CUTOFF},
        ipsae_distance_cutoff=${IPSAE_DISTANCE_CUTOFF},
    ),
    filters={},  # No filters, only compute metrics
    output_dir=str(OUTPUT_DIR),
)

# IPSAE 参数说明：
# - 脚本路径自动检测（优先查找 scripts/ipsae.py），无需手动设置
# - 只输出 IPSAE 特有参数：ipsae, ipsae_d0chn, ipsae_d0dom

def load_designs() -> list:
    """Load all designs from input directory"""
    designs = []
    # Support both PDB and CIF files
    pdb_files = list(INPUT_DIR.glob("*.pdb")) + list(INPUT_DIR.glob("*.cif"))
    
    # 如果启用了聚类筛选，只加载选中的文件
    if $(shell_to_python_bool "${ENABLE_CLUSTERING}"):
        clustering_selected_file = OUTPUT_DIR / "clustering_selected_files.txt"
        if clustering_selected_file.exists():
            with open(clustering_selected_file, 'r') as f:
                selected_filenames = {line.strip() for line in f if line.strip()}
            # 只保留在选中列表中的文件
            pdb_files = [f for f in pdb_files if f.name in selected_filenames]
            logger.info(f"After clustering filter: {len(pdb_files)} structures selected")
        else:
            logger.warning("Clustering selected files list not found, using all files")
    
    logger.info(f"Found {len(pdb_files)} structure files in {INPUT_DIR}")
    
    for pdb_file in pdb_files:
        try:
            sequence = "MKLLVL..."  # TODO: Extract from PDB or provide separately
            design = Design(
                sequence=sequence,
                pdb_path=str(pdb_file),
                target_chain=TARGET_CHAIN,
                binder_chain=BINDER_CHAIN,
                design_name=pdb_file.stem,
            )
            designs.append(design)
        except Exception as e:
            logger.warning(f"Error loading {pdb_file}: {e}")
            continue
    
    return designs

def compute_metrics(designs: list) -> list:
    """Compute metrics for all designs"""
    filter_system = ProteinFilter(config)
    metrics_list = []
    
    total = len(designs)
    for i, design in enumerate(designs):
        if (i + 1) % 100 == 0:
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
                "pdb_path": design.pdb_path,
                "error": str(e),
            })
    
    return metrics_list

def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("Stage 1 Metrics Computation")
    logger.info("=" * 60)
    logger.info(f"Input directory: {INPUT_DIR}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info(f"Metrics file: {METRICS_FILE}")
    logger.info(f"Enabled metrics: {ENABLED_METRICS}")
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load designs
    designs = load_designs()
    if not designs:
        logger.error("No designs found!")
        return 1
    
    # Compute metrics
    logger.info(f"Computing metrics for {len(designs)} designs...")
    metrics_list = compute_metrics(designs)
    
    # Save to parquet
    logger.info(f"Saving metrics to {METRICS_FILE}...")
    save_metrics_to_parquet(metrics_list, METRICS_FILE)
    
    logger.info("=" * 60)
    logger.info("Stage 1 metrics computation complete!")
    logger.info(f"Metrics saved to: {METRICS_FILE}")
    logger.info(f"Total designs processed: {len(metrics_list)}")
    logger.info("=" * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
PYTHON_SCRIPT

chmod +x "$OUTPUT_DIR/compute_stage1_metrics.py"

# 运行 Python 脚本
echo "=========================================="
echo "Stage 1 Metrics Computation"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Input directory: $INPUT_DIR"
echo "  Output directory: $OUTPUT_DIR"
echo "  Metrics file: $METRICS_FILE"
echo "  Relaxer: $RELAXER"
if ${ENABLE_IPSAE}; then
    echo "  IPSAE: Enabled (只输出特有参数: ipsae, ipsae_d0chn, ipsae_d0dom)"
    echo "    PAE cutoff: ${IPSAE_PAE_CUTOFF}"
    echo "    Distance cutoff: ${IPSAE_DISTANCE_CUTOFF}"
    echo "    Script: 自动检测 scripts/ipsae.py"
fi
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

echo "Running metrics computation..."
echo ""

$PYTHON_CMD "$OUTPUT_DIR/compute_stage1_metrics.py" 2>&1 | tee "$OUTPUT_DIR/compute_stage1_metrics.log"

EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    echo ""
    echo "=========================================="
    echo "Stage 1 metrics computation completed!"
    echo "=========================================="
    echo "Metrics saved to: $OUTPUT_DIR/$METRICS_FILE"
    echo ""
    echo "Next step: Run part1_filter_stage1_metrics.sh to filter based on thresholds"
else
    echo ""
    echo "=========================================="
    echo "Stage 1 metrics computation failed!"
    echo "=========================================="
    exit $EXIT_CODE
fi
