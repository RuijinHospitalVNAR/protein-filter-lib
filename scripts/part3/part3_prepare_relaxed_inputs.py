#!/usr/bin/env python3
"""
Prepare inputs for Relaxed-structure Part3 pipeline:
1. From rosetta_static CSV: take top 30 by interface_score + WT row -> 31-row CSV for Part2 (column 'pdb').
2. After Part2 with dump_pdb: build Part3 relaxed CSV (top 30 rows with pdb_path = relaxed files).
3. Optionally create part3 dir and copy WT relaxed as Protein.pdb.

Usage:
  # Step 1: create 31-structure CSV for Part2
  python3 prepare_relaxed_part3_inputs.py --step for_part2 --source_csv <rosetta_static_0_with_afpd.csv> --out_csv <top30_wt_for_relax.csv>

  # Step 2: after Part2 run, build Part3 relaxed CSV and WT path
  python3 prepare_relaxed_part3_inputs.py --step relaxed_csv --source_csv <31-row CSV or same as step1> --relaxed_dir <Part2 output_dir> --out_csv <part3_relaxed_top30.csv> --wt_relaxed_path_out <file.txt>

  # Step 3: create part3 dir and copy WT relaxed as Protein.pdb
  python3 prepare_relaxed_part3_inputs.py --step prep_wt_dir --wt_relaxed_path <relax_WT_original_model.cif> --part3_base <part3_100ns_relaxed>
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

import pandas as pd


def step_for_part2(source_csv: str, out_csv: str, top_n: int = 30) -> None:
    """Build 31-row CSV (top_n + WT) with column 'pdb' = pdb_path for Part2 run_pyrosetta_static.py."""
    df = pd.read_csv(source_csv)
    if "pdb_path" not in df.columns or "interface_score" not in df.columns:
        raise SystemExit("CSV 需含 pdb_path 与 interface_score 列")
    # Sort by interface_score ascending (more negative = better)
    df = df.sort_values("interface_score").reset_index(drop=True)
    top = df.head(top_n)
    wt = df[df["pdb_name"] == "WT_original_model"]
    if wt.empty:
        raise SystemExit("CSV 中未找到 pdb_name == WT_original_model 的行")
    wt = wt.iloc[[0]]
    combined = pd.concat([top, wt], ignore_index=True)
    # Part2 expects column 'pdb'
    out_df = combined[["pdb_name", "pdb_path"]].copy()
    out_df = out_df.rename(columns={"pdb_path": "pdb"})
    out_df.to_csv(out_csv, index=False)
    print(f"已写入 {out_csv}，共 {len(out_df)} 行（前 {top_n} + WT）")


def step_relaxed_csv(
    source_csv: str,
    relaxed_dir: str,
    out_csv: str,
    wt_relaxed_path_out: str | None,
    top_n: int = 30,
) -> None:
    """Build Part3 CSV with pdb_path = relaxed_dir/relax_<basename> for top_n rows; write WT relaxed path to file."""
    relaxed_dir = Path(relaxed_dir).resolve()
    df = pd.read_csv(source_csv)
    # Source may have 'pdb' (Part2 input) or 'pdb_path' (original)
    path_col = "pdb" if "pdb" in df.columns else "pdb_path"
    if path_col not in df.columns:
        raise SystemExit(f"CSV 需含 {path_col} 列")
    name_col = "pdb_name" if "pdb_name" in df.columns else None
    rows = []
    wt_relaxed_path = None
    for i, r in df.iterrows():
        orig_path = r[path_col]
        if not isinstance(orig_path, str) or not orig_path.strip():
            continue
        base = os.path.basename(orig_path)
        relaxed_path = relaxed_dir / f"relax_{base}"
        if not relaxed_path.exists():
            print(f"警告: 未找到 {relaxed_path}", file=sys.stderr)
        name = r[name_col] if name_col else Path(orig_path).stem
        if name == "WT_original_model":
            wt_relaxed_path = str(relaxed_path)
            continue  # WT not in top30 CSV for Part3
        rows.append({"pdb_name": name, "pdb_path": str(relaxed_path)})
    out_df = pd.DataFrame(rows).head(top_n)
    out_df.to_csv(out_csv, index=False)
    print(f"已写入 {out_csv}，共 {len(out_df)} 行")
    if wt_relaxed_path_out and wt_relaxed_path:
        Path(wt_relaxed_path_out).parent.mkdir(parents=True, exist_ok=True)
        with open(wt_relaxed_path_out, "w") as f:
            f.write(wt_relaxed_path)
        print(f"WT relaxed 路径已写入 {wt_relaxed_path_out}: {wt_relaxed_path}")
    elif wt_relaxed_path_out and not wt_relaxed_path:
        # Source CSV might be only top30; then WT path from relaxed_dir
        wt_cand = relaxed_dir / "relax_WT_original_model.cif"
        if not wt_cand.exists():
            wt_cand = relaxed_dir / "relax_WT_original_model.pdb"
        if wt_cand.exists():
            with open(wt_relaxed_path_out, "w") as f:
                f.write(str(wt_cand))
            print(f"WT relaxed 路径已写入 {wt_relaxed_path_out}: {wt_cand}")


def step_prep_wt_dir(wt_relaxed_path: str, part3_base: str) -> None:
    """Create part3_base/WT_original_gpu0/WT_original_model/ and copy wt_relaxed as Protein.pdb."""
    wt_path = Path(wt_relaxed_path)
    if not wt_path.is_file():
        raise SystemExit(f"WT relaxed 文件不存在: {wt_relaxed_path}")
    out_dir = Path(part3_base) / "WT_original_gpu0" / "WT_original_model"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "Protein.pdb"
    # PyRosetta dump_pdb writes PDB format; filename may be .cif. Copy as .pdb.
    shutil.copy2(wt_path, dest)
    print(f"已复制 {wt_path} -> {dest}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Prepare relaxed Part3 inputs")
    ap.add_argument("--step", choices=["for_part2", "relaxed_csv", "prep_wt_dir"], required=True)
    ap.add_argument("--source_csv", type=str, default="")
    ap.add_argument("--out_csv", type=str, default="")
    ap.add_argument("--relaxed_dir", type=str, default="")
    ap.add_argument("--wt_relaxed_path_out", type=str, default="")
    ap.add_argument("--wt_relaxed_path", type=str, default="")
    ap.add_argument("--part3_base", type=str, default="")
    ap.add_argument("--top_n", type=int, default=30)
    args = ap.parse_args()

    if args.step == "for_part2":
        if not args.source_csv or not args.out_csv:
            raise SystemExit("--step for_part2 需 --source_csv 与 --out_csv")
        step_for_part2(args.source_csv, args.out_csv, args.top_n)
    elif args.step == "relaxed_csv":
        if not args.source_csv or not args.relaxed_dir or not args.out_csv:
            raise SystemExit("--step relaxed_csv 需 --source_csv、--relaxed_dir、--out_csv")
        step_relaxed_csv(
            args.source_csv,
            args.relaxed_dir,
            args.out_csv,
            args.wt_relaxed_path_out or None,
            args.top_n,
        )
    elif args.step == "prep_wt_dir":
        if not args.wt_relaxed_path or not args.part3_base:
            raise SystemExit("--step prep_wt_dir 需 --wt_relaxed_path 与 --part3_base")
        step_prep_wt_dir(args.wt_relaxed_path, args.part3_base)


if __name__ == "__main__":
    main()
