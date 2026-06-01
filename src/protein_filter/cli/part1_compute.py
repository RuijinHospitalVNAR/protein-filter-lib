# Part1 compute CLI
import argparse
import json
import logging
import sys
from pathlib import Path

from ..pipeline.stage1 import compute_stage1_metrics

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    ap = argparse.ArgumentParser(description="Part1: 计算 AF3 快速指标，输出 stage1_metrics.parquet")
    ap.add_argument("--input_dir", "-i", required=True, help="输入目录")
    ap.add_argument("--output_dir", "-o", required=True, help="输出目录")
    ap.add_argument("--target_chain", default="B")
    ap.add_argument("--binder_chain", default="A")
    ap.add_argument("--relaxer", default="none", choices=("none", "pyrosetta"))
    ap.add_argument("--metrics", nargs="+", default=["plddt", "clashes", "pdockq", "ipsae"])
    ap.add_argument("--ipsae_pae_cutoff", type=float, default=5.0)
    ap.add_argument("--ipsae_distance_cutoff", type=float, default=5.0)
    ap.add_argument("--clustering_config", type=str, default=None)
    args = ap.parse_args()
    clustering_config = None
    if args.clustering_config:
        raw = args.clustering_config.strip()
        if raw.startswith("{"):
            clustering_config = json.loads(raw)
        else:
            with open(Path(raw).expanduser()) as f:
                clustering_config = json.load(f)
    try:
        out = compute_stage1_metrics(
            args.input_dir, args.output_dir,
            target_chain=args.target_chain, binder_chain=args.binder_chain,
            relaxer=args.relaxer, enabled_metrics=args.metrics,
            clustering_config=clustering_config,
            ipsae_pae_cutoff=args.ipsae_pae_cutoff,
            ipsae_distance_cutoff=args.ipsae_distance_cutoff,
        )
        print("Stage1 metrics saved to", out)
        return 0
    except Exception as e:
        logging.exception("%s", e)
        return 1

if __name__ == "__main__":
    sys.exit(main())
