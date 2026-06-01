#!/bin/bash
# Part2 dump_pdb 完成后运行：将 WT Relax 结构复制到 part3_100ns_relaxed/WT_original_gpu0/WT_original_model/Protein.pdb
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELAXED_DIR="/data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_relaxed_structures"
PART3_BASE="/data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_part3_100ns_relaxed"
WT_PATH_FILE="${RELAXED_DIR}/wt_relaxed_path.txt"

if [[ ! -f "$WT_PATH_FILE" ]]; then
    echo "错误: 未找到 $WT_PATH_FILE（请先运行 prepare_relaxed_part3_inputs.py --step relaxed_csv）"
    exit 1
fi
WT_RELAXED="$(cat "$WT_PATH_FILE")"
if [[ ! -f "$WT_RELAXED" ]]; then
    echo "错误: WT Relax 文件不存在: $WT_RELAXED"
    echo "请等待 Part2 dump_pdb 完成后再运行本脚本。"
    exit 1
fi

python3 "${SCRIPT_DIR}/prepare_relaxed_part3_inputs.py" --step prep_wt_dir \
    --wt_relaxed_path "$WT_RELAXED" \
    --part3_base "$PART3_BASE"
echo ""
echo "WT 起始结构已就绪。可启动 Part3："
echo "  cd $(dirname "$SCRIPT_DIR") && ./run_part3_unified_relaxed.sh"
