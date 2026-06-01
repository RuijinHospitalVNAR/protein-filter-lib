#!/usr/bin/env bash
# 单结构 AMBER MMPBSA（PB 模型，按链 ID 自动解析并转换为残基范围 mask）
# 设计目标：
#   - 与当前 AMBER Part3 MD 流程解耦，只依赖每个结构目录中的 system.prmtop + md_1.nc + system.pdb
#   - 使用 AmberTools 自带的 MMPBSA.py（PB 模型），采用 receptor_mask / ligand_mask + strip_mask 的方式
#   - 按链 ID 自动解析复合物的两个蛋白链（更通用，避免写死 1-105 / 106-211），再转换为 Amber mask 语法的残基范围
#   - 为后续蛋白设计 pipeline 搭建一个可复用的“单结构打分后端”
#
# 用法示例（在某个结构目录下运行）：
#   cd /data/wcf/AF3_prediction/.../amber_try5/gpu1/Y84A_S86G_model
#   bash /data/wcf/protein_filter_lib/AMBER_MMPBSA/run_mmpbsa_single.sh
#
# 或指定结构目录：
#   bash /data/wcf/protein_filter_lib/AMBER_MMPBSA/run_mmpbsa_single.sh \
#       --amber_dir /data/wcf/.../amber_try5/gpu1/Y84A_S86G_model
#
# 可选环境变量：
#   MMPBSA_CPUS="96-127"     # 用 taskset 绑定 MMPBSA.py 的 CPU 亲和性（默认空，不绑）
#   MMPBSA_INTERVAL=50       # 取帧间隔（默认 50）
#   MMPBSA_STARTFRAME=1      # 起始帧（默认 1）
#   MMPBSA_ENDFRAME=9999999  # 截止帧（默认 9999999，表示所有可用帧）
#   MMPBSA_RECEPTOR_MASK=":1-105"  # 若设置则跳过自动解析，直接使用
#   MMPBSA_LIGAND_MASK=":106-211"  # 若设置则跳过自动解析，直接使用
#
# 显式 mask 示例（等价于受体 A:1-105，配体 B:106-211）：
#   run_mmpbsa_single.sh --amber_dir <dir> --receptor_mask ":1-105" --ligand_mask ":106-211"
# 或带链前缀（脚本会去掉链 ID，只保留残基范围）：
#   run_mmpbsa_single.sh --receptor_mask "A:1-105" --ligand_mask "B:106-211"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMBER_MMPBSA_DIR="$SCRIPT_DIR"

amber_dir=""
receptor_mask_arg=""
ligand_mask_arg=""

show_usage() {
    echo "Usage: $0 [--amber_dir <dir>] [--receptor_mask <mask>] [--ligand_mask <mask>]"
    echo "  --receptor_mask  受体残基范围，如 :1-105 或 A:1-105"
    echo "  --ligand_mask    配体残基范围，如 :106-211 或 B:106-211"
    echo "  默认: 使用当前目录为 amber_dir；mask 可由环境变量或自动解析。"
}

# 将 "A:1-105" 规范为 ":1-105"（Amber mask 仅用残基范围）
normalize_mask() {
    local m="$1"
    if [[ -z "$m" ]]; then echo ""; return; fi
    if [[ "$m" =~ ^[A-Za-z][[:space:]]*:(.*) ]]; then
        echo ":${BASH_REMATCH[1]}"
    else
        echo "$m"
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --amber_dir)
            amber_dir="$2"
            shift 2
            ;;
        --receptor_mask)
            receptor_mask_arg="$2"
            shift 2
            ;;
        --ligand_mask)
            ligand_mask_arg="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

if [[ -z "$amber_dir" ]]; then
    amber_dir="$(pwd)"
fi

amber_dir="$(realpath "$amber_dir")"
cd "$amber_dir"

echo "[MMPBSA] Amber directory: $amber_dir"

