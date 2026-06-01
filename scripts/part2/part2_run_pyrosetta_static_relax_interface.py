#!/usr/bin/env python3
"""
PyRosetta 静态物理分析：界面能量（interface_dG）与 FastRelax。

整合自：
- /data/Tools/germinal (pyrosetta_utils.score_interface, Relax, SAP 等)
- /data/Tools/PPIFlow-main (demo_scripts/relax_complex.py: FastRelax + InterfaceAnalyzerMover)

重要：默认启用 Relax，使 AF3 预测结构符合物理力场，确保 interface_dG 评估准确。

用法：
  CSV 模式：--csv_path <csv>，CSV 需含 `pdb` 列，可选 `ligand`、`receptor` 列用于界面定义
  目录模式：--pdb_dir <dir>，配合 --binder_chain/--target_chain 定义界面
           默认只分析主模型文件（排除 seed- 目录中的文件）

输出：
  - <output_dir>/rosetta_static_<batch_idx>.csv：分析结果
  - <output_dir>/resource_usage.json：资源使用统计
  - <output_dir>/relax_<原名>：Relax 后结构（仅当 --dump_pdb 或 --dump_top_n>0 时）
     若指定 --dump_top_n N，则仅保留 interface_score 前 N 的 relax_*，其余删除，供 Part3 直接使用
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("警告：psutil 未安装，无法监控资源使用情况", file=sys.stderr)

# 项目根目录
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _bool_arg(s: str) -> bool:
    t = s.strip().lower()
    if t in ("true", "t", "yes", "y", "1"):
        return True
    if t in ("false", "f", "no", "n", "0"):
        return False
    raise ValueError(f"Cannot interpret '{s}' as bool")


def _cif_to_pdb(cif_path: str, output_dir: str) -> str:
    """将 CIF 文件转换为 PDB 格式（PyRosetta 兼容）。"""
    import tempfile
    from Bio.PDB import MMCIFParser, PDBIO
    
    pdb_name = os.path.basename(cif_path).replace(".cif", "")
    pdb_path = os.path.join(output_dir, f"{pdb_name}_temp.pdb")
    
    # 如果已存在，直接返回
    if os.path.exists(pdb_path):
        return pdb_path
    
    try:
        parser = MMCIFParser(QUIET=True)
        structure = parser.get_structure("structure", cif_path)
        io = PDBIO()
        io.set_structure(structure)
        io.save(pdb_path)
        return pdb_path
    except Exception as e:
        # 转换失败，返回原路径（让 PyRosetta 尝试直接读取）
        print(f"警告：CIF 转 PDB 失败 {cif_path}: {e}", file=sys.stderr)
        return cif_path


def _init_pyrosetta_worker():
    """在工作进程中初始化 PyRosetta（每个进程需要独立初始化）"""
    import pyrosetta
    pyrosetta.init(
        "-use_input_sc -ignore_unrecognized_res -ignore_zero_occupancy false "
        "-load_PDB_components false -relax:default_repeats 2 -no_fconfig"
    )


def _run_single_worker(args_tuple):
    """工作进程函数（用于multiprocessing）"""
    (pdb_path, interface, relax, fixbb, fixed_chains, max_iter, min_type, dump_pdb, output_dir) = args_tuple
    return _run_single(
        pdb_path, interface, relax, fixbb, fixed_chains, max_iter, min_type, dump_pdb, output_dir
    )


def _run_single(
    pdb_path: str,
    interface: str | None,
    relax: bool,
    fixbb: bool,
    fixed_chains: list[str],
    max_iter: int,
    min_type: str | None,
    dump_pdb: bool,
    output_dir: str,
) -> dict:
    """对单个 PDB 执行 Relax（可选）与 InterfaceAnalyzerMover。调用前需已初始化 PyRosetta。"""
    from pyrosetta import pose_from_pdb, get_score_function
    from pyrosetta.rosetta.core.kinematics import MoveMap
    from pyrosetta.rosetta.protocols.analysis import InterfaceAnalyzerMover
    from pyrosetta.rosetta.protocols.relax import FastRelax

    start = time.time()
    pdb_name = os.path.basename(pdb_path).replace(".pdb", "").replace(".cif", "")

    try:
        # 如果是 CIF 文件，先转换为 PDB
        actual_path = pdb_path
        if pdb_path.endswith(".cif") or pdb_path.endswith(".mmcif"):
            temp_dir = os.path.join(output_dir, ".temp_pdb")
            os.makedirs(temp_dir, exist_ok=True)
            actual_path = _cif_to_pdb(pdb_path, temp_dir)
        
        pose = pose_from_pdb(actual_path)
        if pose.total_residue() == 0:
            raise ValueError(f"加载的结构为空（残基数为 0）: {pdb_path}")
        original_pose = pose.clone()
        scorefxn = get_score_function()

        if relax:
            fr = FastRelax()
            fr.set_scorefxn(scorefxn)
            fr.max_iter(max_iter)
            
            # 平衡模式：适合AF3预测结构
            # - 约束到起始坐标：保持AF3预测的折叠
            # - 禁止整体链移动：保持相对位置
            fr.constrain_relax_to_start_coords(True)  # 保持AF3预测结构
            
            # 最小化类型设置（默认使用LBFGS算法，收敛更快）
            if min_type:
                fr.min_type(min_type)  # 如 "lbfgs_armijo_nonmonotone"
            # 如果min_type为空字符串，使用默认算法
            
            mm = MoveMap()
            mm.set_bb(True)
            mm.set_chi(True)
            mm.set_jump(False)  # 禁止整体链移动，保持相对位置
            if fixbb and fixed_chains:
                for i in range(1, pose.total_residue() + 1):
                    ch = pose.pdb_info().chain(i)
                    mm.set_bb(i, ch not in fixed_chains)
            fr.set_movemap(mm)
            fr.apply(pose)

        ia = InterfaceAnalyzerMover()
        if interface:
            ia.set_interface(interface.replace(",", ""))
        ia.set_skip_reporting(True)
        ia.set_scorefunction(scorefxn)
        ia.set_compute_interface_energy(True)
        ia.set_calc_dSASA(True)
        ia.apply(pose)

        elapsed = time.time() - start
        row = {
            "pdb_name": pdb_name,
            "pdb_path": pdb_path,
            "interface_score": ia.get_interface_dG(),
            "interface_delta_sasa": ia.get_interface_delta_sasa(),
            "complexed_sasa": ia.get_complexed_sasa(),
            "time_consumed": round(elapsed, 2),
        }
        if relax:
            row["relaxed"] = scorefxn(pose)
            row["original"] = scorefxn(original_pose)
            row["delta"] = scorefxn(pose) - scorefxn(original_pose)

        if dump_pdb and relax:
            out_pdb = os.path.join(output_dir, f"relax_{os.path.basename(pdb_path)}")
            pose.dump_pdb(out_pdb)

        return row
    except Exception as e:
        print(f"处理 {pdb_path} 时出错: {e}", file=sys.stderr)
        return {
            "pdb_name": pdb_name,
            "pdb_path": pdb_path,
            "interface_score": None,
            "interface_delta_sasa": None,
            "complexed_sasa": None,
            "time_consumed": 0.0,
            "error": str(e),
        }


class ResourceMonitor:
    """资源使用监控器"""
    
    def __init__(self):
        self.start_time = time.time()
        self.start_cpu_times = None
        self.start_memory = None
        self.process = None
        self.peak_memory_mb = 0
        self.total_cpu_time = 0
        
        if PSUTIL_AVAILABLE:
            self.process = psutil.Process()
            self.start_cpu_times = self.process.cpu_times()
            self.start_memory = self.process.memory_info()
        else:
            self.process = None
    
    def update_peak_memory(self):
        """更新峰值内存"""
        if self.process:
            current_memory_mb = self.process.memory_info().rss / 1024 / 1024
            if current_memory_mb > self.peak_memory_mb:
                self.peak_memory_mb = current_memory_mb
    
    def get_current_stats(self) -> dict:
        """获取当前资源统计"""
        if not self.process:
            return {}
        
        current_cpu_times = self.process.cpu_times()
        current_memory = self.process.memory_info()
        
        elapsed = time.time() - self.start_time
        cpu_user = current_cpu_times.user - self.start_cpu_times.user
        cpu_system = current_cpu_times.system - self.start_cpu_times.system
        cpu_total = cpu_user + cpu_system
        
        self.update_peak_memory()
        
        return {
            "elapsed_time_seconds": elapsed,
            "cpu_time_seconds": {
                "user": cpu_user,
                "system": cpu_system,
                "total": cpu_total,
            },
            "cpu_utilization_percent": (cpu_total / elapsed * 100) if elapsed > 0 else 0,
            "current_memory_mb": current_memory.rss / 1024 / 1024,
            "peak_memory_mb": self.peak_memory_mb,
            "memory_increase_mb": (current_memory.rss - self.start_memory.rss) / 1024 / 1024,
        }
    
    def get_final_report(self) -> dict:
        """获取最终资源使用报告"""
        stats = self.get_current_stats()
        stats["start_time"] = datetime.fromtimestamp(self.start_time).isoformat()
        stats["end_time"] = datetime.now().isoformat()
        
        # 格式化时间
        elapsed = stats["elapsed_time_seconds"]
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = elapsed % 60
        stats["elapsed_time_formatted"] = f"{hours}h {minutes}m {seconds:.1f}s"
        
        return stats


def main() -> None:
    ap = argparse.ArgumentParser(
        description="PyRosetta 静态分析：界面能量 + FastRelax（默认启用，使结构符合物理力场）"
    )
    ap.add_argument("--csv_path", type=str, default="", help="CSV：含 pdb 列，可选 ligand、receptor")
    ap.add_argument("--pdb_dir", type=str, default="", help="PDB 目录；与 --binder_chain/--target_chain 配合")
    ap.add_argument("--output_dir", type=str, required=True, help="输出目录")
    ap.add_argument("--batch_idx", type=int, default=0, help="批次编号，用于输出文件名")
    ap.add_argument("--relax", type=_bool_arg, default=True, help="是否先 FastRelax（默认 True，使结构符合物理力场）")
    ap.add_argument("--fixbb", type=_bool_arg, default=False, help="Relax 时是否固定指定链骨架")
    ap.add_argument("--fixed_chain", type=str, default="", help="固定骨架的链，如 A_B")
    ap.add_argument("--max_iter", type=int, default=200, help="FastRelax 最大迭代次数（默认200=Germinal配置）")
    ap.add_argument("--dump_pdb", type=_bool_arg, default=False, help="是否写出 Relax 后的 PDB")
    ap.add_argument("--dump_top_n", type=int, default=0, help="仅保留 interface_score 前 N 的 Relax 结构（0=不按排名保留；>0 时先全量写出再删除非前 N，避免 Part3 再跑 Part2 浪费资源）")
    ap.add_argument("--binder_chain", type=str, default="B", help="结合子链（目录模式）")
    ap.add_argument("--target_chain", type=str, default="A", help="靶标链（目录模式）")
    ap.add_argument("--only_main_models", type=_bool_arg, default=True, help="只分析主模型（排除 seed- 目录；主文件夹内为每轮预测选出的最佳结果）")
    ap.add_argument("--one_per_design", type=_bool_arg, default=False, help="每个 design 只取一个结构：主文件夹中 *_model.cif（排除 seed- 后，同 design 下若有多次运行则优先取无时间戳的 run 文件夹内文件）")
    ap.add_argument("--n_jobs", type=int, default=0, help="并行进程数（0=自动计算，基于CPU和内存）")
    ap.add_argument("--max_cpu_percent", type=float, default=70.0, help="最大CPU使用率阈值（%，默认70）")
    ap.add_argument("--min_type", type=str, default="lbfgs_armijo_nonmonotone", help="最小化类型（默认'lbfgs_armijo_nonmonotone'=LBFGS算法，空字符串=使用默认）")
    ap.add_argument("--resume", action="store_true", help="断点续跑：跳过已完成的 pdb，并合并到已有 CSV")
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    fixed_chains = [x.strip() for x in args.fixed_chain.split("_") if x.strip()]

    # 构建界面字符串（目录模式）
    default_interface = "_".join(sorted([args.binder_chain, args.target_chain]))

    # 初始化资源监控
    resource_monitor = ResourceMonitor()
    
    # 计算并行进程数
    if args.n_jobs == 0:
        # 自动计算：基于CPU核心数和内存
        import psutil
        cpu_count = psutil.cpu_count()
        available_memory_gb = psutil.virtual_memory().available / (1024**3)
        
        # CPU限制：不超过max_cpu_percent
        max_cpu_cores = int(cpu_count * args.max_cpu_percent / 100)
        
        # 内存限制：每个进程约需1-2GB，保留20GB给系统
        max_memory_cores = int((available_memory_gb - 20) / 2)
        
        # 取较小值，但至少为1
        n_jobs = max(1, min(max_cpu_cores, max_memory_cores, 32))  # 最多32个进程
        print(f"自动计算并行进程数: {n_jobs} (CPU核心: {cpu_count}, 可用内存: {available_memory_gb:.1f}GB)")
    else:
        n_jobs = args.n_jobs
        print(f"使用指定的并行进程数: {n_jobs}")
    
    # 单进程模式：在主进程初始化 PyRosetta
    if n_jobs == 1:
        print("初始化 PyRosetta（单进程模式）...")
        import pyrosetta
        pyrosetta.init(
            "-use_input_sc -ignore_unrecognized_res -ignore_zero_occupancy false "
            "-load_PDB_components false -relax:default_repeats 2 -no_fconfig"
        )
        print("✅ PyRosetta 初始化完成")
    else:
        print(f"多进程模式：将使用 {n_jobs} 个并行进程")
        print("  （每个进程将独立初始化 PyRosetta）")
    
    if args.relax:
        print(f"⚠️  注意：已启用 Relax，每个结构需要 30-120 秒")
        if n_jobs > 1:
            estimated_time_hours = (313 / n_jobs) * 60 / 3600  # 假设平均60秒/结构
            print(f"   预计完成时间（{n_jobs}进程）: 约 {estimated_time_hours:.1f} 小时")
        if args.dump_top_n > 0:
            print(f"   将自动保留 interface_score 前 {args.dump_top_n} 的 Relax 结构（其余 relax_* 会删除）")
    else:
        print("⚠️  警告：未启用 Relax，结果可能不够准确（AF3 结构可能不符合物理力场）")

    rows: list[dict] = []
    csv_mode = bool(args.csv_path.strip())
    # 若指定 dump_top_n，则本轮对所有结构写出 relax_*，结束后再按排名删除非前 N
    dump_this_run = args.dump_pdb or (args.dump_top_n > 0)

    # 断点续跑：加载 Part2 checkpoint（仅 CSV 模式）
    checkpoint = None
    if args.resume and csv_mode:
        try:
            from protein_filter.pipeline.state import Part2Checkpoint
            checkpoint = Part2Checkpoint.load(Path(args.output_dir))
            if checkpoint:
                print(f"断点续跑：已加载 {len(checkpoint.completed_pdb_paths)} 条已完成记录")
        except Exception as e:
            print(f"警告：加载 checkpoint 失败，将全量重跑: {e}", file=sys.stderr)
            checkpoint = None
    if args.resume and csv_mode and checkpoint:
        # 从已有 CSV 恢复已完成的 rows（保持顺序与列）
        out_csv_existing = Path(args.output_dir) / f"rosetta_static_{args.batch_idx}.csv"
        if out_csv_existing.exists():
            try:
                existing_df = pd.read_csv(out_csv_existing)
                if "pdb_path" in existing_df.columns:
                    for _, r in existing_df.iterrows():
                        path = r.get("pdb_path")
                        if pd.notna(path) and str(path).strip():
                            rows.append(r.to_dict())
                elif "pdb" in existing_df.columns:
                    for _, r in existing_df.iterrows():
                        rows.append(r.to_dict())
                print(f"断点续跑：已从 {out_csv_existing} 恢复 {len(rows)} 条结果")
            except Exception as e:
                print(f"警告：读取已有 CSV 失败: {e}", file=sys.stderr)

    if csv_mode:
        df = pd.read_csv(args.csv_path)
        if df.empty:
            if rows:
                out_csv = os.path.join(args.output_dir, f"rosetta_static_{args.batch_idx}.csv")
                pd.DataFrame(rows).to_csv(out_csv, index=False)
                print(f"CSV 为空，已保留断点续跑结果 {out_csv}，共 {len(rows)} 条")
            return
        if "pdb" not in df.columns:
            print("CSV 需包含 pdb 列")
            return
        has_interface = "ligand" in df.columns and "receptor" in df.columns
        # 构建待处理行（排除已完成的）
        todo_list: list[tuple[str, str | None]] = []
        for _, r in df.iterrows():
            pdb_path = r["pdb"]
            if not os.path.isfile(pdb_path):
                print(f"跳过不存在的文件: {pdb_path}")
                continue
            if checkpoint and checkpoint.is_done(pdb_path):
                continue
            interface = None
            if has_interface:
                lig = str(r.get("ligand", "")).replace(",", "").strip()
                rec = str(r.get("receptor", "")).replace(",", "").strip()
                if lig and rec:
                    interface = "_".join(sorted([lig, rec]))
            if not interface:
                interface = default_interface
            todo_list.append((pdb_path, interface))
        if not todo_list and rows:
            out_csv = os.path.join(args.output_dir, f"rosetta_static_{args.batch_idx}.csv")
            pd.DataFrame(rows).to_csv(out_csv, index=False)
            print(f"断点续跑：无待处理项，已写入 {out_csv}，共 {len(rows)} 条")
            return
        if not todo_list:
            print("没有待处理项且无已有结果，退出")
            return
        print(f"待处理 {len(todo_list)} 条（总 {len(df)} 条）")
        for pdb_path, interface in todo_list:
            row = _run_single(
                pdb_path,
                interface=interface,
                relax=args.relax,
                fixbb=args.fixbb,
                fixed_chains=fixed_chains,
                max_iter=args.max_iter,
                min_type=args.min_type if args.min_type else None,
                dump_pdb=dump_this_run,
                output_dir=args.output_dir,
            )
            rows.append(row)
            if checkpoint:
                checkpoint.mark_done(pdb_path)
                checkpoint.save(Path(args.output_dir))
            # 增量写入
            out_csv = os.path.join(args.output_dir, f"rosetta_static_{args.batch_idx}.csv")
            pd.DataFrame(rows).to_csv(out_csv, index=False)
    else:
        if not args.pdb_dir or not os.path.isdir(args.pdb_dir):
            print("请提供 --csv_path 或有效的 --pdb_dir")
            return
        
        # 递归查找 PDB 和 CIF 文件
        pat_pdb = os.path.join(args.pdb_dir, "**", "*.pdb")
        pat_cif = os.path.join(args.pdb_dir, "**", "*.cif")
        all_files = sorted(glob.glob(pat_pdb, recursive=True)) + sorted(glob.glob(pat_cif, recursive=True))
        
        # 如果启用 only_main_models，排除 seed- 目录中的文件（只保留主文件夹内的最佳结果）
        if args.only_main_models:
            files = [f for f in all_files if "/seed-" not in f]
            print(f"找到 {len(all_files)} 个结构文件，过滤后保留 {len(files)} 个主模型文件（主文件夹内）")
        else:
            files = all_files
            print(f"找到 {len(files)} 个结构文件")

        # 若启用 one_per_design：每个 design（顶层目录）只保留一个结构，优先取主 run 文件夹（无 _YYYYMMDD_HHMMSS 后缀）内的 *_model.cif
        if args.one_per_design and files:
            import re
            pdb_dir_r = os.path.realpath(args.pdb_dir)
            design_to_paths: dict = {}
            for f in files:
                f_abs = os.path.realpath(f)
                try:
                    rel = os.path.relpath(f_abs, pdb_dir_r)
                except ValueError:
                    rel = f
                parts = rel.split(os.sep)
                design_id = parts[0] if parts else ""
                parent_dir = os.path.basename(os.path.dirname(f))
                design_to_paths.setdefault(design_id, []).append((f, parent_dir))
            one_per = []
            for design_id, candidates in sorted(design_to_paths.items()):
                # 优先：父目录名不带 _YYYYMMDD_HHMMSS 的（主 run）
                no_ts = [p for p in candidates if not re.search(r"_\d{8}_\d{6}$", p[1])]
                chosen = (no_ts[0][0] if no_ts else candidates[0][0])
                one_per.append(chosen)
            files = sorted(one_per)
            print(f"one_per_design 已启用：每个 design 取 1 个主结果，共 {len(files)} 个结构")

        if not files:
            print("未找到任何结构文件，退出")
            return
        
        print(f"开始处理 {len(files)} 个结构...")
        out_csv = os.path.join(args.output_dir, f"rosetta_static_{args.batch_idx}.csv")
        
        if n_jobs > 1:
            # 多进程并行处理
            from multiprocessing import Pool
            from functools import partial
            
            # 准备参数列表
            worker_args = [
                (pdb_path, default_interface, args.relax, args.fixbb, fixed_chains,
                 args.max_iter, args.min_type if args.min_type else None, dump_this_run, args.output_dir)
                for pdb_path in files
            ]
            
            print(f"使用 {n_jobs} 个进程并行处理...")
            
            # 使用进程池并行处理
            completed = 0
            with Pool(processes=n_jobs, initializer=_init_pyrosetta_worker) as pool:
                # 使用imap_unordered以便实时显示进度
                for i, row in enumerate(pool.imap_unordered(_run_single_worker, worker_args), 1):
                    rows.append(row)
                    completed = i
                    
                    # 更新资源监控
                    resource_monitor.update_peak_memory()
                    
                    # 每处理10个显示进度
                    if completed % 10 == 0 or completed == len(files):
                        stats = resource_monitor.get_current_stats()
                        print(f"  已处理 {completed}/{len(files)} 个结构 ({completed*100//len(files)}%)")
                        if stats:
                            print(f"    资源使用: CPU {stats['cpu_utilization_percent']:.1f}%, "
                                  f"内存 {stats['current_memory_mb']:.1f} MB (峰值 {stats['peak_memory_mb']:.1f} MB), "
                                  f"已用时间 {stats['elapsed_time_seconds']/60:.1f} 分钟")
                        
                        # 增量保存
                        temp_df = pd.DataFrame(rows)
                        temp_df.to_csv(out_csv, index=False)
                        print(f"  ✅ 已保存进度到 {out_csv}")
        else:
            # 单进程顺序处理（原有逻辑）
            for i, pdb_path in enumerate(files, 1):
                if i % 50 == 0:
                    stats = resource_monitor.get_current_stats()
                    print(f"  已处理 {i}/{len(files)} 个结构...")
                    if stats:
                        print(f"    资源使用: CPU {stats['cpu_utilization_percent']:.1f}%, "
                              f"内存 {stats['current_memory_mb']:.1f} MB (峰值 {stats['peak_memory_mb']:.1f} MB), "
                              f"已用时间 {stats['elapsed_time_seconds']/60:.1f} 分钟")
                elif i % 10 == 0:
                    print(f"  已处理 {i}/{len(files)} 个结构...", end="\r")
                
                row = _run_single(
                    pdb_path,
                    interface=default_interface,
                    relax=args.relax,
                    fixbb=args.fixbb,
                    fixed_chains=fixed_chains,
                    max_iter=args.max_iter,
                    min_type=args.min_type if args.min_type else None,
                    dump_pdb=dump_this_run,
                    output_dir=args.output_dir,
                )
                rows.append(row)
                
                # 更新资源监控
                resource_monitor.update_peak_memory()
                
                # 每 10 个文件增量写入一次
                if i % 10 == 0 or i == len(files):
                    temp_df = pd.DataFrame(rows)
                    # 追加模式（第一次写入时创建文件）
                    if i == 10:
                        temp_df.to_csv(out_csv, index=False)
                    else:
                        temp_df.to_csv(out_csv, index=False, mode='w')  # 覆盖写入最新状态
                    print(f"  ✅ 已保存进度: {i}/{len(files)} 个结构")

    if not rows:
        print("没有处理任何结构，退出")
        return

    # 最终写入（确保所有数据都写入）
    out_df = pd.DataFrame(rows)
    out_csv = os.path.join(args.output_dir, f"rosetta_static_{args.batch_idx}.csv")
    out_df.to_csv(out_csv, index=False)
    print(f"✅ 已写入 {out_csv}，共 {len(rows)} 条")

    # 若指定 dump_top_n：仅保留 interface_score 前 N 的 relax_* 文件，删除其余
    if args.dump_top_n > 0 and "interface_score" in out_df.columns and "pdb_path" in out_df.columns:
        valid = out_df.dropna(subset=["interface_score"])
        if not valid.empty:
            top = valid.sort_values("interface_score", ascending=True).head(args.dump_top_n)
            keep_basenames = {"relax_" + os.path.basename(str(p)) for p in top["pdb_path"]}
            removed = 0
            for f in glob.glob(os.path.join(args.output_dir, "relax_*")):
                if os.path.isfile(f) and os.path.basename(f) not in keep_basenames:
                    try:
                        os.remove(f)
                        removed += 1
                    except OSError as e:
                        print(f"警告: 删除 {f} 失败: {e}", file=sys.stderr)
            print(f"✅ 已保留 interface_score 前 {args.dump_top_n} 的 Relax 结构，删除 {removed} 个非前 N 文件")
        else:
            print("⚠️  无有效 interface_score，未做 relax_* 清理")
    
    # 保存资源使用报告
    resource_report = resource_monitor.get_final_report()
    resource_report["total_structures"] = len(rows)
    resource_report["relax_enabled"] = args.relax
    resource_report["max_iter"] = args.max_iter if args.relax else 0
    resource_report["n_jobs"] = n_jobs
    resource_report["max_cpu_percent"] = args.max_cpu_percent
    
    resource_json = os.path.join(args.output_dir, "resource_usage.json")
    with open(resource_json, "w") as f:
        json.dump(resource_report, f, indent=2)
    
    print("\n" + "="*60)
    print("资源使用报告")
    print("="*60)
    print(f"总处理时间: {resource_report['elapsed_time_formatted']}")
    if resource_report.get("cpu_time_seconds"):
        cpu_time = resource_report["cpu_time_seconds"]["total"]
        cpu_hours = cpu_time / 3600
        print(f"CPU 时间: {cpu_time:.1f} 秒 ({cpu_hours:.2f} CPU-小时)")
        print(f"CPU 利用率: {resource_report['cpu_utilization_percent']:.1f}%")
    print(f"峰值内存: {resource_report['peak_memory_mb']:.1f} MB ({resource_report['peak_memory_mb']/1024:.2f} GB)")
    print(f"内存增长: {resource_report['memory_increase_mb']:.1f} MB")
    if len(rows) > 0:
        avg_time = resource_report["elapsed_time_seconds"] / len(rows)
        print(f"平均每个结构: {avg_time:.1f} 秒")
    print(f"资源报告已保存到: {resource_json}")
    print("="*60)


if __name__ == "__main__":
    main()
