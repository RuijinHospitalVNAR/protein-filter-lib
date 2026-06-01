# PyRosetta 环境配置指南

## 当前环境信息

根据检查，您的 PyRosetta 安装情况：

- **PyRosetta 安装路径**: `/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360/`
- **Conda 环境**: `PyRosetta` (Python 3.6.13)
- **Python 路径**: `/home/supervisor/anaconda3/envs/PyRosetta/bin/python`

## 问题分析

### 问题 1: Python 版本不兼容

- **PyRosetta 环境**: Python 3.6.13
- **protein_filter_lib 要求**: Python >= 3.8

这会导致 `protein_filter_lib` 无法在 PyRosetta 环境中运行（缺少 `dataclasses` 等特性）。

### 问题 2: PYTHONPATH 未设置

PyRosetta 安装在特定目录，需要设置 `PYTHONPATH` 才能被 Python 找到。

## 解决方案

### 方案 1: 使用更新的 Python 环境（推荐）

创建一个新的 conda 环境，安装 PyRosetta 和 protein_filter_lib：

```bash
# 创建新环境（Python 3.8+）
conda create -n protein-filter-pyrosetta python=3.10 -y
conda activate protein-filter-pyrosetta

# 安装依赖
pip install numpy scipy biopython pandas

# 设置 PyRosetta 路径
export PYTHONPATH=/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360:$PYTHONPATH

# 安装 protein_filter_lib
cd /data/Tools/protein_filter_lib
pip install --user .
```

**注意**: 如果 PyRosetta 是为 Python 3.6 编译的，可能无法在 Python 3.10 中使用。需要下载对应 Python 版本的 PyRosetta。

### 方案 2: 在 Python 3.6 环境中安装 dataclasses backport

如果必须使用 Python 3.6：

```bash
conda activate PyRosetta

# 安装 dataclasses backport（Python 3.6 需要）
pip install dataclasses

# 设置 PYTHONPATH
export PYTHONPATH=/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360:$PYTHONPATH

# 安装其他依赖
pip install numpy scipy biopython pandas

# 安装 protein_filter_lib
cd /data/Tools/protein_filter_lib
pip install --user .
```

### 方案 3: 使用脚本配置（已更新脚本支持）

修改 `compute_stage2_metrics.sh` 配置：

```bash
# PyRosetta 配置
PYROSETTA_PATH="/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360"
PYTHON_CMD="/home/supervisor/anaconda3/envs/PyRosetta/bin/python3"
```

然后运行脚本：

```bash
./scripts/compute_stage2_metrics.sh
```

## 验证配置

### 1. 检查 PyRosetta 是否可用

```bash
# 使用 PyRosetta 环境的 Python
/home/supervisor/anaconda3/envs/PyRosetta/bin/python3 -c "
import sys
sys.path.insert(0, '/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360')
import pyrosetta
pyrosetta.init()
print('✅ PyRosetta OK')
"
```

### 2. 检查 protein_filter_lib 是否可用

```bash
# 在正确的环境中
python3 -c "
import sys
sys.path.insert(0, '/data/Tools/protein_filter_lib/src')
from protein_filter.config import MetricConfig
print('✅ protein_filter_lib OK')
"
```

## 使用 compute_stage2_metrics.sh

### 方法 1: 激活环境后运行

```bash
# 激活 PyRosetta 环境
conda activate PyRosetta

# 设置 PYTHONPATH
export PYTHONPATH=/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360:$PYTHONPATH

# 运行脚本（脚本会自动使用当前环境的 Python）
cd /data/Tools/protein_filter_lib
./scripts/compute_stage2_metrics.sh
```

### 方法 2: 在脚本中配置

编辑 `scripts/compute_stage2_metrics.sh`：

```bash
# 设置这些变量
PYROSETTA_PATH="/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360"
PYTHON_CMD="/home/supervisor/anaconda3/envs/PyRosetta/bin/python3"
```

然后直接运行：

```bash
./scripts/compute_stage2_metrics.sh
```

## 推荐配置

基于您的环境，推荐配置：

```bash
# 在 compute_stage2_metrics.sh 中设置：
PYROSETTA_PATH="/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360"
PYTHON_CMD="/home/supervisor/anaconda3/envs/PyRosetta/bin/python3"
RELAXER="pyrosetta"
ENABLE_INTERFACE=true
ENABLE_SAP=true
ENABLE_SECONDARY_STRUCTURE=true
```

## 注意事项

1. **Python 版本兼容性**: 
   - 如果使用 Python 3.6，需要安装 `dataclasses` backport
   - 推荐使用 Python 3.8+ 以获得更好的兼容性

2. **PYTHONPATH 设置**:
   - 必须包含 PyRosetta 安装目录
   - 可以在脚本中设置，也可以在运行前 export

3. **环境隔离**:
   - 建议为不同项目使用不同的 conda 环境
   - 避免依赖冲突

## 故障排除

### 问题: ModuleNotFoundError: No module named 'pyrosetta'

**解决**: 设置 PYTHONPATH
```bash
export PYTHONPATH=/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360:$PYTHONPATH
```

### 问题: ModuleNotFoundError: No module named 'dataclasses'

**解决**: 安装 dataclasses backport（Python 3.6）
```bash
pip install dataclasses
```

### 问题: Python 版本不匹配

**解决**: 使用对应 Python 版本的 PyRosetta，或升级 Python 环境
