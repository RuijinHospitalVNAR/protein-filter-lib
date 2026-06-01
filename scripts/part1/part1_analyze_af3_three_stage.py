#!/usr/bin/env python3
"""
三级AF3分析流程：AF3评分筛选 → Foldseek粗聚类 → 簇内H-A接触精细分析

功能：
1. Stage 1: 基于AF3评分（pLDDT、clashes、pDockQ等）筛选高置信度结构
2. Stage 2: 使用Foldseek对筛选后的结构做整体结构聚类（粗分组）
3. Stage 3: 在每个Foldseek簇内基于H-A接触集做精细聚类（找出不同结合模式）

优势：
- 大幅减少需要处理的结构数量（评分筛选）
- 显著降低距离矩阵计算量（Foldseek粗聚后按簇处理）
- 保持基于接触模式的生物学意义（精细聚类）
"""

import sys
import os
from pathlib import Path
import logging
from datetime import datetime
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
import tempfile
import subprocess
import pickle
import time
import psutil
from contextlib import contextmanager

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入所需的模块
from protein_filter.utils.af3_utils import extract_metrics_from_af3_output, auto_extract_af3_metrics
from protein_filter.utils.pdb_utils import calculate_clash_score
from protein_filter.utils.pdockq_utils import get_pdockq, pDockQ2
from protein_filter.clustering.backend.analyzer import AF3ClusterAnalyzer


@contextmanager
def _performance_monitor(process_name: str):
    """
    性能监控上下文管理器
    
    记录：
    - CPU时间（用户时间 + 系统时间）
    - 实时内存使用（RSS）
    - 虚拟内存使用（VMS）
    - 运行时间（wall clock time）
    
    返回：
    - dict: 性能指标字典
    """
    process = psutil.Process()
    
    # 初始状态
    start_time = time.time()
    start_cpu_times = process.cpu_times()
    start_memory = process.memory_info()
    
    perf_data = {
        'process_name': process_name,
        'start_time': datetime.now().isoformat(),
        'start_cpu_times': {
            'user': start_cpu_times.user,
            'system': start_cpu_times.system,
        },
        'start_memory': {
            'rss_mb': start_memory.rss / 1024 / 1024,  # MB
            'vms_mb': start_memory.vms / 1024 / 1024,  # MB
        }
    }
    
    try:
        yield perf_data
    finally:
        # 结束状态
        end_time = time.time()
        end_cpu_times = process.cpu_times()
        end_memory = process.memory_info()
        
        # 计算差异
        wall_time = end_time - start_time
        cpu_user = end_cpu_times.user - start_cpu_times.user
        cpu_system = end_cpu_times.system - start_cpu_times.system
        cpu_total = cpu_user + cpu_system
        
        max_memory = process.memory_info()
        peak_rss_mb = max_memory.rss / 1024 / 1024
        peak_vms_mb = max_memory.vms / 1024 / 1024
        
        perf_data.update({
            'end_time': datetime.now().isoformat(),
            'wall_clock_time_seconds': wall_time,
            'wall_clock_time_formatted': f"{int(wall_time // 3600)}h {int((wall_time % 3600) // 60)}m {wall_time % 60:.1f}s",
            'cpu_time_seconds': {
                'user': cpu_user,
                'system': cpu_system,
                'total': cpu_total,
            },
            'cpu_utilization_percent': (cpu_total / wall_time * 100) if wall_time > 0 else 0,
            'memory_peak_mb': {
                'rss': peak_rss_mb,
                'vms': peak_vms_mb,
            },
            'memory_increase_mb': {
                'rss': peak_rss_mb - perf_data['start_memory']['rss_mb'],
                'vms': peak_vms_mb - perf_data['start_memory']['vms_mb'],
            }
        })


def _write_partial_performance(
    output_dir: Path,
    overall_start_time: float,
    overall_start_memory,
    stage_performances: dict,
    pipeline_status: str,
    error_msg: Optional[str] = None,
):
    """失败时写入部分性能指标，便于对比与排查。"""
    import psutil
    end_time = time.time()
    end_memory = psutil.Process().memory_info()
    wall = end_time - overall_start_time
    payload = {
        "pipeline_status": pipeline_status,
        "error_message": error_msg,
        "total_wall_clock_time_seconds": wall,
        "total_wall_clock_time_formatted": f"{int(wall // 3600)}h {int((wall % 3600) // 60)}m {wall % 60:.1f}s",
        "start_time": datetime.fromtimestamp(overall_start_time).isoformat(),
        "end_time": datetime.fromtimestamp(end_time).isoformat(),
        "peak_memory_mb": {
            "rss": end_memory.rss / 1024 / 1024,
            "vms": end_memory.vms / 1024 / 1024,
        },
        "memory_increase_mb": {
            "rss": (end_memory.rss - overall_start_memory.rss) / 1024 / 1024,
            "vms": (end_memory.vms - overall_start_memory.vms) / 1024 / 1024,
        },
        "stage_performances": stage_performances,
    }
    path = output_dir / "performance_metrics.json"
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    logger.info(f"已保存部分性能数据至: {path} (pipeline_status={pipeline_status})")


def _to_json_safe(obj):
    """递归将 numpy 类型转为 Python 原生类型，便于 json.dump 序列化。"""
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_safe(x) for x in obj]
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return _to_json_safe(obj.tolist())
    return obj


