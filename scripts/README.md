# Filter Scripts

**环境设置**：VNAR_OP 环境由仓库根目录的 `setup_VNAR_OP.sh` 创建，推荐在根目录执行 `./setup_VNAR_OP.sh`；`scripts/setup_VNAR_OP.sh` 为兼容包装。

## 新架构：指标计算与筛选分离

**推荐使用新的分离架构**，实现指标计算和筛选的完全分离，支持快速阈值调整而无需重新计算指标。

### Part 1（AF3 评分 + 聚类）相关脚本

- 主入口：`scripts/part1/part1_analyze_af3_three_stage.py`（详见 docs/PART1_AF3_AND_CLUSTERING.md）
- `part1/part1_compute_stage1_metrics.sh`：计算快速指标并保存到 parquet 文件
- `part1/part1_filter_stage1_metrics.sh`：基于已保存的指标进行筛选
- `part1/part1_compute_stage2_metrics.sh`：计算精细指标并保存到 parquet 文件
- `part1/part1_filter_stage2_metrics.sh`：基于已保存的指标进行筛选
- `run_full_pipeline.sh`：一键运行 Part1 两阶段指标计算与筛选（自动同步配置到 part1/）

### Part 2（PyRosetta 静态分析）相关脚本

- `part2/part2_run_pyrosetta_static_relax_interface.py`：对结构做 FastRelax + InterfaceAnalyzer 打分
- `part2/part2_run_pyrosetta_batch.sh`：在 VNAR_OP 环境下批量调用 Part2（`scripts/run_pyrosetta_batch.sh` 为兼容包装）
- 详细说明：`README_PYROSETTA_BATCH.md`

### Part 3（MD + 后处理 + MM(PB/GB)SA）相关脚本

- `part3/part3_run_md_pipeline.py`：通用 Part3 配置化驱动脚本
- `part3/part3_run_amber_md_unified_relaxed_nvt310_ff14sb.sh`：AMBER 统一 100 ns NVT310K 流程脚本（de novo 默认 backend）
- `run_md_mmgbsa_rmsd.py`：旧版 AMBER+MMGBSA 驱动脚本（仍用于某些配置）
- `part3/part3_run_amber_md_31driver.py` + `AMBER/run_single.sh`：亲和力成熟示例中用于多 GPU 分配与单结构 AMBER 的后端
- `part3/part3_run_postprocess_31_amber.py`、`part3/part3_finish_relaxed_setup.sh`、`part3/part3_prepare_relaxed_inputs.py`：针对 31 结构 Part3 的辅助脚本
- `part3/part3_wait_postprocess_then_mmpbsa.sh`、`part3/part3_monitor_md_jobs.sh`：Part3 后处理与 MMPBSA 的队列/监控辅助

### 两种模式的主入口（仅此两个）

- **`run_denovo_design.sh`**：De novo design 模式一键入口（默认 Part1+Part2+Part3，可通过 RUN_PART3=0 关闭 MD）；内部调用 `part1/part1_run_denovo_orchestrator.py` 与 YAML 配置（`config/full_pipeline.yaml`）。
- **`run_optimization_pipeline.sh`**：Optimization/亲和力成熟模式主脚本（Part2 → Part3 AMBER → 后处理 → MMGBSA）。配置优先从 `config/optimizing_default.yaml` 加载，环境变量覆盖 YAML。`examples/affinity_maturation_example/run_example.sh` 为兼容入口，会转发到本脚本。

### GPU 与 CPU 核使用（run_optimization_pipeline.sh）

- **配置**：编辑 `config/optimizing_default.yaml` 中的 `af3_dir`、`example_base`、`top_n`、`production_ns`、`ntomp` 等；或通过环境变量覆盖。`CONFIG=` 可指定其它 YAML。
- **N_GPU**：不设置或 `N_GPU=0` 或 `N_GPU=auto` 时自动检测；`N_GPU=1` 单卡串行；`N_GPU=2`～`8` 多卡并行。示例：`N_GPU=8 bash scripts/run_optimization_pipeline.sh`。
- **NTOMP**：多 GPU 时每进程绑定的 CPU 核数（默认 8）。各 GPU 进程通过 `taskset` 绑定到不重叠的核区间（gpu0→0–7，gpu1→8–15，…），避免相互侵占。需保证 `NTOMP × N_GPU` ≤ 本机逻辑核数。

