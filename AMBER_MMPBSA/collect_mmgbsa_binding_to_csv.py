#!/usr/bin/env python3
"""收集 31 个结构的 MMGBSA binding 结果，整理为 CSV。

扫描 amber_root 下所有 model 目录（gpu0..7/*_model 以及 WT_original），
查找 `FINAL_RESULTS_MMGBSA_BINDING.dat`，从中解析 `DELTA TOTAL` 一行，
输出形如：

model,delta_total,delta_total_stddev,delta_total_stderr
S86G_E96S_model,-15.0559,21.8495,0.6909
...

用法示例：
  cd /data/wcf/protein_filter_lib
  python3 AMBER_MMPBSA/collect_mmgbsa_binding_to_csv.py \
      --amber_root /data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_part3_100ns_amber_try5 \
      --out mmpbsa_binding_31.csv

可以在批量计算尚未完全结束时运行，此时只会收集已完成的结构；
等全部结束后再运行一次即可得到完整 31 行表格。
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


def parse_delta_total(path: Path) -> tuple[float, float, float] | None:
    """从 FINAL_RESULTS_MMGBSA_BINDING.dat 中解析 DELTA TOTAL 三个数字。

    目标行类似：
      DELTA TOTAL                -15.0559               21.8495              0.6909
    返回 (avg, stddev, stderr)。
    """
    line_re = re.compile(r"^DELTA TOTAL\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)")
    try:
        for line in path.read_text().splitlines():
            m = line_re.match(line.strip())
            if m:
                avg, stddev, stderr = map(float, m.groups())
                return avg, stddev, stderr
    except FileNotFoundError:
        return None
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Collect MMGBSA binding ΔG from 31 models into CSV.")
    ap.add_argument("--amber_root", "-i", required=True, help="AMBER Part3 根目录 (含 gpu0..7 等)")
    ap.add_argument("--out", "-o", default="mmgbsa_binding_31.csv", help="输出 CSV 路径")
    args = ap.parse_args()

    root = Path(args.amber_root).resolve()
    if not root.is_dir():
        raise SystemExit(f"amber_root not a directory: {root}")

    records: list[dict[str, str | float]] = []

    for binding_file in root.rglob("FINAL_RESULTS_MMGBSA_BINDING.dat"):
        # model 目录名，例如 gpu0/S86G_E96S_model -> S86G_E96S_model
        model = binding_file.parent.name
        parsed = parse_delta_total(binding_file)
        if parsed is None:
            continue
        avg, stddev, stderr = parsed
        records.append(
            {
                "model": model,
                "delta_total": avg,
                "delta_total_stddev": stddev,
                "delta_total_stderr": stderr,
                "path": str(binding_file),
            }
        )

    out_path = Path(args.out).resolve()
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["model", "delta_total", "delta_total_stddev", "delta_total_stderr", "path"],
        )
        writer.writeheader()
        for rec in sorted(records, key=lambda r: str(r["model"])):
            writer.writerow(rec)

    print(f"Wrote {len(records)} records to {out_path}")


if __name__ == "__main__":
    main()
