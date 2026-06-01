#!/bin/bash
# Part3 新 MD 方案对比入口：前30 + WT 共 31 个结构，gpu0～gpu7 一并管理
# 直接调用已废弃（DEPRECATED）：请使用 scripts/run_part3.py 或 scripts/run_optimization_pipeline.sh。
# 本脚本仍由 run_denovo_design.sh 内部编排调用，勿删除。
# 使用 NVT+310K、amber14sb_parmbsc1、PBC/comm，输出到独立目录，不与 part3_100ns_relaxed 混用
#
# 用法：
#   ./run_part3_unified_relaxed_nvt310_ff14sb.sh              # 按 index%8 分配 + resume/rerun-failed
#   ./run_part3_unified_relaxed_nvt310_ff14sb.sh --scan-existing   # 就地续跑

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 支持通过环境变量覆盖（供 run_denovo_design.sh 内部编排等调用）
INPUT_CSV="${PART3_INPUT_CSV:-/data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_part3_relaxed_top30.csv}"
OUTPUT_BASE="${PART3_OUTPUT_BASE:-/data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_part3_100ns_relaxed_nvt310_ff14sb}"
TOP_N=30
WT_DIR="${OUTPUT_BASE}/WT_original_gpu0/WT_original_model"
WT_OUTPUT_DIR="${OUTPUT_BASE}/WT_original_gpu7/WT_original_model"
SCAN_EXISTING=""
[[ "${1:-}" == "--scan-existing" ]] && SCAN_EXISTING="--scan-existing"

# 本次运行使用新 log 文件
RUN_LOG_ID=$(date +%Y%m%d_%H%M)
echo "================================================"
echo "Part3 新方案运行（NVT+310K, amber14sb_parmbsc1，前${TOP_N} + WT = 31 结构，gpu0～gpu7）"
echo "================================================"
echo "本次 log 后缀: run_resume_${RUN_LOG_ID}.log"
echo "输出目录: $OUTPUT_BASE"
echo "输入 CSV: $INPUT_CSV"
if [[ -n "$SCAN_EXISTING" ]]; then
    echo "模式: 就地续跑 (--scan-existing)，各目录内已存在的前${TOP_N}未完成 + WT"
else
    echo "模式: 按 GPU 分配 (index%%8) + resume/rerun-failed，再跑 WT 于 gpu7"
fi
echo "================================================"
echo ""

if [[ ! -f "${WT_DIR}/Protein.pdb" ]]; then
    echo "错误: 未找到 WT 起始结构 ${WT_DIR}/Protein.pdb"
    echo "请先运行 Part2 dump_pdb 完成后，执行："
    echo "  python3 scripts/prepare_relaxed_part3_inputs.py --step prep_wt_dir --wt_relaxed_path \$(cat /data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_relaxed_structures/wt_relaxed_path.txt) --part3_base ${OUTPUT_BASE}"
    exit 1
fi

# 安全终止
cleanup() {
    trap - INT TERM HUP EXIT
    echo "[CLEANUP] 正在停止所有子进程..."
    pids="$(jobs -pr 2>/dev/null || true)"
    [ -n "$pids" ] && kill $pids 2>/dev/null || true
    sleep 2
    pkill -TERM -P $$ 2>/dev/null || true
    sleep 1
    pkill -KILL -P $$ 2>/dev/null || true
    exit ${1:-0}
}
trap 'cleanup $?' INT TERM HUP EXIT

# 激活环境
source /home/supervisor/anaconda3/etc/profile.d/conda.sh
conda activate amber22_py310

echo "验证 GPU 可见性..."
nvidia-smi -L | head -10
echo ""

declare -a ALL_PIDS=()

# ---------- GPU 1～7：仅跑本 GPU 分配的前30；gpu7 完成后额外跑 WT ----------
LOG_WT="${OUTPUT_BASE}/WT_original_gpu7/run_resume_${RUN_LOG_ID}.log"
mkdir -p "${OUTPUT_BASE}/WT_original_gpu7"

