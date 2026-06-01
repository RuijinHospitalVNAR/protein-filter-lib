#!/usr/bin/env python3
"""
Part 3: MD 计算（MM/PBSA、RMSD 变化）

对接 protein_filter_lib Part 2 输出，对候选结构运行 MD + MM/PBSA，
输出结合自由能与 RMSD 统计，用于最终筛选。

- 输入：Part 2 的 rosetta_static_*.csv，或含 PDB/CIF 的目录
- 链约定：--target_chain（默认 A，抗原）、--binder_chain（默认 B，抗体）
- 后端：YZC_MD_SCRIPT/run_part3_md_single.sh（GROMACS + gmx_MMPBSA）

依赖：GROMACS, gmx_MMPBSA, pdb2pqr, obabel（见 docs/PART3_MD.md）
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from protein_filter.utils.chain_detection import auto_detect_chains, generate_auto_config
    from protein_filter.utils.topology_check import check_prmtop_pdb_consistency
    HAS_NEW_MODULES = True
except ImportError:
    HAS_NEW_MODULES = False


def _cif_to_pdb(cif_path: str, out_dir: str) -> str:
    """CIF → PDB，保存到 out_dir，返回 PDB 路径。若文件实为 PDB 内容（如 PyRosetta relax 写出），则直接复制。"""
    os.makedirs(out_dir, exist_ok=True)
    base = Path(cif_path).stem.replace(".mmcif", "")
    pdb_path = os.path.join(out_dir, f"{base}.pdb")
    if os.path.exists(pdb_path) and os.path.getsize(pdb_path) > 1000:
        return pdb_path
    if os.path.exists(pdb_path):
        os.remove(pdb_path)

    # 若扩展名为 .cif 但内容实为 PDB（如 PyRosetta dump_pdb 写出），直接复制
    with open(cif_path, "rb") as f:
        first = f.read(64).decode("utf-8", errors="ignore").strip()
    if first.startswith("HEADER") or first.startswith("ATOM") or first.startswith("REMARK") or first.startswith("CRYST1"):
        shutil.copy2(cif_path, pdb_path)
        return pdb_path

    # 优先使用 obabel（标准 mmCIF）
    try:
        subprocess.run(
            ["obabel", "-icif", cif_path, "-opdb", "-O", pdb_path],
            capture_output=True,
            text=True,
            check=True,
        )
        if os.path.exists(pdb_path) and os.path.getsize(pdb_path) > 0:
            return pdb_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Fallback 到 BioPython（标准 mmCIF，需以 data_ 开头）
    try:
        from Bio.PDB import MMCIFParser, PDBIO

        parser = MMCIFParser(QUIET=True)
        struc = parser.get_structure("s", cif_path)
        io = PDBIO()
        io.set_structure(struc)
        io.save(pdb_path)
        return pdb_path
    except Exception as e:
        raise RuntimeError(f"CIF→PDB 失败 {cif_path}: {e}") from e


def _check_structure_status(structure_dir: Path) -> str | None:
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


def _create_status_file(structure_dir: Path, status: str, error: str = "") -> None:
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
            "mmpbsa_results": str(structure_dir / "FINAL_RESULTS_MMGBSA_BINDING.dat"),
            "rmsd": str(structure_dir / "rmsd_bb.dat"),
        }
    
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(status_data, f, indent=2, ensure_ascii=False)


def _progress_level(structure_dir: Path) -> int:
    """返回结构目录的进度等级：0=无/空，1=EM_steep，2=EM_cg，3=NPT，4=Production，5=FINAL。"""
    if not structure_dir.exists() or not structure_dir.is_dir():
        return 0
    if (structure_dir / "FINAL_RESULTS_MMGBSA_BINDING.dat").exists():
        return 5
    if (structure_dir / "Production.xtc").exists() or (structure_dir / "Production.cpt").exists():
        return 4
    if (structure_dir / "NPT.gro").exists():
        return 3
    if (structure_dir / "EM_cg.gro").exists():
        return 2
    if (structure_dir / "EM_steep.gro").exists():
        return 1
    return 0


def _find_best_copies(
    output_base: Path, top30_names: list[str], n_gpu: int
) -> dict[str, tuple[int, Path]]:
    """跨 gpu0..gpu(n_gpu-1) 检索每个前30 结构进度最优的一份，返回 name -> (best_gpu_id, best_path)。"""
    result: dict[str, tuple[int, Path]] = {}
    level_names = ("无", "EM_steep", "EM_cg", "NPT", "Production", "FINAL")
    for name in top30_names:
        best_level = -1
        best_gpu_id = -1
        best_path: Path | None = None
        for gpu_id in range(n_gpu):
            subdir = output_base / f"gpu{gpu_id}" / name
            level = _progress_level(subdir)
            if level > best_level:
                best_level = level
                best_gpu_id = gpu_id
                best_path = subdir
        if best_path is not None and best_level >= 0:
            result[name] = (best_gpu_id, best_path)
    return result


def _migrate_to_owner(
    output_base: Path, top30_names: list[str], n_gpu: int, dry_run: bool = False
) -> None:
    """将前30 结构迁移到应属 GPU 目录：保留完成度最高的一份在 owner 目录，删除其余副本。"""
    level_names = ("无", "EM_steep", "EM_cg", "NPT", "Production", "FINAL")
    for idx, name in enumerate(top30_names):
        owner_gpu = idx % n_gpu
        target_dir = output_base / f"gpu{owner_gpu}" / name
        copies: list[tuple[int, Path, int]] = []
        for g in range(n_gpu):
            p = output_base / f"gpu{g}" / name
            if p.exists() and p.is_dir():
                level = _progress_level(p)
                copies.append((g, p, level))
        if not copies:
            continue
        # 选完成度最高的；同等级时优先已在 owner 的
        best = max(copies, key=lambda x: (x[2], 1 if x[0] == owner_gpu else 0))
        best_gpu, best_path, best_level = best
        level_str = level_names[best_level] if 0 <= best_level < len(level_names) else str(best_level)
        if best_path == target_dir:
            # 最优已在应属目录，只删其它副本
            to_remove = [p for (g, p, _) in copies if p != target_dir]
            if to_remove:
                print(f"[migrate] {name} 已在 gpu{owner_gpu} ({level_str})，删除 {len(to_remove)} 个副本")
                for p in to_remove:
                    if dry_run:
                        print(f"  [dry-run] 将删除 {p}")
                    else:
                        shutil.rmtree(p, ignore_errors=True)
                        print(f"  已删除 {p}")
        else:
            # 最优在其它 GPU，迁到 owner 后删其它（含原最优所在目录）
            if dry_run:
                print(f"[dry-run] {name}: 将把 gpu{best_gpu} ({level_str}) 迁到 gpu{owner_gpu}，并删除其它副本")
                continue
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            shutil.copytree(best_path, target_dir)
            print(f"[migrate] {name}: 已从 gpu{best_gpu} ({level_str}) 复制到 gpu{owner_gpu}")
            for (g, p, _) in copies:
                if p != target_dir:
                    shutil.rmtree(p, ignore_errors=True)
                    print(f"  已删除 {p}")


def _infer_mmpbsa_masks(pdb_path: str, target_chain: str, binder_chain: str) -> tuple[str, str] | None:
    """根据输入 PDB 的链顺序推断 MMPBSA 的 receptor/ligand mask。
    假设 tleap 重新编号后，残基按 PDB 中的链出现顺序连续排列。
    """
    chains: dict[str, set[int]] = {}
    first_chain: str | None = None
    try:
        with open(pdb_path, "r", errors="ignore") as f:
            for line in f:
                if not (line.startswith("ATOM") or line.startswith("HETATM")):
                    continue
                resname = line[17:20].strip()
                if resname in {"WAT", "HOH", "Na+", "Na", "K+", "K", "Cl-", "Cl"}:
                    continue
                chain = line[21].strip() or "_"
                try:
                    resseq = int(line[22:26])
                except ValueError:
                    continue
                if chain not in chains:
                    chains[chain] = set()
                chains[chain].add(resseq)
                if first_chain is None:
                    first_chain = chain
    except Exception:
        return None

    if target_chain not in chains or binder_chain not in chains:
        return None

    n_target = len(chains[target_chain])
    n_binder = len(chains[binder_chain])
    n_total = n_target + n_binder

    if first_chain == target_chain:
        return f":1-{n_target}", f":{n_target + 1}-{n_total}"
    elif first_chain == binder_chain:
        return f":{n_binder + 1}-{n_total}", f":1-{n_binder}"
    else:
        # 首链既不是 target 也不是 binder，可能有第三条链，不做推断
        return None


def _run_single(
    structure_path: str,
    output_subdir: str,
    target_chain: str,
    binder_chain: str,
    production_ns: int,
    npt_ns: int,
    tmp: float,
    ph: float,
    conc: float,
    gpu_id: int,
    interval: int,
    ntomp: int,
    forcefield: str = "ff19SB",
    buffer: str = "8.0",
    skip_if_complete: bool = False,
    resume_md: bool = False,
    pinoffset: int | None = None,
) -> dict:
    """对单结构运行 Part 3 MD + MM/PBSA，返回汇总行。"""
    os.makedirs(output_subdir, exist_ok=True)
    out = Path(output_subdir).resolve()
    s = Path(structure_path).resolve()
    
    # Resume 检查
    if skip_if_complete:
        status = _check_structure_status(out)
        if status == "success":
            print(f"  跳过已完成结构: {s.name}")
            # 读取已有结果
            summary_csv = out / "mmgbsa_summary.csv"
            if summary_csv.is_file():
                with open(summary_csv, newline="", encoding="utf-8") as f:
                    r = csv.DictReader(f)
                    for rr in r:
                        return {
                            "pdb_name": s.stem.replace(".mmcif", ""),
                            "structure_path": str(s),
                            "target_chain": target_chain,
                            "binder_chain": binder_chain,
                            "mmgbsa_dG_kcal_mol": rr.get("mmgbsa_dG_kcal_mol", ""),
                            "rmsd_mean_nm": rr.get("rmsd_mean_nm", ""),
                            "rmsd_max_nm": rr.get("rmsd_max_nm", ""),
                            "error": "",
                        }
            # 如果没有 summary，返回空结果
            return {
                "pdb_name": s.stem.replace(".mmcif", ""),
                "structure_path": str(s),
                "target_chain": target_chain,
                "binder_chain": binder_chain,
                "mmgbsa_dG_kcal_mol": "",
                "rmsd_mean_nm": "",
                "rmsd_max_nm": "",
                "error": "",
            }
    
    # 标记为运行中
    _create_status_file(out, "running")

    # CIF → PDB 写入 output_subdir，供 shell 使用
    if str(s).lower().endswith(".cif") or str(s).lower().endswith(".mmcif"):
        pdb_for_md = _cif_to_pdb(str(s), str(out))
    else:
        pdb_for_md = str(s)

    AMBER_SCRIPT = Path(__file__).resolve().parent.parent.parent / "AMBER" / "run_single.sh"
    if not AMBER_SCRIPT.is_file():
        print(f"[Error] AMBER脚本未找到: {AMBER_SCRIPT}")
        return {
            "pdb_name": Path(structure_path).stem.replace(".mmcif", ""),
            "structure_path": structure_path,
            "target_chain": target_chain,
            "binder_chain": binder_chain,
            "mmgbsa_dG_kcal_mol": "Error: AMBER script not found",
            "rmsd_mean_nm": "",
            "rmsd_max_nm": "",
        }

    cmd = [
        "bash",
        str(AMBER_SCRIPT),
        "--structure", pdb_for_md,
        "--output_dir", str(out),
        "--gpu_id", str(gpu_id),
        "--production_ns", str(production_ns),
        "--npt_ns", str(npt_ns),
        "--forcefield", forcefield,
        "--buffer", buffer,
        "--interval", str(interval),
    ]

    # 推断 MMPBSA mask（基于原始输入 PDB）
    masks = _infer_mmpbsa_masks(pdb_for_md, target_chain, binder_chain)
    if masks:
        rec_mask, lig_mask = masks
        cmd.extend(["--receptor_mask", rec_mask, "--ligand_mask", lig_mask])
        print(f"  [MMPBSA mask] receptor={rec_mask}, ligand={lig_mask}")

    try:
        subprocess.run(cmd, check=True, cwd=str(out))
        _create_status_file(out, "success")
    except subprocess.CalledProcessError as e:
        _create_status_file(out, "failed", str(e))
        raise

    row = {
        "pdb_name": s.stem.replace(".mmcif", ""),
        "structure_path": str(s),
        "target_chain": target_chain,
        "binder_chain": binder_chain,
        "mmgbsa_dG_kcal_mol": "",
        "rmsd_mean_nm": "",
        "rmsd_max_nm": "",
        "error": "",
    }

    summary_csv = out / "mmgbsa_summary.csv"
    if summary_csv.is_file():
        with open(summary_csv, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for rr in r:
                row["mmgbsa_dG_kcal_mol"] = rr.get("mmgbsa_dG_kcal_mol", "")
                row["rmsd_mean_nm"] = rr.get("rmsd_mean_nm", "")
                row["rmsd_max_nm"] = rr.get("rmsd_max_nm", "")
                row["error"] = rr.get("error", "")
                break

    return row


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Part 3 MD：MM/PBSA、RMSD，对接 Part 2 候选"
    )
    ap.add_argument("--input_csv", type=str, default="", help="Part 2 CSV（含 pdb_path / pdb_name）")
    ap.add_argument("--input_dir", type=str, default="", help="含 PDB/CIF 的目录（与 --input_csv 二选一）")
    ap.add_argument("--output_dir", type=str, required=True, help="输出目录")
    ap.add_argument("--reference", type=str, default="", help="参考结构 PDB（可选，用于 RMSD）")
    ap.add_argument("--target_chain", type=str, default="A", help="靶标链（抗原）")
    ap.add_argument("--binder_chain", type=str, default="B", help="结合子链（抗体）")
    ap.add_argument("--top_n", type=int, default=0, help="仅处理 interface_score 前 N 个（0=全部）")
    ap.add_argument("--production_ns", type=int, default=10, help="生产模拟 ns")
    ap.add_argument("--npt_ns", type=int, default=1, help="NPT 平衡 ns")
    ap.add_argument("--tmp", type=float, default=298.15, help="温度 K")
    ap.add_argument("--ph", type=float, default=7.4, help="pH")
    ap.add_argument("--conc", type=float, default=0.154, help="离子浓度 M")
    ap.add_argument("--gpu_id", type=int, default=0, help="GPU 编号")
    ap.add_argument("--interval", type=int, default=5, help="MM/PBSA 取帧间隔")
    ap.add_argument("--ntomp", type=int, default=12, help="OpenMP 线程数")
    ap.add_argument("--forcefield", type=str, default="ff19SB", help="力场名称（默认 ff19SB，支持 ff19SB/ff14SB/amber99sb）")
    ap.add_argument("--n_gpu", type=int, default=1, help="总GPU数（用于自动分配结构，默认1）")
    ap.add_argument("--resume", action="store_true", help="跳过已完成的结构（基于 status.json）")
    ap.add_argument("--rerun-failed", action="store_true", help="只重跑失败的结构")
    ap.add_argument(
        "--scan-existing",
        action="store_true",
        help="仅处理 output_dir 内已存在且属前 N 的未完成结构（就地续跑，不按 GPU 重分配）",
    )
    ap.add_argument(
        "--report-best-copies",
        action="store_true",
        help="跨 gpu0..gpu(n_gpu-1) 检索前 N 结构的最优进度并输出报告（需 --input_csv --top_n --output_dir 指向含 gpuX 的基目录）",
    )
    ap.add_argument(
        "--migrate-to-owner",
        action="store_true",
        help="将前 N 结构迁移到应属 GPU 目录：保留完成度最高的一份在 owner 目录，删除其余副本（需 --input_csv --top_n --output_dir 基目录 --n_gpu）",
    )
    ap.add_argument(
        "--migrate-dry-run",
        action="store_true",
        help="与 --migrate-to-owner 同用：仅打印将要执行的操作，不实际迁移/删除",
    )
    args = ap.parse_args()

    # GPU 可见性检查与日志
    cuda_visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if cuda_visible:
        visible_list = [x.strip() for x in cuda_visible.split(",") if x.strip()]
        print(
            f"[GPU] 检测到 CUDA_VISIBLE_DEVICES={cuda_visible} "
            f"(可见 GPU 数={len(visible_list)})"
        )
    else:
        print("[GPU] 未设置 CUDA_VISIBLE_DEVICES，默认可见所有物理 GPU")

    # GROMACS MD script check disabled - using AMBER instead
    # if not PART3_MD_SCRIPT.is_file():
    #     print(f"警告：未找到 Part 3 MD 脚本 {PART3_MD_SCRIPT}")

    # 逻辑 GPU 编号（用于结构分片），与物理 GPU 可能不同
    logical_gpu_id = args.gpu_id

    # 物理 GPU 编号（传递给底层 MD 脚本）
    # - 如果设置了 CUDA_VISIBLE_DEVICES，则当前进程只能看到一个或多个“重映射”的 GPU，
    #   此时物理 GPU 编号统一使用 0
    # - 如果未设置，则继续使用命令行传入的 gpu_id
    if cuda_visible:
        physical_gpu_id = 0
        # 简单一致性检查：当仅暴露一个 GPU，但逻辑 gpu_id 超过 0 时给出提示
        try:
            visible_count = len([x for x in cuda_visible.split(",") if x.strip()])
        except Exception:
            visible_count = 1
        if visible_count == 1 and logical_gpu_id != 0:
            print(
                f"[GPU][警告] CUDA_VISIBLE_DEVICES 仅暴露 1 个 GPU，但收到 "
                f"--gpu_id={logical_gpu_id}；将物理 GPU 统一映射为 0 继续运行。"
            )
    else:
        physical_gpu_id = logical_gpu_id

    structures: list[tuple[str, str]] = []  # (path, name)

    if args.input_csv:
        import pandas as pd

        df = pd.read_csv(args.input_csv)
        if "pdb_path" not in df.columns:
            print("错误：CSV 需含 pdb_path 列", file=sys.stderr)
            sys.exit(1)
        if "interface_score" in df.columns and args.top_n > 0:
            df = df.sort_values("interface_score").head(args.top_n)
        for _, r in df.iterrows():
            p = r["pdb_path"]
            if not os.path.isabs(p):
                base = Path(args.input_csv).resolve().parent
                p = str((base / p).resolve())
            if os.path.isfile(p):
                name = r.get("pdb_name", Path(p).stem)
                structures.append((p, name))

    # Auto-detect chains if enabled
    if HAS_NEW_MODULES and structures and (args.target_chain == "A" and args.binder_chain == "B"):
        try:
            pdb_path = structures[0][0]
            auto_config = generate_auto_config(pdb_path)
            args.target_chain = auto_config["chains"]["target_chain"]
            args.binder_chain = auto_config["chains"]["binder_chain"]
            print(f"[Auto-detect] 靶标链: {args.target_chain}, 结合子链: {args.binder_chain}")
        except Exception as e:
            print(f"[Auto-detect] 警告: {e}")

    out_root = Path(args.output_dir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    # --report-best-copies：跨 GPU 检索前 N 结构的最优进度并输出报告后退出
    if args.report_best_copies:
        if not args.input_csv or args.top_n <= 0 or not structures:
            print(
                "错误：--report-best-copies 需同时指定 --input_csv、--top_n > 0，且 --output_dir 为含 gpu0..gpuN 的基目录",
                file=sys.stderr,
            )
            sys.exit(1)
        top30_names = [name for _, name in structures]
        best = _find_best_copies(out_root, top30_names, args.n_gpu)
        level_names = ("无", "EM_steep", "EM_cg", "NPT", "Production", "FINAL")
        lines = [
            "# Part3 前 N 结构跨 GPU 最优进度（每个结构取进度最高的那一份）",
            "# 格式: 结构名 | 最优 gpu_id | 进度等级 | 路径",
            "",
        ]
        for name in top30_names:
            if name in best:
                gpu_id, path = best[name]
                level = _progress_level(path)
                level_str = level_names[level] if 0 <= level < len(level_names) else str(level)
                lines.append(f"{name}\tgpu{gpu_id}\t{level_str}\t{path}")
                print(f"[report-best-copies] {name} -> gpu{gpu_id} ({level_str}) {path}")
            else:
                lines.append(f"{name}\t(无)\t无\t")
                print(f"[report-best-copies] {name} -> (无)")
        report_path = out_root / "part3_best_copies.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"[report-best-copies] 报告已写入 {report_path}")
        sys.exit(0)

    # --migrate-to-owner：将前 N 结构迁移到应属 GPU 目录，保留完成度最高的一份，删除其余副本
    if args.migrate_to_owner:
        if not args.input_csv or args.top_n <= 0 or not structures:
            print(
                "错误：--migrate-to-owner 需同时指定 --input_csv、--top_n > 0，且 --output_dir 为含 gpu0..gpuN 的基目录",
                file=sys.stderr,
            )
            sys.exit(1)
        top30_names = [name for _, name in structures]
        _migrate_to_owner(out_root, top30_names, args.n_gpu, dry_run=args.migrate_dry_run)
        print("[migrate-to-owner] 迁移完成，可运行补全任务：./run_part3_unified.sh")
        sys.exit(0)

    # --scan-existing：仅处理本 GPU 应属（index%n_gpu）且本 output_dir 内已存在的前 N 未完成结构（就地续跑）
    if args.scan_existing:
        if not args.input_csv or args.top_n <= 0:
            print("错误：--scan-existing 需同时指定 --input_csv 与 --top_n > 0", file=sys.stderr)
            sys.exit(1)
        top30_full = list(structures)
        structures = []
        for idx, (path, name) in enumerate(top30_full):
            if idx % args.n_gpu != logical_gpu_id:
                continue  # 该结构不属于本 GPU，不处理
            subdir = out_root / name
            if subdir.exists() and subdir.is_dir():
                if (subdir / "FINAL_RESULTS_MMGBSA_BINDING.dat").exists():
                    print(f"[scan-existing] 跳过已完成: {name}")
                    continue
                structures.append((path, name))
        print(
            f"[scan-existing] 本 GPU 应属且本目录未完成共 {len(structures)} 个，将就地续跑"
        )
        if not structures:
            print("本目录无待续跑结构，退出。")
            sys.exit(0)

    # Note: GPU分配仅在n_gpu>1时需要，正常流程直接跳过
    if args.n_gpu > 1:
        total = len(structures)
        if total > 0:
            structures_per_gpu = total // args.n_gpu
            remainder = total % args.n_gpu
            start_idx = logical_gpu_id * structures_per_gpu + min(
                logical_gpu_id, remainder
            )
            end_idx = start_idx + structures_per_gpu + (
                1 if logical_gpu_id < remainder else 0
            )
            structures = structures[start_idx:end_idx]
            print(
                f"[GPU {logical_gpu_id}/{args.n_gpu}] 分配结构 "
                f"{start_idx+1}-{end_idx} (共 {len(structures)} 个)"
            )

    # Normal processing when input_csv is provided: structures already loaded
    # Skip input_dir processing if not specified
    if not args.input_dir:
        # Check if we have structures from CSV - that's the normal flow
        if structures:
            pass  # OK, continue to processing
        else:
            print("请提供 --input_csv 或 --input_dir", file=sys.stderr)
            sys.exit(1)
    elif args.input_dir:
        base = Path(args.input_dir).resolve()
        for ext in ("*.pdb", "*.cif", "*.mmcif"):
            for f in sorted(base.rglob(ext)):
                if "seed-" in str(f):
                    continue
                rel = f.relative_to(base)
                subdir_name = str(rel).replace("/", "__").rsplit(".", 1)[0]
                structures.append((str(f.resolve()), subdir_name))
        if not structures:
            print("错误：input_dir 下未找到 PDB/CIF", file=sys.stderr)
            sys.exit(1)

    rows: list[dict] = []
    seen: set[str] = set()
    skip_if_complete = args.resume or args.rerun_failed
    
    for i, (path, name) in enumerate(structures, 1):
        if path in seen:
            continue
        seen.add(path)
        subdir = out_root / name
        
        # Resume/Rerun 逻辑
        if skip_if_complete:
            status = _check_structure_status(subdir)
            if args.rerun_failed:
                # 只重跑失败的结构
                # 检查：status="failed" 或 status="running"（卡住）或 无status但有错误结果
                is_failed = False
                has_success = (subdir / "FINAL_RESULTS_MMGBSA_BINDING.dat").exists() and \
                              list(subdir.glob("md_*.nc"))
                
                if status == "failed":
                    is_failed = True
                elif status == "running":
                    # 标记为 running 但没有成功结果，视为失败（卡住）
                    if not has_success:
                        is_failed = True
                elif status is None:
                    # 没有 status.json，检查是否有成功的结果文件
                    if not has_success:
                        # 没有成功结果，视为失败，需要重跑
                        is_failed = True
                
                if not is_failed:
                    print(f"[{i}/{len(structures)}] 跳过（非失败）: {name}")
                    # 读取已有结果（如果有）
                    summary_csv = subdir / "mmgbsa_summary.csv"
                    if summary_csv.is_file():
                        with open(summary_csv, newline="", encoding="utf-8") as f:
                            r = csv.DictReader(f)
                            for rr in r:
                                rows.append({
                                    "pdb_name": name,
                                    "structure_path": path,
                                    "target_chain": args.target_chain,
                                    "binder_chain": args.binder_chain,
                                    "mmgbsa_dG_kcal_mol": rr.get("mmgbsa_dG_kcal_mol", ""),
                                    "rmsd_mean_nm": rr.get("rmsd_mean_nm", ""),
                                    "rmsd_max_nm": rr.get("rmsd_max_nm", ""),
                                    "error": "",
                                })
                                break
                    continue
                else:
                    print(f"[{i}/{len(structures)}] 重跑失败结构: {name}")
            elif args.resume:
                # 跳过已完成的结构
                if status == "success":
                    print(f"[{i}/{len(structures)}] 跳过已完成: {name}")
                    # 读取已有结果
                    summary_csv = subdir / "mmgbsa_summary.csv"
                    if summary_csv.is_file():
                        with open(summary_csv, newline="", encoding="utf-8") as f:
                            r = csv.DictReader(f)
                            for rr in r:
                                rows.append({
                                    "pdb_name": name,
                                    "structure_path": path,
                                    "target_chain": args.target_chain,
                                    "binder_chain": args.binder_chain,
                                    "mmgbsa_dG_kcal_mol": rr.get("mmgbsa_dG_kcal_mol", ""),
                                    "rmsd_mean_nm": rr.get("rmsd_mean_nm", ""),
                                    "rmsd_max_nm": rr.get("rmsd_max_nm", ""),
                                    "error": "",
                                })
                                break
                    continue
        
        print(f"[{i}/{len(structures)}] Part 3 MD+PBSA: {name}")
        try:
            row = _run_single(
                structure_path=path,
                output_subdir=str(subdir),
                target_chain=args.target_chain,
                binder_chain=args.binder_chain,
                production_ns=args.production_ns,
                npt_ns=args.npt_ns,
                tmp=args.tmp,
                ph=args.ph,
                conc=args.conc,
                gpu_id=physical_gpu_id,
                interval=args.interval,
                ntomp=args.ntomp,
                forcefield=args.forcefield,
                buffer="8.0",
                resume_md=args.resume,
                skip_if_complete=False,  # 已在上面处理
                pinoffset=logical_gpu_id * args.ntomp,  # 多任务并行时分隔 CPU 核
            )
            rows.append(row)
        except subprocess.CalledProcessError as e:
            rows.append({
                "pdb_name": name,
                "structure_path": path,
                "target_chain": args.target_chain,
                "binder_chain": args.binder_chain,
                "mmgbsa_dG_kcal_mol": "",
                "rmsd_mean_nm": "",
                "rmsd_max_nm": "",
                "error": str(e),
            })
            print(f"  失败: {e}", file=sys.stderr)

    out_csv = out_root / "part3_results.csv"
    fieldnames = [
        "pdb_name",
        "structure_path",
        "target_chain",
        "binder_chain",
        "mmgbsa_dG_kcal_mol",
        "rmsd_mean_nm",
        "rmsd_max_nm",
        "error",
    ]
    if rows:
        if args.scan_existing and out_csv.exists():
            # 就地续跑模式：合并已有 part3_results，避免覆盖
            existing_by_name = {}
            with open(out_csv, newline="", encoding="utf-8") as f:
                r = csv.DictReader(f)
                for rr in r:
                    existing_by_name[rr.get("pdb_name", "")] = rr
            for row in rows:
                existing_by_name[row["pdb_name"]] = row
            rows = list(existing_by_name.values())
            print(f"[scan-existing] 已与已有 part3_results 合并，共 {len(rows)} 条")
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        print(f"Part 3 汇总已写入: {out_csv}")
    else:
        print("未处理任何结构。", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
