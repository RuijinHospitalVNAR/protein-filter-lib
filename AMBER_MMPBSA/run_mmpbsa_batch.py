#!/usr/bin/env python3
"""
批量 AMBER MMPBSA（PB 模型）驱动脚本。

设计目标：
  - 在 AMBER Part3 MD（run_amber_31_8gpu.sh）全部完成后，一条命令对所有结构做 MM/PBSA。
  - 自动在 <amber_root>/gpu0..7 下发现结构子目录（以及 WT_original_gpu7/WT_original_model，如果存在）。
  - 对每个含有 system.prmtop + md_1.nc 的目录调用 AMBER_MMPBSA/run_mmpbsa_single.sh。
  - 可配置最大并发数（CPU 并行度），便于根据物理核数量调优。

使用示例：
  # 默认 amber_root（当前推荐 try5 目录）：
  #   /data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_part3_100ns_amber_try5
  #
  # 建议在 MD 全部结束后运行：
  #
  #   cd /data/wcf/protein_filter_lib
  #   source /home/supervisor/anaconda3/etc/profile.d/conda.sh
  #   conda activate amber22_py310
  #
  #   export MMPBSA_CPUS=\"96-127\"   # 可选：绑到高位 CPU 核
  #
  #   python3 AMBER_MMPBSA/run_mmpbsa_batch.py \\
  #       --amber_root /data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_part3_100ns_amber_try5 \\
  #       --max_workers 4
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AMBER_MMPBSA_DIR = PROJECT_ROOT / "AMBER_MMPBSA"
RUN_SINGLE_PB = AMBER_MMPBSA_DIR / "run_mmpbsa_single.sh"
RUN_SINGLE_GB = AMBER_MMPBSA_DIR / "run_mmpbsa_single_gb.sh"


@dataclass
class AmberTarget:
    gpu: int | None
    structure_id: str
    amber_dir: Path


def canonical_name(dirname: str, expected: set[str]) -> str | None:
    if dirname in expected:
        return dirname
    cands = [e for e in expected if dirname.startswith(e + "_")]
    return max(cands, key=len) if cands else None


def load_mask_mapping(mask_csv: Path) -> dict[str, tuple[str, str]]:
    mapping: dict[str, tuple[str, str]] = {}
    with mask_csv.open(newline="", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = str(row.get("pdb_name", "") or row.get("model", "")).strip()
            rec = str(row.get("receptor_mask", "")).strip()
            lig = str(row.get("ligand_mask", "")).strip()
            if not name or not rec or not lig:
                continue
            mapping[name] = (rec, lig)
    return mapping


def discover_targets(amber_root: Path, only_completed: bool = True) -> List[AmberTarget]:
    """在 amber_root 下发现所有可跑 MMPBSA 的结构目录。"""
    targets: List[AmberTarget] = []

    # gpu0..7 结构
    for gpu_id in range(8):
        gpu_dir = amber_root / f"gpu{gpu_id}"
        if not gpu_dir.is_dir():
            continue
        for sub in gpu_dir.iterdir():
            if not sub.is_dir():
                continue
            # 跳过 log 等非结构目录
            if sub.name.endswith(".log"):
                continue
            prmtop = sub / "system.prmtop"
            traj = sub / "md_total.nc" if (sub / "md_total.nc").is_file() else sub / "md_1.nc"
            rst = sub / "md_1.rst"
            if not prmtop.is_file() or not traj.is_file():
                continue
            if only_completed and not rst.is_file():
                # 仅在认为 Production 完成时才加入任务
                continue
            targets.append(AmberTarget(gpu=gpu_id, structure_id=sub.name, amber_dir=sub))

    # WT（如果存在）
    wt_dir = amber_root / "WT_original_gpu7" / "WT_original_model"
    if wt_dir.is_dir():
        prmtop = wt_dir / "system.prmtop"
        traj = wt_dir / "md_total.nc" if (wt_dir / "md_total.nc").is_file() else wt_dir / "md_1.nc"
        rst = wt_dir / "md_1.rst"
        if prmtop.is_file() and traj.is_file() and (not only_completed or rst.is_file()):
            targets.append(AmberTarget(gpu=7, structure_id="WT_original_model", amber_dir=wt_dir))

    return targets


def run_single(
    target: AmberTarget,
    env: dict | None = None,
    receptor_mask: str | None = None,
    ligand_mask: str | None = None,
    run_script: Path | None = None,
) -> int:
    """对单个结构调用 run_mmpbsa_single.sh 或 run_mmpbsa_single_gb.sh。"""
    script = run_script or RUN_SINGLE_PB
    cmd = ["bash", str(script), "--amber_dir", str(target.amber_dir)]
    if receptor_mask and ligand_mask:
        cmd.extend(["--receptor_mask", receptor_mask, "--ligand_mask", ligand_mask])
    print(f"[BATCH] GPU {target.gpu} | {target.structure_id} -> {target.amber_dir}")
    proc = subprocess.run(cmd, cwd=str(target.amber_dir), env=env)
    return proc.returncode


def main() -> None:
    ap = argparse.ArgumentParser(description="批量运行 AMBER MMPBSA（PB，按链ID解析）。")
    ap.add_argument(
        "--amber_root",
        type=str,
        default="/data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_part3_100ns_amber_try5",
        help="AMBER Part3 输出根目录（包含 gpu0..7 子目录）",
    )
    ap.add_argument(
        "--max_workers",
        type=int,
        default=12,
        help="同时并行的 MMPBSA 任务数（默认 12，建议 <= 可用物理核数的一半）",
    )
    ap.add_argument(
        "--include_incomplete",
        action="store_true",
        help="包括尚未完成 100ns（缺少 md_1.rst）的结构（一般不建议）",
    )
    ap.add_argument(
        "--receptor_mask",
        type=str,
        default="",
        help="受体残基 mask，如 :1-105 或 A:1-105（与 --ligand_mask 同时指定时跳过链自动解析）",
    )
    ap.add_argument(
        "--ligand_mask",
        type=str,
        default="",
        help="配体残基 mask，如 :106-211 或 B:106-211",
    )
    ap.add_argument(
        "--method",
        type=str,
        choices=("pb", "gb"),
        default="pb",
        help="PB (MM/PBSA) 或 GB (MMGBSA)，默认 pb。GB 使用 protein_only.prmtop + md_protein_nowat.nc",
    )
    ap.add_argument(
        "--mask_csv",
        type=str,
        default="",
        help="可选：包含每结构 receptor_mask/ligand_mask 的 CSV（列名支持 pdb_name|model）。",
    )
    args = ap.parse_args()

    run_script = RUN_SINGLE_GB if args.method == "gb" else RUN_SINGLE_PB
    if not run_script.is_file():
        print(f"ERROR: script not found: {run_script}", file=sys.stderr)
        sys.exit(1)

    amber_root = Path(args.amber_root).resolve()
    if not amber_root.is_dir():
        print(f"ERROR: amber_root not a directory: {amber_root}", file=sys.stderr)
        sys.exit(1)

    print(f"[BATCH] AMBER root: {amber_root}")
    print(f"[BATCH] Method: {args.method.upper()} | Script: {run_script.name}")

    targets = discover_targets(amber_root, only_completed=not args.include_incomplete)
    if not targets:
        print("[BATCH] No eligible structures found (check md_1.nc / md_1.rst / system.prmtop).")
        sys.exit(0)

    print(f"[BATCH] Found {len(targets)} structures to process.")
    for t in targets:
        print(f"  - GPU {t.gpu} | {t.structure_id} | {t.amber_dir}")

    # 传递当前环境（含 MMPBSA_CPUS 等配置）
    env = os.environ.copy()

    rec_mask_global = args.receptor_mask.strip() or None
    lig_mask_global = args.ligand_mask.strip() or None
    per_target_masks: dict[str, tuple[str, str]] = {}
    if args.mask_csv.strip():
        mask_csv = Path(args.mask_csv).resolve()
        if not mask_csv.is_file():
            print(f"ERROR: mask_csv not found: {mask_csv}", file=sys.stderr)
            sys.exit(1)
        per_target_masks = load_mask_mapping(mask_csv)
        print(f"[BATCH] Loaded per-target masks: {len(per_target_masks)} from {mask_csv}")
    if rec_mask_global and lig_mask_global:
        print(f"[BATCH] Using global explicit masks: receptor={rec_mask_global}, ligand={lig_mask_global}")
    elif per_target_masks:
        expected = set(per_target_masks.keys())
        mapped = 0
        for t in targets:
            if canonical_name(t.structure_id, expected) is not None:
                mapped += 1
        print(f"[BATCH] Per-target masks can cover {mapped}/{len(targets)} discovered dirs")

    max_workers = max(1, int(args.max_workers))
    failures: List[AmberTarget] = []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut_map = {}
        expected = set(per_target_masks.keys())
        for t in targets:
            rec_mask = rec_mask_global
            lig_mask = lig_mask_global
            if (not rec_mask or not lig_mask) and per_target_masks:
                key = canonical_name(t.structure_id, expected)
                if key is not None:
                    rec_mask, lig_mask = per_target_masks[key]
            fut = ex.submit(run_single, t, env, rec_mask, lig_mask, run_script)
            fut_map[fut] = t
        for fut in as_completed(fut_map):
            t = fut_map[fut]
            try:
                rc = fut.result()
            except Exception as exc:  # noqa: BLE001
                print(f"[BATCH] ERROR: {t.structure_id} raised exception: {exc}", file=sys.stderr)
                failures.append(t)
                continue
            if rc != 0:
                print(f"[BATCH] ERROR: {t.structure_id} exit code {rc}", file=sys.stderr)
                failures.append(t)

    if failures:
        print(f"[BATCH] {len(failures)} structures failed:")
        for t in failures:
            print(f"  - GPU {t.gpu} | {t.structure_id} | {t.amber_dir}")
        sys.exit(1)

    print("[BATCH] All structures processed successfully.")


if __name__ == "__main__":
    main()

