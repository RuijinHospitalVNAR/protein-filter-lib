# Part1 filter CLI
import argparse
import json
import logging
import sys

from ..pipeline.stage1 import filter_stage1

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    ap = argparse.ArgumentParser(description="Part1: 基于 stage1_metrics.parquet 筛选")
    ap.add_argument("--metrics_file", "-m", required=True, help="stage1_metrics.parquet")
    ap.add_argument("--output_dir", "-o", required=True, help="输出目录")
    ap.add_argument("--filters", "-f", required=True, help='JSON e.g. {"plddt":{"threshold":0.7,"operator":">="}}')
    ap.add_argument("--top_n", type=int, default=0)
    ap.add_argument("--score_weights", type=str, default=None)
    args = ap.parse_args()
    filters = json.loads(args.filters)
    score_weights = json.loads(args.score_weights) if args.score_weights else None
    try:
        out = filter_stage1(args.metrics_file, args.output_dir, filters, top_n=args.top_n, score_weights=score_weights)
        print("Stage1 passed saved to", out)
        return 0
    except Exception as e:
        logging.exception("%s", e)
        return 1

if __name__ == "__main__":
    sys.exit(main())
