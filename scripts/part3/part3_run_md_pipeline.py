#!/usr/bin/env python3
"""
Part 3 统一入口脚本（配置驱动）

支持 YAML 配置 + 命令行覆盖，实现 pipeline 化的使用体验。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
PART3_MD_SCRIPT = PROJECT_ROOT / "YZC_MD_SCRIPT" / "run_part3_md_single.sh"
CONFIG_DIR = PROJECT_ROOT / "config"
RUNNER_SCRIPT = PROJECT_ROOT / "scripts" / "run_md_mmgbsa_rmsd.py"


def load_config(config_path: str | Path) -> Dict[str, Any]:
    """加载 YAML 配置"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def merge_config_with_args(config: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    """合并配置与命令行参数（命令行优先）"""
    merged = config.copy()
    
    # 输入
    if args.input_csv:
        merged["input"]["csv"] = args.input_csv
    if args.input_dir:
        merged["input"]["dir"] = args.input_dir
    if args.top_n is not None:
        merged["input"]["top_n"] = args.top_n
    
    # 链
    if args.target_chain:
        merged["chains"]["target_chain"] = args.target_chain
    if args.binder_chain:
        merged["chains"]["binder_chain"] = args.binder_chain
    
    # 物理参数
    if args.tmp is not None:
        merged["physics"]["temperature"] = args.tmp
    if args.ph is not None:
        merged["physics"]["ph"] = args.ph
    if args.conc is not None:
        merged["physics"]["ion_concentration"] = args.conc
    
    # MD 参数
    if args.production_ns is not None:
        merged["md"]["production_ns"] = args.production_ns
    if args.npt_ns is not None:
        merged["md"]["npt_ns"] = args.npt_ns
    if args.interval is not None:
        merged["md"]["interval"] = args.interval
    
    # 力场
    if args.forcefield:
        merged["forcefield"] = args.forcefield
    
    # 资源
    if args.n_gpu is not None:
        merged["resources"]["n_gpu"] = args.n_gpu
    if args.gpu_ids:
        merged["resources"]["gpu_ids"] = [int(x) for x in args.gpu_ids.split(",")]
    if args.ntomp is not None:
        merged["resources"]["ntomp"] = args.ntomp
    
    # 输出
    if args.output_dir:
        merged["output"]["base_dir"] = args.output_dir
    if args.run_id:
        merged["output"]["run_id"] = args.run_id
    
    # Resume
    if args.resume is not None:
        merged["resume"]["enabled"] = args.resume
    if args.rerun_failed is not None:
        merged["resume"]["rerun_failed"] = args.rerun_failed
    
    return merged


def generate_run_id() -> str:
    """生成运行 ID：YYYYMMDD_HHMMSS"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def create_manifest(config: Dict[str, Any], run_id: str, output_dir: Path) -> None:
    """创建 manifest.json：记录运行信息"""
    manifest = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "config": config,
        "environment": {
            "python_version": sys.version,
            "cwd": str(Path.cwd()),
        },
    }
    
    # Git 信息（如果可用）
    try:
        import git
        repo = git.Repo(PROJECT_ROOT, search_parent_directories=True)
        manifest["git"] = {
            "commit": repo.head.commit.hexsha,
            "branch": repo.active_branch.name if not repo.head.is_detached else None,
            "dirty": repo.is_dirty(),
        }
    except ImportError:
        manifest["git"] = {"note": "gitpython not installed"}
    except Exception:
        manifest["git"] = None
    
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def create_status_file(structure_dir: Path, status: str, error: str = "") -> None:
    """创建/更新结构的状态文件"""
    status_path = structure_dir / "status.json"
    status_data = {
        "status": status,  # running, success, failed
        "timestamp": datetime.now().isoformat(),
        "error": error,
    }
    
    # 如果成功，记录关键文件路径
    if status == "success":
        status_data["outputs"] = {
            "mmgbsa_summary": str(structure_dir / "mmgbsa_summary.csv"),
            "mmpbsa_results": str(structure_dir / "FINAL_RESULTS_MMPBSA.dat"),
            "rmsd": str(structure_dir / "rmsd.xvg"),
        }
    
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(status_data, f, indent=2, ensure_ascii=False)