for GPU_ID in 1 2 3 4 5 6 7; do
    GPU_DIR="${OUTPUT_BASE}/gpu${GPU_ID}"
    LOG_FILE="${GPU_DIR}/run_resume_${RUN_LOG_ID}.log"
    mkdir -p "$GPU_DIR"
    if [[ "$GPU_ID" -eq 7 ]]; then
        echo "[GPU $GPU_ID] 启动（前30 分配 + WT）-> $LOG_FILE / $LOG_WT"
    else
        echo "[GPU $GPU_ID] 启动 -> $LOG_FILE"
    fi
    (
        export CUDA_VISIBLE_DEVICES=$GPU_ID
        python3 "${SCRIPT_DIR}/scripts/run_md_mmgbsa_rmsd.py" \
            --input_csv "$INPUT_CSV" \
            --top_n "$TOP_N" \
            --output_dir "$GPU_DIR" \
            --target_chain A \
            --binder_chain B \
            --production_ns 100 \
            --npt_ns 1 \
            --tmp 310 \
            --ph 7.4 \
            --conc 0.154 \
            --gpu_id "$GPU_ID" \
            --n_gpu 8 \
            --interval 5 \
            --ntomp 12 \
            --forcefield amber14sb_parmbsc1 \
            --resume \
            $SCAN_EXISTING \
            --rerun-failed \
            >> "$LOG_FILE" 2>&1

        # gpu7 前30 跑完后，在同一 GPU 上跑 WT（31 个结构中的最后一个）
        if [[ "$GPU_ID" -eq 7 ]] && [[ -f "${WT_DIR}/Protein.pdb" ]] && [[ ! -f "${WT_OUTPUT_DIR}/FINAL_RESULTS_MMPBSA.dat" ]]; then
            mkdir -p "$WT_OUTPUT_DIR"
            { echo "[GPU 7] 前30 完成，开始 WT_original_model (31/31)..."; \
              bash "${SCRIPT_DIR}/YZC_MD_SCRIPT/run_part3_md_single.sh" \
                --structure "${WT_DIR}/Protein.pdb" \
                --output_dir "$WT_OUTPUT_DIR" \
                --target_chain A \
                --binder_chain B \
                --production_ns 100 \
                --npt_ns 1 \
                --tmp 310 \
                --ph 7.4 \
                --conc 0.154 \
                --gpu_id 0 \
                --pinoffset 84 \
                --interval 5 \
                --ntomp 12 \
                --forcefield amber14sb_parmbsc1 \
                --resume; \
            } >> "$LOG_WT" 2>&1
        fi
    ) &
    ALL_PIDS+=($!)
    sleep 0.5
done

# ---------- GPU 0：仅跑本 GPU 分配的前30 ----------
GPU0_DIR="${OUTPUT_BASE}/gpu0"
LOG_GPU0="${GPU0_DIR}/run_resume_${RUN_LOG_ID}.log"
mkdir -p "$GPU0_DIR"
echo "[GPU 0] 启动 -> $LOG_GPU0"
(
    export CUDA_VISIBLE_DEVICES=0
    python3 "${SCRIPT_DIR}/scripts/run_md_mmgbsa_rmsd.py" \
        --input_csv "$INPUT_CSV" \
        --top_n "$TOP_N" \
        --output_dir "$GPU0_DIR" \
        --target_chain A \
        --binder_chain B \
        --production_ns 100 \
        --npt_ns 1 \
        --tmp 310 \
        --ph 7.4 \
        --conc 0.154 \
        --gpu_id 0 \
        --n_gpu 8 \
        --interval 5 \
        --ntomp 12 \
        --forcefield amber14sb_parmbsc1 \
        --resume \
        $SCAN_EXISTING \
        --rerun-failed \
        >> "$LOG_GPU0" 2>&1
) &
ALL_PIDS+=($!)

echo ""
echo "8 个 GPU 任务已全部启动（新方案 NVT+310K/amber14sb_parmbsc1，前30 + WT）。"
echo "查看日志: tail -f ${OUTPUT_BASE}/gpu{0..7}/run_resume_${RUN_LOG_ID}.log"
echo "WT 日志:  tail -f ${OUTPUT_BASE}/WT_original_gpu7/run_resume_${RUN_LOG_ID}.log"
echo "等待全部完成..."
fail_count=0
for PID in "${ALL_PIDS[@]}"; do
    if ! wait "$PID"; then
        fail_count=$((fail_count + 1))
    fi
done

if [[ "$fail_count" -gt 0 ]]; then
    echo "警告: 有 $fail_count 个任务异常退出，请查看上述 log。"
    exit 1
fi

echo ""
echo "================================================"
echo "Part3 新方案运行完成（NVT+310K/amber14sb_parmbsc1，前${TOP_N} + WT）。"
echo "================================================"