兼容说明：`run_full_pipeline_v2.py` 仅为兼容包装，转发至 `part1/part1_run_denovo_orchestrator.py`，不作为推荐主入口。

详见：[指标计算与筛选分离架构](../docs/METRICS_COMPUTATION_SEPARATION.md)

---

## 快速开始

### 方式 1: 一键运行（推荐用于阈值已确定）

```bash
# 1. 编辑 scripts/run_full_pipeline.sh，设置所有配置和阈值
# 2. 运行：
./scripts/run_full_pipeline.sh
```

### 方式 2: 分步运行（推荐用于阈值调整阶段）

```bash
# 1. 编辑 scripts/part1/part1_compute_stage1_metrics.sh，设置 INPUT_DIR 等配置
./scripts/part1/part1_compute_stage1_metrics.sh

# 2. 编辑 scripts/part1/part1_filter_stage1_metrics.sh，设置阈值（可反复调整）
./scripts/part1/part1_filter_stage1_metrics.sh

# 3. 编辑 scripts/part1/part1_compute_stage2_metrics.sh，设置配置
./scripts/part1/part1_compute_stage2_metrics.sh

# 4. 编辑 scripts/part1/part1_filter_stage2_metrics.sh，设置阈值（可反复调整）
./scripts/part1/part1_filter_stage2_metrics.sh
```


---

## 配置说明

**所有脚本的配置都在脚本文件顶部的"配置变量"部分**，修改后直接运行即可。

### 主要配置项

#### 路径配置
- `INPUT_DIR`: AF3 预测结果目录（包含 PDB 和 JSON 文件）
- `OUTPUT_DIR`: 输出目录
- `METRICS_FILE`: 指标文件名（.parquet 格式）

#### 链配置
- `TARGET_CHAIN`: 目标链 ID（通常为 'A'）
- `BINDER_CHAIN`: 结合子链 ID（通常为 'B'）

#### Stage 1 阈值（快速指标）
- `PLDDT_THRESHOLD`: pLDDT 阈值（>=，推荐 0.7）
- `CLASHES_THRESHOLD`: 碰撞阈值（<，推荐 5）
- `PDOCKQ_THRESHOLD`: pDockQ 阈值（>=，推荐 0.2）
- `IPTM_THRESHOLD`: iPTM 阈值（>=，0 表示不启用）
- `SAP_THRESHOLD`: SAP 阈值（<，0 表示不启用）
- `IPSAE_THRESHOLD`: IPSAE 阈值（>=，0 表示不启用）
- `TOP_N`: 保留 top N 候选进入 Stage 2（推荐 1000）

#### Stage 2 阈值（精细指标）
- `INTERFACE_DG_THRESHOLD`: 界面 dG 阈值（<，推荐 -10.0）
- `INTERFACE_PACKSTAT_THRESHOLD`: 界面 packstat 阈值（>=，推荐 0.6）
- `INTERFACE_SC_THRESHOLD`: 界面形状互补性阈值（>=，0 表示不启用）
- `A2BINDER_THRESHOLD`: A2binder 亲和力阈值（>=，0 表示不启用）

---

## 使用场景

### 场景 1: 大规模筛选（100,000+ 设计）

**推荐配置**：
- Stage 1: 快速指标（pLDDT, clashes, pDockQ, SAP, IPSAE）
- Stage 1 TOP_N: 1000-5000（保留 1%-5%）
- Stage 2: 精细指标（界面分析，可选 A2binder）

**工作流程**：
1. 编辑 `part1/part1_compute_stage1_metrics.sh`，设置 `INPUT_DIR`
2. 运行 `part1_compute_stage1_metrics.sh`（耗时，一次性）
3. 编辑 `part1/part1_filter_stage1_metrics.sh`，设置阈值和 `TOP_N`
4. 运行 `part1_filter_stage1_metrics.sh`（秒级，可反复调整）
5. 编辑 `part1/part1_compute_stage2_metrics.sh`，设置配置
6. 运行 `part1_compute_stage2_metrics.sh`（只对通过的设计）
7. 编辑 `part1/part1_filter_stage2_metrics.sh`，设置阈值
8. 运行 `part1_filter_stage2_metrics.sh`（秒级，可反复调整）