def check_structure_status(structure_dir: Path) -> str | None:
    """检查结构状态：返回 status 或 None（未运行）"""
    status_path = structure_dir / "status.json"
    if not status_path.exists():
        return None
    
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("status")
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Part 3 统一入口（配置驱动）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 使用默认配置（100ns）
  %(prog)s --config config/part3_100ns.yaml --input_csv path/to/rosetta_static_0.csv --output_dir /path/to/output

  # 快速评估（10ns）
  %(prog)s --config config/part3_quick.yaml --input_csv path/to/rosetta_static_0.csv --output_dir /path/to/output

  # 命令行覆盖配置
  %(prog)s --config config/part3.yaml --input_csv path/to/rosetta_static_0.csv --output_dir /path/to/output --production_ns 50 --top_n 20
        """,
    )
    
    # 配置
    ap.add_argument(
        "--config",
        type=str,
        default=str(CONFIG_DIR / "part3.yaml"),
        help="YAML 配置文件路径（默认：config/part3.yaml）",
    )
    
    # 输入（覆盖配置）
    ap.add_argument("--input_csv", type=str, help="Part 2 CSV（覆盖配置）")
    ap.add_argument("--input_dir", type=str, help="结构目录（覆盖配置）")
    ap.add_argument("--top_n", type=int, help="仅处理前 N 个（覆盖配置）")
    
    # 链（覆盖配置）
    ap.add_argument("--target_chain", type=str, help="靶标链（覆盖配置）")
    ap.add_argument("--binder_chain", type=str, help="结合子链（覆盖配置）")
    
    # 物理参数（覆盖配置）
    ap.add_argument("--tmp", type=float, help="温度 K（覆盖配置）")
    ap.add_argument("--ph", type=float, help="pH（覆盖配置）")
    ap.add_argument("--conc", type=float, help="离子浓度 M（覆盖配置）")
    
    # MD 参数（覆盖配置）
    ap.add_argument("--production_ns", type=int, help="生产模拟 ns（覆盖配置）")
    ap.add_argument("--npt_ns", type=int, help="NPT 平衡 ns（覆盖配置）")
    ap.add_argument("--interval", type=int, help="MM/PBSA 取帧间隔（覆盖配置）")
    
    # 力场（覆盖配置）
    ap.add_argument("--forcefield", type=str, help="力场名称（覆盖配置）")
    
    # 资源（覆盖配置）
    ap.add_argument("--n_gpu", type=int, help="总 GPU 数（覆盖配置）")
    ap.add_argument("--gpu_ids", type=str, help="GPU ID 列表，逗号分隔（覆盖配置，如：0,1,2,3）")
    ap.add_argument("--ntomp", type=int, help="OpenMP 线程数（覆盖配置）")
    
    # 输出（覆盖配置）
    ap.add_argument("--output_dir", type=str, required=True, help="输出根目录（必填）")
    ap.add_argument("--run_id", type=str, help="运行 ID（覆盖配置，默认自动生成）")
    
    # Resume（覆盖配置）
    ap.add_argument("--resume", action="store_true", help="启用 resume（跳过已完成结构）")
    ap.add_argument("--rerun-failed", action="store_true", help="只重跑失败的结构")
    
    args = ap.parse_args()
    
    # 加载配置
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"错误：配置文件不存在: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = load_config(config_path)

    # 处理自动链识别
    auto_detect = config.get("chains", {}).get("auto_detect", {})
    if auto_detect.get("enabled", False):
        from protein_filter.utils.chain_detection import auto_detect_chains, get_mmpbsa_masks
        if config.get("input", {}).get("dir"):
            pdb_dir = config["input"]["dir"]
            pdb_files = list(Path(pdb_dir).glob("*.pdb")) + list(Path(pdb_dir).glob("*/relaxed*.pdb"))
            if pdb_files:
                target_seq = auto_detect.get("target_sequence", "")
                binder_seq = auto_detect.get("binder_sequence", "")
                strategy = auto_detect.get("strategy", "by_length")
                try:
                    target_chain, binder_chain = auto_detect_chains(
                        str(pdb_files[0]),
                        strategy=strategy,
                        target_sequence=target_seq if target_seq else None,
                        binder_sequence=binder_seq if binder_seq else None
                    )
                    config["chains"]["target_chain"] = target_chain
                    config["chains"]["binder_chain"] = binder_chain
                    print(f"[Auto-detect] 识别结果: target_chain={target_chain}, binder_chain={binder_chain}")
                except Exception as e:
                    print(f"[Warning] 自动链识别失败: {e}，使用配置中的默认链ID", file=sys.stderr)

    # 合并命令行参数
    config = merge_config_with_args(config, args)
    
    # 验证必填项
    if not config["output"]["base_dir"]:
        print("错误：--output_dir 必填", file=sys.stderr)
        sys.exit(1)
    
    if not config["input"]["csv"] and not config["input"]["dir"]:
        print("错误：需提供 --input_csv 或 --input_dir", file=sys.stderr)
        sys.exit(1)
    
    # 生成运行 ID
    run_id = config["output"]["run_id"] or generate_run_id()
    
    # 创建输出目录结构
    output_base = Path(config["output"]["base_dir"]).resolve()
    output_dir = output_base / "runs" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存使用的配置
    config_path_out = output_dir / "config.yaml"
    with open(config_path_out, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    # 创建 manifest
    create_manifest(config, run_id, output_dir)
    
    print(f"==========================================")
    print(f"Part 3 运行（配置驱动）")
    print(f"==========================================")
    print(f"运行 ID: {run_id}")
    print(f"输出目录: {output_dir}")
    print(f"配置: {config_path}")
    print(f"==========================================")
    
    # 调用底层脚本（保持兼容）
    # 这里我们仍然使用 run_md_mmgbsa_rmsd.py，但传入标准化参数
    
    cmd = [
        sys.executable,
        str(RUNNER_SCRIPT),
        "--output_dir", str(output_dir),
        "--target_chain", config["chains"]["target_chain"],
        "--binder_chain", config["chains"]["binder_chain"],
        "--production_ns", str(config["md"]["production_ns"]),
        "--npt_ns", str(config["md"]["npt_ns"]),
        "--tmp", str(config["physics"]["temperature"]),
        "--ph", str(config["physics"]["ph"]),
        "--conc", str(config["physics"]["ion_concentration"]),
        "--interval", str(config["md"]["interval"]),
        "--ntomp", str(config["resources"]["ntomp"]),
        "--forcefield", config["forcefield"],
        "--n_gpu", str(config["resources"]["n_gpu"]),
    ]
    
    if config["input"]["csv"]:
        cmd.extend(["--input_csv", config["input"]["csv"]])
    elif config["input"]["dir"]:
        cmd.extend(["--input_dir", config["input"]["dir"]])
    
    if config["input"]["top_n"] > 0:
        cmd.extend(["--top_n", str(config["input"]["top_n"])])
    
    # 多 GPU 并行：为每个 GPU 启动一个进程
    if config["resources"]["n_gpu"] > 1:
        gpu_ids = config["resources"]["gpu_ids"][:config["resources"]["n_gpu"]]
        print(f"\n启动 {len(gpu_ids)} 个 GPU 并行任务...")

        # 使用 CUDA_VISIBLE_DEVICES 隔离物理 GPU：
        # - 对于第 k 个任务：CUDA_VISIBLE_DEVICES=physical_id_k，run_md_mmgbsa_rmsd.py 收到 --gpu_id=k
        # - 脚本内部使用逻辑 GPU 编号进行结构切分，物理 GPU 始终为可见的第 0 号
        pids = []
        for logical_idx, gpu_id in enumerate(gpu_ids):
            gpu_output_dir = output_dir / f"gpu{gpu_id}"
            gpu_cmd = cmd + [
                "--gpu_id",
                str(logical_idx),
                "--output_dir",
                str(gpu_output_dir),
            ]
            
            # 添加 resume/rerun-failed 参数
            if config.get("resume", {}).get("enabled"):
                gpu_cmd.append("--resume")
            if config.get("resume", {}).get("rerun_failed"):
                gpu_cmd.append("--rerun-failed")
            
            log_file = gpu_output_dir / "run.log"
            gpu_output_dir.mkdir(parents=True, exist_ok=True)
            
            # 为每个进程设置独立的 CUDA_VISIBLE_DEVICES，实现 GPU 隔离
            env = os.environ.copy()
            env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
            print(
                f"  [GPU {gpu_id}] 启动任务 (逻辑索引={logical_idx}, "
                f"CUDA_VISIBLE_DEVICES={env['CUDA_VISIBLE_DEVICES']})"
            )

            with open(log_file, "a", encoding="utf-8") as f:  # 追加模式，支持续跑
                proc = subprocess.Popen(
                    gpu_cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=env,
                )
                pids.append((gpu_id, proc))

            print(f"    -> 进程 PID: {proc.pid}")
            # 避免同时启动导致资源竞争
            import time
            time.sleep(2)
        
        # 等待所有进程完成
        print(f"\n等待所有 GPU 任务完成...")
        for gpu_id, proc in pids:
            proc.wait()
            print(f"  [GPU {gpu_id}] 完成")
        
        print(f"\n所有 GPU 任务完成！")
        print(f"结果目录: {output_dir}/gpu*/")
    else:
        # 单 GPU
        single_gpu_id = config["resources"]["gpu_ids"][0]
        # 在隔离环境中，底层脚本只看到 1 块 GPU，因此传递逻辑 GPU 编号 0
        cmd.extend(["--gpu_id", "0"])
        
        # 添加 resume/rerun-failed 参数
        if config.get("resume", {}).get("enabled"):
            cmd.append("--resume")
        if config.get("resume", {}).get("rerun_failed"):
            cmd.append("--rerun-failed")
        
        log_file = output_dir / "run.log"
        
        # 确保 GPU 可见性：使用 CUDA_VISIBLE_DEVICES 隔离到单块 GPU
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(single_gpu_id)
        print(
            f"  [GPU {single_gpu_id}] 单 GPU 模式，"
            f"设置 CUDA_VISIBLE_DEVICES={env['CUDA_VISIBLE_DEVICES']}，传递 --gpu_id=0"
        )
        
        with open(log_file, "a", encoding="utf-8") as f:  # 追加模式，支持续跑
            subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, check=True, env=env)
        
        print(f"\n任务完成！")
        print(f"结果目录: {output_dir}/")


if __name__ == "__main__":
    main()
