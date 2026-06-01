# Stage 2 Metrics Computation 使用说明

## 概述

`part1_compute_stage2_metrics.sh` 用于计算精细指标，只对 Stage 1 通过的设计进行处理。

## 主要特性

- ✅ **只处理 Stage 1 通过的设计**：从 `stage1_filtered/stage1_passed_design_names.txt` 读取
- ✅ **支持 PyRosetta 指标**：界面分析、SAP、二级结构
- ✅ **自动检测 PyRosetta**：如果不可用会给出警告
- ✅ **支持结构松弛**：使用 PyRosetta 进行结构优化（可选）
- ✅ **支持 A2binder**：亲和力预测（可选）

## 使用步骤

### 1. 配置脚本

编辑 `scripts/part1/part1_compute_stage2_metrics.sh`，修改以下配置：

```bash
# 输入/输出路径
INPUT_DIR="/path/to/your/pdb/files"                    # PDB/CIF 文件目录
STAGE1_PASSED="./stage1_filtered/stage1_passed_design_names.txt"  # Stage 1 通过列表
OUTPUT_DIR="./stage2_metrics"                          # 输出目录

# 链配置
TARGET_CHAIN="A"                                       # 目标链 ID
BINDER_CHAIN="B"                                       # 结合子链 ID

# 结构松弛
RELAXER="pyrosetta"                                    # "none" 或 "pyrosetta"

# 指标配置
ENABLE_INTERFACE=true                                  # 界面分析（需要 PyRosetta）
ENABLE_SAP=true                                        # SAP 指标（需要 PyRosetta）
ENABLE_SECONDARY_STRUCTURE=true                       # 二级结构（需要 PyRosetta）
ENABLE_A2BINDER=false                                 # A2binder 亲和力
```

### 2. 运行脚本

```bash
cd /data/Tools/protein_filter_lib
./scripts/part1/part1_compute_stage2_metrics.sh
```

### 3. 查看结果

结果保存在：
- `stage2_metrics/stage2_metrics.parquet` - 指标数据
- `stage2_metrics/compute_stage2_metrics.log` - 运行日志

## 指标说明

### 界面分析指标（需要 PyRosetta）

如果 `ENABLE_INTERFACE=true`，会计算以下指标：

- `interface_dG` - 界面结合自由能（kcal/mol，越低越好）
- `interface_dSASA` - 界面可及表面积变化（Å²）
- `interface_packstat` - 界面包装统计（0-1）
- `interface_sc` - 界面形状互补性（0-1）
- `interface_hbonds` - 界面氢键数量
- `interface_hydrophobicity` - 界面疏水性百分比
- `binder_score` - 结合子总能量分数
- `surface_hydrophobicity` - 表面疏水性（0-1）

### SAP 指标（需要 PyRosetta）

如果 `ENABLE_SAP=true`，会计算：

- `sap_score` - SAP 总分（越低越好）
- `cdr_sap` - CDR 区域 SAP
- `hydrophobic_patches_binder` - 疏水斑块数量

### 二级结构指标（需要 PyRosetta）

如果 `ENABLE_SECONDARY_STRUCTURE=true`，会计算：

- `alpha_all` - 全部螺旋百分比
- `beta_all` - 全部折叠百分比
- `loops_all` - 全部环区百分比

### A2binder 亲和力（可选）

如果 `ENABLE_A2BINDER=true`，需要配置：

```bash
A2BINDER_MODEL_PATH="/path/to/model"
A2BINDER_DEVICE="cuda"  # 或 "cpu"
```

## PyRosetta 要求

### 检查 PyRosetta 是否可用

脚本会自动检查 PyRosetta 是否可用。如果不可用，会显示警告并询问是否继续。

### 手动检查

```bash
python3 -c "import pyrosetta; pyrosetta.init(); print('PyRosetta OK')"
```

### 安装 PyRosetta

1. 访问 https://www.pyrosetta.org/
2. 注册并获取许可证
3. 下载对应 Python 版本的 PyRosetta
4. 安装：
   ```bash
   tar -xjf PyRosetta-*.tar.bz2
   cd PyRosetta-*
   python setup.py install
   ```

## 常见问题

### Q: PyRosetta 不可用怎么办？

A: 可以禁用需要 PyRosetta 的指标：
```bash
ENABLE_INTERFACE=false
ENABLE_SAP=false
ENABLE_SECONDARY_STRUCTURE=false
```

### Q: 如何只计算部分指标？

A: 在配置中设置相应的 `ENABLE_*` 变量为 `false`。

### Q: Stage 1 通过列表格式是什么？

A: 支持两种格式：
- `.txt` 文件：每行一个设计名称
- `.parquet` 文件：包含 `design_name` 列的 parquet 文件

### Q: 结构松弛是必需的吗？

A: 不是。可以设置 `RELAXER="none"` 跳过结构松弛。但使用 `RELAXER="pyrosetta"` 可以获得更准确的指标。

## 输出文件

### stage2_metrics.parquet

包含所有计算的指标，每行一个设计，列包括：
- `design_name` - 设计名称
- `pdb_path` - PDB 文件路径
- 各种指标列（根据配置启用）

### compute_stage2_metrics.log

运行日志，包含：
- 配置信息
- 处理进度
- 错误和警告信息

## 下一步

计算完成后，运行筛选脚本：

```bash
./scripts/part1/part1_filter_stage2_metrics.sh
```

## 参考

- [README.md](README.md) - 完整文档
- [PyRosetta 官网](https://www.pyrosetta.org/) - PyRosetta 安装指南
