#!/usr/bin/env bash
# Optimization / 亲和力成熟模式主脚本：Part2 → 准备 Part3 CSV → Part3 AMBER → 后处理 → MMGBSA → 结果汇总
# 支持单 GPU 串行或多 GPU 并行（N_GPU 手动设定或自动检测）。
#
# 用法（从仓库根目录执行）：
#   bash scripts/run_optimization_pipeline.sh
#   CONFIG=config/my_optimizing.yaml bash scripts/run_optimization_pipeline.sh
#   AF3_DIR=/path/to/af3 TOP_N=50 PRODUCTION_NS=1 bash scripts/run_optimization_pipeline.sh
#
# 配置：优先从 config/optimizing_default.yaml 加载（可用 CONFIG 指定其它 YAML），
#       环境变量 AF3_DIR、TOP_N 等会覆盖 YAML 中的值。
# N_GPU：不设置或 N_GPU=0 或 N_GPU=auto 时自动检测（nvidia-smi），在 8 卡机上会使用 8 GPU 并行；
#        显式 N_GPU=1 为单卡串行；N_GPU=2~8 为多卡并行。
#
# 环境变量（可覆盖 YAML）：
#   N_GPU, NTOMP, AF3_DIR, EXAMPLE_BASE, TOP_N, PRODUCTION_NS, POSTPROCESS_WORKERS, MMPBSA_WORKERS, SKIP_MMGBSA
# 依赖：conda 环境 VNAR_OP（Part2）和 amber22_py310（Part3）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

# 从 YAML 加载配置（环境变量优先覆盖）
eval "$(python3 "${SCRIPT_DIR}/utils/load_config_env.py" 2>/dev/null)" || true

