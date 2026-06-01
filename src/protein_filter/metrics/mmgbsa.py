"""
MM/GBSA 结合自由能结果汇总（Part3 产出）。

从 AMBER MMPBSA 输出目录递归查找 FINAL_RESULTS_MMGBSA_BINDING.dat，
解析 DELTA TOTAL，输出 CSV 表（model, delta_total, delta_total_stddev, delta_total_stderr, path）。
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import List, Dict, Any, Optional


def parse_delta_total(path: Path) -> Optional[tuple[float, float, float]]:
    """
    从 FINAL_RESULTS_MMGBSA_BINDING.dat 中解析 DELTA TOTAL 三个数字。

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


def collect_binding_to_csv(
    amber_root: str | Path,
    out_path: str | Path,
    *,
    binding_filename: str = "FINAL_RESULTS_MMGBSA_BINDING.dat",
) -> Path:
    """
    扫描 amber_root 下所有 FINAL_RESULTS_MMGBSA_BINDING.dat，解析 ΔG_bind，写出 CSV。

    Args:
        amber_root: Part3 AMBER 根目录（含 gpu0..7 等子目录）
        out_path: 输出 CSV 路径
        binding_filename: 结果文件名，默认 FINAL_RESULTS_MMGBSA_BINDING.dat

    Returns:
        输出的 CSV 路径
    """
    root = Path(amber_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"amber_root is not a directory: {root}")

    records: List[Dict[str, Any]] = []
    for binding_file in root.rglob(binding_filename):
        model = binding_file.parent.name
        parsed = parse_delta_total(binding_file)
        if parsed is None:
            continue
        avg, stddev, stderr = parsed
        records.append({
            "model": model,
            "delta_total": avg,
            "delta_total_stddev": stddev,
            "delta_total_stderr": stderr,
            "path": str(binding_file),
        })

    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["model", "delta_total", "delta_total_stddev", "delta_total_stderr", "path"],
        )
        writer.writeheader()
        for rec in sorted(records, key=lambda r: str(r["model"])):
            writer.writerow(rec)

    return out_path
