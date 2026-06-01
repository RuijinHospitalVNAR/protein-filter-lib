#!/usr/bin/env bash
# 单结构 AMBER MMGBSA（GB 模型，包含 binding 计算：Complex/Receptor/Ligand + ΔG_bind）。

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMBER_MMPBSA_DIR="$SCRIPT_DIR"

amber_dir=""
receptor_mask_arg=""
ligand_mask_arg=""

show_usage() {
    echo "Usage: $0 [--amber_dir <dir>] [--receptor_mask <mask>] [--ligand_mask <mask>]"
}

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
        --amber_dir) amber_dir="$2"; shift 2 ;;
        --receptor_mask) receptor_mask_arg="$2"; shift 2 ;;
        --ligand_mask) ligand_mask_arg="$2"; shift 2 ;;
        -h|--help) show_usage; exit 0 ;;
        *) echo "Unknown option: $1"; show_usage; exit 1 ;;
    esac
done

[[ -z "$amber_dir" ]] && amber_dir="$(pwd)"
amber_dir="$(realpath "$amber_dir")"
cd "$amber_dir"

echo "[MMGBSA] Amber directory: $amber_dir"

PDB_SYS="system.pdb"
[[ ! -f "$PDB_SYS" ]] && { echo "[ERROR] $PDB_SYS not found (for mask parsing)"; exit 1; }

# 轨迹：优先 md_protein_nowat.nc
if [[ -f "md_protein_nowat.nc" ]]; then
    TRAJ="md_protein_nowat.nc"
else
    if [[ -n "${MMPBSA_TRAJ:-}" ]]; then TRAJ="$MMPBSA_TRAJ"
    elif [[ -f "md_total.nc" ]]; then TRAJ="md_total.nc"
    else TRAJ="md_1.nc"; fi
fi
[[ ! -f "$TRAJ" ]] && { echo "[ERROR] $TRAJ not found"; exit 1; }

echo "[MMGBSA] Using trajectory: $TRAJ"

if ! command -v MMPBSA.py &>/dev/null; then
    echo "[ERROR] MMPBSA.py not found. Please load AmberTools."
    exit 1
fi

# 受体/配体 mask
# 优先级：
#   1) 命令行参数 --receptor_mask / --ligand_mask
#   2) 环境变量 MMPBSA_RECEPTOR_MASK / MMPBSA_LIGAND_MASK
#   3) 自动从 system.pdb 推断（尽可能利用链信息或残基数）
#   4) 最后兜底：:1-105 / :106-211（当前示例的默认划分）
if [[ -n "$receptor_mask_arg" && -n "$ligand_mask_arg" ]]; then
    RECEPTOR_MASK="$(normalize_mask "$receptor_mask_arg")"
    LIGAND_MASK="$(normalize_mask "$ligand_mask_arg")"
else
    RECEPTOR_MASK="$(normalize_mask "${MMPBSA_RECEPTOR_MASK:-}")"
    LIGAND_MASK="$(normalize_mask "${MMPBSA_LIGAND_MASK:-}")"
fi

