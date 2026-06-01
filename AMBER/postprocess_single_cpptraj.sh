#!/usr/bin/env bash
# 单结构 AMBER 后处理：合并 md_*.nc、RMSD、去水、每 10 ns 抽帧、最后一帧、平均结构。
# 用法: postprocess_single_cpptraj.sh <结构目录>
# 需在结构目录内有 system.prmtop 和至少一个 md_*.nc。

set -e

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <structure_dir>"
    exit 1
fi

STRUCT_DIR="$(realpath "$1")"
cd "$STRUCT_DIR"

PRMTOP="system.prmtop"
if [[ ! -f "$PRMTOP" ]]; then
    echo "[SKIP] $STRUCT_DIR: 无 $PRMTOP"
    exit 0
fi

# 按段号排序的 md_*.nc
MDNCS=()
for f in md_*.nc; do
    [[ -f "$f" ]] || continue
    n="${f#md_}"
    n="${n%.nc}"
    [[ "$n" =~ ^[0-9]+$ ]] && MDNCS+=("$f")
done
if [[ ${#MDNCS[@]} -eq 0 ]]; then
    echo "[SKIP] $STRUCT_DIR: 无 md_*.nc"
    exit 0
fi
# 按数字排序
mapfile -t MDNCS < <(printf '%s\n' "${MDNCS[@]}" | sort -t_ -k2 -n)

CPPTRAJ="${CPPTRAJ:-cpptraj}"
if ! command -v "$CPPTRAJ" &>/dev/null; then
    if [[ -x /data/Tools/Amber22/bin/cpptraj ]]; then
        CPPTRAJ=/data/Tools/Amber22/bin/cpptraj
    else
        echo "[ERROR] cpptraj 未找到"
        exit 2
    fi
fi

# 单段：不合并，直接以 md_1.nc 为总轨迹；多段：先合并再处理
if [[ ${#MDNCS[@]} -eq 1 ]]; then
    cp -f "${MDNCS[0]}" md_total.nc
    echo "[INFO] 单段轨迹，已复制为 md_total.nc，不做合并"
fi

CPPIN1="postprocess_cpptraj_1.in"
if [[ ${#MDNCS[@]} -ge 2 ]]; then
    # 多段：合并 md_1 + md_2 + … → md_total.nc
    {
        echo "parm $PRMTOP"
        for f in "${MDNCS[@]}"; do
            echo "trajin $f"
        done
        echo "autoimage"
        echo "trajout md_total.nc"
        echo "run"
        echo ""
        echo "clear trajin"
        echo "trajin md_total.nc"
        echo "reference md_total.nc 1"
        echo "rmsd rmsd_bb reference @CA,C,N"
        echo "strip :WAT,Na+,Cl-,K+ parmout protein_only.prmtop"
        echo "trajout md_protein_nowat.nc"
        echo "run"
        echo "writedata rmsd_bb.dat rmsd_bb"
        echo "quit"
    } > "$CPPIN1"
    "$CPPTRAJ" -i "$CPPIN1" -o postprocess_cpptraj_1.log
else
    # 单段：md_total.nc 已存在，只做 RMSD、去水
    {
        echo "parm $PRMTOP"
        echo "trajin md_total.nc"
        echo "reference md_total.nc 1"
        echo "rmsd rmsd_bb reference @CA,C,N"
        echo "strip :WAT,Na+,Cl-,K+ parmout protein_only.prmtop"
        echo "trajout md_protein_nowat.nc"
        echo "run"
        echo "writedata rmsd_bb.dat rmsd_bb"
        echo "quit"
    } > "$CPPIN1"
    "$CPPTRAJ" -i "$CPPIN1" -o postprocess_cpptraj_1.log
fi

# 第二次 cpptraj：用 stripped 拓扑读去水轨迹，写 10ns 帧、最后帧、平均结构（用绝对路径避免拓扑/轨迹错配）
if [[ ! -f protein_only.prmtop || ! -s protein_only.prmtop || ! -f md_protein_nowat.nc ]]; then
    echo "[WARN] $STRUCT_DIR: 未生成 protein_only.prmtop 或 md_protein_nowat.nc，跳过 10ns/最后帧/平均"
else
    # 取最后一帧的帧号（cpptraj 的 trajin 不接受 last 作 start）
    LAST_FRAME=$(ncdump -h md_protein_nowat.nc 2>/dev/null | sed -n 's/.*frame = UNLIMITED ; \/\/ (\([0-9]*\) currently).*/\1/p')
    [[ -z "$LAST_FRAME" || ! "$LAST_FRAME" =~ ^[0-9]+$ ]] && LAST_FRAME=50000
    CPPIN2="postprocess_cpptraj_2.in"
    PARDIR="$STRUCT_DIR"
    {
        echo "parm ${PARDIR}/protein_only.prmtop"
        echo "trajin ${PARDIR}/md_protein_nowat.nc 1 last 5000"
        echo "trajout protein_10ns.pdb pdb"
        echo "run"
        echo ""
        echo "clear trajin"
        echo "trajin ${PARDIR}/md_protein_nowat.nc $LAST_FRAME $LAST_FRAME"
        echo "trajout last_frame.pdb pdb"
        echo "run"
        echo ""
        echo "clear trajin"
        echo "trajin ${PARDIR}/md_protein_nowat.nc"
        echo "average crdset avg_crd"
        echo "run"
        echo "crdout avg_crd avg_structure.pdb pdb"
        echo "quit"
    } > "$CPPIN2"
    "$CPPTRAJ" -i "$CPPIN2" -o postprocess_cpptraj_2.log
fi
echo "[OK] $STRUCT_DIR: md_total.nc, rmsd_bb.dat, md_protein_nowat.nc, protein_10ns.pdb, last_frame.pdb, avg_structure.pdb"
