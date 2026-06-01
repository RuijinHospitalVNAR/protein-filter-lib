# 指标计算与筛选分离架构

## 概述

本库实现了**指标计算**和**筛选过滤**的完全分离，使得阈值调整可以在不重新计算指标的情况下快速完成。这对于大规模设计筛选（100,000+）特别重要，因为：

1. **指标计算**（慢）：需要 PyRosetta、模型推理等耗时操作
2. **筛选过滤**（快）：只是对已计算指标的简单逻辑判断

通过将指标保存为 parquet 文件，可以：
- 一次计算，多次筛选
- 快速调整阈值，无需等待
- 方便进行阈值敏感性分析
- 支持不同筛选策略的对比

## 架构设计

### 两阶段流程

```
┌─────────────────────────────────────────────────────────────┐
│                    Stage 1: 快速指标                          │
├─────────────────────────────────────────────────────────────┤
│  1. part1/part1_compute_stage1_metrics.sh                   │
│     → 计算快速指标（pLDDT, pDockQ, clashes, SAP, IPSAE等） │
│     → 保存到 stage1_metrics.parquet                          │
│                                                              │
│  2. part1/part1_filter_stage1_metrics.sh                    │
│     → 从 stage1_metrics.parquet 读取                        │
│     → 应用阈值筛选                                           │
│     → 输出 stage1_passed_design_names.txt                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Stage 2: 精细指标                          │
├─────────────────────────────────────────────────────────────┤
│  3. part1/part1_compute_stage2_metrics.sh                   │
│     → 只对 stage1 通过的设计计算精细指标                     │
│     → 计算慢速指标（Interface 分析、A2binder等）            │
│     → 保存到 stage2_metrics.parquet                         │
│                                                              │
│  4. part1/part1_filter_stage2_metrics.sh                    │
│     → 从 stage2_metrics.parquet 读取                        │
│     → 应用阈值筛选（仅基于 stage2 指标）                     │
│     → 输出最终通过的设计                                     │
└─────────────────────────────────────────────────────────────┘
```

## 快速指标（Stage 1）

### 包含的指标

- **结构预测置信度**：`external_plddt`, `external_ptm`, `external_iptm`
- **结构质量**：`clashes`, `clashes_ca`
- **pDockQ 系列**：`pdockq`, `pdockq2`, `lis`, `lia`
- **二级结构**：`alpha_all`, `beta_all`, `loops_all`
- **SAP 评分**：`sap_score`, `cdr_sap`（已移至快速指标）
- **IPSAE**：`ipsae`, `ipsae_d0chn`, `ipsae_d0dom`（可选）

### 计算时间

约 0.1-1 秒/设计（取决于结构大小和启用的指标）

## 精细指标（Stage 2）

### 包含的指标

- **界面分析**（16个指标）：
  - `interface_dG`, `interface_dSASA`, `interface_packstat`
  - `interface_sc`, `interface_hbonds`, `interface_hydrophobicity`
  - `binder_score`, `surface_hydrophobicity`
  - 等等...
- **亲和力预测**：`a2binder_affinity`（可选）

### 计算时间

约 20-50 秒/设计（取决于启用的指标）

## 使用流程

### 步骤 1: 计算 Stage 1 指标

```bash
./scripts/part1/part1_compute_stage1_metrics.sh \
  --input-dir ./af3_predictions \
  --output-dir ./stage1_metrics \
  --metrics-file stage1_metrics.parquet \
  --enable-sap \
  --enable-ipsae
```

**输出**：
- `stage1_metrics/stage1_metrics.parquet`：所有设计的快速指标

### 步骤 2: 筛选 Stage 1（可反复调整阈值）

