# 三级AF3分析流程使用说明

## 概述

三级AF3分析流程是一个优化的抗原-抗体结合模式聚类方案，通过**AF3评分筛选 → Foldseek粗聚类 → 簇内H-A接触精细聚类**的三级策略，显著提升大规模数据集的处理效率。

## 流程架构

```
Stage 1: AF3评分筛选
  ↓ (筛选高置信度结构)
Stage 2: Foldseek整体结构粗聚类
  ↓ (按结构相似性分组)
Stage 3: 簇内H-A接触精细聚类
  ↓ (找出不同结合模式)
最终结果：结合模式聚类 + 代表结构分析
```

## 快速开始

### 方法1：命令行运行（推荐）

直接使用 Python 主入口，将 `<pdb_dir>` 替换为你的 AF3 输出目录：

```bash
cd /path/to/protein_filter_lib
python3 scripts/part1/part1_analyze_af3_three_stage.py <pdb_dir> \
  --chainA B \
  --antigen-chains A \
  --n-jobs 8
```

### 方法2：指标计算与筛选分离（适合调参）

使用 `scripts/run_full_pipeline.sh` 或分步执行 `scripts/part1/part1_compute_stage1_metrics.sh` → `part1_filter_stage1_metrics.sh` → `part1_compute_stage2_metrics.sh` → `part1_filter_stage2_metrics.sh`。详见 [METRICS_COMPUTATION_SEPARATION.md](METRICS_COMPUTATION_SEPARATION.md)。

## Stage 1：AF3评分筛选

### 默认筛选阈值（基于BindCraft/Germinal经验）

| 指标 | 阈值 | 说明 |
|------|------|------|
| **pLDDT** | ≥ 0.7 | 预测置信度 |
| **clashes** | < 5 | 原子碰撞数 |
| **pDockQ** | ≥ 0.2 | 对接质量分数 |
| **iPTM** | ≥ 0.6 | 界面预测TM-score |
| **ranking_confidence** | ≥ 0.7 | 综合评分（0.8×ipTM + 0.2×pTM） |
| **ipSAE** | ≥ 0.6 | 界面置信度分数（Dunbrack；高=高置信度，>0.6 常用作可能结合，若存在） |

### 自定义筛选阈值

```bash
python3 analyze_af3_three_stage.py \
  <pdb_dir> \
  --plddt-threshold 0.75 \
  --clashes-threshold 3 \
  --pdockq-threshold 0.25 \
  --iptm-threshold 0.65 \
  --ranking-confidence-threshold 0.75 \
  --ipsae-threshold 0.6
```

## Stage 2：Foldseek粗聚类

### 配置参数

- `--foldseek-path`: Foldseek可执行文件路径（默认：`/mnt/share/public/foldseek/bin/foldseek`）
- `--foldseek-sensitivity`: Foldseek敏感度（1-9，默认：7.5，较低值更快）
- `--min-cluster-size`: 最小粗簇大小（默认：5）

### Foldseek原生支持

- **直接使用CIF文件**：无需转换为PDB
- **高效结构比对**：基于3Di序列的结构相似性搜索
- **内存占用低**：比传统Jaccard距离矩阵方法节省90%+内存

## Stage 3：簇内H-A接触精细聚类

### 聚类方法

支持三种聚类算法：

1. **kmeans**（默认）：适合已知簇数量或需要固定簇数的情况
2. **hdbscan**：适合自动发现簇数量，能处理噪声点
3. **dbscan**：适合密度不均匀的数据

### 配置参数

- `--contact-cutoff`: 接触距离阈值（默认：5.0 Å）
- `--interface-cutoff`: 界面识别距离阈值（默认：8.0 Å）
- `--clustering-method`: 聚类方法（默认：kmeans）
- `--min-cluster-size`: 最小簇大小（默认：5）

## 输出结果

### 输出目录结构

```
<output_dir>/
├── three_stage_analysis_<timestamp>.log      # 时间戳日志
├── three_stage_analysis_latest.log           # 最新日志链接
├── stage1_filtering_result.json              # Stage 1筛选结果
├── stage2_foldseek_clustering.json           # Foldseek粗聚类结果（Stage 2 成功时）
├── stage3_fine_clustering.json               # 精细聚类结果（Stage 3 成功时）
├── three_stage_summary.json                  # 综合分析总结（流程完整完成时）
└── performance_metrics.json                  # 性能指标（成功或失败均会写入，便于对比）
```

### Stage 1结果 (`stage1_filtering_result.json`)

```json
{
  "n_total": 18000,
  "n_filtered": 3500,
  "pass_rate": 19.44,
  "filter_stats": {
    "failed_plddt": 1200,
    "failed_clashes": 800,
    "failed_pdockq": 1500,
    "failed_iptm": 2000,
    "failed_ranking_confidence": 1500,
    "failed_ipsae": 500
  },
  "metrics_summary": {
    "plddt": {"mean": 0.82, "std": 0.08, ...},
    "iptm": {"mean": 0.72, "std": 0.10, ...},
    ...
  },
  "filter_criteria": {...}
}
```

### Stage 2结果 (`stage2_foldseek_clustering.json`)

