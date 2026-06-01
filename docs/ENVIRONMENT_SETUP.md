# 独立环境设置指南

## 概述

本指南说明如何创建/使用 **VNAR_OP** 等独立环境运行 pipeline。所有脚本会自动使用当前激活的 Python 环境。

## 方法 1：使用自动安装脚本（推荐）

### 快速开始（VNAR_OP，Part2/Part3 全流程）

```bash
cd /path/to/protein_filter_lib
chmod +x setup_VNAR_OP.sh
./setup_VNAR_OP.sh
```

激活环境：`conda activate VNAR_OP`。环境定义见 [environment_VNAR_OP.yml](../environment_VNAR_OP.yml)。

### 脚本功能

`setup_VNAR_OP.sh` 会创建/更新 conda 环境 **VNAR_OP**，并安装 PyRosetta 与依赖，适用于 Part2（PyRosetta）与 Part3（MD）及完整 pipeline。

## 方法 2：使用 conda 环境文件（手动）

### 步骤 1：创建环境

```bash
cd /path/to/protein_filter_lib
conda env create -f environment_VNAR_OP.yml
```

### 步骤 2：激活环境

```bash
conda activate VNAR_OP
```

### 步骤 3：验证安装

```bash
python -c "from protein_filter import ProteinFilter; print('✅ 安装成功')"
```

## 方法 3：手动创建（完全控制）

### 步骤 1：创建 conda 环境

```bash
conda create -n protein-filter-lib python=3.10 -y
conda activate protein-filter-lib
```

### 步骤 2：安装核心依赖

```bash
# 使用 conda（推荐，避免编译问题）
conda install -y -c conda-forge \
    numpy>=1.20.0,<3.0.0 \
    scipy>=1.7.0 \
    biopython>=1.79 \
    pandas>=1.3.0

# 或使用 pip
pip install numpy>=1.20.0,<3.0.0 scipy>=1.7.0 biopython>=1.79 pandas>=1.3.0
```

### 步骤 3：安装库本身

```bash
cd /path/to/protein_filter_lib
pip install -e .
```

### 步骤 4：（可选）安装性能优化包

```bash
# 尝试安装 mdtraj（如果失败可以跳过）
pip install mdtraj>=1.9.0 || echo "mdtraj 安装失败，将使用 BioPython 方法"
```

## 使用新环境运行脚本

### 重要：脚本会自动使用当前激活的环境

所有脚本使用 `#!/usr/bin/env python3`，会**自动使用当前激活的 Python 环境**，无需修改脚本。

### 运行流程

```bash
# 1. 激活环境
conda activate protein-filter-lib

# 2. 进入库目录
cd /path/to/protein_filter_lib

# 3. 运行脚本（脚本会自动使用当前环境）
./scripts/part1/part1_compute_stage1_metrics.sh
./scripts/part1/part1_filter_stage1_metrics.sh
./scripts/part1/part1_compute_stage2_metrics.sh
./scripts/part1/part1_filter_stage2_metrics.sh

# 或运行完整流程
./scripts/run_full_pipeline.sh
```

### 验证环境

```bash
# 检查 Python 路径
which python
# 应该显示：/path/to/anaconda3/envs/protein-filter-lib/bin/python

# 检查库是否可导入
python -c "from protein_filter import ProteinFilter; print('✅ 库可用')"

# 检查依赖
python -c "import numpy, scipy, Bio, pandas; print('✅ 所有依赖已安装')"
```

## 环境管理

### 查看所有环境

```bash
conda env list
```

### 删除环境

```bash
conda env remove -n protein-filter-lib
```

### 导出环境配置

```bash
conda activate protein-filter-lib
conda env export > environment_backup.yml
```

### 从备份恢复

```bash
conda env create -f environment_backup.yml
```

## 依赖说明

### 核心依赖（必需）

| 包 | 版本 | 用途 | 安装方式 |
|----|------|------|---------|
| `numpy` | >=1.20.0,<3.0.0 | 数值计算 | conda/pip |
| `scipy` | >=1.7.0 | 科学计算 | conda/pip |
| `biopython` | >=1.79 | 结构解析（pDockQ2/LIS 必需） | conda/pip |
| `pandas` | >=1.3.0 | 数据处理（pDockQ2/LIS 必需） | conda/pip |

### 可选依赖

| 包 | 版本 | 用途 | 如果缺失 |
|----|------|------|---------|
| `mdtraj` | >=1.9.0 | 性能优化 | 使用 BioPython 方法 |

## 常见问题

### Q1: 脚本找不到 `protein_filter` 模块

**原因**：未激活环境或库未安装

**解决**：
```bash
# 1. 激活环境
conda activate protein-filter-lib

# 2. 确认库已安装
pip list | grep protein-filter-lib

# 3. 如果未安装，重新安装
pip install -e /path/to/protein_filter_lib
```

### Q2: 如何在不同项目中使用不同环境？

**方法**：为每个项目创建独立环境

```bash
# 项目 1
conda create -n project1-filter python=3.10
conda activate project1-filter
pip install -e /path/to/protein_filter_lib

# 项目 2
conda create -n project2-filter python=3.10
conda activate project2-filter
pip install -e /path/to/protein_filter_lib
```

### Q3: 可以在 AF3 环境中使用吗？

**可以**，但建议使用独立环境以避免冲突。如果必须在 AF3 环境中使用，请参考 [AF3_ENVIRONMENT_COMPATIBILITY.md](./AF3_ENVIRONMENT_COMPATIBILITY.md)。

### Q4: 如何更新库？

```bash
conda activate protein-filter-lib
cd /path/to/protein_filter_lib
git pull  # 如果使用 git
pip install -e . --upgrade
```

### Q5: 环境占用空间太大？

**清理缓存**：
```bash
conda clean -a
pip cache purge
```

## 环境文件说明

### `environment_VNAR_OP.yml`

Conda 环境配置文件，包含：
- 环境名称：`VNAR_OP`
- Python 与 PyRosetta 等依赖
- 适用于 Part2/Part3 及完整 pipeline

### `setup_VNAR_OP.sh`

自动安装脚本，功能：
- 检查 conda 是否安装
- 创建/更新 VNAR_OP 环境
- 安装 PyRosetta 与依赖
- 安装库本身

## 总结

✅ **推荐方式**：使用 `setup_VNAR_OP.sh` 一键创建 VNAR_OP 环境（Part2/Part3 全流程）

✅ **脚本兼容性**：所有脚本自动使用当前激活的环境，**无需修改**

✅ **环境隔离**：独立环境不会影响其他项目或 AF3 环境

✅ **依赖管理**：主要依赖在 `environment_VNAR_OP.yml` 中定义