```bash
# 第一次筛选
./scripts/part1/part1_filter_stage1_metrics.sh \
  --metrics-file ./stage1_metrics/stage1_metrics.parquet \
  --output-dir ./stage1_filtered \
  --plddt-threshold 0.7 \
  --pdockq-threshold 0.2 \
  --top-n 1000

# 调整阈值，重新筛选（秒级完成，无需重新计算指标）
./scripts/part1/part1_filter_stage1_metrics.sh \
  --metrics-file ./stage1_metrics/stage1_metrics.parquet \
  --output-dir ./stage1_filtered_v2 \
  --plddt-threshold 0.75 \
  --pdockq-threshold 0.25 \
  --top-n 1000
```

**输出**：
- `stage1_filtered/stage1_passed.parquet`：通过筛选的设计及其指标
- `stage1_filtered/stage1_passed_design_names.txt`：设计名称列表（用于 Stage 2）

### 步骤 3: 计算 Stage 2 指标

```bash
./scripts/part1/part1_compute_stage2_metrics.sh \
  --input-dir ./af3_predictions \
  --stage1-passed ./stage1_filtered/stage1_passed_design_names.txt \
  --output-dir ./stage2_metrics \
  --metrics-file stage2_metrics.parquet \
  --enable-interface \
  --relaxer pyrosetta
```

**输出**：
- `stage2_metrics/stage2_metrics.parquet`：Stage 1 通过设计的精细指标

### 步骤 4: 筛选 Stage 2（可反复调整阈值）

```bash
# 第一次筛选
./scripts/part1/part1_filter_stage2_metrics.sh \
  --metrics-file ./stage2_metrics/stage2_metrics.parquet \
  --output-dir ./stage2_filtered \
  --interface-dg-threshold -10.0 \
  --interface-packstat-threshold 0.6

# 调整阈值，重新筛选（秒级完成）
./scripts/part1/part1_filter_stage2_metrics.sh \
  --metrics-file ./stage2_metrics/stage2_metrics.parquet \
  --output-dir ./stage2_filtered_v2 \
  --interface-dg-threshold -12.0 \
  --interface-packstat-threshold 0.65
```

**输出**：
- `stage2_filtered/stage2_passed.parquet`：最终通过的设计
- `stage2_filtered/stage2_passed_design_names.txt`：最终设计名称列表

## 优势

### 1. 时间效率

**传统方式**（每次调整阈值都重新计算）：
```
调整阈值 → 重新计算所有指标 → 筛选
100,000 设计 × 30秒 = 833小时
```

**新架构**（指标计算与筛选分离）：
```
第一次：计算指标（833小时）
后续：调整阈值 → 筛选（秒级）
```

### 2. 灵活性

- **快速迭代**：可以快速尝试不同的阈值组合
- **敏感性分析**：可以分析不同阈值对结果的影响
- **策略对比**：可以对比不同筛选策略的效果

### 3. 数据持久化

- **指标保存**：所有计算的指标都保存在 parquet 文件中
- **可追溯性**：可以查看每个设计的完整指标历史
- **可复用性**：指标文件可以在不同项目间共享

## 文件格式

### Parquet 格式

使用 parquet 格式存储指标，优势：
- **高效压缩**：文件大小小
- **快速读取**：pandas 可以快速加载
- **列式存储**：支持按列查询
- **跨平台**：支持 Python、R、Julia 等

**如何读取 Parquet 文件**：
- **Python + Pandas**（推荐）：`pd.read_parquet("file.parquet")`
- **转换为 Excel**：`df.to_excel("file.xlsx")`（注意：Excel 最多支持 1,048,576 行）
- **转换为 CSV**：`df.to_csv("file.csv")`（无行数限制，但文件更大）
- **详细说明**：参见 [如何读取 Parquet 文件](HOW_TO_READ_PARQUET.md)

### 文件结构

每个 parquet 文件包含：
- `design_name`：设计名称（主键）
- `pdb_path`：PDB 文件路径
- 各种指标列（如 `external_plddt`, `pdockq`, `interface_dG` 等）

## 最佳实践

### 1. 指标计算

