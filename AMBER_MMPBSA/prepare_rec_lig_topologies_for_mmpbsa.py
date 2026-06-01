#!/usr/bin/env python3
"""为 MMPBSA.py 的 binding 计算准备 -rp/-lp 拓扑（Receptor/Ligand）。

前置：已经有溶质拓扑（例如 system_mmpbsa.prmtop），其残基编号与 mask（如 :1-105、:106-211）一致。

输出：
  receptor_mmpbsa.prmtop
  ligand_mmpbsa.prmtop

说明：ParmEd 写出的 prmtop 可能仍保留 IFBOX>0，这会导致 Amber 的 mmpbsa_py_energy 在 GB/PB 下报错。
这里对输出文件做一次 IFBOX 清零（仅作用于派生文件）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _fix_ifbox_in_prmtop(path: Path) -> None:
    """将 prmtop 中 POINTERS 的第 27/28 项（IFBOX）改为 0（只改第一个非 0 的）。"""
    lines = path.read_text().split("\n")
    in_pt, ptr_count, done_li, done_col = False, 0, -1, -1
    for li, line in enumerate(lines):
        if "%FLAG POINTERS" in line:
            in_pt, ptr_count = True, 0
            continue
        if in_pt and line.strip().startswith("%FLAG"):
            break
        if in_pt and "%FORMAT" not in line and line.strip():
            for col in range(0, min(80, len(line)), 8):
                ptr_count += 1
                val = int(line[col : col + 8]) if line[col : col + 8].strip() else 0
                if ptr_count in (27, 28) and val != 0:
                    done_li, done_col = li, col
                    break
            if done_li >= 0:
                break
    if done_li >= 0:
        old = lines[done_li]
        lines[done_li] = old[:done_col] + "%8d" % 0 + old[done_col + 8 :]
        path.write_text("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description="Prepare receptor/ligand prmtop for MMPBSA binding.")
    ap.add_argument("amber_dir", help="Model directory containing system_mmpbsa.prmtop")
    ap.add_argument("--complex_prmtop", default="system_mmpbsa.prmtop", help="Solute complex prmtop")
    ap.add_argument("--receptor_mask", required=True, help="Receptor residue mask, e.g. :1-105")
    ap.add_argument("--ligand_mask", required=True, help="Ligand residue mask, e.g. :106-211")
    ap.add_argument("--out_receptor", default="receptor_mmpbsa.prmtop")
    ap.add_argument("--out_ligand", default="ligand_mmpbsa.prmtop")
    args = ap.parse_args()

    d = Path(args.amber_dir).resolve()
    cp = d / args.complex_prmtop
    if not cp.is_file():
        print(f"ERROR: complex prmtop not found: {cp}", file=sys.stderr)
        return 1

    try:
        import parmed
    except Exception as e:
        print(f"ERROR: cannot import parmed: {e}", file=sys.stderr)
        return 1

    # receptor: delete ligand residues
    rec = parmed.load_file(str(cp))
    rec.strip(args.ligand_mask)
    rec_out = d / args.out_receptor
    rec.write_parm(str(rec_out))
    _fix_ifbox_in_prmtop(rec_out)

    # ligand: delete receptor residues
    lig = parmed.load_file(str(cp))
    lig.strip(args.receptor_mask)
    lig_out = d / args.out_ligand
    lig.write_parm(str(lig_out))
    _fix_ifbox_in_prmtop(lig_out)

    print(f"[prepare_rec_lig] wrote {rec_out.name} and {lig_out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
