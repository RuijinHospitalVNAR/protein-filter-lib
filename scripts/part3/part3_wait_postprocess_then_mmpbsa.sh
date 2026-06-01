#!/usr/bin/env bash
# 等待 31 个结构目录均生成 md_total.nc 后，再运行 MM/PBSA 批量。
# 用法: wait_postprocess_then_mmpbsa.sh [amber_root] [max_workers]
# 默认 amber_root: .../try5, max_workers: 4

set -e
BASE="${1:-/data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_part3_100ns_amber_try5}"
WORKERS="${2:-4}"

count() {
  local n=0 d gpu
  for gpu in "$BASE"/gpu[0-9]*/; do
    for d in "$gpu"*/; do
      [[ -f "${d}md_1.nc" ]] || continue
      [[ -f "${d}md_total.nc" ]] && ((n++)) || true
    done
  done
  [[ -f "$BASE/WT_original_gpu7/WT_original_model/md_total.nc" ]] && ((n++)) || true
  echo $n
}

echo "[$(date -Iseconds)] 等待 31 个目录生成 md_total.nc ..."
while [[ $(count) -lt 31 ]]; do
  echo "[$(date +%H:%M:%S)] 当前 $(count)/31"
  sleep 90
done
echo "[$(date -Iseconds)] 31/31 就绪，启动 MM/PBSA 批量 (--max_workers $WORKERS)"
cd /data/wcf
python3 protein_filter_lib/AMBER_MMPBSA/run_mmpbsa_batch.py --amber_root "$BASE" --max_workers "$WORKERS"
echo "[$(date -Iseconds)] MM/PBSA 批量结束"
