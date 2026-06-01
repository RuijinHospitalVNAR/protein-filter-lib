"""
Part2：Stage2 指标计算与筛选（PyRosetta 界面/SAP 等）。

- compute_stage2_metrics: 对 Stage1 通过的设计计算 PyRosetta 指标，写出 stage2_metrics.parquet
- filter_stage2: 基于 stage2_metrics.parquet 筛选，写出 stage2_passed.parquet
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import FilterConfig, StructureRelaxerConfig, MetricConfig
from ..core import ProteinFilter
from ..design import Design
from ..filters import apply_filters_to_dataframe
from ..utils import save_metrics_to_parquet, load_metrics_from_parquet

logger = logging.getLogger(__name__)


def compute_stage2_metrics(
    input_dir: str | Path,
    stage1_passed_list: str | Path,
    output_dir: str | Path,
    *,
    target_chain: str = "A",
    binder_chain: str = "B",
    relaxer: str = "pyrosetta",
    enabled_metrics: Optional[List[str]] = None,
    pyrosetta_init: Optional[str] = None,
) -> Path:
    """
    对 Stage1 通过的设计计算 Stage2 指标（PyRosetta 界面 dG、SAP 等），写入 parquet。

    stage1_passed_list: stage1_passed_design_names.txt 或含 design_name 的 parquet 路径。

    Returns:
        stage2_metrics.parquet 路径
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 解析通过的设计名
    list_path = Path(stage1_passed_list)
    if not list_path.exists():
        raise FileNotFoundError(f"Stage1 passed list not found: {list_path}")

    if list_path.suffix.lower() == ".parquet":
        df = load_metrics_from_parquet(list_path)
        if "design_name" not in df.columns or df.empty:
            raise ValueError("stage1_passed parquet must contain design_name")
        design_names = df["design_name"].astype(str).tolist()
    else:
        design_names = [line.strip() for line in list_path.read_text().splitlines() if line.strip()]

    # 按 design_name 找 PDB/CIF（stem 匹配）
    name_to_path: Dict[str, Path] = {}
    for p in list(input_dir.glob("*.pdb")) + list(input_dir.glob("*.cif")):
        name_to_path[p.stem] = p
    designs_to_run = []
    for name in design_names:
        if name in name_to_path:
            designs_to_run.append((name, name_to_path[name]))
        else:
            logger.warning("Design %s not found in %s", name, input_dir)

    if not designs_to_run:
        raise FileNotFoundError(f"No PDB/CIF found in {input_dir} for stage1 passed names")

    if enabled_metrics is None:
        enabled_metrics = [
            "plddt", "clashes", "interface_dG", "interface_dSASA",
            "interface_packstat", "sap_score", "alpha_all", "beta_all", "loops_all",
        ]

    config = FilterConfig(
        structure_relaxer=StructureRelaxerConfig(
            name=relaxer,
            pyrosetta_init=pyrosetta_init,
        ),
        metrics=MetricConfig(enabled=enabled_metrics),
        filters={},
        output_dir=str(output_dir),
    )
    filter_system = ProteinFilter(config)
    metrics_list: List[Dict[str, Any]] = []

    for i, (design_name, pdb_path) in enumerate(designs_to_run):
        if (i + 1) % 20 == 0:
            logger.info("Processing %d/%d designs...", i + 1, len(designs_to_run))
        try:
            try:
                from ..utils.pdb_utils import get_sequence_from_pdb
                sequence = get_sequence_from_pdb(str(pdb_path), binder_chain) or "M"
            except Exception:
                sequence = "M"
            design = Design(
                sequence=sequence,
                pdb_path=str(pdb_path),
                target_chain=target_chain,
                binder_chain=binder_chain,
                design_name=design_name,
            )
            result = filter_system.filter(design)
            row = dict(result.metrics)
            row["design_name"] = design_name
            row["pdb_path"] = str(pdb_path)
            metrics_list.append(row)
        except Exception as e:
            logger.warning("Error for %s: %s", design_name, e)
            metrics_list.append({"design_name": design_name, "pdb_path": str(pdb_path), "error": str(e)})

    out_path = output_dir / "stage2_metrics.parquet"
    save_metrics_to_parquet(metrics_list, out_path)
    logger.info("Saved Stage2 metrics for %d designs to %s", len(metrics_list), out_path)
    return out_path


def filter_stage2(
    metrics_file: str | Path,
    output_dir: str | Path,
    filters: Dict[str, Dict[str, Any]],
) -> Path:
    """
    基于 stage2_metrics.parquet 按阈值筛选。

    Returns:
        stage2_passed.parquet 路径
    """
    metrics_file = Path(metrics_file)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_metrics_from_parquet(metrics_file)
    if df.empty:
        save_metrics_to_parquet([], output_dir / "stage2_passed.parquet")
        return output_dir / "stage2_passed.parquet"

    filtered_df = apply_filters_to_dataframe(df, filters)
    records = filtered_df.to_dict("records")
    passed_path = output_dir / "stage2_passed.parquet"
    save_metrics_to_parquet(records, passed_path)
    logger.info("Stage2 filter: %d passed, saved to %s", len(filtered_df), passed_path)
    return passed_path
