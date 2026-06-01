## De novo 设计 quick cookbook

面向场景：从**大量 AF3 预测结构**中，自动筛选出首批高置信度候选（AF3 置信度 → PyRosetta 静态物理 → 可选 MD/AMBER 动态物理）。

假设：
- 已有 AF3 预测结果目录，例如：`/data/.../af3_predictions/`，包含 `*.pdb` 和可选 `*_scores.json`。
- 已按照 `docs/ENVIRONMENT_SETUP.md` 创建并激活 **VNAR_OP** 环境。

### 步骤 0：激活环境

```bash
conda activate VNAR_OP
cd /path/to/protein_filter_lib
```

### 步骤 1：准备 FullPipelineConfig YAML

以默认 `config/full_pipeline.yaml` 为模板：

- 设置 `part1.input.af3_dir` 为 AF3 输出目录；
- 设置 `part2.input.af3_dir` 或 `part2.input.csv_path` 等；
- 设置 `part3` 段中是否启用 MD（如 `enable: true/false`、production 时长等）。

如需区分不同项目，可以复制为：

```bash
cp config/full_pipeline.yaml config/my_project.yaml
```

并在其中修改：

- AF3 目录路径；
- Stage1/Stage2 阈值（plddt/clashes/pDockQ/interface_dG 等）；
- 是否启用 Part3 以及 Part3 参数。

### 步骤 2：一键运行 De novo pipeline

```bash
# 使用默认配置（config/full_pipeline.yaml）
bash scripts/run_denovo_design.sh

# 或使用自定义配置
CONFIG=config/my_project.yaml bash scripts/run_denovo_design.sh
```

运行效果：

- Part1：从 AF3 结果中计算/加载指标，完成三阶段筛选/聚类，生成 stage1/stage2 parquet 和筛选结果；
- Part2：对通过 Part1 的结构做 PyRosetta 静态分析，输出 `rosetta_static_*.csv`；
- Part3（可选）：根据配置，对候选结构跑 MD/AMBER + MMGBSA，并汇总结果。

### 步骤 3：只跑 Part1+Part2（跳过 MD）

如果当前仅希望得到 **AF3 + PyRosetta 的静态评分**，可关闭 Part3：

```bash
RUN_PART3=0 CONFIG=config/my_project.yaml bash scripts/run_denovo_design.sh
```

此时：

- Part1/Part2 正常运行；
- 不会启动 MD/AMBER 相关脚本；
- 便于快速调整 AF3 / PyRosetta 阈值。

### 步骤 4：查看输出与结果

根据 FullPipelineConfig 中的 `output` 配置，在对应目录下查看：

- Part1 输出：stage1/stage2 parquet、`stage1_passed.parquet`、`stage2_passed.parquet`；
- Part2 输出：`rosetta_static_*.csv`；
- 如启用 Part3：AMBER 运行目录、MMGBSA 汇总 CSV。

可配合：

- [docs/PART1_AF3_AND_CLUSTERING.md](PART1_AF3_AND_CLUSTERING.md)
- [docs/PART2_PYROSETTA.md](PART2_PYROSETTA.md)
- [docs/PART3_MD.md](PART3_MD.md)

理解每一段输出的物理/统计含义。

