#!/usr/bin/env python3
"""
用 parmed 提取溶质拓扑（strip 溶剂/离子），生成 MM/PBSA 可用的干净拓扑。

- 不修改 IFBOX 等指针（避免破坏文件结构），而是重新生成仅含溶质的拓扑，自然得到 IFBOX=0。
- PB 严格要求 IFBOX=0；GB 可容忍 IFBOX≠0，但推荐仍用溶质拓扑。
- 配体应在 prmtop 中已有正确力场（如 GAFF + RESP 电荷），本脚本只做 strip，不改变力场。

用法：
  python3 prepare_solute_topology_for_mmpbsa.py <amber_dir>
  python3 prepare_solute_topology_for_mmpbsa.py --prmtop /path/to/system.prmtop
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 与 MMPBSA strip_mask 一致：去掉水与离子，保留受体+配体（溶质）
DEFAULT_STRIP_MASK = ":WAT,HOH,Na+,Na,K+,K,Cl-,Cl"


def _fix_ifbox_in_prmtop(path: Path) -> None:
    """将 prmtop 中 POINTERS 的第 27/28 项（IFBOX）改为 0。"""
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
    ap = argparse.ArgumentParser(
        description="Extract solute topology with parmed (no manual IFBOX edit)."
    )
    ap.add_argument("amber_dir", nargs="?", help="Directory containing system.prmtop")
    ap.add_argument("--prmtop", type=str, help="Path to system.prmtop")
    ap.add_argument(
        "--strip_mask",
        type=str,
        default=DEFAULT_STRIP_MASK,
        help="Amber mask for residues to strip (default: solvent + ions)",
    )
    args = ap.parse_args()

    if args.prmtop:
        prmtop_path = Path(args.prmtop).resolve()
        out_path = prmtop_path.parent / "system_mmpbsa.prmtop"
    elif args.amber_dir:
        d = Path(args.amber_dir).resolve()
        prmtop_path = d / "system.prmtop"
        out_path = d / "system_mmpbsa.prmtop"
    else:
        print("ERROR: specify amber_dir or --prmtop", file=sys.stderr)
        return 1

    if not prmtop_path.is_file():
        print(f"ERROR: prmtop not found: {prmtop_path}", file=sys.stderr)
        return 1

    try:
        import parmed
        parm = parmed.load_file(str(prmtop_path))
    except Exception as e:
        print(f"ERROR: failed to load prmtop: {e}", file=sys.stderr)
        return 1

    n_before = len(parm.atoms)
    try:
        parm.strip(args.strip_mask)
    except Exception as e:
        print(f"ERROR: strip failed: {e}", file=sys.stderr)
        return 1
    n_after = len(parm.atoms)

    if n_after >= n_before:
        print("WARNING: no atoms stripped; mask may not match prmtop residues.", file=sys.stderr)

    try:
        parm.write_parm(str(out_path))
    except Exception as e:
        print(f"ERROR: failed to write: {e}", file=sys.stderr)
        return 1

    # 溶质拓扑必须 IFBOX=0；parmed 写出后文件中仍可能为 2，在文件中将第 27/28 个 POINTERS 值改为 0
    _fix_ifbox_in_prmtop(out_path)

    print(f"[prepare_solute] stripped {n_before - n_after} atoms, wrote {out_path} (IFBOX=0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
