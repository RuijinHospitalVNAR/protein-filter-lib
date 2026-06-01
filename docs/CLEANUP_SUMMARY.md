# protein_filter_lib 脚本与文档清理总结

与 README Quickstart 一致，此处为**脚本级入口清单**。本文档记录按《protein_filter_lib 脚本与文档清理规划》执行的清理结果，便于日常使用与历史参考。

## 1. 当前推荐入口脚本清单

### Part 1（AF3 + 聚类）

| 类型     | 脚本/入口 |
|----------|------------|
| 主入口   | `analyze_af3_three_stage.py` |
| Shell 流程 | `scripts/run_full_pipeline.sh`（指标计算与筛选分离，一键或分步） |
| 工具脚本 | `scripts/part1/part1_compute_stage1_metrics.sh`、`part1_filter_stage1_metrics.sh`、`part1_compute_stage2_metrics.sh`、`part1_filter_stage2_metrics.sh` |

### Part 2（PyRosetta 静态分析）

| 类型     | 脚本/入口 |
|----------|------------|
| Python 主入口 | `scripts/run_pyrosetta_static.py` |
| 批量入口 | `scripts/part2/part2_run_pyrosetta_batch.sh`（兼容：`scripts/run_pyrosetta_batch.sh`） |

### Part 3（MD + MM/PBSA）

| 类型     | 脚本/入口 |
|----------|------------|
| 主入口（推荐） | `scripts/run_part3.py`（配置驱动，如 `--config config/part3_100ns.yaml --n_gpu 8`） |
| 底层批处理   | `scripts/run_md_mmgbsa_rmsd.py`（供高级/调试用户直接调用） |
| 单结构后端   | `YZC_MD_SCRIPT/run_part3_md_single.sh` |
| 兼容/示例脚本 | `run_part3_8gpu_100ns.sh`（等价于 run_part3.py，头部已注明） |

## 2. 已标注为「推荐主入口优先」的脚本

以下脚本仍可使用，但文档与头部注释已标明**推荐优先使用主入口**：

- **`run_part3_8gpu_100ns.sh`**：等价于 `scripts/run_part3.py`，保留作历史记录/示例。
- **`run_part3_unified.sh`**、**`run_part3_unified_relaxed_nvt310_ff14sb.sh`**：供 `run_full_pipeline_v2.py` 或历史用法调用；推荐主入口为 `scripts/run_part3.py`。

## 2.5 关键废弃脚本与替代入口

| 废弃/历史脚本 | 推荐替代 |
|---------------|----------|
| `run_three_stage_*`、`run_from_stage2.sh` 等旧 Part1 shell | `scripts/run_denovo_design.sh` + `scripts/part1/part1_analyze_af3_three_stage.py` 或 `scripts/run_full_pipeline.sh` |
| `run_part3_unified.sh`、`run_part3_unified_relaxed*.sh`（直接调用） | `scripts/run_part3.py` 或 `scripts/run_optimization_pipeline.sh` |
| `run_part3_8gpu_100ns.sh`（直接调用） | `scripts/run_part3.py --config config/part3_100ns.yaml --n_gpu 8` |
| `resume_part3_gpu1-7.sh`、`resume_gpu0_and_wt.sh`、`finish_top30_in_place.sh` | 功能已由 `run_part3.py` / `run_optimization_pipeline.sh` 覆盖，历史见 `archive/` |

其他已删除脚本见第 5 节「历史清理记录」。

## 3. 文档与引用调整

- **Part1**：`docs/PART1_AF3_AND_CLUSTERING.md`、`docs/README_THREE_STAGE.md`、`docs/STAGE1_RELAXED_THRESHOLDS.md`、`docs/FOLDSEEK_AND_FINE_CLUSTERING.md` 中已删除或替换对已移除脚本（如 `run_three_stage_*`、`run_from_stage2.sh`）的引用，统一为 `analyze_af3_three_stage.py` 或 `scripts/run_full_pipeline.sh`。
- **Part3**：`docs/PART3_PARALLEL_8GPU_ANALYSIS.md` 中并行运行示例已改为 `scripts/run_part3.py` 与 `run_part3_8gpu_100ns.sh`；`docs/archive/PART3_8GPU_PARALLEL_SUMMARY.md` 已加历史说明并更新脚本名。
- **顶层**：`README.md` 中安装与环境说明已统一为推荐 **VNAR_OP** 环境（`environment_VNAR_OP.yml`、`setup_VNAR_OP.sh`）；Part3 描述改为以 `scripts/run_part3.py` 为主入口。
- **总览**：`docs/PIPELINE_OVERVIEW.md` 中 Part3 脚本列表已更新为主入口、底层、单结构后端与兼容脚本。

## 4. 环境说明

- **推荐环境**：**VNAR_OP**（Part2 PyRosetta + Part3 及全流程）。环境文件：`environment_VNAR_OP.yml`，一键设置：`./setup_VNAR_OP.sh`。
- 仅跑 Part1 时可在其他 Python 环境中安装依赖后直接运行 `analyze_af3_three_stage.py` 或 `scripts/run_full_pipeline.sh`。

## 5. 历史清理记录（此前已删除，本次未改动）

此前已删除的脚本（见 `docs/archive/FINAL_CLEANUP_SUMMARY.md` 等）包括但不限于：  
`run_three_stage_batch_0001_0114.sh`、`run_three_stage_ipsae_vis.sh`、`run_three_stage_latest.sh`、`run_three_stage_relaxed_newdir.sh`、`run_from_stage2.sh`、`run_from_stage3_relaxed.sh` 等旧 Part1 shell；`run_part3_parallel_8gpu.sh` / `run_part3_parallel_8gpu_fixed.sh` 未在仓库中保留，文档中已改为推荐 `run_part3.py` / `run_part3_8gpu_100ns.sh`。

---

**日常使用**：Part1 → `analyze_af3_three_stage.py` 或 `scripts/run_full_pipeline.sh`；Part2 → `scripts/part2/part2_run_pyrosetta_batch.sh`（或 `scripts/run_pyrosetta_batch.sh`）；Part3 → `scripts/run_part3.py`（或 `run_part3_8gpu_100ns.sh` 作兼容）；优化模式 → `scripts/run_optimization_pipeline.sh` + `config/optimizing_default.yaml`。  
**查文档**：顶层 README + `docs/PIPELINE_OVERVIEW.md` + 各 Part 主文档即可覆盖绝大多数使用场景。  
**Part3 结果可视化**：`examples/part3_analysis/plot_rmsd_and_mmgbsa.py`（RMSD + MMGBSA ΔG 出图），见 `examples/part3_analysis/README.md`。