if [[ -z "$RECEPTOR_MASK" || -z "$LIGAND_MASK" ]]; then
    echo "[MMGBSA] Auto-detecting receptor/ligand masks from $PDB_SYS..."
    set +e
    PYTHON_MASKS=$(python3 - <<'PY'
import os, sys
pdb_path = "system.pdb"
solvent_like = {"WAT", "HOH"}
ion_like = {"Na+", "Na", "K+", "K", "Cl-", "Cl"}

chains = {}
res_indices = set()
try:
    with open(pdb_path, "r", errors="ignore") as f:
        for line in f:
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            resname = line[17:20].strip()
            try:
                resseq = int(line[22:26])
            except ValueError:
                continue
            if resname in solvent_like or resname in ion_like:
                continue
            res_indices.add(resseq)
            chain_id = line[21].strip() or "_"
            if chain_id not in chains:
                chains[chain_id] = {"min": resseq, "max": resseq}
            else:
                chains[chain_id]["min"] = min(chains[chain_id]["min"], resseq)
                chains[chain_id]["max"] = max(chains[chain_id]["max"], resseq)
except FileNotFoundError:
    print("ERROR: system.pdb not found", file=sys.stderr)
    sys.exit(1)

if not res_indices:
    print("ERROR: No protein residues in system.pdb", file=sys.stderr)
    sys.exit(2)

# 优先使用链信息：至少两条非溶剂链时，按链拆分并映射到连续编号
sorted_chains = sorted([(cid, span) for cid, span in chains.items() if cid != "_"], key=lambda kv: kv[0])
if len(sorted_chains) >= 2:
    rec_span = sorted_chains[0][1]
    rec_len = rec_span["max"] - rec_span["min"] + 1
    rec_mask = f":1-{rec_len}"
    lig_start = rec_len + 1
    lig_masks = []
    for _, lig_span in sorted_chains[1:]:
        lig_len = lig_span["max"] - lig_span["min"] + 1
        lig_end = lig_start + lig_len - 1
        lig_masks.append(f":{lig_start}-{lig_end}")
        lig_start = lig_end + 1
    lig_mask = ",".join(lig_masks)
    print(rec_mask)
    print(lig_mask)
    sys.exit(0)

# 若只有一条链或链信息丢失，则尝试使用环境变量 MMPBSA_RECEPTOR_LEN
res_min, res_max = min(res_indices), max(res_indices)
total_len = res_max - res_min + 1
rec_len_env = os.environ.get("MMPBSA_RECEPTOR_LEN")
if rec_len_env:
    try:
        rec_len = int(rec_len_env)
    except ValueError:
        rec_len = None
    if rec_len and 0 < rec_len < total_len:
        rec_mask = f":1-{rec_len}"
        lig_mask = f":{rec_len+1}-{total_len}"
        print(rec_mask)
        print(lig_mask)
        sys.exit(0)

# 自动推断失败，交由 shell 兜底为固定划分
sys.exit(3)
PY
)
    py_ret=$?
    set -e
    if [[ $py_ret -eq 0 ]] && [[ -n "$PYTHON_MASKS" ]]; then
        RECEPTOR_MASK="$(echo "$PYTHON_MASKS" | sed -n '1p')"
        LIGAND_MASK="$(echo "$PYTHON_MASKS" | sed -n '2p')"
    else
        # 单链/链信息缺失时，不再使用固定默认划分（容易导致拓扑不一致）。
        # 可选：通过 MMPBSA_RECEPTOR_LEN 提供受体长度，按连续残基切分。
        if [[ -n "${MMPBSA_RECEPTOR_LEN:-}" ]]; then
            TOTAL_LEN=$(python3 - <<'PY'
import sys
res=set()
for line in open("system.pdb", errors="ignore"):
    if line.startswith(("ATOM","HETATM")):
        rn=line[17:20].strip()
        if rn in {"WAT","HOH","Na+","Na","K+","K","Cl-","Cl"}:
            continue
        try:
            res.add(int(line[22:26]))
        except Exception:
            pass
if not res:
    print("")
else:
    print(max(res)-min(res)+1)
PY
)
            if [[ -n "$TOTAL_LEN" ]] && [[ "$MMPBSA_RECEPTOR_LEN" =~ ^[0-9]+$ ]] && [[ "$MMPBSA_RECEPTOR_LEN" -gt 0 ]] && [[ "$MMPBSA_RECEPTOR_LEN" -lt "$TOTAL_LEN" ]]; then
                RECEPTOR_MASK=":1-${MMPBSA_RECEPTOR_LEN}"
                LIGAND_MASK=":$((MMPBSA_RECEPTOR_LEN+1))-${TOTAL_LEN}"
                echo "[MMGBSA] Fallback by MMPBSA_RECEPTOR_LEN=${MMPBSA_RECEPTOR_LEN}: receptor=${RECEPTOR_MASK}, ligand=${LIGAND_MASK}"
            else
                echo "[ERROR] Auto mask failed and MMPBSA_RECEPTOR_LEN invalid for total_len=${TOTAL_LEN:-unknown}."
                exit 1
            fi
        else
            echo "[ERROR] Auto mask failed (likely single/blank chain IDs). Please provide --receptor_mask/--ligand_mask or MMPBSA_RECEPTOR_LEN."
            exit 1
        fi
    fi