def _extract_metrics_worker(cif_file, pdb_dir):
    """
    工作函数：提取单个结构的评分（模块级别，可被pickle）
    
    参数：
    - cif_file: CIF文件路径
    - pdb_dir: 基础目录（用于计算相对路径）
    
    返回：
    - (rel_path, metrics) 元组，如果失败返回 (None, None)
    """
    try:
        from pathlib import Path
        metrics = {}
        cif_path = Path(cif_file)
        
        # 从CIF文件的B-factor提取pLDDT
        from protein_filter.utils.pdockq_utils import pdb_2_coords, _is_cif_file
        is_cif = _is_cif_file(str(cif_path))
        try:
            chain_coords, plddt_array = pdb_2_coords(str(cif_path), is_cif=is_cif)
            if len(plddt_array) > 0:
                plddt_normalized = plddt_array / 100.0
                metrics['plddt'] = float(np.mean(plddt_normalized))
        except Exception as e:
            logger.debug(f"提取pLDDT失败 {cif_path}: {e}")
            metrics['plddt'] = 0.0
        
        # 计算clashes
        try:
            clashes = calculate_clash_score(str(cif_path), threshold=2.4, only_ca=False)
            metrics['clashes'] = clashes
        except Exception as e:
            logger.debug(f"计算clashes失败 {cif_path}: {e}")
            metrics['clashes'] = 999
        
        # 查找JSON文件提取iPTM等（以及后续可能用于IPSAE计算的PAE矩阵）
        # AF3输出可能在子目录中（如seed-42_sample-0/）
        # 
        # 重要：ipSAE 计算需要完整的 PAE 矩阵，存储在 `confidences.json` 或 `*_confidences.json` 中
        # 而 `summary_confidences.json` 只包含汇总统计（无 PAE 矩阵）
        # 因此查找顺序应为：confidences.json > *_confidences.json > *_data.json > summary_confidences.json
        
        json_for_metrics = []       # 用于提取 iptm/ptm 等基础指标
        json_for_ipsae = []         # 用于 ipSAE 计算（需要 PAE 矩阵）
        
        # 先检查同目录
        # 优先查找完整 confidences 文件（含 PAE 矩阵）
        json_for_ipsae.extend(list(cif_path.parent.glob("confidences.json")))
        json_for_ipsae.extend(list(cif_path.parent.glob("*_confidences.json")))
        json_for_ipsae.extend(list(cif_path.parent.glob("*_data.json")))
        json_for_ipsae.extend(list(cif_path.parent.glob("*_full_data*.json")))
        
        # summary 文件用于基础指标
        json_for_metrics.extend(list(cif_path.parent.glob("summary_confidences.json")))
        json_for_metrics.extend(list(cif_path.parent.glob("*_summary_confidences.json")))
        json_for_metrics.extend(list(cif_path.parent.glob("*_scores.json")))
        
        # 再检查父目录（对于 seed-*/model.cif 格式）
        parent_dir = cif_path.parent.parent
        if parent_dir.exists() and parent_dir != cif_path.parent:
            json_for_ipsae.extend(list(parent_dir.glob("*_confidences.json")))
            json_for_ipsae.extend(list(parent_dir.glob("*_data.json")))
            json_for_metrics.extend(list(parent_dir.glob("*_summary_confidences.json")))
        
        json_path_for_ipsae = None
        
        # 提取基础指标（从 summary 或完整文件）
        all_json_candidates = json_for_ipsae + json_for_metrics
        if all_json_candidates:
            try:
                # 优先使用 summary 文件提取基础指标（更快）
                metrics_json = json_for_metrics[0] if json_for_metrics else all_json_candidates[0]
                json_dir = metrics_json.parent
                json_metrics = extract_metrics_from_af3_output(str(json_dir))
                metrics.update(json_metrics)
            except Exception as e:
                logger.debug(f"解析JSON失败: {e}")
        
        # 为 ipSAE 计算选择包含 PAE 矩阵的完整 JSON 文件
        # 排除 summary 文件（不含 PAE 矩阵）
        if json_for_ipsae:
            # 优先使用同目录的 confidences.json
            for candidate in json_for_ipsae:
                if 'summary' not in candidate.name.lower():
                    json_path_for_ipsae = str(candidate)
                    break
        
        # 计算 ranking_confidence (0.8*ipTM + 0.2*pTM)
        # 标准公式：0.8*ipTM + 0.2*pTM
        if 'iptm' in metrics and 'ptm' in metrics:
            metrics['ranking_confidence'] = 0.8 * metrics['iptm'] + 0.2 * metrics['ptm']
        elif 'iptm' in metrics:
            # 如果没有pTM，使用ipTM作为近似值（但标记为不完整）
            metrics['ranking_confidence'] = metrics['iptm']
            metrics['ranking_confidence_incomplete'] = True  # 标记缺少pTM
        # 如果没有ipTM，不计算ranking_confidence（因为ipTM是主要组成部分）
        
        # 尝试提取 / 计算 ipSAE
        # 1) 先从现有 metrics 中查找（例如上游已计算并写入 JSON 的情况）
        if 'ipsae' not in metrics:
            for key in ['ipsae', 'ipSAE', 'ipsae_score']:
                if key in metrics:
                    metrics['ipsae'] = metrics[key]
                    break

        # 2) 如仍不存在且找到 AF3 JSON，则调用官方 ipsae.py 计算
        #    注意：这是逐结构调用，可能较耗时，但能保证 ipSAE 真正参与筛选
        #    
        #    重要发现：
        #    - ipSAE (d0res): 基于残基归一化，值通常较低（0.01-0.4），不适合筛选
        #    - ipSAE_d0chn: 基于链长度归一化，值在合理范围（0.4-1.0），更适合筛选
        #    使用默认 PAE=5.0, Dist=5.0（Dunbrack 推荐的标准阈值）
        if 'ipsae' not in metrics and json_path_for_ipsae is not None:
            try:
                from protein_filter.utils.ipsae_utils import calculate_ipsae_from_script
                ipsae_metrics = calculate_ipsae_from_script(
                    json_path=json_path_for_ipsae,
                    pdb_path=str(cif_path),
                    pae_cutoff=5.0,   # 使用默认阈值（Dunbrack 推荐）
                    dist_cutoff=5.0,  # 使用默认阈值
                )
                # 优先使用 ipSAE_d0chn（链长度归一化），因为值在合理范围（0.4-1.0）
                # 原始的 ipSAE (d0res) 值通常较低（0.01-0.4），不适合筛选
                if ipsae_metrics.get("ipsae_d0chn") is not None:
                    metrics["ipsae"] = float(ipsae_metrics["ipsae_d0chn"])
                    metrics["ipsae_metric_type"] = "d0chn"
                elif ipsae_metrics.get("ipsae") is not None:
                    metrics["ipsae"] = float(ipsae_metrics["ipsae"])
                    metrics["ipsae_metric_type"] = "d0res"
                    # 保留其他变体用于调试和分析
                    if "ipsae_d0chn" in ipsae_metrics:
                        metrics["ipsae_d0chn"] = float(ipsae_metrics["ipsae_d0chn"])
                    if "ipsae_d0dom" in ipsae_metrics:
                        metrics["ipsae_d0dom"] = float(ipsae_metrics["ipsae_d0dom"])
                    if "ipsae_pdockq" in ipsae_metrics:
                        metrics["ipsae_pdockq"] = float(ipsae_metrics["ipsae_pdockq"])
            except Exception as e:
                logger.debug(f"计算IPSAE失败 {cif_path}: {e}")
        
        # 计算pDockQ（需要链信息）
        try:
            pdockq = get_pdockq(str(cif_path))
            metrics['pdockq'] = pdockq
        except Exception as e:
            logger.debug(f"计算pDockQ失败 {cif_path}: {e}")
            metrics['pdockq'] = 0.0
        
        # 获取相对路径
        pdb_path = Path(pdb_dir)
        rel_path = cif_path.relative_to(pdb_path)
        
        return str(rel_path), metrics
    except Exception as e:
        logger.warning(f"处理文件失败 {cif_file}: {e}")
        return None, None


def stage1_af3_score_filtering(
    pdb_dir: Path,
    chainA: str,
    antigen_chains: List[str],
    plddt_threshold: float = 0.7,
    clashes_threshold: int = 5,
    pdockq_threshold: float = 0.2,
    iptm_threshold: float = 0.6,
    ranking_confidence_threshold: float = 0.7,
    ipsae_threshold: float = 0.6,
    n_jobs: int = 4
) -> Tuple[List[str], Dict[str, Dict], Dict, Dict]:
    """
    Stage 1: 基于AF3评分筛选高置信度结构
    
    参数：
    - pdb_dir: AF3输出目录（包含子目录，每个子目录一个结构）
    - chainA: 抗体链ID
    - antigen_chains: 抗原链ID列表
    - plddt_threshold: pLDDT阈值（>=，默认：0.7）
    - clashes_threshold: 碰撞阈值（<，默认：5）
    - pdockq_threshold: pDockQ阈值（>=，默认：0.2）
    - iptm_threshold: iPTM阈值（>=，默认：0.6）
    - ranking_confidence_threshold: ranking_confidence阈值（>=，默认：0.7）
        计算公式：0.8*ipTM + 0.2*pTM
    - ipsae_threshold: ipSAE阈值（>=，默认：0.6）。高 ipSAE 表示界面置信度高；
        >0.6 常用作可能结合，真实互作多接近 0.8（Dunbrack/Levitate）。若 ipSAE 不存在则跳过此筛选。
    - n_jobs: 并行进程数
    
    返回：
    - filtered_files: 通过筛选的文件列表（相对路径）
    - metrics_dict: 所有结构的评分字典 {file_name: {metric: value}}
    """
    logger.info("=" * 60)
    logger.info("Stage 1: AF3评分筛选")
    logger.info("=" * 60)
    
    # 性能监控
    with _performance_monitor("Stage 1: AF3评分筛选") as perf_data:
        # 查找所有CIF文件
        cif_files = sorted(list(pdb_dir.rglob("*.cif")))
        logger.info(f"找到 {len(cif_files)} 个CIF文件")
        
        if len(cif_files) == 0:
            logger.error("未找到任何CIF文件")
            return [], {}, {}, {}
        
        # 并行提取评分
        from multiprocessing import Pool
        import psutil
        
        max_workers = min(n_jobs if n_jobs > 0 else 4, 8)
        logger.info(f"使用 {max_workers} 个并行进程提取AF3评分...")
        
        # 使用 functools.partial 传递 pdb_dir 参数（因为 pdb_dir 需要传递给 worker）
        from functools import partial
        
        # 并行处理
        metrics_dict = {}
        worker_func = partial(_extract_metrics_worker, pdb_dir=pdb_dir)
        with Pool(processes=max_workers) as pool:
            results = pool.map(worker_func, cif_files)
        
        # 收集结果
        for rel_path, metrics in results:
            if rel_path and metrics:
                metrics_dict[rel_path] = metrics
        
        logger.info(f"成功提取 {len(metrics_dict)} 个结构的评分")
    
    # 应用筛选条件
    filtered_files = []
    filter_stats = {
        'total': len(metrics_dict),
        'failed_plddt': 0,
        'failed_clashes': 0,
        'failed_pdockq': 0,
        'failed_iptm': 0,
        'failed_ranking_confidence': 0,
        'failed_ipsae': 0,
        'passed': 0
    }
    
    for file_name, metrics in metrics_dict.items():
        # 检查所有阈值
        passed = True
        
        # pLDDT筛选
        if metrics.get('plddt', 0.0) < plddt_threshold:
            filter_stats['failed_plddt'] += 1
            passed = False
            continue
        
        # clashes筛选
        if metrics.get('clashes', 999) >= clashes_threshold:
            filter_stats['failed_clashes'] += 1
            passed = False
            continue
        
        # pDockQ筛选
        if metrics.get('pdockq', 0.0) < pdockq_threshold:
            filter_stats['failed_pdockq'] += 1
            passed = False
            continue
        
        # iPTM筛选
        if metrics.get('iptm', 0.0) < iptm_threshold:
            filter_stats['failed_iptm'] += 1
            passed = False
            continue
        
        # ranking_confidence筛选
        ranking_conf = metrics.get('ranking_confidence', None)
        if ranking_conf is not None and ranking_conf < ranking_confidence_threshold:
            filter_stats['failed_ranking_confidence'] += 1
            passed = False
            continue
        
        # ipSAE筛选（如果存在）。高 ipSAE = 高界面置信度，须 >= 阈值才通过
        ipsae = metrics.get('ipsae', None)
        if ipsae is not None and ipsae < ipsae_threshold:
            filter_stats['failed_ipsae'] += 1
            passed = False
            continue
        
        if passed:
            filtered_files.append(file_name)
            filter_stats['passed'] += 1
    
    # 计算通过率
    pass_rate = (filter_stats['passed'] / filter_stats['total'] * 100) if filter_stats['total'] > 0 else 0
    
    logger.info(f"筛选结果: {len(filtered_files)}/{len(metrics_dict)} 个结构通过筛选（通过率: {pass_rate:.2f}%）")
    logger.info(f"筛选条件:")
    logger.info(f"  - pLDDT >= {plddt_threshold}")
    logger.info(f"  - clashes < {clashes_threshold}")
    logger.info(f"  - pDockQ >= {pdockq_threshold}")
    logger.info(f"  - iPTM >= {iptm_threshold}")
    logger.info(f"  - ranking_confidence >= {ranking_confidence_threshold} (0.8*ipTM + 0.2*pTM)")
    logger.info(f"  - ipSAE >= {ipsae_threshold} (如果存在)")
    logger.info(f"\n筛选统计:")
    logger.info(f"  - 总结构数: {filter_stats['total']}")
    logger.info(f"  - 通过筛选: {filter_stats['passed']}")
    logger.info(f"  - 未通过原因分布:")
    logger.info(f"    * pLDDT不达标: {filter_stats['failed_plddt']}")
    logger.info(f"    * clashes过多: {filter_stats['failed_clashes']}")
    logger.info(f"    * pDockQ不足: {filter_stats['failed_pdockq']}")
    logger.info(f"    * iPTM不足: {filter_stats['failed_iptm']}")
    logger.info(f"    * ranking_confidence不足: {filter_stats['failed_ranking_confidence']}")
    logger.info(f"    * ipSAE不足: {filter_stats['failed_ipsae']}")
    
    # 计算指标分布统计（仅对通过的结构）
    if len(filtered_files) > 0:
        passed_metrics = [metrics_dict[f] for f in filtered_files]
        logger.info(f"\n通过结构的指标分布（均值±标准差）:")
        for metric_name in ['plddt', 'clashes', 'pdockq', 'iptm', 'ptm', 'ranking_confidence', 'ipsae']:
            values = [m.get(metric_name) for m in passed_metrics if m.get(metric_name) is not None]
            if len(values) > 0:
                mean_val = np.mean(values)
                std_val = np.std(values)
                logger.info(f"  - {metric_name}: {mean_val:.3f} ± {std_val:.3f} (n={len(values)})")
        
        # 记录性能指标到perf_data（已在context manager中自动更新）
        pass
    
    # 性能总结
    logger.info(f"\nStage 1 性能统计:")
    logger.info(f"  - 运行时间: {perf_data['wall_clock_time_formatted']}")
    logger.info(f"  - CPU利用率: {perf_data['cpu_utilization_percent']:.1f}%")
    logger.info(f"  - 峰值内存: {perf_data['memory_peak_mb']['rss']:.1f} MB (RSS)")
    
    return filtered_files, metrics_dict, filter_stats, perf_data