# MM/PBSA PB 要求 prmtop 的 IFBOX=0（无周期边界）；MD 的 system.prmtop 通常 IFBOX=1 或 2
# 先生成 system_mmpbsa.prmtop（若尚未存在或需覆盖）
if [[ -f "system.prmtop" ]]; then
    python3 "${AMBER_MMPBSA_DIR}/fix_prmtop_for_mmpbsa.py" "$(pwd)" || true
fi
if [[ -f "system_mmpbsa.prmtop" ]]; then
    PRMTOP="system_mmpbsa.prmtop"
else
    PRMTOP="system.prmtop"
fi
# 优先使用后处理得到的总轨迹（0–100 ns 合并），否则用 md_1.nc；可通过 MMPBSA_TRAJ 覆盖
if [[ -n "${MMPBSA_TRAJ:-}" ]]; then
    TRAJ="$MMPBSA_TRAJ"
elif [[ -f "md_total.nc" ]]; then
    TRAJ="md_total.nc"
else
    TRAJ="md_1.nc"
fi
PDB_SYS="system.pdb"

if [[ ! -f "$PRMTOP" ]]; then
    echo "[ERROR] $PRMTOP not found in $amber_dir"
    exit 1
fi

if [[ ! -f "$TRAJ" ]]; then
    echo "[ERROR] $TRAJ not found in $amber_dir (Production NetCDF trajectory required)"
    exit 1
fi
echo "[MMPBSA] Using trajectory: $TRAJ"

if [[ ! -f "$PDB_SYS" ]]; then
    echo "[ERROR] $PDB_SYS not found in $amber_dir (needed for chain-based mask parsing)"
    exit 1
fi

if ! command -v MMPBSA.py &>/dev/null; then
    echo "[ERROR] MMPBSA.py not found in PATH. Please load AmberTools environment."
    exit 1
fi

# 优先级：命令行 > 环境变量 > 按链 ID 自动解析
if [[ -n "$receptor_mask_arg" && -n "$ligand_mask_arg" ]]; then
    RECEPTOR_MASK="$(normalize_mask "$receptor_mask_arg")"
    LIGAND_MASK="$(normalize_mask "$ligand_mask_arg")"
else
    RECEPTOR_MASK="${MMPBSA_RECEPTOR_MASK:-}"
    LIGAND_MASK="${MMPBSA_LIGAND_MASK:-}"
fi

if [[ -z "$RECEPTOR_MASK" || -z "$LIGAND_MASK" ]]; then
    echo "[MMPBSA] Auto-detecting receptor/ligand masks from $PDB_SYS (by sequence length)..."
    # 使用 Python 解析 system.pdb，基于序列长度自动构造残基范围 mask：
    # - 忽略溶剂/离子（WAT/HOH/Na+/Cl-/K+ 等）
    # - 对每个链统计最小/最大 resid，组合成 ':start-end' mask
    # - 按序列长度排序，最长的链为 receptor，其余为 ligand
    PYTHON_MASKS=$(python3 - <<'PY'
import sys

pdb_path = "system.pdb"
solvent_like = {"WAT", "HOH"}
ion_like = {"Na+", "Na", "K+", "K", "Cl-", "Cl"}

chains = {}

try:
    with open(pdb_path, "r", errors="ignore") as f:
        for line in f:
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            resname = line[17:20].strip()
            chain_id = line[21].strip() or "_"
            try:
                resseq = int(line[22:26])
            except ValueError:
                continue
            if resname in solvent_like or resname in ion_like:
                continue
            if chain_id not in chains:
                chains[chain_id] = {"min": resseq, "max": resseq, "count": 0}
            else:
                chains[chain_id]["min"] = min(chains[chain_id]["min"], resseq)
                chains[chain_id]["max"] = max(chains[chain_id]["max"], resseq)
            chains[chain_id]["count"] += 1
except FileNotFoundError:
    print("ERROR: system.pdb not found", file=sys.stderr)
    sys.exit(1)

if not chains:
    print("ERROR: No non-solvent/ion chains detected in system.pdb", file=sys.stderr)
    sys.exit(2)

# 按序列长度排序（氨基酸残基数量），最长的为 receptor
sorted_chains = sorted(chains.items(), key=lambda kv: kv[1]["count"], reverse=True)

if len(sorted_chains) == 1:
    cid, span = sorted_chains[0]
    msg = f"ERROR: Only one protein chain ({cid}) detected (resid {span['min']}-{span['max']}); cannot auto-split receptor/ligand."
    print(msg, file=sys.stderr)
    sys.exit(3)

rec_cid, rec_span = sorted_chains[0]
rec_mask = f":{rec_span['min']}-{rec_span['max']}"

lig_masks = []
for cid, span in sorted_chains[1:]:
    lig_masks.append(f":{span['min']}-{span['max']}")
lig_mask = ",".join(lig_masks)

print(rec_mask)
print(lig_mask)
print(f"[INFO] Detected: receptor={rec_cid} (len={rec_span['count']}), ligand chains={[c[0] for c in sorted_chains[1:]]}", file=sys.stderr)
PY
)

    if [[ $? -ne 0 ]]; then
        echo "[ERROR] Failed to auto-detect receptor/ligand masks from $PDB_SYS"
        exit 1
    fi

    RECEPTOR_MASK="$(echo "$PYTHON_MASKS" | sed -n '1p')"
    LIGAND_MASK="$(echo "$PYTHON_MASKS" | sed -n '2p')"
