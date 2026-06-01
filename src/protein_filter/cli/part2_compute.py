#!/usr/bin/env python3
"""CLI: pf-part2-compute-metrics — Part2 PyRosetta 指标计算，输出 stage2_metrics.parquet。"""

import argparse
import logging
import sys

from ..pipeline.stage2 import compute_stage2_metrics


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    ap = argparse.ArgumentParser(
        description="Part2: 对 Stage1 通过的设计计算 PyRosetta 指标（界面 dG、SAP 等），输出 stage2_metrics.parquet",
    )
    ap.add_argument("--input_dir", "-i", required=True, help="输入目录（含 PDB/CIF）")
    ap.add_argument("--stage1_passed", "-s", required=True, help="stage1_passed_design_names.txt 或 stage1_passed.parquet")
    ap.add_argument("--output_dir", "-o", required=True, help="输出目录")
    ap.add_argument("--target_chain", default="A", help="目标链")
    ap.add_argument("--binder_chain", default="B", help="结合链")
    ap.add_argument("--relaxer", default="pyrosetta", choices=("none", "pyrosetta"))
    ap.add_argument("--metrics", nargs="+", default=None, help="启用的指标（默认：interface_dG, sap_score 等）")
    ap.add_argument("--pyrosetta_init", type=str, default=None, help="PyRosetta 初始化选项")
    args = ap.parse_args()

    try:
        out = compute_stage2_metrics(
            args.input_dir,
            args.stage1_passed,
            args.output_dir,
            target_chain=args.target_chain,
            binder_chain=args.binder_chain,
            relaxer=args.relaxer,
            enabled_metrics=args.metrics,
            pyrosetta_init=args.pyrosetta_init,
        )
        print(f"Stage2 metrics saved to {out}")
        return 0
    except Exception as e:
        logging.exception("%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
