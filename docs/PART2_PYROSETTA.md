# Part 2: PyRosetta 静态物理分析 — 整合说明

Part 2 负责 **界面能量（interface_dG）计算与评估**，以及可选的 **FastRelax**。逻辑整合自外部工具（如 germinal、PPIFlow）；路径可通过项目环境或配置指定，见 [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md)。

## 1. 功能概览

- **InterfaceAnalyzerMover**：计算 `interface_dG`、`interface_delta_sasa`、`complexed_sasa` 等界面指标。
- **可选 FastRelax**：对复合物做 Relax，支持 `fixbb` + `fixed_chain` 固定指定链骨架（PPIFlow 风格）。
- **输出**：`<output_dir>/rosetta_static_<batch_idx>.csv`，含 `pdb_name`、`interface_score`、`interface_delta_sasa`、`time_consumed` 等列；若启用 Relax，另有 `relaxed`、`original`、`delta`。

## 2. 脚本与用法

### 2.1 主脚本

- **`scripts/part2/part2_run_pyrosetta_static_relax_interface.py`**  （兼容入口仍为 `scripts/run_pyrosetta_static.py`）
  - 支持 **CSV 模式**：`--csv_path <csv>`，CSV 需含 `pdb` 列；可选 `ligand`、`receptor` 列用于界面定义（如 `A`、`B` → `A_B`）。
  - 支持 **目录模式**：`--pdb_dir <dir>`，配合 `--binder_chain`、`--target_chain` 定义界面（默认 B、A）。
  - 输出目录：`--output_dir`（必填）。  
  - **主模型与每 design 一个**：`--only_main_models` 默认 True，只保留主文件夹内的 `*_model.cif`（排除 `seed-*` 采样目录）；`--one_per_design` 为 True 时，每个顶层 design 目录只取一个结构（优先取无时间戳的 run 文件夹内文件，如 `sequence_alpaca_1PIT32_model.cif`）。
  - 其他常用参数：`--relax`、`--fixbb`、`--fixed_chain`、`--max_iter`、`--dump_pdb`、`--batch_idx`。

### 2.2 示例

```bash
# 目录模式：对 fine_clusters 下 PDB/CIF 做静态分析，界面 H_A
python scripts/run_pyrosetta_static.py \
  --pdb_dir /path/to/fine_clusters/cluster_0 \
  --output_dir /path/to/rosetta_static_out \
  --binder_chain H \
  --target_chain A \
  --batch_idx 0

# CSV 模式：CSV 含 pdb、ligand、receptor 列，先 Relax 再算界面
python scripts/run_pyrosetta_static.py \
  --csv_path /path/to/candidates.csv \
  --output_dir /path/to/rosetta_static_out \
  --relax true \
  --fixbb true \
  --fixed_chain A \
  --batch_idx 1
```

## 3. 与 Germinal / PPIFlow 的关系

- **Germinal**（`germinal/filters/pyrosetta_utils.py`）：`score_interface`、`calculate_loop_sc`、SAP、Relax 等；本脚本采用相同的 InterfaceAnalyzerMover + 可选 FastRelax 模式，界面定义方式兼容。
- **PPIFlow**（`demo_scripts/relax_complex.py`）：FastRelax + InterfaceAnalyzerMover、CSV 输入、`ligand`/`receptor`、`fixbb`/`fixed_chain`；`run_pyrosetta_static.py` 的 Relax 与 CSV 用法与之对齐。

更完整的界面指标（如 loop_sc、packstat、SAP 等）仍可通过 **protein_filter** 的 `InterfaceCalculator`（`metrics/calculators.py`）或直接使用 Germinal 的 `score_interface` 获取。

## 4. 依赖与环境

- **PyRosetta**：需已安装并可用（如 `pyrosetta`、`pyrosetta.rosetta`）。
- **pandas**：用于读写 CSV。
- 建议在专有的 PyRosetta 环境（如 `germinal` 或项目 `environment_VNAR_OP.yml` 中配置的 PyRosetta 环境）中运行。

## 5. 数据流

- **输入**：Part 1 的 `fine_clusters/` 下结构，或由 `stage1_filtering_result.json` 等构建的候选 CSV。
- **输出**：`rosetta_static_<batch_idx>.csv`，可用于按 `interface_score` 等筛选，再送入 Part 3 MD。