fi

echo "[MMPBSA] Receptor mask: $RECEPTOR_MASK"
echo "[MMPBSA] Ligand   mask: $LIGAND_MASK"

INTERVAL="${MMPBSA_INTERVAL:-50}"
STARTFRAME="${MMPBSA_STARTFRAME:-1}"
ENDFRAME="${MMPBSA_ENDFRAME:-9999999}"

MMPBSA_IN="mmpbsa_amber_pb.in"

if [[ ! -f "${AMBER_MMPBSA_DIR}/mmpbsa_pb.in.template" ]]; then
    echo "[ERROR] Template not found: ${AMBER_MMPBSA_DIR}/mmpbsa_pb.in.template"
    exit 1
fi

echo "[MMPBSA] Generating $MMPBSA_IN from template..."
sed \
    -e "s/RECEPTOR_MASK_PLACEHOLDER/${RECEPTOR_MASK//\//\\/}/g" \
    -e "s/LIGAND_MASK_PLACEHOLDER/${LIGAND_MASK//\//\\/}/g" \
    -e "s/STARTFRAME_PLACEHOLDER/${STARTFRAME}/g" \
    -e "s/ENDFRAME_PLACEHOLDER/${ENDFRAME}/g" \
    -e "s/INTERVAL_PLACEHOLDER/${INTERVAL}/g" \
    "${AMBER_MMPBSA_DIR}/mmpbsa_pb.in.template" > "$MMPBSA_IN"

OUT_FILE="FINAL_RESULTS_MMPBSA_AMBER.dat"

echo "[MMPBSA] Running MMPBSA.py (PB model) ..."

MMPBSA_CPUS_RANGE="${MMPBSA_CPUS:-}"

CMD=(MMPBSA.py -O -i "$MMPBSA_IN" -o "$OUT_FILE" -cp "$PRMTOP" -y "$TRAJ")

if [[ -n "$MMPBSA_CPUS_RANGE" && -x "$(command -v taskset 2>/dev/null)" ]]; then
    echo "[MMPBSA] Using taskset -c ${MMPBSA_CPUS_RANGE}"
    CMD=(taskset -c "${MMPBSA_CPUS_RANGE}" "${CMD[@]}")
fi

echo "[MMPBSA] Command: ${CMD[*]}"
"${CMD[@]}"

echo "[MMPBSA] Done. Results written to: $amber_dir/$OUT_FILE"