```json
{
  "n_coarse_clusters": 25,
  "cluster_sizes": {
    "0": 450,
    "1": 320,
    ...
  }
}
```

### 性能指标 (`performance_metrics.json`)

**无论流程成功或中途失败，都会写入**，便于与两阶段脚本对比、排查问题。

- **成功时**：`pipeline_status: "completed"`，包含各阶段耗时、峰值内存、时间占比等。
- **失败时**：`pipeline_status` 为 `failed_at_stage1_no_structures` 或 `failed_at_stage2_foldseek`，包含已完成阶段的性能数据及 `error_message`。

### Stage 3结果 (`stage3_fine_clustering.json`)

```json
{
  "fine_labels": [1000, 1001, 1002, ...],
  "file_names": [...],
  "metrics_summary": {
    "n_total_structures": 3500,
    "n_fine_clusters": 85,
    "n_coarse_clusters": 25
  }
}
```

## 性能优势

### 相比传统方法

| 指标 | 传统方法 | 三级流程 | 提升 |
|------|----------|----------|------|
| **内存占用** | ~100GB (N=18K) | ~10-20GB | **减少80-90%** |
| **处理时间** | 5-6小时 | 2-3小时 | **缩短50-60%** |
| **距离计算** | O(N²) 全量 | O(N²/B) 分簇 | **减少90%+** |

### 关键优化点

1. **Stage 1筛选**：从18K减少到3-5K，减少75-85%的数据量
2. **Foldseek粗聚类**：将3-5K结构分为20-50个粗簇，平均每簇100-250个结构
3. **簇内精细聚类**：每簇的距离矩阵从O(N²)降到O((N/B)²)，其中B是粗簇数

## 监控和调试

### 查看实时日志

```bash
tail -f <output_dir>/three_stage_analysis_latest.log
```

### 检查各阶段结果

```bash
# Stage 1筛选统计
cat <output_dir>/stage1_filtering_result.json | jq '.filter_stats'

# Stage 2粗簇分布
cat <output_dir>/stage2_foldseek_clustering.json | jq '.cluster_sizes'

# Stage 3精细簇数
cat <output_dir>/stage3_fine_clustering.json | jq '.metrics_summary'

# 性能指标（含 pipeline_status）
cat <output_dir>/performance_metrics.json | jq '.pipeline_status, .total_wall_clock_time_formatted, .peak_memory_mb'
```

### 两阶段 vs 三阶段性能对比

两阶段脚本（`analyze_af3_results` / `analyze_af3_full`）会将性能写入 `performance_metrics_two_stage.json`。使用对比脚本：

```bash
python3 scripts/compare_performance.py \
  --three-stage-dir /path/to/batch_xxx_three_stage_clustering \
  --two-stage-dir   /path/to/batch_xxx_clustering \
  -o comparison.json
```

可只传 `--three-stage-dir` 或 `--two-stage-dir`，缺失时跳过对应分支。`-o` 可选，用于将对比结果写出为 JSON。

## 常见问题

### Q: ranking_confidence 如何计算？

A: 标准公式为 `0.8*ipTM + 0.2*pTM`。如果只有ipTM没有pTM，则使用ipTM作为近似值。

### Q: ipSAE不存在怎么办？

A: 如果ipSAE不存在，会跳过ipSAE筛选条件，不影响其他筛选。

### Q: Foldseek 报 "No structures found" / 聚类失败怎么办？

A: 当前实现已改为**目录输入**：在临时目录下创建 `structures/`，将 CIF 符号链接为 `000000.cif`、`000001.cif` 等，再 `foldseek createdb structures/ ...`。若仍失败，请检查：
- Foldseek 路径、版本是否支持 mmCIF；
- CIF 是否含有效蛋白链、骨架原子等。
- 流程会在 Stage 2 失败时写出**部分性能指标**（`performance_metrics.json`），便于排查。

### Q: 如何调整筛选阈值？

A: 根据第一次运行的通过率和指标分布，可以适当调整：
- 通过率过低（<5%）：适当放宽1-2个阈值
- 通过率过高（>50%）：适当收紧关键阈值（如pLDDT或iPTM）

## 参数参考

### 完整命令行参数

```bash
python3 analyze_af3_three_stage.py \
  <pdb_dir> \
  --chainA H \
  --antigen-chains A \
  --output-dir <output_dir> \
  --plddt-threshold 0.7 \
  --clashes-threshold 5 \
  --pdockq-threshold 0.2 \
  --iptm-threshold 0.6 \
  --ranking-confidence-threshold 0.7 \
  --ipsae-threshold 0.6 \
  --foldseek-path /path/to/foldseek \
  --foldseek-sensitivity 7.5 \
  --min-cluster-size 5 \
  --contact-cutoff 5.0 \
  --interface-cutoff 8.0 \
  --clustering-method kmeans \
  --n-jobs 8 \
  --max-representatives 3
```

## 引用和参考

- **BindCraft**: [相关阈值经验](https://github.com/bindcraft)
- **Germinal**: [筛选策略参考](https://github.com/germinal)
- **Foldseek**: [结构相似性搜索工具](https://github.com/steineggerlab/foldseek)
- **AlphaFold3**: [预测质量指标](https://alphafold.ebi.ac.uk/)