- **一次性计算**：对所有设计计算一次指标，保存到 parquet
- **定期更新**：如果结构文件更新，重新计算指标
- **版本控制**：为不同版本的指标文件添加版本号

### 2. 筛选策略

- **宽松的 Stage 1**：设置相对宽松的阈值，避免过早淘汰
- **严格的 Stage 2**：在精细指标上设置严格阈值
- **多次尝试**：尝试不同的阈值组合，找到最佳平衡

### 3. 性能优化

- **并行计算**：Stage 1 和 Stage 2 的计算都可以并行化
- **批量处理**：对于超大规模，考虑分批处理
- **缓存利用**：重复使用已计算的指标文件

## 注意事项

### Stage 2 筛选

- **只基于 Stage 2 指标**：`part1_filter_stage2_metrics.sh` 只使用 `stage2_metrics.parquet` 中的指标
- **不考虑 Stage 1**：Stage 2 筛选不会参考 Stage 1 的指标
- **独立筛选**：如果需要结合 Stage 1 和 Stage 2 指标，需要手动合并两个 parquet 文件

### SAP 指标

- **已移至快速指标**：SAP 计算相对较快，已移至 Stage 1
- **可选启用**：可以通过 `--enable-sap` / `--disable-sap` 控制

### 指标文件管理

- **文件大小**：100,000 设计的指标文件约 50-100 MB（parquet 压缩后）
- **备份建议**：定期备份指标文件，避免重新计算
- **清理策略**：保留最终通过的设计，可以删除中间文件

## 示例工作流

### 完整流程示例

```bash
# 1. 计算 Stage 1 指标（一次性，耗时）
./scripts/part1/part1_compute_stage1_metrics.sh \
  --input-dir ./af3_predictions \
  --output-dir ./stage1_metrics \
  --enable-sap --enable-ipsae

# 2. 尝试不同的 Stage 1 阈值（快速，秒级）
for plddt in 0.7 0.75 0.8; do
  for pdockq in 0.2 0.25 0.3; do
    ./scripts/part1/part1_filter_stage1_metrics.sh \
      --metrics-file ./stage1_metrics/stage1_metrics.parquet \
      --output-dir ./stage1_filtered_plddt${plddt}_pdockq${pdockq} \
      --plddt-threshold $plddt \
      --pdockq-threshold $pdockq \
      --top-n 1000
  done
done

# 3. 选择最佳 Stage 1 结果，计算 Stage 2 指标（耗时）
./scripts/part1/part1_compute_stage2_metrics.sh \
  --input-dir ./af3_predictions \
  --stage1-passed ./stage1_filtered_plddt0.75_pdockq0.25/stage1_passed_design_names.txt \
  --output-dir ./stage2_metrics \
  --enable-interface

# 4. 尝试不同的 Stage 2 阈值（快速，秒级）
for dg in -10.0 -12.0 -15.0; do
  ./scripts/part1/part1_filter_stage2_metrics.sh \
    --metrics-file ./stage2_metrics/stage2_metrics.parquet \
    --output-dir ./stage2_filtered_dg${dg} \
    --interface-dg-threshold $dg \
    --interface-packstat-threshold 0.6
done
```

## 故障排除

### 问题 1: Parquet 文件无法读取

**解决方案**：
```bash
pip install pyarrow pandas
```

### 问题 2: 指标文件太大

**解决方案**：
- 使用 parquet 格式（自动压缩）
- 只保存需要的指标列
- 分批处理大规模数据

### 问题 3: Stage 2 找不到设计文件

**解决方案**：
- 确保 `--input-dir` 包含所有设计的 PDB 文件
- 检查 `stage1_passed_design_names.txt` 中的设计名称是否正确
- 确保 PDB 文件命名与设计名称匹配

## 参考

- [两阶段筛选指南](TWO_STAGE_FILTERING.md)
- [脚本使用说明](../scripts/README.md)
- [指标说明](../README.md#filter-评估系统)
