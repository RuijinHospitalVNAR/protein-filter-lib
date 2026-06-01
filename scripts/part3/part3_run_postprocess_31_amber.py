#!/usr/bin/env python3
"""
对 Part3 AMBER 的 31 个 MD 结果做后处理：合并轨迹、RMSD、去水、10ns 抽帧、最后帧、平均结构。
用法: python run_postprocess_31_amber.py --base_dir <try5目录>
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
POSTPROCESS_SH = PROJECT_ROOT / "AMBER" / "postprocess_single_cpptraj.sh"


def find_structure_dirs(base: Path) -> list[Path]:
    """收集所有含 md_*.nc 的结构目录（gpu0..gpu7 下各子目录 + WT_original_gpu7/WT_original_model）。"""
    base = base.resolve()
    if not base.is_dir():
        return []
    dirs: list[Path] = []
    for gpu_dir in sorted(base.iterdir()):
        if not gpu_dir.is_dir():
            continue
        name = gpu_dir.name
        if name.startswith("gpu") and name[3:].isdigit():
            for sub in sorted(gpu_dir.iterdir()):
                if sub.is_dir() and (sub / "md_1.nc").exists():
                    dirs.append(sub)
        elif name == "WT_original_gpu7":
            wt_model = gpu_dir / "WT_original_model"
            if wt_model.is_dir() and (wt_model / "md_1.nc").exists():
                dirs.append(wt_model)
    return dirs


def main() -> None:
    ap = argparse.ArgumentParser(description="对 31 个 AMBER Part3 MD 结果做 cpptraj 后处理")
    ap.add_argument(
        "--base_dir",
        type=str,
        default="/data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_part3_100ns_amber_try5",
        help="Part3 AMBER 输出根目录（含 gpu0..gpu7 与 WT_original_gpu7）",
    )
    ap.add_argument("--dry_run", action="store_true", help="只列出目录，不执行")
    args = ap.parse_args()

    if not POSTPROCESS_SH.is_file():
        print(f"错误：未找到 {POSTPROCESS_SH}", file=sys.stderr)
        sys.exit(1)

    base = Path(args.base_dir)
    dirs = find_structure_dirs(base)
    print(f"共 {len(dirs)} 个结构目录")

    if args.dry_run:
        for d in dirs:
            print(d)
        return

    failed: list[tuple[Path, int]] = []
    for i, d in enumerate(dirs, 1):
        print(f"[{i}/{len(dirs)}] {d.relative_to(base)}", flush=True)
        ret = subprocess.run(
            ["bash", str(POSTPROCESS_SH), str(d)],
            cwd=str(d),
        )
        if ret.returncode != 0:
            failed.append((d, ret.returncode))

    if failed:
        print(f"\n失败 {len(failed)} 个:", file=sys.stderr)
        for d, code in failed:
            print(f"  {d} (exit {code})", file=sys.stderr)
        sys.exit(1)
    print("\n全部完成。")


if __name__ == "__main__":
    main()
