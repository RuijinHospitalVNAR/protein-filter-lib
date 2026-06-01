#!/usr/bin/env python3
"""
为 MM/PBSA 生成无周期边界的 prmtop（IFBOX=0）。

PB 求解器要求 prmtop 中 IFBOX=0，而 MD 的 system.prmtop 通常带周期边界（IFBOX=1 或 2）。
本脚本在同一目录下生成 system_mmpbsa.prmtop，供 run_mmpbsa_single.sh 使用。

用法：
  python3 fix_prmtop_for_mmpbsa.py <amber_dir>
  或
  python3 fix_prmtop_for_mmpbsa.py --prmtop /path/to/system.prmtop
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Amber prmtop: IFBOX 在 POINTERS 中为第 27 项（1-based）；部分文件中实际在第 28 项
IFBOX_POSITIONS_1BASED = (27, 28)


def fix_prmtop_file(prmtop_path: Path, out_path: Path) -> tuple[bool, int]:
    """
    Read prmtop, set IFBOX (27th or 28th value in POINTERS) to 0, write to out_path.
    Returns (changed, original_ifbox).
    """
    lines = prmtop_path.read_text().split("\n")
    in_pointers = False
    ptr_count = 0
    ifbox_val = -1
    done_li, done_col = -1, -1

    for li, line in enumerate(lines):
        if "%FLAG POINTERS" in line:
            in_pointers = True
            ptr_count = 0
            continue
        if in_pointers:
            if line.strip().startswith("%FLAG"):
                break
            if "%FORMAT" in line or not line.strip():
                continue
            for col in range(0, min(80, len(line)), 8):
                chunk = line[col : col + 8]
                ptr_count += 1
                val = int(chunk) if chunk.strip() else 0
                if ptr_count in IFBOX_POSITIONS_1BASED and val != 0:
                    ifbox_val = val
                    done_li, done_col = li, col
                    break
            if done_li >= 0:
                break

    if ifbox_val <= 0:
        if out_path != prmtop_path:
            out_path.write_text("\n".join(lines))
        return False, 0 if ifbox_val == 0 else -1

    old_line = lines[done_li]
    lines[done_li] = old_line[:done_col] + "%8d" % 0 + old_line[done_col + 8 :]
    out_path.write_text("\n".join(lines))
    return True, ifbox_val


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate IFBOX=0 prmtop for MMPBSA.")
    ap.add_argument("amber_dir", nargs="?", help="Directory containing system.prmtop")
    ap.add_argument("--prmtop", type=str, help="Path to system.prmtop (alternative to amber_dir)")
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

    changed, orig = fix_prmtop_file(prmtop_path, out_path)
    if changed:
        print(f"[fix_prmtop] IFBOX {orig} -> 0, wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