fi

echo "[MMGBSA] Receptor mask: $RECEPTOR_MASK"
echo "[MMGBSA] Ligand   mask: $LIGAND_MASK"

# 1) 提取溶质拓扑（IFBOX=0），与 md_protein_nowat.nc 的 strip 一致
if [[ -f "system.prmtop" && ( ! -f "system_mmpbsa.prmtop" || "system.prmtop" -nt "system_mmpbsa.prmtop" ) ]]; then
    python3 "${AMBER_MMPBSA_DIR}/prepare_solute_topology_for_mmpbsa.py" "$(pwd)" --strip_mask ":WAT,Na+,Cl-,K+" || true
fi
if [[ -f "system_mmpbsa.prmtop" ]]; then
    PRMTOP_COMPLEX="system_mmpbsa.prmtop"
else
    PRMTOP_COMPLEX="system.prmtop"
fi
[[ ! -f "$PRMTOP_COMPLEX" ]] && { echo "[ERROR] Complex prmtop not found: $PRMTOP_COMPLEX"; exit 1; }

# 2) 生成 receptor / ligand 拓扑
python3 "${AMBER_MMPBSA_DIR}/prepare_rec_lig_topologies_for_mmpbsa.py" "$(pwd)" \
    --complex_prmtop "$PRMTOP_COMPLEX" \
    --receptor_mask "$RECEPTOR_MASK" \
    --ligand_mask "$LIGAND_MASK" || true

[[ ! -f "receptor_mmpbsa.prmtop" || ! -f "ligand_mmpbsa.prmtop" ]] && {
    echo "[ERROR] receptor_mmpbsa.prmtop 或 ligand_mmpbsa.prmtop 缺失"; exit 1; }

INTERVAL="${MMPBSA_INTERVAL:-50}"
STARTFRAME="${MMPBSA_STARTFRAME:-1}"
ENDFRAME="${MMPBSA_ENDFRAME:-9999999}"
MMPBSA_IN="mmpbsa_amber_gb.in"
TEMPLATE="${AMBER_MMPBSA_DIR}/mmpbsa_gb.in.template"
OUT_FILE="FINAL_RESULTS_MMGBSA_BINDING.dat"

[[ ! -f "$TEMPLATE" ]] && { echo "[ERROR] Template not found: $TEMPLATE"; exit 1; }

sed -e "s/RECEPTOR_MASK_PLACEHOLDER/${RECEPTOR_MASK//\//\\/}/g" \
    -e "s/LIGAND_MASK_PLACEHOLDER/${LIGAND_MASK//\//\\/}/g" \
    -e "s/STARTFRAME_PLACEHOLDER/${STARTFRAME}/g" \
    -e "s/ENDFRAME_PLACEHOLDER/${ENDFRAME}/g" \
    -e "s/INTERVAL_PLACEHOLDER/${INTERVAL}/g" \
    "$TEMPLATE" > "$MMPBSA_IN"

echo "[MMGBSA] Running MMPBSA.py (GB binding) ..."
CMD=(MMPBSA.py -O -i "$MMPBSA_IN" -o "$OUT_FILE" -cp "$PRMTOP_COMPLEX" -rp "receptor_mmpbsa.prmtop" -lp "ligand_mmpbsa.prmtop" -y "$TRAJ")
if [[ -n "${MMPBSA_CPUS:-}" && -x "$(command -v taskset 2>/dev/null)" ]]; then
    echo "[MMGBSA] Using taskset -c ${MMPBSA_CPUS}"
    CMD=(taskset -c "${MMPBSA_CPUS}" "${CMD[@]}")
fi

echo "[MMGBSA] Command: ${CMD[*]}"
"${CMD[@]}"

echo "[MMGBSA] Done. Binding results: $amber_dir/$OUT_FILE"
