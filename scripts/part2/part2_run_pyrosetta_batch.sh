#!/bin/bash
###############################################################################
# Part2 批量 PyRosetta 静态分析
#
# 用法（从仓库根目录）：bash scripts/part2/part2_run_pyrosetta_batch.sh
# 兼容：bash scripts/run_pyrosetta_batch.sh 会转发到本脚本
###############################################################################

set -e

# 配置
INPUT_DIR="/data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_output"
OUTPUT_DIR="/data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_output_pyrosetta"
BINDER_CHAIN="B"      # 抗体链（检测到链 A 和 B，B 通常为抗体）
TARGET_CHAIN="A"      # 抗原链（A 通常为抗原）
BATCH_IDX=0
RELAX=true            # ✅ 默认启用 Relax（使结构符合物理力场，结果更准确）
FIXBB=false           # Relax 时是否固定骨架
FIXED_CHAIN=""        # 固定骨架的链（如 "A" 表示固定抗原链）
MAX_ITER=200          # FastRelax 最大迭代次数（200=Germinal配置，精细优化）
MIN_TYPE="lbfgs_armijo_nonmonotone"  # 最小化类型（LBFGS算法，收敛更快）
N_JOBS=0              # 并行进程数（0=自动计算，基于CPU和内存）
MAX_CPU_PERCENT=70.0  # 最大CPU使用率阈值（%，默认70）
DUMP_TOP_N=100        # 仅保留 interface_score 前 N 的 Relax 结构（0=不保留；100=Part3 可直接用，无需再跑 Part2）

# Conda 环境配置
CONDA_ENV="VNAR_OP"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

# 本脚本位于 scripts/part2/；仓库根目录用于 .pyrosetta_path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYROSETTA_CONFIG="$REPO_ROOT/.pyrosetta_path"
if [ -f "$PYROSETTA_CONFIG" ]; then
    PYROSETTA_SITE_PACKAGES=$(cat "$PYROSETTA_CONFIG")
else
    # 默认路径
    PYROSETTA_SITE_PACKAGES="/data/Tools/PyRosetta4.Release.python310.linux.release-387/setup"
fi

PYROSETTA_SCRIPT="$SCRIPT_DIR/part2_run_pyrosetta_static_relax_interface.py"

# 检查输入目录
if [ ! -d "$INPUT_DIR" ]; then
    echo "❌ 错误：输入目录不存在: $INPUT_DIR"
    exit 1
fi

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 设置 PyRosetta 路径
if [ -d "$PYROSETTA_SITE_PACKAGES" ]; then
    export PYTHONPATH="$PYROSETTA_SITE_PACKAGES:$PYTHONPATH"
else
    echo "⚠️  警告：PyRosetta 目录不存在: $PYROSETTA_SITE_PACKAGES"
    echo "   请先运行: ./setup_VNAR_OP.sh"
    exit 1
fi

echo "=========================================="
echo "Part 2: PyRosetta 静态物理分析"
echo "=========================================="
echo "输入目录: $INPUT_DIR"
echo "输出目录: $OUTPUT_DIR"
echo "链配置: binder=$BINDER_CHAIN, target=$TARGET_CHAIN"
echo "模式: 只分析主模型（排除 seed- 目录）"
echo "Relax: $RELAX ✅"
if [ "$RELAX" = "true" ]; then
    echo "  - fixbb: $FIXBB"
    echo "  - fixed_chain: ${FIXED_CHAIN:-（无）}"
    echo "  - max_iter: $MAX_ITER"
    echo "  - dump_top_n: $DUMP_TOP_N（仅保留 interface_score 前 ${DUMP_TOP_N} 的 relax 结构）"
    echo ""
    echo "⚠️  注意：启用 Relax（平衡模式）后，每个结构需要 60-120 秒"
    echo "   313 个结构预计需要："
    echo "     - 单进程：~5-10 小时"
    echo "     - 32进程：~30-60 分钟"
