"""
Part1：Stage1 指标计算与筛选（AF3 置信度 + 可选聚类）。

- compute_stage1_metrics: 扫描输入目录，计算快速指标，写出 stage1_metrics.parquet
- filter_stage1: 读取 parquet，按阈值筛选，可选 Top-N，写出 stage1_passed.parquet 与设计列表
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import FilterConfig, StructureRelaxerConfig, MetricConfig
from ..core import ProteinFilter
from ..design import Design
from ..filters import apply_filters_to_dataframe, composite_score_row
from ..utils import save_metrics_to_parquet, load_metrics_from_parquet

logger = logging.getLogger(__name__)


def compute_stage1_metrics(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    target_chain: str = "B",
    binder_chain: str = "A",
    relaxer: str = "none",
    enabled_metrics: Optional[List[str]] = None,
    clustering_config: Optional[Dict[str, Any]] = None,
    ipsae_pae_cutoff: float = 5.0,
    ipsae_distance_cutoff: float = 5.0,
) -> Path:
    """
    对输入目录中的 PDB/CIF 计算 Stage1 快速指标，并写入 parquet。

    若提供 clustering_config，先做抗原-抗体界面聚类，仅对选中结构计算指标。

    Returns:
        输出的 stage1_metrics.parquet 路径
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if enabled_metrics is None:
        enabled_metrics = ["plddt", "clashes", "pdockq", "ipsae"]

    # 可选：聚类筛选
    selected_names: Optional[set[str]] = None
    if clustering_config:
        try:
            try:
                from ..clustering import InterfaceClusteringFilter
            except ImportError:
                import importlib.util
                _clustering_py = Path(__file__).resolve().parent.parent / "clustering.py"
                _spec = importlib.util.spec_from_file_location("_clustering_mod", _clustering_py)
                _mod = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                InterfaceClusteringFilter = _mod.InterfaceClusteringFilter
            filter_obj = InterfaceClusteringFilter(
                pdb_dir=str(input_dir),
                chainA=clustering_config.get("chain_a", target_chain),
                antigen_chains=clustering_config.get("antigen_chains", [binder_chain]),
                contact_cutoff=float(clustering_config.get("contact_cutoff", 5.0)),
                interface_cutoff=float(clustering_config.get("interface_cutoff", 8.0)),
                clustering_method=clustering_config.get("clustering_method", "kmeans"),
                min_cluster_size=int(clustering_config.get("min_cluster_size", 5)),
                min_samples=int(clustering_config.get("min_samples", 3)),
                target_cluster_id=clustering_config.get("target_cluster_id"),
            )
            filter_obj.perform_clustering()
            selected_names = set(filter_obj.selected_file_names)
            selected_path = output_dir / "clustering_selected_files.txt"
            with open(selected_path, "w") as f:
                for name in filter_obj.selected_file_names:
                    f.write(name + "\n")
            logger.info("Clustering selected %d structures, list saved to %s", len(selected_names), selected_path)
        except Exception as e:
            logger.warning("Clustering failed, using all files: %s", e)

    # 收集待处理文件
    pdb_files: List[Path] = []
    for ext in ("*.pdb", "*.cif"):
        pdb_files.extend(input_dir.glob(ext))
    if selected_names is not None:
        pdb_files = [f for f in pdb_files if f.name in selected_names]
    pdb_files = sorted(set(pdb_files))

    if not pdb_files:
        raise FileNotFoundError(f"No PDB/CIF files found in {input_dir} (after clustering)")

    config = FilterConfig(
        structure_relaxer=StructureRelaxerConfig(name=relaxer),
        metrics=MetricConfig(
            enabled=enabled_metrics,
            ipsae_pae_cutoff=ipsae_pae_cutoff,
            ipsae_distance_cutoff=ipsae_distance_cutoff,
            ipsae_include_duplicate_metrics=False,
        ),
        filters={},
        output_dir=str(output_dir),
    )
    filter_system = ProteinFilter(config)
    metrics_list: List[Dict[str, Any]] = []

    for i, pdb_file in enumerate(pdb_files):
        if (i + 1) % 100 == 0:
            logger.info("Processing %d/%d designs...", i + 1, len(pdb_files))
        try:
            try:
                from ..utils.pdb_utils import get_sequence_from_pdb
                sequence = get_sequence_from_pdb(str(pdb_file), binder_chain) or "M"
            except Exception:
                sequence = "M"
            design = Design(
                sequence=sequence,
                pdb_path=str(pdb_file),
                target_chain=target_chain,
                binder_chain=binder_chain,
                design_name=pdb_file.stem,
            )
            result = filter_system.filter(design)
            row = dict(result.metrics)
            row["design_name"] = design.design_name
            row["pdb_path"] = str(design.pdb_path)
            metrics_list.append(row)
        except Exception as e:
            logger.warning("Error for %s: %s", pdb_file.name, e)
            metrics_list.append({
                "design_name": pdb_file.stem,
                "pdb_path": str(pdb_file),
                "error": str(e),
            })

    out_path = output_dir / "stage1_metrics.parquet"
    save_metrics_to_parquet(metrics_list, out_path)
    logger.info("Saved Stage1 metrics for %d designs to %s", len(metrics_list), out_path)
    return out_path


def filter_stage1(
    metrics_file: str | Path,
    output_dir: str | Path,
    filters: Dict[str, Dict[str, Any]],
    *,
    top_n: int = 0,
    score_weights: Optional[Dict[str, float]] = None,
) -> Path:
    """
    基于 stage1_metrics.parquet 按阈值筛选，可选按综合分取 Top-N。

    Returns:
        stage1_passed.parquet 路径
    """
    metrics_file = Path(metrics_file)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_metrics_from_parquet(metrics_file)
    if df.empty:
        save_metrics_to_parquet([], output_dir / "stage1_passed.parquet")
        (output_dir / "stage1_passed_design_names.txt").write_text("")
        return output_dir / "stage1_passed.parquet"

    filtered_df = apply_filters_to_dataframe(df, filters)
    if top_n > 0 and score_weights and len(filtered_df) > top_n:
        filtered_df = filtered_df.copy()
        filtered_df["composite_score"] = filtered_df.apply(
            lambda row: composite_score_row(row, score_weights), axis=1
        )
        filtered_df = filtered_df.nlargest(top_n, "composite_score")

    records = filtered_df.to_dict("records")
    passed_path = output_dir / "stage1_passed.parquet"
    save_metrics_to_parquet(records, passed_path)

    names_path = output_dir / "stage1_passed_design_names.txt"
    if "design_name" in filtered_df.columns:
        with open(names_path, "w") as f:
            for name in filtered_df["design_name"]:
                f.write(str(name) + "\n")
    else:
        names_path.write_text("")

    logger.info("Stage1 filter: %d passed, saved to %s", len(filtered_df), passed_path)
    return passed_path
