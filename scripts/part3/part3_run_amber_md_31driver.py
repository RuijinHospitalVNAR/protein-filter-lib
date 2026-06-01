#!/usr/bin/env python3
"""
AMBER Part3：31 结构（前 30 + WT）按 8 GPU 块分配，每 GPU 顺序跑 AMBER 单结构。
由 run_amber_31_8gpu.sh 用 CUDA_VISIBLE_DEVICES + taskset 启动 8 个本进程。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
# 仓库根目录（scripts/part3 -> scripts -> 仓库根）
PROJECT_ROOT = SCRIPT_DIR.parent.parent
AMBER_RUN_SINGLE = PROJECT_ROOT / "AMBER" / "run_single.sh"


def main() -> None:
    ap = argparse.ArgumentParser(description="AMBER Part3 单 GPU 驱动：跑本 GPU 分配的结构列表")
    ap.add_argument("--input_csv", type=str, required=True, help="前 30 结构 CSV（含 pdb_path）")
    ap.add_argument("--output_dir", type=str, required=True, help="本 GPU 输出目录（如 .../gpu0）")
    ap.add_argument("--gpu_id", type=int, default=0, help="逻辑 GPU 编号（0-7）")
    ap.add_argument("--n_gpu", type=int, default=8, help="总 GPU 数")
    ap.add_argument("--top_n", type=int, default=30, help="前 N 个结构（0=全部）")
    ap.add_argument("--resume", action="store_true", help="跳过已完成的 AMBER 结构（md_1.rst 存在即视为完成）")
    ap.add_argument("--wt_structure", type=str, default="", help="WT 结构路径（仅 gpu7 在跑完前 30 后跑）")
    ap.add_argument("--wt_gpu_id", type=int, default=-1, help="执行 WT 的逻辑 GPU ID（默认 -1 表示 n_gpu-1）")
    ap.add_argument("--production_ns", type=int, default=100, help="Production 目标时长（ns）；1 表示 1ns 快速示例")
    ap.add_argument("--manifest_name", type=str, default="", help="可选：manifest 文件名（默认 part3_manifest_gpu<id>.json）")
    args = ap.parse_args()

    if not AMBER_RUN_SINGLE.is_file():
        print(f"错误：未找到 AMBER 单结构脚本 {AMBER_RUN_SINGLE}", file=sys.stderr)
        sys.exit(1)

    import pandas as pd

    df = pd.read_csv(args.input_csv)
    if "pdb_path" not in df.columns:
        print("错误：CSV 需含 pdb_path 列", file=sys.stderr)
        sys.exit(1)
    if "interface_score" in df.columns and args.top_n > 0:
        df = df.sort_values("interface_score").head(args.top_n)
    elif args.top_n > 0:
        df = df.head(args.top_n)

    structures: list[tuple[str, str]] = []
    base_csv = Path(args.input_csv).resolve().parent
    for _, r in df.iterrows():
        p = r["pdb_path"]
        if not os.path.isabs(p):
            p = str((base_csv / p).resolve())
        if os.path.isfile(p):
            name = r.get("pdb_name", Path(p).stem)
            structures.append((p, name))

    total = len(structures)
    if total == 0:
        print("本 GPU 无结构可跑，退出。")
        sys.exit(0)

    # 块分配（与 run_md_mmgbsa_rmsd.py 一致）
    logical_gpu_id = args.gpu_id
    structures_per_gpu = total // args.n_gpu
    remainder = total % args.n_gpu
    start_idx = logical_gpu_id * structures_per_gpu + min(logical_gpu_id, remainder)
    end_idx = start_idx + structures_per_gpu + (1 if logical_gpu_id < remainder else 0)
    my_structures = structures[start_idx:end_idx]

    print(f"[GPU {logical_gpu_id}/{args.n_gpu}] 分配结构 {start_idx+1}-{end_idx}（共 {len(my_structures)} 个）")

    out_root = Path(args.output_dir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    manifest_path = out_root / (args.manifest_name or f"part3_manifest_gpu{logical_gpu_id}.json")

    cuda_visible = os.environ.get("CUDA_VISIBLE_DEVICES", "<unset>")
    print(
        f"[GPU-MAP] logical_gpu_id={logical_gpu_id} "
        f"CUDA_VISIBLE_DEVICES={cuda_visible} "
        f"run_single_gpu_id=0 (由 CUDA_VISIBLE_DEVICES 决定实际设备)"
    )

    # 失败结构列表：单个失败不中断，继续跑同 GPU 其余结构；最后统一汇总
    failed_list: list[tuple[str, int | str]] = []
    run_records: list[dict[str, object]] = []

    # Production 目标时间（与 run_single.sh 中 TARGET_PS 一致）
    TARGET_PS = 1_000.0 if args.production_ns == 1 else 100_000.0

    def _production_done(subdir: Path) -> bool:
        """根据 md_*.out 中的 TIME(PS) 和 NSTEP 判断是否已跑满目标时长（支持多段 md_1/md_2/...）。

        对于多段续跑：
        - TIME(PS) 是累计的（从第一段开始累加），检查最后一段的 TIME 即可
        - NSTEP 是每段独立计数，需要累计各段的最大 NSTEP

        判定标准（允许 2% 误差）：
        - 1 ns : TIME >= 1000 ps 且 累计 NSTEP >= 490000
        - 100 ns: TIME >= 100000 ps 且 累计 NSTEP >= 49_000_000
        """
        import re

        mdouts = list(subdir.glob("md_*.out"))
        if not mdouts:
            return False

        def segment_num(p: Path) -> int:
            stem = p.stem  # md_1 -> 1
            try:
                return int(stem.split("_", 1)[1])
            except (IndexError, ValueError):
                return 0

        # 按段号排序，最后一段用于 TIME(PS)，所有段用于累计 NSTEP
        sorted_outs = sorted(mdouts, key=segment_num)
        latest_out = sorted_outs[-1]

        # 累计时间：AMBER 续跑时 TIME(PS) 会在最后一段给出总时间
        last_time_ps: float | None = None
        for line in open(latest_out, errors="ignore"):
            m = re.search(r"TIME\s*\(\s*PS\s*\)\s*=\s*(\d+(?:\.\d*)?)", line)
            if m:
                last_time_ps = float(m.group(1))

        if last_time_ps is None:
            return False

        # 累计所有段的最大 NSTEP（每段各自从 0 计数）
        total_max_nstep = 0
        for mdout in sorted_outs:
            seg_max = 0
            for line in open(mdout, errors="ignore"):
                m = re.search(r"NSTEP\s*=\s*(\d+)", line)
                if m:
                    nstep = int(m.group(1))
                    if nstep > seg_max:
                        seg_max = nstep
            total_max_nstep += seg_max

        # 目标步数（允许 2% 误差），dt=0.002 ps
        target_nstep = int(TARGET_PS / 0.002 * 0.98)
        time_ok = last_time_ps >= TARGET_PS
        step_ok = total_max_nstep >= target_nstep

        return time_ok and step_ok

    for path, name in my_structures:
        subdir = out_root / name
        subdir.mkdir(parents=True, exist_ok=True)
        
        # 检查完成状态
        if args.resume:
            done = _production_done(subdir)
            if done:
                print(f"  跳过已完成: {name}")
                run_records.append({
                    "name": name,
                    "structure_path": path,
                    "output_dir": str(subdir),
                    "status": "skipped_completed",
                    "return_code": 0,
                    "reason": "production_done_and_resume",
                })
                continue
            else:
                # 检查是否有部分进度
                mdouts = list(subdir.glob("md_*.out"))
                if mdouts:
                    import re
                    latest_out = max(mdouts, key=lambda p: int(p.stem.split("_", 1)[1]) if "_" in p.stem else 0)
                    last_time = None
                    for line in open(latest_out, errors="ignore"):
                        m = re.search(r"TIME\s*\(\s*PS\s*\)\s*=\s*(\d+(?:\.\d*)?)", line)
                        if m:
                            last_time = float(m.group(1))
                    if last_time is not None and last_time > 0:
                        print(f"  续跑未完成: {name} (当前 {last_time:.1f} ps / 目标 {TARGET_PS:.0f} ps)")
                    else:
                        print(f"  运行 AMBER: {name} (从头开始)")
                else:
                    print(f"  运行 AMBER: {name} (从头开始)")
        else:
            print(f"  运行 AMBER: {name}")
        
        cmd = [
            "bash",
            str(AMBER_RUN_SINGLE),
            "--structure",
            path,
            "--output_dir",
            str(subdir),
            "--gpu_id",
            "0",
            "--production_ns",
            str(args.production_ns),
        ]
        if args.resume:
            cmd.append("--resume")
        ret = subprocess.run(cmd, cwd=str(subdir))
        if ret.returncode != 0:
            print(f"  失败: {name} (exit {ret.returncode})", file=sys.stderr)
            print(f"  提示: 检查 {subdir}/md_*.out 和 {subdir}/run_*.log 中的错误信息", file=sys.stderr)
            failed_list.append((name, ret.returncode))
            run_records.append({
                "name": name,
                "structure_path": path,
                "output_dir": str(subdir),
                "status": "failed",
                "return_code": ret.returncode,
                "reason": "run_single_nonzero_exit",
            })
            continue

        # 验证完成状态
        if not _production_done(subdir):
            print(f"  警告: {name} 运行结束但未达到目标时长，可能提前终止", file=sys.stderr)
            print(f"  提示: 检查 {subdir}/md_*.out 中的错误信息", file=sys.stderr)
            failed_list.append((name, "未达目标时长"))
            run_records.append({
                "name": name,
                "structure_path": path,
                "output_dir": str(subdir),
                "status": "failed",
                "return_code": 2,
                "reason": "production_not_reached",
            })
        else:
            run_records.append({
                "name": name,
                "structure_path": path,
                "output_dir": str(subdir),
                "status": "success",
                "return_code": 0,
                "reason": "ok",
            })

    # 指定 GPU：前 30 跑完后跑 WT（默认最后一张卡）
    wt_gpu_id = args.wt_gpu_id if args.wt_gpu_id >= 0 else (args.n_gpu - 1)
    if logical_gpu_id == wt_gpu_id and args.wt_structure and os.path.isfile(args.wt_structure):
        wt_dir = out_root.parent / f"WT_original_gpu{wt_gpu_id}" / "WT_original_model"
        wt_dir.mkdir(parents=True, exist_ok=True)
        if args.resume and _production_done(wt_dir):
            print(f"[GPU {wt_gpu_id}] WT 已完成，跳过")
            run_records.append({
                "name": "WT_original_model",
                "structure_path": args.wt_structure,
                "output_dir": str(wt_dir),
                "status": "skipped_completed",
                "return_code": 0,
                "reason": "wt_production_done_and_resume",
            })
        else:
            print(f"[GPU {wt_gpu_id}] 前 30 完成，开始 WT_original_model (31/31)...")
            cmd = [
                "bash",
                str(AMBER_RUN_SINGLE),
                "--structure",
                args.wt_structure,
                "--output_dir",
                str(wt_dir),
                "--gpu_id",
                "0",
                "--production_ns",
                str(args.production_ns),
            ]
            if args.resume:
                cmd.append("--resume")
            ret = subprocess.run(cmd, cwd=str(wt_dir))
            if ret.returncode != 0:
                print("WT 失败", file=sys.stderr)
                failed_list.append(("WT_original_model", ret.returncode))
                run_records.append({
                    "name": "WT_original_model",
                    "structure_path": args.wt_structure,
                    "output_dir": str(wt_dir),
                    "status": "failed",
                    "return_code": ret.returncode,
                    "reason": "wt_run_single_nonzero_exit",
                })
            elif not _production_done(wt_dir):
                print("WT 运行结束但未达到目标时长", file=sys.stderr)
                failed_list.append(("WT_original_model", "未达目标时长"))
                run_records.append({
                    "name": "WT_original_model",
                    "structure_path": args.wt_structure,
                    "output_dir": str(wt_dir),
                    "status": "failed",
                    "return_code": 2,
                    "reason": "wt_production_not_reached",
                })
            else:
                run_records.append({
                    "name": "WT_original_model",
                    "structure_path": args.wt_structure,
                    "output_dir": str(wt_dir),
                    "status": "success",
                    "return_code": 0,
                    "reason": "wt_ok",
                })

    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "gpu_id": logical_gpu_id,
        "n_gpu": args.n_gpu,
        "input_csv": str(Path(args.input_csv).resolve()),
        "output_dir": str(out_root),
        "resume": bool(args.resume),
        "production_ns": args.production_ns,
        "records": run_records,
        "failed_count": len([r for r in run_records if r["status"] == "failed"]),
        "success_count": len([r for r in run_records if r["status"] == "success"]),
        "skipped_count": len([r for r in run_records if r["status"] == "skipped_completed"]),
    }
    manifest_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[GPU {logical_gpu_id}] Manifest: {manifest_path}")

    # 失败汇总：有失败时打印列表，并以非零退出码返回（pipeline 可据此判断部分失败）
    if failed_list:
        print(f"\n[GPU {logical_gpu_id}] 本 GPU 有 {len(failed_list)} 个结构失败:", file=sys.stderr)
        for name, reason in failed_list:
            print(f"  - {name}: {reason}", file=sys.stderr)
        print(f"  提示: 可使用 --resume 重新运行以跳过已完成结构，仅重试失败项", file=sys.stderr)
        sys.exit(1)

    print(f"[GPU {logical_gpu_id}] 本 GPU 任务完成。")


if __name__ == "__main__":
    main()
