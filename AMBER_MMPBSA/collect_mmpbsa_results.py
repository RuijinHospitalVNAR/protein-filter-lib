#!/usr/bin/env python3
"""
收集 AMBER MMPBSA（PB）结果并汇总为一张 CSV，用于接回设计 pipeline。

假设每个结构目录下使用 run_mmpbsa_single.sh 生成：
  - FINAL_RESULTS_MMPBSA_AMBER.dat

本脚本会：
  - 在 amber_root/gpu0..7 以及 WT_original_gpu7/WT_original_model 下查找上述文件；
  - 解析其中的 binding free energy（在 Amber 中通常是 “DELTA G binding” 一行的最后一列）；
  - 输出 CSV：structure_id,gpu,amber_dir,delta_g_binding_kcal_per_mol。
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple


def parse_delta_g_binding(path: Path) -> Optional[float]:
    """
    从 Amber FINAL_RESULTS_MMPBSA_AMBER.dat 中提取整体结合自由能（kcal/mol）。

    优先策略：
      1. 找到包含 'DELTA G binding' 字样的行，记住其后第一行的最后一个数值。
      2. 若失败，退而求其次：在文件末尾向上扫描，找到含多个浮点数的行，取最后一列。
    """
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return None

    lines = text.splitlines()
    idx = None
    for i, line in enumerate(lines):
        if "DELTA G binding" in line:
            idx = i
            break

    float_pattern = re.compile(r"[-+]?\d+\.\d+(?:[Ee][-+]?\d+)?")

    if idx is not None:
        # 在该行之后找第一行数值
        for j in range(idx + 1, len(lines)):
            line = lines[j].strip()
            if not line or line.startswith("#"):
                continue
            nums = float_pattern.findall(line)
            if nums:
                try:
                    return float(nums[-1])
                except ValueError:
                    continue

    # fallback：从文件末尾向上扫描
    for line in reversed(lines):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        nums = float_pattern.findall(line)
        if len(nums) >= 1:
            try:
                return float(nums[-1])
            except ValueError:
                continue

    return None


def discover_results(amber_root: Path) -> List[Tuple[int | None, str, Path, Path]]:
    """发现所有 FINAL_RESULTS_MMPBSA_AMBER.dat 文件。"""
    results: List[Tuple[int | None, str, Path, Path]] = []

    for gpu_id in range(8):
        gpu_dir = amber_root / f"gpu{gpu_id}"
        if not gpu_dir.is_dir():
            continue
        for sub in gpu_dir.iterdir():
            if not sub.is_dir():
                continue
            dat = sub / "FINAL_RESULTS_MMPBSA_AMBER.dat"
            if dat.is_file():
                results.append((gpu_id, sub.name, sub, dat))

    wt_dir = amber_root / "WT_original_gpu7" / "WT_original_model"
    if wt_dir.is_dir():
        dat = wt_dir / "FINAL_RESULTS_MMPBSA_AMBER.dat"
        if dat.is_file():
            results.append((7, "WT_original_model", wt_dir, dat))

    return results


def main() -> None:
    ap = argparse.ArgumentParser(description="收集 AMBER MMPBSA（PB）结果并汇总到 CSV。")
    ap.add_argument(
        "--amber_root",
        type=str,
        default="/data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_part3_100ns_amber_try5",
        help="AMBER Part3 输出根目录（包含 gpu0..7 子目录）",
    )
    ap.add_argument(
        "--output_csv",
        type=str,
        default="part3_amber_mmpbsa_results.csv",
        help="汇总结果 CSV 输出路径（相对于 amber_root 或绝对路径）",
    )
    args = ap.parse_args()

    amber_root = Path(args.amber_root).resolve()
    if not amber_root.is_dir():
        print(f"ERROR: amber_root not a directory: {amber_root}", file=sys.stderr)
        sys.exit(1)

    results = discover_results(amber_root)
    if not results:
        print("No FINAL_RESULTS_MMPBSA_AMBER.dat files found.", file=sys.stderr)
        sys.exit(0)

    rows = []
    for gpu, sid, sdir, dat in results:
        dg = parse_delta_g_binding(dat)
        rows.append(
            {
                "structure_id": sid,
                "gpu": gpu,
                "amber_dir": str(sdir),
                "result_file": str(dat),
                "delta_g_binding_kcal_per_mol": dg,
            }
        )

    out_path = Path(args.output_csv)
    if not out_path.is_absolute():
        out_path = amber_root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "structure_id",
        "gpu",
        "amber_dir",
        "result_file",
        "delta_g_binding_kcal_per_mol",
    ]

    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()

