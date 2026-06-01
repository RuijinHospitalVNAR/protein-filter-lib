#!/usr/bin/env python3
"""CLI: pf-part2-filter — 基于 stage2_metrics.parquet 筛选，输出 stage2_passed.parquet。"""

import argparse
import json
import logging
import sys

from ..pipeline.stage2 import filter_stage2


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    ap = argparse.ArgumentParser(
        description="Part2: 基于 stage2_metrics.parquet 按阈值筛选",
    )
    ap.add_argument("--metrics_file", "-m", required=True, help="stage2_metrics.parquet 路径")
    ap.add_argument("--output_dir", "-o", required=True, help="输出目录")
    ap.add_argument("--filters", "-f", required=True, help='筛选规则 JSON，如 {"interface_dG":{"threshold":-10,"operator":"<"}}')
    args = ap.parse_args()

    filters = json.loads(args.filters)

    try:
        out = filter_stage2(args.metrics_file, args.output_dir, filters)
        print(f"Stage2 passed saved to {out}")
        return 0
    except Exception as e:
        logging.exception("%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
