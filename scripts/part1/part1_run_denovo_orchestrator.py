#!/usr/bin/env python3
"""
De novo 模式内部编排器：Part1（可选）→ Part2 → Part3。供 run_denovo_design.sh 调用，不作为用户主入口。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# 项目根（本脚本位于 scripts/part1/）
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from protein_filter.pipeline.config import (
    FullPipelineConfig,
    PipelineConfig,
    Stage1Config,
    Stage2Config,
    Stage3Config,
)
from protein_filter.pipeline.logging import setup_logging
from protein_filter.pipeline.state import (
    PipelineRunState,
    load_pipeline_state,
    save_pipeline_state,
)


def run_part1(cfg: FullPipelineConfig) -> Path | None:
    """运行 Part1：AF3 过滤 + 可选 Stage3。返回 Part1 输出 CSV 路径（若有）。"""
    from protein_filter.pipeline import Pipeline, PipelineData
    from protein_filter.pipeline.stages import (
        AF3ScoreFilteringStage,
        FineContactClusteringStage,
        FoldseekClusteringStage,
    )

    if not cfg.part1 or not cfg.part1.pdb_dir:
        return None
    p1 = cfg.part1
    output_dir = cfg.output_dir or p1.output_dir
    if not output_dir:
        output_dir = p1.pdb_dir.parent / f"{p1.pdb_dir.name}_clustering"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 简化流程：Stage1 + 可选 Stage2(skip_foldseek=True) + Stage3
    stages = [
        AF3ScoreFilteringStage(p1.stage1),
        FoldseekClusteringStage(Stage2Config(skip_foldseek=True)),
        FineContactClusteringStage(p1.stage3),
    ]
    data = PipelineData(
        stage="",
        pdb_dir=p1.pdb_dir,
        chain_a=p1.chain_a,
        antigen_chains=p1.antigen_chains,
    )
    data.metadata["output_dir"] = str(output_dir)
    pipeline = Pipeline(stages=stages, output_dir=output_dir, resume=cfg.resume)
    result = pipeline.run(data)
    if not result.success:
        raise RuntimeError(f"Part1 failed: {result.error_message}")
    # Part1 输出为 filtered_files / fine_clusters，需由调用方生成 Part2 输入 CSV
    # 此处仅返回 output_dir；实际 Part2 输入 CSV 通常由 prepare_relaxed_part3_inputs 等生成
    return output_dir


def run_part2(cfg: FullPipelineConfig, part2_csv: Path | None) -> Path:
    """运行 Part2：run_pyrosetta_static.py。返回 Part2 输出目录（内含 rosetta_static_*.csv）。"""
    p2 = cfg.part2
    csv_path = part2_csv or p2.csv_path
    if not csv_path or not Path(csv_path).exists():
        raise FileNotFoundError(f"Part2 输入 CSV 不存在: {csv_path}")
    out_dir = p2.output_dir or (cfg.output_dir and Path(cfg.output_dir) / "part2")
    if not out_dir:
        out_dir = Path(csv_path).parent / "rosetta_static"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "run_pyrosetta_static.py"),
        "--csv_path", str(csv_path),
        "--output_dir", str(out_dir),
        "--batch_idx", str(p2.batch_idx),
        "--relax", "true" if p2.relax else "false",
        "--dump_top_n", str(p2.dump_top_n),
    ]
    if p2.n_jobs > 0:
        cmd += ["--n_jobs", str(p2.n_jobs)]
    if cfg.resume:
        cmd.append("--resume")
    subprocess.run(cmd, check=True, cwd=str(PROJECT_ROOT))
    return out_dir


def run_part3(cfg: FullPipelineConfig, part2_output_dir: Path) -> None:
    """运行 Part3：调用统一脚本，通过环境变量传入 INPUT_CSV 与 OUTPUT_BASE。"""
    p3 = cfg.part3
    # Part2 输出 CSV 通常为 rosetta_static_0.csv
    part2_csv = part2_output_dir / "rosetta_static_0.csv"
    if not part2_csv.exists():
        part2_csv = next(part2_output_dir.glob("rosetta_static_*.csv"), None)
    if not part2_csv:
        raise FileNotFoundError(f"Part2 输出目录下未找到 rosetta_static_*.csv: {part2_output_dir}")
    base_out = p3.base_output_dir or (cfg.output_dir and Path(cfg.output_dir) / "part3")
    if not base_out:
        base_out = part2_output_dir.parent / "part3_100ns"
    base_out = Path(base_out)
    script = p3.md_script or (PROJECT_ROOT / "scripts" / "part3" / "part3_run_amber_md_unified_relaxed_nvt310_ff14sb.sh")
    if not script.exists():
        raise FileNotFoundError(f"Part3 脚本不存在: {script}")
    env = os.environ.copy()
    env["PART3_INPUT_CSV"] = str(part2_csv)
    env["PART3_OUTPUT_BASE"] = str(base_out)
    subprocess.run(["bash", str(script)], check=True, cwd=str(PROJECT_ROOT), env=env)


def main() -> None:
    ap = argparse.ArgumentParser(description="端到端流水线编排器 v2")
    ap.add_argument("--config", type=str, required=True, help="FullPipelineConfig YAML 路径")
    ap.add_argument("--resume", action="store_true", help="从上次断点续跑")
    ap.add_argument("--run-part3", action="store_true", help="执行 Part3（默认只跑 Part1+Part2）")
    ap.add_argument("--part2-csv", type=str, default="", help="覆盖 Part2 输入 CSV（否则从 Part1 输出或 config 读取）")
    args = ap.parse_args()

    # 加载配置（YAML）
    try:
        import yaml
        with open(args.config) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"加载配置失败: {e}", file=sys.stderr)
        sys.exit(1)
    cfg = FullPipelineConfig.from_dict(data)
    if args.resume:
        cfg.resume = True
    errs = cfg.validate()
    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        sys.exit(1)

    output_dir = cfg.output_dir or Path.cwd()
    output_dir = Path(output_dir)
    log_file = output_dir / "pipeline_v2.log"
    setup_logging(level="INFO", log_file=log_file)
    import logging
    log = logging.getLogger(__name__)

    state = load_pipeline_state(output_dir) if cfg.resume else None
    if state is None:
        state = PipelineRunState()

    part2_csv_override = Path(args.part2_csv) if args.part2_csv else None

    try:
        if cfg.pipeline_mode == "de_novo" and cfg.part1 and "part1" not in state.completed_parts:
            log.info("Running Part1 (AF3 filtering + clustering)...")
            run_part1(cfg)
            state.completed_parts.append("part1")
            state.current_part = "part2"
            save_pipeline_state(state, output_dir)
        # Part2 输入 CSV：若 affinity_maturation 则用 config part2.csv_path；否则需用户通过 --part2-csv 或由 Part1 后处理提供
        if "part2" not in state.completed_parts:
            part2_csv = part2_csv_override or cfg.part2.csv_path
            if not part2_csv:
                log.warning("Part2 未指定 csv_path 且未传 --part2-csv，跳过 Part2")
            else:
                log.info("Running Part2 (PyRosetta)...")
                part2_out = run_part2(cfg, Path(part2_csv))
                state.completed_parts.append("part2")
                state.current_part = "part3"
                save_pipeline_state(state, output_dir)
                if args.run_part3:
                    log.info("Running Part3 (MD)...")
                    run_part3(cfg, part2_out)
                    state.completed_parts.append("part3")
                    save_pipeline_state(state, output_dir)
        elif args.run_part3 and "part3" not in state.completed_parts:
            part2_out = cfg.part2.output_dir or (output_dir / "part2")
            if part2_out.exists():
                run_part3(cfg, Path(part2_out))
                state.completed_parts.append("part3")
                save_pipeline_state(state, output_dir)
    except Exception as e:
        log.exception("Pipeline failed: %s", e)
        sys.exit(1)
    log.info("Pipeline finished. State: %s", state.completed_parts)


if __name__ == "__main__":
    main()