### 场景 2: 阈值已确定，一键运行

**推荐使用**：`run_full_pipeline.sh`

1. 编辑 `run_full_pipeline.sh`，设置所有配置和阈值
2. 运行：`./scripts/run_full_pipeline.sh`
3. 脚本会自动同步配置到各个子脚本并依次执行

---

## 输入文件结构

脚本期望的输入目录结构：

```
af3_predictions/
├── design_001.pdb
├── design_001_scores.json      # 可选，用于提取 PTM、iPTM、PAE
├── design_002.pdb
├── design_002_scores.json
└── ...
```

**注意**：
- PDB 文件必须存在
- JSON 文件可选，如果存在会自动提取额外指标
- 脚本会自动从 PDB 的 B-factor 字段提取 pLDDT

---

## 输出文件

### Stage 1 输出
- `stage1_metrics/stage1_metrics.parquet`: 所有设计的快速指标
- `stage1_filtered/stage1_passed.parquet`: 通过 Stage 1 筛选的设计
- `stage1_filtered/stage1_passed_design_names.txt`: 通过的设计名称列表

### Stage 2 输出
- `stage2_metrics/stage2_metrics.parquet`: Stage 1 通过设计的精细指标
- `stage2_filtered/stage2_passed.parquet`: 最终通过筛选的设计
- `stage2_filtered/stage2_passed_design_names.txt`: 最终通过的设计名称列表

---

## 性能优化建议

1. **使用两阶段筛选**：对于 10,000+ 设计，两阶段筛选可以节省大量时间

2. **调整 top-n**：根据计算资源调整
   - 资源充足：top-n = 5,000-10,000
   - 资源有限：top-n = 500-1,000

3. **跳过松弛**：Stage 1 使用 `RELAXER="none"` 可以显著加快速度

4. **阈值调整**：由于指标已保存，筛选过程秒级完成，可以反复调整阈值

---

## 常见问题

**Q: 如何调整阈值？**  
A: 编辑对应的 `filter_stage*.sh` 脚本，修改阈值变量，然后重新运行。由于指标已保存，筛选过程秒级完成。

**Q: 如何只运行某个阶段？**  
A: 直接运行对应的脚本即可，例如：`./scripts/part1/part1_compute_stage1_metrics.sh`

**Q: 如何查看指标文件内容？**  
A: 使用 Python pandas 读取 parquet 文件：
```python
import pandas as pd
df = pd.read_parquet('stage1_metrics/stage1_metrics.parquet')
print(df)
```

**Q: 如何修改指标计算配置？**  
A: 编辑对应的 `compute_stage*.sh` 脚本，修改 `ENABLE_*` 变量。

**Q: 脚本运行失败怎么办？**  
A: 查看日志文件：
- Stage 1: `./stage1_metrics/compute_stage1_metrics.log`
- Stage 2: `./stage2_metrics/compute_stage2_metrics.log`
检查错误信息并修复配置。

---

## 注意事项

1. **序列提取**: 脚本中的序列是占位符，实际使用时需要：
   - 从 PDB 文件提取序列
   - 或提供序列文件映射
   - 或修改脚本添加序列提取逻辑

2. **并行处理**: 当前版本使用单进程，如需并行化可以：
   - 修改脚本添加并行处理
   - 或使用 GNU parallel 等工具

3. **内存使用**: 大规模筛选时注意内存使用，可以：
   - 使用批处理模式
   - 或分批处理不同目录

---

## 更多信息

- [主 README](../README.md) - 项目主文档
- [指标计算与筛选分离架构](../docs/METRICS_COMPUTATION_SEPARATION.md) - 架构详细说明
- [两阶段筛选指南](../docs/TWO_STAGE_FILTERING.md) - 两阶段策略原理
