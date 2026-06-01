# PF 环境运行检查报告

**检查时间**: 2026-01-16  
**环境**: `pf` conda 环境

---

## 执行摘要

✅ **PF 环境可以运行，但需要注意 PyRosetta 配置**

- ✅ Python 版本兼容（3.10.19，满足 >= 3.8 要求）
- ✅ 核心依赖已安装（numpy, scipy, biopython, pandas）
- ✅ protein_filter_lib 已安装
- ⚠️ PyRosetta 未安装在环境中，但可以通过 PYTHONPATH 配置使用

---

## 1. 环境信息

### 1.1 Python 版本

- **版本**: Python 3.10.19
- **路径**: `/home/supervisor/anaconda3/envs/pf/bin/python`
- **兼容性**: ✅ 满足 protein_filter_lib 要求（>= 3.8）

### 1.2 已安装的包

```
biopython          1.86
numpy              2.2.6
pandas             2.3.3
protein-filter-lib 0.1.0
scipy              1.15.3
```

✅ 所有核心依赖都已安装

---

## 2. PyRosetta 状态

### 2.1 环境中的 PyRosetta

**结果**: ❌ 未安装

```
ModuleNotFoundError: No module named 'pyrosetta'
```

### 2.2 使用外部 PyRosetta

可以通过设置 PYTHONPATH 使用外部安装的 PyRosetta：

```bash
export PYTHONPATH=/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360:$PYTHONPATH
```

**注意**: 
- 外部 PyRosetta 是为 Python 3.6 编译的
- 可能无法在 Python 3.10 环境中正常运行
- 建议使用对应 Python 版本的 PyRosetta

---

## 3. 运行方式

### 方式 1: 不使用 PyRosetta 功能（推荐）

如果不需要 SAP、二级结构和界面分析指标：

```bash
# 激活 pf 环境
conda activate pf

# 编辑 compute_stage2_metrics.sh，设置：
ENABLE_INTERFACE=false
ENABLE_SAP=false
ENABLE_SECONDARY_STRUCTURE=false
RELAXER="none"

# 运行脚本
cd /data/Tools/protein_filter_lib
./scripts/compute_stage2_metrics.sh
```

### 方式 2: 使用外部 PyRosetta（需要测试）

```bash
# 激活 pf 环境
conda activate pf

# 编辑 compute_stage2_metrics.sh，设置：
PYROSETTA_PATH="/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360"
PYTHON_CMD="/home/supervisor/anaconda3/envs/pf/bin/python3"

# 运行脚本
cd /data/Tools/protein_filter_lib
./scripts/compute_stage2_metrics.sh
```

**注意**: 由于 PyRosetta 是为 Python 3.6 编译的，可能在 Python 3.10 中无法正常工作。

### 方式 3: 在 pf 环境中安装 PyRosetta（推荐，如果可用）

如果可以获得对应 Python 3.10 版本的 PyRosetta：

```bash
conda activate pf

# 下载并安装对应 Python 3.10 版本的 PyRosetta
# （需要从 PyRosetta 官网获取）

# 然后直接运行脚本
cd /data/Tools/protein_filter_lib
./scripts/compute_stage2_metrics.sh
```

---

## 4. 推荐配置

### 配置 1: 不使用 PyRosetta（最简单）

在 `compute_stage2_metrics.sh` 中：

```bash
PYTHON_CMD="/home/supervisor/anaconda3/envs/pf/bin/python3"
RELAXER="none"
ENABLE_INTERFACE=false
ENABLE_SAP=false
ENABLE_SECONDARY_STRUCTURE=false
ENABLE_A2BINDER=false  # 如果需要可以启用
```

### 配置 2: 尝试使用外部 PyRosetta

在 `compute_stage2_metrics.sh` 中：

```bash
PYROSETTA_PATH="/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360"
PYTHON_CMD="/home/supervisor/anaconda3/envs/pf/bin/python3"
RELAXER="pyrosetta"
ENABLE_INTERFACE=true
ENABLE_SAP=true
ENABLE_SECONDARY_STRUCTURE=true
```

**注意**: 需要测试 PyRosetta 是否能在 Python 3.10 中正常工作。

---

## 5. 测试步骤

### 测试 1: 基本功能（不使用 PyRosetta）

```bash
conda activate pf
cd /data/Tools/protein_filter_lib

# 测试导入
python3 -c "
import sys
sys.path.insert(0, 'src')
from protein_filter import ProteinFilter, FilterConfig, Design
print('✅ Basic functionality OK')
"
```

### 测试 2: PyRosetta 导入（如果使用外部 PyRosetta）

```bash
conda activate pf
export PYTHONPATH=/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360:$PYTHONPATH

python3 -c "
import sys
sys.path.insert(0, '/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360')
try:
    import pyrosetta
    print('✅ PyRosetta import OK')
    # 尝试初始化（可能失败）
    try:
        pyrosetta.init()
        print('✅ PyRosetta init OK')
    except Exception as e:
        print(f'⚠️  PyRosetta init failed: {e}')
except ImportError as e:
    print(f'❌ PyRosetta import failed: {e}')
"
```

---

## 6. 总结

### ✅ 可以运行的情况

1. **不使用 PyRosetta 功能**:
   - ✅ 完全兼容
   - ✅ 所有核心功能可用
   - ✅ 推荐使用此方式

2. **使用 A2binder 功能**:
   - ✅ 可以正常使用（如果配置了 A2binder）

### ⚠️ 需要注意的情况

1. **使用外部 PyRosetta**:
   - ⚠️ 需要设置 PYTHONPATH
   - ⚠️ Python 版本不匹配可能导致问题
   - ⚠️ 需要实际测试是否可用

2. **在 pf 环境中安装 PyRosetta**:
   - ✅ 如果可以获得 Python 3.10 版本的 PyRosetta，这是最佳方案

---

## 7. 建议

### 推荐方案

**方案 A: 不使用 PyRosetta 功能**（最简单可靠）
- 在 pf 环境中运行
- 禁用需要 PyRosetta 的指标
- 使用其他可用指标

**方案 B: 使用 PyRosetta conda 环境**
- 在 PyRosetta 环境中运行
- 安装 dataclasses backport（Python 3.6 需要）
- 设置 PYTHONPATH

**方案 C: 在 pf 环境中安装 PyRosetta**（最佳，如果可用）
- 获取 Python 3.10 版本的 PyRosetta
- 在 pf 环境中安装
- 直接使用

---

## 8. 快速开始

### 在 pf 环境中运行（不使用 PyRosetta）

```bash
# 1. 激活环境
conda activate pf

# 2. 编辑脚本配置
vim scripts/compute_stage2_metrics.sh
# 设置：
#   PYTHON_CMD="/home/supervisor/anaconda3/envs/pf/bin/python3"
#   ENABLE_INTERFACE=false
#   ENABLE_SAP=false
#   ENABLE_SECONDARY_STRUCTURE=false
#   RELAXER="none"

# 3. 运行脚本
./scripts/compute_stage2_metrics.sh
```

---

## 附录

### 相关文件

- 脚本: `scripts/compute_stage2_metrics.sh`
- 配置指南: `scripts/PYROSETTA_SETUP.md`
- 使用说明: `scripts/STAGE2_USAGE.md`

### 环境路径

- PF 环境: `/home/supervisor/anaconda3/envs/pf`
- PyRosetta 安装: `/data/Tools/PyRosetta4.Release.python36.ubuntu.release-360`