# 激活 conda（兼容常见路径）
if [[ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
elif [[ -f "$(conda info --base 2>/dev/null)/etc/profile.d/conda.sh" ]]; then
    source "$(conda info --base)/etc/profile.d/conda.sh"
else
    echo "错误：未找到 conda，请先安装并初始化 conda"
    exit 1
fi

# 以上由 load_config_env.py 从 config/optimizing_default.yaml 加载；环境变量可覆盖
AF3_DIR="${AF3_DIR:-}"
EXAMPLE_BASE="${EXAMPLE_BASE:-$REPO_ROOT/examples/affinity_maturation_example}"
PART2_OUT="$EXAMPLE_BASE/part2_out"
TOP_N="${TOP_N:-10}"
PRODUCTION_NS="${PRODUCTION_NS:-1}"
PART3_CSV="$EXAMPLE_BASE/part3_input_${TOP_N}.csv"
PART3_OUT_BASE="$EXAMPLE_BASE/part3_amber_out"
NTOMP="${NTOMP:-8}"
PART3_ALLOW_PARTIAL_FAILURE="${PART3_ALLOW_PARTIAL_FAILURE:-1}"
PART3_FAIL_COUNT=0

if [[ ! -d "$AF3_DIR" ]]; then
    echo "错误：AF3 目录不存在: $AF3_DIR"
    echo "请设置环境变量 AF3_DIR，或编辑 config/optimizing_default.yaml 中的 af3_dir。"
    exit 1
fi

# ONLY_MAIN_MODELS：1/true=只分析主模型（排除 seed- 目录，仅主文件夹内最佳结果）；0/false=包含 seed- 下所有采样
ONLY_MAIN_MODELS="${ONLY_MAIN_MODELS:-True}"
# ONE_PER_DESIGN：1/true=每个 design 只取一个结构（主 run 文件夹内 *_model.cif）；0/false=同 design 多 run 均保留
ONE_PER_DESIGN="${ONE_PER_DESIGN:-False}"

# ---------- Part2 ----------
if [[ ! -f "$PART2_OUT/rosetta_static_0.csv" ]]; then
    echo "=== 1. Part2 PyRosetta (环境: VNAR_OP, dump_top_n=$TOP_N, only_main_models=$ONLY_MAIN_MODELS, one_per_design=$ONE_PER_DESIGN) ==="
    conda activate VNAR_OP
    python3 scripts/part2/part2_run_pyrosetta_static_relax_interface.py \
      --pdb_dir "$AF3_DIR" \
      --output_dir "$PART2_OUT" \
      --target_chain A --binder_chain B \
      --relax True --dump_pdb True --dump_top_n "$TOP_N" \
      --only_main_models "$ONLY_MAIN_MODELS" \
      --one_per_design "$ONE_PER_DESIGN"
else
    echo "Part2 已完成，跳过（$PART2_OUT/rosetta_static_0.csv 已存在）"
fi

# ---------- 准备 Part3 CSV ----------
if [[ ! -f "$PART3_CSV" ]]; then
    echo "=== 2. 准备 Part3 输入 CSV ==="
    python3 examples/affinity_maturation_example/prepare_part3_csv.py \
      --part2_csv "$PART2_OUT/rosetta_static_0.csv" \
      --part2_dir "$PART2_OUT" \
      --top_n "$TOP_N" \
      --output "$PART3_CSV"
else
    echo "Part3 CSV 已存在，跳过"
fi

# ---------- Part3：GPU 数量（自动检测或手动设定）----------
# 未设置或 N_GPU=0 或 N_GPU=auto 时自动检测；否则使用设定值（显式 N_GPU=1 为单卡串行）
if [[ -z "${N_GPU+x}" ]] || [[ "$N_GPU" == "0" ]] || [[ "$N_GPU" == "auto" ]]; then
    DETECTED=$(nvidia-smi -L 2>/dev/null | wc -l)
    [[ -z "$DETECTED" ]] && DETECTED=0
    if [[ "$DETECTED" -eq 0 ]]; then
        DETECTED=$(nvidia-smi --query-gpu=uuid --format=csv,noheader 2>/dev/null | wc -l)
        [[ -z "$DETECTED" ]] && DETECTED=0
    fi
    if [[ "$DETECTED" -lt 1 ]]; then
        DETECTED=1
        echo "未检测到 GPU 或 nvidia-smi 不可用，使用单 GPU"
    else
        echo "自动检测到 GPU 数量: $DETECTED"
    fi
    N_GPU=$((DETECTED > TOP_N ? TOP_N : DETECTED))
    N_GPU=$((N_GPU > 8 ? 8 : N_GPU))
    N_GPU=$((N_GPU < 1 ? 1 : N_GPU))
    echo "Part3 将使用 GPU 数: $N_GPU（结构数 TOP_N=$TOP_N）"
else
    N_GPU=$((N_GPU))
    if [[ "$N_GPU" -lt 1 ]]; then N_GPU=1; fi
    if [[ "$N_GPU" -gt "$TOP_N" ]]; then
        N_GPU=$TOP_N
        echo "N_GPU 已截断为结构数: $N_GPU"
    fi
    echo "Part3 使用设定 GPU 数: $N_GPU"
fi

conda activate amber22_py310
echo ""
echo "=== 3. Part3 AMBER (环境: amber22_py310, production_ns=$PRODUCTION_NS) ==="

if [[ "$N_GPU" -eq 1 ]]; then
    echo "模式: 单 GPU 串行 (gpu0)"
    PART3_OUT="$PART3_OUT_BASE/gpu0"
    python3 scripts/part3/part3_run_amber_md_31driver.py \
      --input_csv "$PART3_CSV" \
      --output_dir "$PART3_OUT" \
      --gpu_id 0 --n_gpu 1 --top_n "$TOP_N" \
      --production_ns "$PRODUCTION_NS" \
      --resume
else
    echo "模式: $N_GPU GPU 并行 (gpu0..gpu$((N_GPU-1)))"
    nvidia-smi -L 2>/dev/null | head -10

    cleanup() {
        trap - INT TERM HUP
        echo "[CLEANUP] 正在停止所有子进程..."
        pids="$(jobs -pr 2>/dev/null || true)"
        [ -n "$pids" ] && kill $pids 2>/dev/null || true
        sleep 2
        pkill -TERM -P $$ 2>/dev/null || true
        sleep 1
        pkill -KILL -P $$ 2>/dev/null || true
        exit ${1:-130}
    }
    trap 'cleanup 130' INT TERM HUP

    RUN_LOG_ID=$(date +%Y%m%d_%H%M)
    declare -a ALL_PIDS=()

    for GPU_ID in $(seq 0 $((N_GPU - 1))); do
        GPU_DIR="${PART3_OUT_BASE}/gpu${GPU_ID}"
        LOG_FILE="${GPU_DIR}/run_${RUN_LOG_ID}.log"
        mkdir -p "$GPU_DIR"
        CPU_START=$((GPU_ID * NTOMP))
        CPU_END=$((CPU_START + NTOMP - 1))
        echo "[GPU $GPU_ID] 启动 -> $LOG_FILE (CPU ${CPU_START}-${CPU_END})"
        echo "[GPU-MAP] logical_gpu_id=$GPU_ID CUDA_VISIBLE_DEVICES=$GPU_ID physical_gpu=$GPU_ID"
        (
            export CUDA_VISIBLE_DEVICES=$GPU_ID
            echo "[GPU-MAP] logical_gpu_id=$GPU_ID CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES} physical_gpu=$GPU_ID cpu_range=${CPU_START}-${CPU_END}"
            taskset -c ${CPU_START}-${CPU_END} python3 scripts/part3/part3_run_amber_md_31driver.py \
                --input_csv "$PART3_CSV" \
                --output_dir "$GPU_DIR" \
                --gpu_id "$GPU_ID" \
                --n_gpu "$N_GPU" \
                --top_n "$TOP_N" \
                --production_ns "$PRODUCTION_NS" \
                --resume \
                >> "$LOG_FILE" 2>&1
        ) &
        ALL_PIDS+=($!)
        sleep 0.5
    done

    echo ""
    echo "$N_GPU 个 GPU 任务已启动。查看日志: tail -f ${PART3_OUT_BASE}/gpu0/run_${RUN_LOG_ID}.log"
    echo "等待全部完成..."

    fail_count=0
    for PID in "${ALL_PIDS[@]}"; do
        if ! wait "$PID"; then
            fail_count=$((fail_count + 1))
        fi
    done

    if [[ "$fail_count" -gt 0 ]]; then
        echo "警告: 有 $fail_count 个任务异常退出，请查看各 gpu*/run_*.log"
        PART3_FAIL_COUNT="$fail_count"
        if [[ "$PART3_ALLOW_PARTIAL_FAILURE" == "1" ]]; then
            echo "继续后续步骤（PART3_ALLOW_PARTIAL_FAILURE=1）：将仅处理已完成结构。"
        else
            echo "按严格模式退出（PART3_ALLOW_PARTIAL_FAILURE=0）。"
            exit 1
        fi
    fi
fi

# ---------- 步骤 4：后处理 ----------
echo ""
echo "=== 4. Part3 后处理（合并轨迹、去水、RMSD） ==="
POSTPROCESS_SH="$REPO_ROOT/AMBER/postprocess_single_cpptraj.sh"
if [[ ! -f "$POSTPROCESS_SH" ]]; then
    echo "警告: 未找到后处理脚本 $POSTPROCESS_SH，跳过后处理"
else
    POSTPROCESS_DIRS=()
    for GPU_DIR in "$PART3_OUT_BASE"/gpu*/; do
        [[ -d "$GPU_DIR" ]] || continue
        for STRUCT_DIR in "$GPU_DIR"*/; do
            [[ -d "$STRUCT_DIR" ]] || continue
            if [[ -f "$STRUCT_DIR/md_1.nc" ]] && [[ -f "$STRUCT_DIR/system.prmtop" ]]; then
                POSTPROCESS_DIRS+=("$STRUCT_DIR")
            fi
        done
    done

    if [[ ${#POSTPROCESS_DIRS[@]} -gt 0 ]]; then
        echo "找到 ${#POSTPROCESS_DIRS[@]} 个结构需要后处理"
        MAX_POST_W="${POSTPROCESS_WORKERS:-12}"
        idx=0
        for STRUCT_DIR in "${POSTPROCESS_DIRS[@]}"; do
            idx=$((idx + 1))
            STRUCT_NAME=$(basename "$STRUCT_DIR")
            echo "[$idx/${#POSTPROCESS_DIRS[@]}] 后处理: $STRUCT_NAME"
            bash "$POSTPROCESS_SH" "$STRUCT_DIR" &
            while [[ $(jobs -pr | wc -l) -ge "$MAX_POST_W" ]]; do
                sleep 1
            done
        done
        wait
        echo "后处理完成"
    else
        echo "未找到需要后处理的结构目录"
    fi
fi

# ---------- 步骤 5：MMGBSA ----------
echo ""
echo "=== 5. MMGBSA（结合自由能计算） ==="
MMPBSA_BATCH="$REPO_ROOT/AMBER_MMPBSA/run_mmpbsa_batch.py"
MMPBSA_SINGLE="$REPO_ROOT/AMBER_MMPBSA/run_mmpbsa_single_gb.sh"
SKIP_MMGBSA="${SKIP_MMGBSA:-0}"

if [[ "$SKIP_MMGBSA" == "1" ]]; then
    echo "跳过 MMGBSA（SKIP_MMGBSA=1）"
elif [[ -f "$MMPBSA_BATCH" ]]; then
    echo "使用批量 MMGBSA 脚本"
    python3 "$MMPBSA_BATCH" \
        --amber_root "$PART3_OUT_BASE" \
        --max_workers "${MMPBSA_WORKERS:-12}" \
        --mask_csv "$PART3_CSV" \
        --method gb || {
        echo "警告: MMGBSA 批量计算失败，尝试单结构..."
        for GPU_DIR in "$PART3_OUT_BASE"/gpu*/; do
            [[ -d "$GPU_DIR" ]] || continue
            for STRUCT_DIR in "$GPU_DIR"*/; do
                [[ -d "$STRUCT_DIR" ]] || continue
                if [[ -f "$STRUCT_DIR/system.prmtop" ]] && [[ -f "$STRUCT_DIR/md_total.nc" || -f "$STRUCT_DIR/md_1.nc" ]]; then
                    bash "$MMPBSA_SINGLE" --amber_dir "$STRUCT_DIR" || true
                fi
            done
        done
    }
elif [[ -f "$MMPBSA_SINGLE" ]]; then
    for GPU_DIR in "$PART3_OUT_BASE"/gpu*/; do
        [[ -d "$GPU_DIR" ]] || continue
        for STRUCT_DIR in "$GPU_DIR"*/; do
            [[ -d "$STRUCT_DIR" ]] || continue
            if [[ -f "$STRUCT_DIR/system.prmtop" ]] && [[ -f "$STRUCT_DIR/md_total.nc" || -f "$STRUCT_DIR/md_1.nc" ]]; then
                bash "$MMPBSA_SINGLE" --amber_dir "$STRUCT_DIR" || true
            fi
        done
    done
else
    echo "警告: 未找到 MMGBSA 脚本，跳过"
fi

# ---------- 步骤 6：收集 MMGBSA 结果 ----------
echo ""
echo "=== 6. 收集 MMGBSA 结果 ==="
MMGBSA_CSV="$EXAMPLE_BASE/mmgbsa_results.csv"
if command -v pf-part3-collect-mmgbsa &>/dev/null; then
    pf-part3-collect-mmgbsa -i "$PART3_OUT_BASE" -o "$MMGBSA_CSV" && echo "已收集到: $MMGBSA_CSV" || \
    python3 "$REPO_ROOT/AMBER_MMPBSA/collect_mmgbsa_binding_to_csv.py" --amber_root "$PART3_OUT_BASE" --out "$MMGBSA_CSV" 2>/dev/null && echo "已收集到: $MMGBSA_CSV" || true
elif python3 -c "from protein_filter.metrics.mmgbsa import collect_binding_to_csv" 2>/dev/null; then
    python3 -c "
from protein_filter.metrics.mmgbsa import collect_binding_to_csv
collect_binding_to_csv('$PART3_OUT_BASE', '$MMGBSA_CSV')
print('已收集到: $MMGBSA_CSV')
" || true
elif [[ -f "$REPO_ROOT/AMBER_MMPBSA/collect_mmgbsa_binding_to_csv.py" ]]; then
    python3 "$REPO_ROOT/AMBER_MMPBSA/collect_mmgbsa_binding_to_csv.py" \
        --amber_root "$PART3_OUT_BASE" --out "$MMGBSA_CSV" && echo "已收集到: $MMGBSA_CSV" || true
else
    echo "警告: 未找到 pf-part3-collect-mmgbsa、Python 模块或 AMBER_MMPBSA/collect_mmgbsa_binding_to_csv.py，跳过收集"
fi

echo ""
echo "================================================"
echo "Optimization 流程完成"
echo "================================================"
echo "Part2 结果: $PART2_OUT"
echo "Part3 MD 结果: $PART3_OUT_BASE"
if [[ -f "$MMGBSA_CSV" ]]; then
    echo "MMGBSA 结果: $MMGBSA_CSV"
fi
if [[ "${PART3_FAIL_COUNT:-0}" -gt 0 ]]; then
    echo "注意：Part3 阶段有 ${PART3_FAIL_COUNT} 个 GPU 子任务异常退出（已按策略继续）。"
fi
echo ""
echo "提示：AF3_DIR / TOP_N / PRODUCTION_NS / N_GPU 等可通过环境变量覆盖；跳过 MMGBSA: SKIP_MMGBSA=1；严格模式: PART3_ALLOW_PARTIAL_FAILURE=0"
