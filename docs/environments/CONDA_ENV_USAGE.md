# Conda 环境自动激活功能使用说明

## 概述

`compute_stage2_metrics.sh` 现在支持自动激活 conda 环境，这样可以在运行时自动切换到包含 PyRosetta 的环境。

## 配置方法

### 方法 1: 使用 CONDA_ENV 配置（推荐）

在脚本配置部分设置：

```bash
# Conda 环境配置
CONDA_ENV="PyRosetta"  # 指定要激活的 conda 环境名称
```

脚本会自动：
1. 检测并初始化 conda
2. 激活指定的环境
3. 使用该环境中的 Python
4. 自动设置环境变量

### 方法 2: 手动激活环境

如果不想在脚本中自动激活，可以手动激活：

```bash
conda activate PyRosetta
./scripts/compute_stage2_metrics.sh
```

## 完整配置示例

```bash
# 输入/输出路径
INPUT_DIR="/path/to/your/pdb/files"
STAGE1_PASSED="./stage1_filtered/stage1_passed_design_names.txt"
OUTPUT_DIR="./stage2_metrics"
METRICS_FILE="stage2_metrics.parquet"

# 链配置
TARGET_CHAIN="A"
BINDER_CHAIN="B"
RELAXER="pyrosetta"

# 指标配置
ENABLE_INTERFACE=true
ENABLE_SAP=true
ENABLE_SECONDARY_STRUCTURE=true
ENABLE_A2BINDER=false

# Conda 环境配置（推荐）
CONDA_ENV="PyRosetta"  # 自动激活此环境

# PyRosetta 配置（如果环境外有 PyRosetta）
PYROSETTA_PATH=""  # 如果 PyRosetta 在环境中，留空即可
PYROSETTA_INIT=""

# Python 配置（如果设置了 CONDA_ENV，此选项会被忽略）
PYTHON_CMD=""  # 留空，使用环境中的 Python
```

## 工作原理

### 1. 环境检测

脚本会尝试找到 conda 初始化脚本：
- `$HOME/anaconda3/etc/profile.d/conda.sh`
- `/opt/conda/etc/profile.d/conda.sh`
- 从 `conda` 命令路径推断

### 2. 环境激活

```bash
# 检查环境是否存在
conda env list | grep "^${CONDA_ENV}\s"

# 激活环境
conda activate "$CONDA_ENV"
```

### 3. Python 使用

环境激活后，脚本会自动使用该环境中的 `python3`。

## 优势

### ✅ 优点

1. **自动化**: 无需手动激活环境
2. **一致性**: 确保使用正确的 Python 和依赖
3. **隔离**: 不同项目可以使用不同环境
4. **简单**: 只需设置一个环境名称

### ⚠️ 注意事项

1. **Conda 必须可用**: 脚本需要能够找到 conda 命令
2. **环境必须存在**: 指定的环境必须已创建
3. **权限**: 需要能够激活 conda 环境

## 使用场景

### 场景 1: PyRosetta 环境

```bash
CONDA_ENV="PyRosetta"
RELAXER="pyrosetta"
ENABLE_INTERFACE=true
ENABLE_SAP=true
ENABLE_SECONDARY_STRUCTURE=true
```

### 场景 2: PF 环境（不使用 PyRosetta）

```bash
CONDA_ENV="pf"
RELAXER="none"
ENABLE_INTERFACE=false
ENABLE_SAP=false
ENABLE_SECONDARY_STRUCTURE=false
```

### 场景 3: 自定义环境

```bash
CONDA_ENV="my_custom_env"
# 其他配置...
```

## 故障排除

### 问题 1: conda 命令未找到

**错误信息**:
```
Warning: conda command not found
```

**解决方案**:
1. 确保 conda 已安装
2. 手动初始化 conda：
   ```bash
   source ~/anaconda3/etc/profile.d/conda.sh
   ```
3. 或者使用完整路径：
   ```bash
   /home/supervisor/anaconda3/bin/conda env list
   ```

### 问题 2: 环境不存在

**错误信息**:
```
❌ Conda environment not found: PyRosetta
```

**解决方案**:
1. 检查环境名称是否正确：
   ```bash
   conda env list
   ```
2. 创建环境（如果需要）：
   ```bash
   conda create -n PyRosetta python=3.6 -y
   ```

### 问题 3: 环境激活失败

**错误信息**:
```
❌ Failed to activate conda environment: PyRosetta
```

**解决方案**:
1. 检查环境是否损坏
2. 尝试手动激活：
   ```bash
   conda activate PyRosetta
   ```
3. 如果手动激活也失败，可能需要重建环境

## 最佳实践

### 1. 使用环境名称（推荐）

```bash
CONDA_ENV="PyRosetta"
PYTHON_CMD=""  # 留空，自动使用环境中的 Python
```

### 2. 明确指定 Python 路径（备选）

如果不想使用自动激活：

```bash
CONDA_ENV=""  # 留空
PYTHON_CMD="/home/supervisor/anaconda3/envs/PyRosetta/bin/python3"
```

### 3. 组合使用

```bash
CONDA_ENV="PyRosetta"  # 激活环境
PYROSETTA_PATH="/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360"  # 如果需要额外的 PyRosetta 路径
```

## 示例输出

运行脚本时的输出示例：

```
==========================================
Stage 2 Metrics Computation
==========================================

Configuration:
  Input directory: /path/to/pdb/files
  Stage1 passed file: ./stage1_filtered/stage1_passed_design_names.txt
  Output directory: ./stage2_metrics
  Metrics file: stage2_metrics.parquet
  Relaxer: pyrosetta
  Conda environment: PyRosetta

Activating conda environment: PyRosetta
✅ Conda environment activated: PyRosetta
Using Python from conda environment: PyRosetta

Enabled metrics:
  - Interface analysis (requires PyRosetta)
  - SAP metrics (requires PyRosetta)
  - Secondary structure (requires PyRosetta)

Checking PyRosetta availability...
✅ PyRosetta is available

Running metrics computation...
```

## 总结

使用 `CONDA_ENV` 配置是最简单可靠的方式：

1. ✅ **设置简单**: 只需一个环境名称
2. ✅ **自动管理**: 脚本自动处理环境切换
3. ✅ **依赖隔离**: 确保使用正确的依赖版本
4. ✅ **易于维护**: 环境配置集中管理

推荐在所有需要 PyRosetta 的场景中使用此功能。