fi
echo ""
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# 设置资源限制（避免 CPU 过载）
# 使用 nice 降低优先级（值越大优先级越低，范围 0-19，默认 10）
NICE_VALUE=10  # 中等优先级，不抢占其他任务
# 限制每个进程的线程数（避免单个进程使用过多 CPU）
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

echo "资源限制配置:"
echo "  - 进程优先级: nice $NICE_VALUE"
echo "  - 单进程线程限制: OMP_NUM_THREADS=$OMP_NUM_THREADS"
echo "  - 并行进程数: $N_JOBS (0=自动计算)"
echo "  - 最大CPU使用率: ${MAX_CPU_PERCENT}%"
echo ""

# 运行 PyRosetta 分析（Germinal配置：max_iter=200, LBFGS最小化）
nice -n $NICE_VALUE python3 "$PYROSETTA_SCRIPT" \
    --pdb_dir "$INPUT_DIR" \
    --output_dir "$OUTPUT_DIR" \
    --binder_chain "$BINDER_CHAIN" \
    --target_chain "$TARGET_CHAIN" \
    --batch_idx "$BATCH_IDX" \
    --relax "$RELAX" \
    --fixbb "$FIXBB" \
    --fixed_chain "$FIXED_CHAIN" \
    --max_iter "$MAX_ITER" \
    --min_type "$MIN_TYPE" \
    --dump_pdb false \
    --dump_top_n "$DUMP_TOP_N" \
    --only_main_models true \
    --n_jobs "$N_JOBS" \
    --max_cpu_percent "$MAX_CPU_PERCENT"

EXIT_CODE=$?

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ PyRosetta 分析完成！"
    echo "结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    echo "结果文件: $OUTPUT_DIR/rosetta_static_$BATCH_IDX.csv"
    echo "资源报告: $OUTPUT_DIR/resource_usage.json"
    echo ""
    # 显示结果统计
    if [ -f "$OUTPUT_DIR/rosetta_static_$BATCH_IDX.csv" ]; then
        TOTAL=$(tail -n +2 "$OUTPUT_DIR/rosetta_static_$BATCH_IDX.csv" | wc -l)
        echo "处理的结构数: $TOTAL"
        echo ""
        echo "结果预览（前 5 行）:"
        head -6 "$OUTPUT_DIR/rosetta_static_$BATCH_IDX.csv" | column -t -s, 2>/dev/null || head -6 "$OUTPUT_DIR/rosetta_static_$BATCH_IDX.csv"
    fi
    echo ""
    # 显示资源使用摘要
    if [ -f "$OUTPUT_DIR/resource_usage.json" ]; then
        echo "资源使用摘要:"
        python3 -c "
import json
with open('$OUTPUT_DIR/resource_usage.json') as f:
    data = json.load(f)
    print(f\"  总时间: {data.get('elapsed_time_formatted', 'N/A')}\")
    if 'cpu_time_seconds' in data:
        cpu_total = data['cpu_time_seconds']['total']
        print(f\"  CPU 时间: {cpu_total:.1f} 秒 ({cpu_total/3600:.2f} CPU-小时)\")
        print(f\"  CPU 利用率: {data.get('cpu_utilization_percent', 0):.1f}%\")
    print(f\"  峰值内存: {data.get('peak_memory_mb', 0):.1f} MB ({data.get('peak_memory_mb', 0)/1024:.2f} GB)\")
    if data.get('total_structures', 0) > 0:
        avg_time = data['elapsed_time_seconds'] / data['total_structures']
        print(f\"  平均每个结构: {avg_time:.1f} 秒\")
" 2>/dev/null || echo "  （无法解析资源报告）"
    fi
else
    echo "❌ PyRosetta 分析失败，退出代码: $EXIT_CODE"
    echo "请检查错误信息"
fi
echo "=========================================="

exit $EXIT_CODE
