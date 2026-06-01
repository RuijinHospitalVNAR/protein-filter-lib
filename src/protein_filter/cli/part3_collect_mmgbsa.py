#!/usr/bin/env python3
"""CLI: pf-part3-collect-mmgbsa — 收集 Part3 MM/GBSA 结果，输出 ΔG_bind CSV。"""

import argparse
import logging
import sys

from ..metrics.mmgbsa import collect_binding_to_csv


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    ap = argparse.ArgumentParser(
        description="Part3: 收集 AMBER MMGBSA binding 结果，汇总为 CSV（model, delta_total, ...）",
    )
    ap.add_argument("--amber_root", "-i", required=True, help="AMBER Part3 根目录（含 gpu0..7 等）")
    ap.add_argument("--out", "-o", default="mmgbsa_binding.csv", help="输出 CSV 路径")
    ap.add_argument("--binding_filename", default="FINAL_RESULTS_MMGBSA_BINDING.dat", help="结果文件名")
    args = ap.parse_args()

    try:
        out = collect_binding_to_csv(
            args.amber_root,
            args.out,
            binding_filename=args.binding_filename,
        )
        print(f"Wrote {out}")
        return 0
    except Exception as e:
        logging.exception("%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