def stage2_foldseek_coarse_clustering(
    pdb_dir: Path,
    filtered_files: List[str],
    foldseek_path: str = '/mnt/share/public/foldseek/bin/foldseek',
    sensitivity: float = 7.5,
    coverage: float = 0.0,
    min_seq_id: float = 0.0,
    n_jobs: int = 8
) -> Tuple[Dict[int, List[str]], Dict]:
    """
    Stage 2: 使用Foldseek对筛选后的结构做整体结构聚类
    
    参数：
    - pdb_dir: 结构文件根目录
    - filtered_files: 通过筛选的文件列表（相对路径）
    - foldseek_path: Foldseek可执行文件路径
    - sensitivity: Foldseek敏感度（1-9，较低值更快）
    - coverage: 覆盖度阈值
    - min_seq_id: 最小序列ID（用于聚类）
    - n_jobs: Foldseek使用的线程数
    
    返回：
    - coarse_clusters: {cluster_id: [file_name, ...]} 粗簇字典
    """
    logger.info("=" * 60)
    logger.info("Stage 2: Foldseek整体结构粗聚类")
    logger.info("=" * 60)
    logger.info(f"对 {len(filtered_files)} 个筛选后的结构进行Foldseek聚类...")
    
    # 性能监控
    with _performance_monitor("Stage 2: Foldseek粗聚类") as perf_data:
        # 创建临时工作目录
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 准备结构文件：创建 structures/ 子目录并放入 CIF 符号链接
            # Foldseek createdb 接受 directory | .tsv | 单个 PDB/mmCIF；列表文件易报 "No structures found"
            structures_dir = temp_path / "structures"
            structures_dir.mkdir(parents=True, exist_ok=True)
            index_to_file = []  # Foldseek DB 序号 -> 原始 file_name
            for i, file_name in enumerate(filtered_files):
                full_path = pdb_dir / file_name
                if not full_path.exists():
                    continue
                link_path = structures_dir / f"{i:06d}.cif"
                try:
                    link_path.symlink_to(full_path.resolve())
                    index_to_file.append(file_name)
                except OSError as e:
                    logger.warning(f"无法创建符号链接 {link_path} -> {full_path}: {e}")
            
            if len(index_to_file) == 0:
                logger.error("没有有效的结构文件")
                return {}, perf_data
            
            logger.info(f"准备了 {len(index_to_file)} 个结构文件（structures/ 目录）")
            
            # 创建Foldseek数据库（目录输入）
            database_path = temp_path / "structures_db"
            logger.info("创建Foldseek数据库...")
            try:
                # 验证structures_dir中确实有CIF文件
                cif_files_in_dir = list(structures_dir.glob("*.cif"))
                logger.info(f"structures/目录中有 {len(cif_files_in_dir)} 个CIF文件")
                if len(cif_files_in_dir) == 0:
                    logger.error("structures/目录为空，无法创建Foldseek数据库")
                    return {}, perf_data
                
                # 测试第一个文件是否可读
                test_file = cif_files_in_dir[0]
                if not test_file.exists() or test_file.stat().st_size == 0:
                    logger.error(f"测试文件 {test_file} 不存在或为空")
                    return {}, perf_data
                
                cmd = [foldseek_path, "createdb", str(structures_dir), str(database_path)]
                logger.debug(f"Foldseek命令: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    cwd=str(temp_path),
                )
                if result.returncode != 0:
                    logger.error(f"Foldseek database creation failed (returncode={result.returncode})")
                    logger.error(f"Stdout: {result.stdout[:500]}")
                    logger.error(f"Stderr: {result.stderr[:500]}")
                    return {}, perf_data
                logger.info("Foldseek数据库创建成功")
            except Exception as e:
                logger.error(f"Foldseek database creation error: {e}")
                return {}, perf_data
            
            # 运行Foldseek聚类
            cluster_db_path = temp_path / "clusters_db"
            cluster_tsv_path = temp_path / "clusters.tsv"
            logger.info("运行Foldseek聚类...")
            try:
                cmd = [
                    foldseek_path, 'cluster',
                    str(database_path),
                    str(cluster_db_path),
                    str(temp_path / "tmp"),
                    '-s', str(sensitivity),
                    '-c', str(coverage),
                    '--min-seq-id', str(min_seq_id),
                    '--threads', str(n_jobs)
                ]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600
                )
                if result.returncode != 0:
                    logger.error(f"Foldseek clustering failed (returncode={result.returncode})")
                    logger.error(f"Stdout: {result.stdout[:500]}")
                    logger.error(f"Stderr: {result.stderr[:500]}")
                    return {}, perf_data
                logger.info("Foldseek聚类完成")
                logger.debug(f"Foldseek stdout: {result.stdout[:200]}")
            except Exception as e:
                logger.error(f"Foldseek clustering error: {e}")
                return {}, perf_data
            
            # Foldseek cluster 输出的是数据库，需要转换为TSV
            # 首先检查 cluster_db_path 目录下的文件
            logger.info(f"检查聚类结果目录: {cluster_db_path}")
            if cluster_db_path.exists():
                cluster_files = list(cluster_db_path.glob("*"))
                logger.info(f"cluster_db_path 中的文件: {[f.name for f in cluster_files]}")
            
            # 尝试使用 foldseek createtsv 将聚类数据库转换为TSV
            cluster_tsv_path = temp_path / "clusters.tsv"
            logger.info("将Foldseek聚类数据库转换为TSV...")
            try:
                cmd_tsv = [
                    foldseek_path, 'createtsv',
                    str(database_path),
                    str(database_path),
                    str(cluster_db_path),
                    str(cluster_tsv_path)
                ]
                result_tsv = subprocess.run(
                    cmd_tsv,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result_tsv.returncode == 0 and cluster_tsv_path.exists():
                    logger.info(f"成功生成TSV文件: {cluster_tsv_path}")
                    cluster_file = cluster_tsv_path
                else:
                    logger.warning(f"createtsv 失败或文件不存在 (returncode={result_tsv.returncode})")
                    logger.info(f"createtsv stdout: {result_tsv.stdout[:500]}")
                    logger.info(f"createtsv stderr: {result_tsv.stderr[:500]}")
                    cluster_file = None
            except Exception as e:
                logger.warning(f"createtsv 执行出错: {e}")
                cluster_file = None
            
            # 如果 createtsv 失败，尝试查找其他可能的输出文件
            if cluster_file is None:
                candidates = [
                    temp_path / "clusters_db" / "clusters.tsv",
                    cluster_db_path / "clusters.tsv",
                    temp_path / "clusters_db_cluster.tsv",
                    temp_path / "clusters_db_clu.tsv",
                    cluster_tsv_path,
                ]
                logger.info(f"尝试查找候选文件: {[str(c) for c in candidates]}")
                for c in candidates:
                    if c.exists():
                        cluster_file = c
                        logger.info(f"找到候选文件: {c}")
                        break
                
                if cluster_file is None:
                    # 递归搜索所有 .tsv 文件
                    logger.info("递归搜索所有 .tsv 文件...")
                    all_tsv = list(temp_path.rglob("*.tsv"))
                    logger.info(f"找到 {len(all_tsv)} 个TSV文件: {[str(f) for f in all_tsv[:10]]}")
                    for p in all_tsv:
                        if "cluster" in p.name.lower() or "clu" in p.name.lower():
                            cluster_file = p
                            logger.info(f"找到聚类相关TSV文件: {p}")
                            break
                
                if cluster_file is None:
                    # 列出所有生成的文件用于调试
                    logger.error("找不到Foldseek聚类结果文件")
                    logger.error(f"temp_path 中的所有文件:")
                    for item in temp_path.rglob("*"):
                        if item.is_file():
                            logger.error(f"  - {item} ({item.stat().st_size} bytes)")
                    return {}, perf_data
            
            logger.info(f"使用聚类结果文件: {cluster_file}")
            
            # 解析聚类结果
            # Foldseek cluster 输出：cluster_id \t representative \t member1 \t member2 ...
            # 成员为 DB 中的序号，对应 structures/ 中 000000.cif, 000001.cif, ... -> index_to_file[i]
            coarse_clusters = {}  # {cluster_id: [file_names]}
            file_to_cluster = {}  # {file_name: cluster_id}
            n_indexed = len(index_to_file)
            
            def parse_foldseek_id(member: str) -> int | None:
                """
                从 Foldseek createtsv 的成员 ID 解析出 0-based 结构索引。
                格式：'000001_A'（索引_链ID）或 '000001' 或 '1'。
                """
                s = member.strip()
                if not s:
                    return None
                # 格式 '000001_A' / '000001_H'：取 '_' 前部分
                if '_' in s:
                    s = s.split('_')[0].strip()
                try:
                    idx = int(s)
                    return idx if 0 <= idx < n_indexed else None
                except ValueError:
                    return None

            def idx_to_fname(member: str) -> str | None:
                """从 Foldseek 成员 ID（如 '000001_A' 或 '000001'）解析索引并返回对应文件名"""
                idx = parse_foldseek_id(member)
                if idx is not None:
                    return index_to_file[idx]
                # 回退：按名称匹配
                base = Path(member).stem if '_' in member else member
                for i, fname in enumerate(index_to_file):
                    if base == f"{i:06d}" or Path(fname).stem == base:
                        return fname
                return None

            logger.info("解析Foldseek聚类结果...")
            try:
                rep_to_members: Dict[str, List[str]] = {}  # rep_id -> [member_ids]
                with open(cluster_file, 'r') as f:
                    for line in f:
                        parts = line.strip().split('\t')
                        if len(parts) < 2:
                            continue
                        # Foldseek createtsv 输出格式：representative \t member
                        # 例如：000001_A \t 000001_A 或 000001_A \t 000000_A
                        if len(parts) == 2:
                            rep, mem = parts[0], parts[1]
                            rep_to_members.setdefault(rep, []).append(mem)
                            continue
                        # 多列格式（如果存在）：cluster_id \t rep \t mem1 \t mem2 ...
                        if len(parts) > 2:
                            try:
                                cluster_id = int(parts[0])
                                members = parts[1:]
                                cluster_files = []
                                for member in members:
                                    fname = idx_to_fname(member)
                                    if fname and fname not in cluster_files:
                                        cluster_files.append(fname)
                                if cluster_files:
                                    coarse_clusters[cluster_id] = cluster_files
                                    for fname in cluster_files:
                                        file_to_cluster[fname] = cluster_id
                            except ValueError:
                                # 如果第一列不是整数，当作两列格式处理
                                rep, mem = parts[0], parts[1]
                                rep_to_members.setdefault(rep, []).append(mem)
                
                # 处理两列格式（representative \t member），如 000001_A \t 000000_A
                if not coarse_clusters and rep_to_members:
                    logger.info(f"检测到两列格式（索引_链ID），共 {len(rep_to_members)} 个代表")
                    # 按结构集合合并：同一批结构的不同链（如 000001_A / 000001_H）会生成相同结构集
                    struct_set_to_files: Dict[frozenset, List[str]] = {}
                    for rep, mems in rep_to_members.items():
                        cluster_files = []
                        seen = set()
                        for m in [rep] + mems:
                            fname = idx_to_fname(m)
                            if fname and fname not in seen:
                                seen.add(fname)
                                cluster_files.append(fname)
                        if not cluster_files:
                            continue
                        key = frozenset(cluster_files)
                        if key not in struct_set_to_files:
                            struct_set_to_files[key] = list(cluster_files)
                    # 去重并生成粗簇
                    for cid, (key, files) in enumerate(struct_set_to_files.items()):
                        uniq = list(dict.fromkeys(files))
                        coarse_clusters[cid] = uniq
                        for fname in uniq:
                            file_to_cluster[fname] = cid
                    logger.info(f"从两列格式解析出 {len(coarse_clusters)} 个粗簇（已按结构合并）")
                
                logger.info(f"Foldseek粗聚类完成: 生成 {len(coarse_clusters)} 个粗簇")
                if coarse_clusters:
                    cluster_sizes = {cid: len(files) for cid, files in coarse_clusters.items()}
                    logger.info(f"粗簇大小分布: {min(cluster_sizes.values())}-{max(cluster_sizes.values())} 个结构")
                
            except Exception as e:
                logger.error(f"解析聚类结果失败: {e}")
                return {}, perf_data
        
        # 记录性能指标到perf_data（已在context manager中自动更新）
        pass
    
    # 性能总结
    logger.info(f"\nStage 2 性能统计:")
    logger.info(f"  - 运行时间: {perf_data['wall_clock_time_formatted']}")
    logger.info(f"  - CPU利用率: {perf_data['cpu_utilization_percent']:.1f}%")
    logger.info(f"  - 峰值内存: {perf_data['memory_peak_mb']['rss']:.1f} MB (RSS)")
    
    return coarse_clusters, perf_data


def stage3_fine_contact_clustering(
    pdb_dir: Path,
    coarse_clusters: Dict[int, List[str]],
    chainA: str,
    antigen_chains: List[str],
    contact_cutoff: float = 5.0,
    interface_cutoff: float = 8.0,
    clustering_method: str = 'kmeans',
    n_jobs: int = 4,
    min_cluster_size_for_fine: int = 5,
    compare_algorithms: bool = False,
    auto_select_best: bool = False,
    output_dir: Optional[Path] = None,
    algorithms_to_test: Optional[List[str]] = None
) -> Tuple[Dict[str, any], Dict]:
    """
    Stage 3: 在每个Foldseek粗簇内基于H-A接触集做精细聚类
    
    参数：
    - pdb_dir: 结构文件根目录
    - coarse_clusters: Foldseek粗簇 {cluster_id: [file_names]}
    - chainA: 抗体链ID
    - antigen_chains: 抗原链ID列表
    - contact_cutoff: 接触距离阈值
    - interface_cutoff: 界面识别距离阈值
    - clustering_method: 聚类方法 ('kmeans', 'hdbscan', 'dbscan', 'spectral')
    - n_jobs: 并行进程数
    - min_cluster_size_for_fine: 只有大于此大小的粗簇才做精细聚类
    - compare_algorithms: 是否比较多种算法
    - auto_select_best: 是否自动选择最佳算法
    - output_dir: 输出目录（用于保存比较结果）
    - algorithms_to_test: 要测试的算法列表，默认 ['kmeans', 'hdbscan', 'dbscan', 'spectral']
    
    返回：
    - fine_clustering_results: 精细聚类结果字典
    """
    logger.info("=" * 60)
    logger.info("Stage 3: 簇内H-A接触精细聚类")
    if compare_algorithms:
        logger.info("算法比较模式: 已启用")
        if auto_select_best:
            logger.info("自动选择最佳算法: 已启用")
    logger.info("=" * 60)
    
    # 如果启用算法比较，先进行比较
    algorithm_comparison_results = {}
    if compare_algorithms:
        logger.info("\n开始算法比较...")
        try:
            import sys
            scripts_dir = Path(__file__).parent / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            from stage3_cluster_comparison import compare_algorithms_for_all_clusters

            if algorithms_to_test is None:
                algorithms_to_test = ['kmeans', 'hdbscan', 'dbscan', 'spectral']

            comparison_output_dir = output_dir / "stage3_comparison" if output_dir else None
            algorithm_comparison_results = compare_algorithms_for_all_clusters(
                pdb_dir=pdb_dir,
                coarse_clusters=coarse_clusters,
                chainA=chainA,
                antigen_chains=antigen_chains,
                contact_cutoff=contact_cutoff,
                interface_cutoff=interface_cutoff,
                n_jobs=n_jobs,
                min_cluster_size=min_cluster_size_for_fine,
                algorithms=algorithms_to_test,
                output_dir=comparison_output_dir
            )
            logger.info("算法比较完成")
        except Exception as e:
            logger.warning(f"算法比较失败: {e}，将使用默认方法")
            compare_algorithms = False
    
    # 性能监控
    with _performance_monitor("Stage 3: 精细聚类") as perf_data:
        all_fine_labels = []  # 最终精细标签
        all_file_names = []   # 所有文件名
        fine_cluster_results = {}  # {coarse_cluster_id: {fine_labels, file_names, ...}}
        
        # 对每个粗簇进行处理
        sorted_coarse = sorted(coarse_clusters.items(), key=lambda x: len(x[1]), reverse=True)
        
        for coarse_id, cluster_files in sorted_coarse:
            cluster_size = len(cluster_files)
            logger.info(f"\n处理粗簇 {coarse_id} ({cluster_size} 个结构)...")
            
            # 如果簇太小，直接使用粗簇标签
            if cluster_size < min_cluster_size_for_fine:
                logger.info(f"  粗簇 {coarse_id} 太小（{cluster_size} < {min_cluster_size_for_fine}），跳过精细聚类")
                fine_labels = [coarse_id] * cluster_size
                fine_cluster_results[coarse_id] = {
                    'fine_labels': fine_labels,
                    'file_names': cluster_files,
                    'method': 'coarse_only'
                }
                all_fine_labels.extend(fine_labels)
                all_file_names.extend(cluster_files)
                continue
        
            # 创建临时目录，只包含这个簇的结构
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # 创建符号链接，并记录映射关系
                temp_to_orig = {}  # 临时文件名 -> 原始文件名
                valid_cluster_files = []  # 实际存在的原始文件列表
                
                for i, file_name in enumerate(cluster_files):
                    source_file = pdb_dir / file_name
                    temp_name = f"struct_{i:06d}.cif"
                    link_name = temp_path / temp_name
                    if source_file.exists():
                        link_name.symlink_to(source_file)
                        temp_to_orig[temp_name] = file_name
                        valid_cluster_files.append(file_name)
                
                # 使用AF3ClusterAnalyzer进行精细聚类
                try:
                    analyzer = AF3ClusterAnalyzer(
                        pdb_dir=str(temp_path),
                        chainA=chainA,
                        antigen_chains=antigen_chains,
                        contact_cutoff=contact_cutoff,
                        irmsd_cutoff=5.0,
                        n_jobs=n_jobs,
                        contact_mode='jaccard',
                        contact_atom_type='interface'
                    )
                    analyzer.interface_cutoff = interface_cutoff
                    analyzer.interface_method = 'residue'
                    
                    # 加载数据
                    logger.info(f"  加载 {len(valid_cluster_files)} 个结构的接触信息...")
                    ok = analyzer.load_and_process_data()
                    if not ok or len(analyzer.contact_sets) == 0:
                        logger.warning(f"  粗簇 {coarse_id} 加载失败，使用粗簇标签")
                        fine_labels = [coarse_id] * len(valid_cluster_files)
                        fine_cluster_results[coarse_id] = {
                            'fine_labels': fine_labels,
                            'file_names': valid_cluster_files,
                            'method': 'load_failed'
                        }
                        all_fine_labels.extend(fine_labels)
                        all_file_names.extend(valid_cluster_files)
                        continue
                    
                    # 确定使用的聚类方法
                    method_to_use = clustering_method
                    if compare_algorithms and auto_select_best:
                        cluster_key = f"coarse_cluster_{coarse_id}"
                        if cluster_key in algorithm_comparison_results:
                            best_alg = algorithm_comparison_results[cluster_key].get('best_algorithm')
                            if best_alg:
                                method_to_use = best_alg
                                logger.info(f"  自动选择最佳算法: {best_alg}")
                    
                    # 执行精细聚类
                    logger.info(f"  在粗簇 {coarse_id} 内进行{method_to_use}精细聚类...")
                    
                    # 自适应n_clusters（对于小簇）
                    fine_n_clusters = max(2, min(5, len(valid_cluster_files) // 3))
                    
                    # 根据算法类型设置参数
                    clustering_kwargs = {}
                    if method_to_use == 'hdbscan':
                        min_cluster_size = max(2, min(10, len(valid_cluster_files) // 10))
                        min_samples = max(2, min(min_cluster_size, int(np.log2(max(len(valid_cluster_files), 2))) + 1))
                        clustering_kwargs['min_cluster_size'] = min_cluster_size
                        clustering_kwargs['min_samples'] = min_samples
                    elif method_to_use == 'dbscan':
                        eps = 0.5
                        min_samples = max(2, int(np.log2(max(len(valid_cluster_files), 2))) + 1)
                        clustering_kwargs['eps'] = eps
                        clustering_kwargs['min_samples'] = min_samples
                    
                    analyzer.perform_coarse_clustering(
                        method=method_to_use,
                        distance_metric='jaccard',
                        n_clusters=fine_n_clusters if method_to_use in ['kmeans', 'spectral'] else None,
                        use_foldseek_prescreening=False,  # 粗簇内不需要再预筛选
                        max_neighbors=min(50, len(valid_cluster_files) - 1),
                        **clustering_kwargs
                    )
                    
                    if analyzer.coarse_labels is None:
                        logger.warning(f"  粗簇 {coarse_id} 聚类失败，使用粗簇标签")
                        fine_labels = [coarse_id] * len(valid_cluster_files)
                    else:
                        # 将精细标签映射回原簇ID（避免跨粗簇标签冲突）
                        base_fine_id = coarse_id * 1000  # 为每个粗簇预留1000个精细簇ID
                        fine_labels = [base_fine_id + label if label >= 0 else -1 
                                      for label in analyzer.coarse_labels]
                    
                    # 关键修复：将临时文件名映射回原始文件名
                    # analyzer.file_names 是临时目录中的文件名（如 struct_000001.cif）
                    # 需要转换为原始文件路径（如 gpu4_.../model.cif）
                    mapped_file_names = []
                    for temp_fn in analyzer.file_names:
                        orig_fn = temp_to_orig.get(temp_fn, temp_fn)
                        mapped_file_names.append(orig_fn)
                    
                    fine_cluster_results[coarse_id] = {
                        'fine_labels': fine_labels,
                        'file_names': mapped_file_names,
                        'method': method_to_use,
                        'n_fine_clusters': len(set([l for l in fine_labels if l >= 0]))
                    }
                    
                    # 如果进行了算法比较，保存比较信息
                    if compare_algorithms:
                        cluster_key = f"coarse_cluster_{coarse_id}"
                        if cluster_key in algorithm_comparison_results:
                            fine_cluster_results[coarse_id]['algorithm_comparison'] = {
                                k: v for k, v in algorithm_comparison_results[cluster_key].items()
                                if k not in ['best_algorithm', 'best_score'] or k == 'best_algorithm'
                            }
                    
                    all_fine_labels.extend(fine_labels)
                    all_file_names.extend(mapped_file_names)
                    
                    logger.info(f"  粗簇 {coarse_id} 精细聚类完成: {len(set([l for l in fine_labels if l >= 0]))} 个精细簇")
                    
                except Exception as e:
                    logger.error(f"  粗簇 {coarse_id} 处理失败: {e}")
                    fine_labels = [coarse_id] * cluster_size
                    fine_cluster_results[coarse_id] = {
                        'fine_labels': fine_labels,
                        'file_names': cluster_files,
                        'method': 'error',
                        'error': str(e)
                    }
                    all_fine_labels.extend(fine_labels)
                    all_file_names.extend(cluster_files)
        
        # 汇总结果
        logger.info("\n" + "=" * 60)
        logger.info("精细聚类汇总")
        logger.info("=" * 60)
        logger.info(f"总结构数: {len(all_file_names)}")
        logger.info(f"精细簇数: {len(set([l for l in all_fine_labels if l >= 0]))}")
        
        # 记录性能指标到perf_data（已在context manager中自动更新）
        pass
    
    # 性能总结
    logger.info(f"\nStage 3 性能统计:")
    logger.info(f"  - 运行时间: {perf_data['wall_clock_time_formatted']}")
    logger.info(f"  - CPU利用率: {perf_data['cpu_utilization_percent']:.1f}%")
    logger.info(f"  - 峰值内存: {perf_data['memory_peak_mb']['rss']:.1f} MB (RSS)")
    
    result = {
        'fine_labels': np.array(all_fine_labels),
        'file_names': all_file_names,
        'coarse_cluster_results': fine_cluster_results,
        'metrics_summary': {
            'n_total_structures': len(all_file_names),
            'n_fine_clusters': len(set([l for l in all_fine_labels if l >= 0])),
            'n_coarse_clusters': len(coarse_clusters)
        }
    }
    
    # 如果进行了算法比较，添加比较结果
    if compare_algorithms and algorithm_comparison_results:
        result['algorithm_comparison'] = algorithm_comparison_results
        
        # 生成可视化
        if output_dir:
            try:
                import sys
                scripts_dir = Path(__file__).parent / "scripts"
                if str(scripts_dir) not in sys.path:
                    sys.path.insert(0, str(scripts_dir))
                from stage3_visualization import generate_all_visualizations
                comparison_dir = output_dir / "stage3_comparison"
                comparison_json = comparison_dir / "algorithm_comparison.json"
                best_algorithm_json = comparison_dir / "best_algorithm_per_cluster.json"
                
                if comparison_json.exists() and best_algorithm_json.exists():
                    viz_dir = comparison_dir / "visualizations"
                    generate_all_visualizations(
                        comparison_json=comparison_json,
                        best_algorithm_json=best_algorithm_json,
                        output_dir=viz_dir
                    )
                    logger.info(f"可视化图表已生成到: {viz_dir}")
            except Exception as e:
                logger.warning(f"生成可视化图表失败: {e}")
    
    return result, perf_data


def _export_fine_clusters(
    pdb_dir: Path,
    output_dir: Path,
    fine_results: Dict[str, any],
) -> None:
    """
    根据Stage 3精细聚类结果，将结构按簇分目录整理，并生成简单的聚类统计。
    
    目录结构示例（参考 2STEP/fine_clusters/）：
    
    fine_clusters/
      ├── cluster_0/
      │     ├── struct1.cif
      │     ├── struct2.cif
      ├── cluster_1/
      │     ├── ...
      ├── noise_cluster/   # 标签为 -1 的噪声点（如果存在）
      └── cluster_info.tsv  # 每个簇的大小统计
    """
    try:
        import shutil
    except ImportError:
        shutil = None
    
    fine_labels = list(fine_results.get("fine_labels", []))
    file_names = list(fine_results.get("file_names", []))
    if not fine_labels or not file_names or len(fine_labels) != len(file_names):
        logger.warning("无法导出精细簇结构：fine_labels 与 file_names 不匹配或为空")
        return
    
    clusters_root = output_dir / "fine_clusters"
    clusters_root.mkdir(parents=True, exist_ok=True)
    
    # 构建簇 -> 文件列表映射
    cluster_to_files: Dict[int, List[str]] = {}
    for label, fname in zip(fine_labels, file_names):
        cluster_to_files.setdefault(int(label), []).append(fname)
    
    # 写 cluster_info.tsv
    info_path = clusters_root / "cluster_info.tsv"
    with open(info_path, "w") as f:
        f.write("cluster_id\tn_structures\n")
        for cid in sorted(cluster_to_files.keys()):
            f.write(f"{cid}\t{len(cluster_to_files[cid])}\n")
    
    # 为每个簇创建文件夹并拷贝/链接结构文件
    for cid, files in cluster_to_files.items():
        if cid < 0:
            subdir = clusters_root / "noise_cluster"
        else:
            subdir = clusters_root / f"cluster_{cid}"
        subdir.mkdir(parents=True, exist_ok=True)
        
        for rel_name in files:
            src = pdb_dir / rel_name
            if not src.exists():
                logger.debug(f"精细簇导出时未找到源文件: {src}")
                continue
            
            # 生成描述性文件名：保留原始路径的关键信息
            # 例如: gpu4_20260108_174350_RAS-P110_2908/.../seed-42_sample-0/model.cif
            # 生成: gpu4_20260108_174350_RAS-P110_2908_seed-42_sample-0_model.cif
            rel_path = Path(rel_name)
            path_parts = rel_path.parts
            
            # 提取关键路径组件：只保留最重要的信息
            key_parts = []
            
            # 1. 第一个目录（通常是 gpuX_...，包含主要标识信息）
            if path_parts and path_parts[0].startswith('gpu'):
                key_parts.append(path_parts[0])
            
            # 2. 查找包含 seed- 或 sample- 的目录（最重要的标识）
            for part in path_parts:
                if 'seed-' in part or 'sample-' in part:
                    key_parts.append(part)
                    break  # 只取第一个匹配的
            
            # 3. 添加文件名（不含扩展名）
            stem = rel_path.stem
            if key_parts:
                # 组合：gpu4_20260108_174350_RAS-P110_2908_seed-42_sample-0_model
                safe_name = '_'.join(key_parts) + '_' + stem
            else:
                # 如果没有关键信息，使用原始路径的最后两级
                if len(path_parts) >= 2:
                    safe_name = '_'.join(path_parts[-2:]) + '_' + stem
                else:
                    safe_name = stem
            
            # 清理文件名中的特殊字符，确保文件系统兼容
            safe_name = safe_name.replace('/', '_').replace('\\', '_').replace(':', '_')
            # 限制文件名长度（避免过长，保留足够信息）
            if len(safe_name) > 200:
                # 如果太长，保留开头和结尾
                safe_name = safe_name[:150] + '...' + safe_name[-47:]
            
            dst = subdir / f"{safe_name}{rel_path.suffix}"
            
            # 如果同名文件已存在（可能来自不同目录），添加序号
            if dst.exists():
                stem = dst.stem
                suffix = dst.suffix
                counter = 1
                while dst.exists():
                    dst = subdir / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            try:
                # 优先使用符号链接，节省空间
                # 重要：符号链接需要绝对路径
                abs_src = src.resolve()
                os.symlink(abs_src, dst)
            except OSError as e:
                # 若符号链接不支持（如跨文件系统），退回到复制
                logger.debug(f"符号链接失败 {src} -> {dst}: {e}，尝试复制")
                if shutil is not None:
                    try:
                        shutil.copy2(src, dst)
                    except Exception as copy_e:
                        logger.debug(f"复制结构文件失败 {src} -> {dst}: {copy_e}")
    
    logger.info(f"精细簇结构已导出到: {clusters_root}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='三级AF3分析流程：评分筛选→Foldseek粗聚→接触精聚')
    parser.add_argument('pdb_dir', type=str, help='AF3输出目录')
    parser.add_argument('--chainA', type=str, default='H', help='抗体链ID（默认：H）')
    parser.add_argument('--antigen-chains', type=str, default='A', help='抗原链ID列表，用逗号分隔（默认：A）')
    parser.add_argument('--output-dir', type=str, default=None, help='输出目录')
    
    # Stage 1 参数
    parser.add_argument('--plddt-threshold', type=float, default=0.7, help='pLDDT阈值（>=，默认：0.7）')
    parser.add_argument('--clashes-threshold', type=int, default=5, help='碰撞阈值（<，默认：5）')
    parser.add_argument('--pdockq-threshold', type=float, default=0.2, help='pDockQ阈值（>=，默认：0.2）')
    parser.add_argument('--iptm-threshold', type=float, default=0.6, help='iPTM阈值（>=，默认：0.6）')
    parser.add_argument('--ranking-confidence-threshold', type=float, default=0.7, help='ranking_confidence阈值（>=，默认：0.7，计算公式：0.8*ipTM + 0.2*pTM）')
    parser.add_argument('--ipsae-threshold', type=float, default=0.6, help='ipSAE阈值（>=，默认：0.6；高 ipSAE=高界面置信度，>0.6 常用作可能结合。若不存在则跳过）')
    
    # Stage 2 参数
    parser.add_argument('--foldseek-path', type=str, default='/mnt/share/public/foldseek/bin/foldseek', help='Foldseek路径')
    parser.add_argument('--foldseek-sensitivity', type=float, default=7.5, help='Foldseek敏感度（默认：7.5）')
    parser.add_argument('--min-cluster-size', type=int, default=5, help='最小粗簇大小（默认：5）')
    
    # Stage 3 参数
    parser.add_argument('--contact-cutoff', type=float, default=5.0, help='接触距离阈值（默认：5.0）')
    parser.add_argument('--interface-cutoff', type=float, default=8.0, help='界面识别距离阈值（默认：8.0）')
    parser.add_argument('--clustering-method', type=str, default='kmeans', choices=['kmeans', 'hdbscan', 'dbscan', 'spectral'], help='精细聚类方法（默认：kmeans）')
    parser.add_argument('--compare-algorithms', action='store_true', help='比较多种聚类算法（KMeans, HDBSCAN, DBSCAN, Spectral）')
    parser.add_argument('--auto-select-best', action='store_true', help='自动选择最佳算法（需要同时启用--compare-algorithms）')
    parser.add_argument('--algorithms-to-test', type=str, nargs='+', default=None, help='要测试的算法列表（默认：kmeans hdbscan dbscan spectral）')
    
    # 其他参数
    parser.add_argument('--n-jobs', type=int, default=8, help='并行进程数（默认：8）')
    parser.add_argument('--max-representatives', type=int, default=3, help='每个精细簇的代表结构数（默认：3）')
    
    # 断点续传选项
    parser.add_argument('--start-from-stage', type=int, choices=[1, 2, 3], default=1, 
                       help='从指定阶段开始运行（默认：1）。如果指定2或3，将尝试加载之前阶段的结果')
    parser.add_argument('--skip-stage1', action='store_true', 
                       help='跳过Stage 1，直接从Stage 2开始（等同于--start-from-stage 2）')
    parser.add_argument('--skip-foldseek', action='store_true',
                       help='跳过Stage 2 Foldseek粗聚类；将所有筛选结构视为一个粗簇后直接做精细聚类。当Foldseek只产生1个簇时等价')
    
    args = parser.parse_args()
    
    # 处理跳过Stage 1的选项
    if args.skip_stage1:
        args.start_from_stage = 2
    
    # 解析抗原链列表
    antigen_chains = [c.strip() for c in args.antigen_chains.split(',')]
    
    # 设置输出目录
    pdb_path = Path(args.pdb_dir)
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = pdb_path.parent / f"{pdb_path.name}_three_stage_clustering"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成日志文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = output_dir / f"three_stage_analysis_{timestamp}.log"
    latest_log = output_dir / "three_stage_analysis_latest.log"
    
    # 设置日志文件处理器
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    # 创建最新日志链接（无权限或非 Unix 环境可能失败，仅记录不中断）
    try:
        if latest_log.exists():
            latest_log.unlink()
        latest_log.symlink_to(log_file.name)
    except OSError as e:
        logger.warning("无法创建 latest 日志链接（可忽略）: %s", e)
    
    logger.info("=" * 60)
    logger.info("三级AF3分析流程启动")
    logger.info("=" * 60)
    logger.info(f"输入目录: {args.pdb_dir}")
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"日志文件: {log_file}")
    logger.info(f"链配置: chainA={args.chainA}, antigen_chains={antigen_chains}")
    logger.info(f"从阶段 {args.start_from_stage} 开始运行")
    
    # 整体性能监控
    overall_start_time = time.time()
    overall_start_memory = psutil.Process().memory_info()
    
    # 初始化变量
    filtered_files = []
    metrics_dict = {}
    filter_stats = {}
    stage1_perf = {}
    coarse_clusters = {}
    stage2_perf = {}
    
    try:
        # Stage 1: AF3评分筛选（如果需要）
        if args.start_from_stage <= 1:
            logger.info("=" * 60)
            logger.info("Stage 1: AF3评分筛选")
            logger.info("=" * 60)
            filtered_files, metrics_dict, filter_stats, stage1_perf = stage1_af3_score_filtering(
                pdb_path,
                args.chainA,
                antigen_chains,
                plddt_threshold=args.plddt_threshold,
                clashes_threshold=args.clashes_threshold,
                pdockq_threshold=args.pdockq_threshold,
                iptm_threshold=args.iptm_threshold,
                ranking_confidence_threshold=args.ranking_confidence_threshold,
                ipsae_threshold=args.ipsae_threshold,
                n_jobs=args.n_jobs
            )
            
            if len(filtered_files) == 0:
                logger.error("Stage 1筛选后没有结构剩余，终止分析")
                _write_partial_performance(
                    output_dir,
                    overall_start_time,
                    overall_start_memory,
                    {"stage1": stage1_perf},
                    "failed_at_stage1_no_structures",
                    "Stage 1筛选后没有结构剩余",
                )
                return
            
            # 保存Stage 1结果
            stage1_result = {
                'filtered_files': filtered_files,
                'n_total': filter_stats.get('n_total', 0),
                'n_filtered': len(filtered_files),
                'pass_rate': len(filtered_files) / filter_stats.get('n_total', 1) * 100 if filter_stats.get('n_total', 0) > 0 else 0,
                'filter_stats': filter_stats,
                'metrics_dict': {f: metrics_dict[f] for f in filtered_files},
                'filter_criteria': {
                    'plddt_threshold': args.plddt_threshold,
                    'clashes_threshold': args.clashes_threshold,
                    'pdockq_threshold': args.pdockq_threshold,
                    'iptm_threshold': args.iptm_threshold,
                    'ranking_confidence_threshold': args.ranking_confidence_threshold,
                    'ranking_confidence_formula': '0.8*ipTM + 0.2*pTM',
                    'ipsae_threshold': args.ipsae_threshold
                }
            }
            with open(output_dir / "stage1_filtering_result.json", 'w') as f:
                json.dump(stage1_result, f, indent=2)
        else:
            # 从Stage 2开始，加载Stage 1的结果
            logger.info("=" * 60)
            logger.info("跳过Stage 1，加载已保存的结果")
            logger.info("=" * 60)
            stage1_result_file = output_dir / "stage1_filtering_result.json"
            if not stage1_result_file.exists():
                logger.error(f"找不到Stage 1结果文件: {stage1_result_file}")
                logger.error("请先运行Stage 1，或使用 --start-from-stage 1")
                return
            
            logger.info(f"从文件加载Stage 1结果: {stage1_result_file}")
            with open(stage1_result_file, 'r') as f:
                stage1_result = json.load(f)
            
            filtered_files = stage1_result['filtered_files']
            metrics_dict = {f: m for f, m in stage1_result.get('metrics_dict', {}).items()}
            filter_stats = stage1_result.get('filter_stats', {})
            logger.info(f"加载了 {len(filtered_files)} 个筛选后的结构")
            logger.info(f"Stage 1通过率: {stage1_result.get('pass_rate', 0):.2f}%")
        
        # 计算通过结构的指标分布统计（如果Stage 1刚运行）
        if args.start_from_stage <= 1:
            passed_metrics = [metrics_dict[f] for f in filtered_files]
            metrics_summary = {}
            for metric_name in ['plddt', 'clashes', 'pdockq', 'iptm', 'ptm', 'ranking_confidence', 'ipsae']:
                values = [m.get(metric_name) for m in passed_metrics if m.get(metric_name) is not None]
                if len(values) > 0:
                    metrics_summary[metric_name] = {
                        'mean': float(np.mean(values)),
                        'std': float(np.std(values)),
                        'min': float(np.min(values)),
                        'max': float(np.max(values)),
                        'count': len(values)
                    }
        
        # Stage 2: Foldseek粗聚类（或跳过）
        if args.start_from_stage > 2:
            # 从Stage 3开始，加载Stage 2的结果
            logger.info("=" * 60)
            logger.info("跳过Stage 2，加载已保存的结果")
            logger.info("=" * 60)
            stage2_result_file = output_dir / "stage2_foldseek_clustering.json"
            if not stage2_result_file.exists():
                logger.error(f"找不到Stage 2结果文件: {stage2_result_file}")
                logger.error("请先运行Stage 2，或使用 --start-from-stage 2")
                return
            
            logger.info(f"从文件加载Stage 2结果: {stage2_result_file}")
            with open(stage2_result_file, 'r') as f:
                stage2_result = json.load(f)
            
            coarse_clusters = {int(k): v for k, v in stage2_result['coarse_clusters'].items()}
            logger.info(f"加载了 {len(coarse_clusters)} 个粗簇")
            logger.info(f"总结构数: {sum(len(v) for v in coarse_clusters.values())}")
        elif getattr(args, 'skip_foldseek', False):
            # 跳过Foldseek：将所有筛选结构视为一个粗簇，直接进入精细聚类
            logger.info("=" * 60)
            logger.info("跳过Stage 2 Foldseek（--skip-foldseek）")
            logger.info("=" * 60)
            coarse_clusters = {0: filtered_files}
            stage2_perf = {
                'process_name': 'Stage 2: Foldseek粗聚类',
                'skipped': True,
                'wall_clock_time_seconds': 0.0,
                'wall_clock_time_formatted': '0h 0m 0.0s',
                'memory_peak_mb': {'rss': 0.0, 'vms': 0.0},
            }
            stage2_result = {
                'coarse_clusters': {'0': filtered_files},
                'n_coarse_clusters': 1,
                'cluster_sizes': {'0': len(filtered_files)},
                'skipped_foldseek': True,
            }
            with open(output_dir / "stage2_foldseek_clustering.json", 'w') as f:
                json.dump(stage2_result, f, indent=2)
            logger.info(f"将所有 {len(filtered_files)} 个筛选结构作为单一粗簇，进入Stage 3")
        else:
            logger.info("=" * 60)
            logger.info("Stage 2: Foldseek整体结构粗聚类")
            logger.info("=" * 60)
            coarse_clusters, stage2_perf = stage2_foldseek_coarse_clustering(
                pdb_path,
                filtered_files,
                foldseek_path=args.foldseek_path,
                sensitivity=args.foldseek_sensitivity,
                n_jobs=args.n_jobs
            )
            if len(coarse_clusters) == 0:
                logger.error("Stage 2 Foldseek聚类失败，终止分析")
                _write_partial_performance(
                    output_dir,
                    overall_start_time,
                    overall_start_memory,
                    {"stage1": stage1_perf, "stage2": stage2_perf},
                    "failed_at_stage2_foldseek",
                    "Foldseek createdb/cluster 失败或未产生聚类结果",
                )
                return
            stage2_result = {
                'coarse_clusters': {str(k): v for k, v in coarse_clusters.items()},
                'n_coarse_clusters': len(coarse_clusters),
                'cluster_sizes': {str(k): len(v) for k, v in coarse_clusters.items()},
            }
            with open(output_dir / "stage2_foldseek_clustering.json", 'w') as f:
                json.dump(stage2_result, f, indent=2)
        
        # Stage 3: 簇内精细聚类
        fine_results, stage3_perf = stage3_fine_contact_clustering(
            pdb_path,
            coarse_clusters,
            args.chainA,
            antigen_chains,
            contact_cutoff=args.contact_cutoff,
            interface_cutoff=args.interface_cutoff,
            clustering_method=args.clustering_method,
            n_jobs=args.n_jobs,
            min_cluster_size_for_fine=args.min_cluster_size,
            compare_algorithms=args.compare_algorithms,
            auto_select_best=args.auto_select_best,
            output_dir=output_dir,
            algorithms_to_test=args.algorithms_to_test
        )
        
        # 保存Stage 3结果（转换 numpy 类型以确保 JSON 可序列化）
        stage3_result = _to_json_safe({
            'fine_labels': fine_results['fine_labels'].tolist(),
            'file_names': fine_results['file_names'],
            'coarse_cluster_results': fine_results['coarse_cluster_results'],
            'metrics_summary': fine_results['metrics_summary']
        })
        
        # 如果进行了算法比较，保存比较结果
        if args.compare_algorithms and 'algorithm_comparison' in fine_results:
            comparison_result = {}
            for k, v in fine_results['algorithm_comparison'].items():
                # 移除labels以减小文件大小
                if isinstance(v, dict):
                    comparison_result[k] = {
                        k2: v2 for k2, v2 in v.items() 
                        if k2 != 'labels'
                    }
                else:
                    comparison_result[k] = v
            stage3_result['algorithm_comparison'] = comparison_result
        with open(output_dir / "stage3_fine_clustering.json", 'w') as f:
            json.dump(stage3_result, f, indent=2)
        
        # 基于 Stage 3 结果导出精细簇结构文件夹和简单统计（类似 2STEP/fine_clusters）
        try:
            _export_fine_clusters(
                pdb_dir=Path(args.pdb_dir),
                output_dir=output_dir,
                fine_results=fine_results,
            )
        except Exception as e:
            logger.warning(f"导出精细簇结构失败: {e}")
        
        # 计算总体性能
        overall_end_time = time.time()
        overall_end_memory = psutil.Process().memory_info()
        overall_wall_time = overall_end_time - overall_start_time
        
        overall_perf = {
            'pipeline_status': 'completed',
            'total_wall_clock_time_seconds': overall_wall_time,
            'total_wall_clock_time_formatted': f"{int(overall_wall_time // 3600)}h {int((overall_wall_time % 3600) // 60)}m {overall_wall_time % 60:.1f}s",
            'start_time': datetime.fromtimestamp(overall_start_time).isoformat(),
            'end_time': datetime.fromtimestamp(overall_end_time).isoformat(),
            'peak_memory_mb': {
                'rss': overall_end_memory.rss / 1024 / 1024,
                'vms': overall_end_memory.vms / 1024 / 1024,
            },
            'memory_increase_mb': {
                'rss': (overall_end_memory.rss - overall_start_memory.rss) / 1024 / 1024,
                'vms': (overall_end_memory.vms - overall_start_memory.vms) / 1024 / 1024,
            },
            'stage_performances': {
                'stage1': stage1_perf,
                'stage2': stage2_perf,
                'stage3': stage3_perf,
            }
        }
        
        # 计算各阶段时间占比（兼容从 Stage 2/3 续跑时未运行的阶段 perf 为空）
        s1 = stage1_perf.get('wall_clock_time_seconds', 0) or 0
        s2 = stage2_perf.get('wall_clock_time_seconds', 0) or 0
        s3 = stage3_perf.get('wall_clock_time_seconds', 0) or 0
        total_stage_time = s1 + s2 + s3
        if total_stage_time > 0 and overall_wall_time > 0:
            overall_perf['stage_time_breakdown'] = {
                'stage1_percent': s1 / overall_wall_time * 100,
                'stage2_percent': s2 / overall_wall_time * 100,
                'stage3_percent': s3 / overall_wall_time * 100,
            }
        
        logger.info("=" * 60)
        logger.info("三级分析流程完成")
        logger.info("=" * 60)
        logger.info(f"最终精细簇数: {fine_results['metrics_summary']['n_fine_clusters']}")
        logger.info(f"结果保存在: {output_dir}")
        logger.info("")
        logger.info("=" * 60)
        logger.info("整体性能统计")
        logger.info("=" * 60)
        logger.info(f"总运行时间: {overall_perf['total_wall_clock_time_formatted']}")
        logger.info(f"峰值内存: {overall_perf['peak_memory_mb']['rss']:.1f} MB (RSS)")
        logger.info(f"内存增长: {overall_perf['memory_increase_mb']['rss']:.1f} MB")
        logger.info("")
        logger.info("各阶段时间分布:")
        if 'stage_time_breakdown' in overall_perf:
            f1 = stage1_perf.get('wall_clock_time_formatted', '0h 0m 0.0s')
            f2 = stage2_perf.get('wall_clock_time_formatted', '0h 0m 0.0s')
            f3 = stage3_perf.get('wall_clock_time_formatted', '0h 0m 0.0s')
            logger.info(f"  - Stage 1: {overall_perf['stage_time_breakdown']['stage1_percent']:.1f}% ({f1})")
            logger.info(f"  - Stage 2: {overall_perf['stage_time_breakdown']['stage2_percent']:.1f}% ({f2})")
            logger.info(f"  - Stage 3: {overall_perf['stage_time_breakdown']['stage3_percent']:.1f}% ({f3})")
        else:
            logger.info("  - （部分阶段从文件加载，未统计时间占比）")
        
        # 保存性能数据
        with open(output_dir / "performance_metrics.json", 'w') as f:
            json.dump(overall_perf, f, indent=2)
        
        logger.info(f"\n性能数据已保存到: {output_dir / 'performance_metrics.json'}")
        
    except Exception as e:
        logger.error(f"分析过程出错: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
