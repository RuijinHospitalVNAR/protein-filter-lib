# AF3 环境兼容性说明

## 概述

本库已调整为与 **AlphaFold3 (AF3) 环境兼容**，可以直接在 AF3 环境中安装和使用，无需创建独立环境。

## 兼容性调整

### 1. 版本要求放宽

**调整前**：
```txt
numpy>=1.20.0
scipy>=1.7.0
```

**调整后**：
```txt
numpy>=1.20.0,<3.0.0  # 兼容 AF3 环境（AF3 通常使用 numpy 1.x 或 2.x）
scipy>=1.7.0
```

### 2. 可选依赖

**`mdtraj` 现在是可选依赖**：
- 如果 AF3 环境中没有 `mdtraj`，库会自动回退到 BioPython 方法
- 只影响 `pDockQ2` 和 `LIS` 计算（会使用替代实现）
- 基础 `pDockQ` 计算不受影响

## 安装方法

### 方法 1：在 AF3 环境中直接安装（推荐，支持 pDockQ2 和 LIS）

```bash
# 1. 激活 AF3 环境
conda activate af3_env  # 或您的 AF3 环境名称

# 2. 进入库目录
cd /path/to/protein_filter_lib

# 3. 安装必需依赖（pDockQ2 和 LIS 需要）
pip install biopython>=1.79 pandas>=1.3.0

# 4. 安装库本身
pip install -e .

# 5. （可选）如果需要性能优化，安装 mdtraj
pip install mdtraj>=1.9.0
# 或使用 conda
conda install -c conda-forge mdtraj
```

### 方法 2：使用 requirements.txt

```bash
# 激活 AF3 环境
conda activate af3_env

# 安装核心依赖（mdtraj 已注释，不会强制安装）
pip install -r requirements.txt

# 安装库本身
pip install -e .
```

### 方法 3：安装完整功能（包括 mdtraj）

```bash
conda activate af3_env
cd /path/to/protein_filter_lib

# 安装完整功能（包括 mdtraj）
pip install -e ".[full]"
```

## 依赖说明

### 核心依赖（必需）

| 包 | 版本要求 | AF3 兼容性 | 用途 |
|----|---------|-----------|------|
| `numpy` | >=1.20.0,<3.0.0 | ✅ 兼容（AF3 通常已安装） | 数值计算（所有功能） |
| `scipy` | >=1.7.0 | ✅ 兼容（AF3 通常已安装） | 科学计算（距离计算等） |
| `biopython` | >=1.79 | ✅ 兼容（**需要安装**） | **结构解析（pDockQ2 和 LIS 必需）** |
| `pandas` | >=1.3.0 | ✅ 兼容（**需要安装**） | **数据处理（pDockQ2 和 LIS 必需）** |

### 可选依赖

| 包 | 用途 | 如果缺失 |
|----|------|---------|
| `mdtraj` | pDockQ2 和 LIS 的性能优化 | 自动回退到 BioPython 方法（功能不受影响） |

### pDockQ2 和 LIS 的依赖说明

**pDockQ2 和 LIS 的 BioPython 替代方法需要**：
- ✅ `biopython` - **必需**（用于结构解析和坐标提取）
- ✅ `pandas` - **必需**（用于数据框操作）
- ✅ `numpy` - **必需**（AF3 环境通常已有）
- ✅ `scipy` - **必需**（用于距离计算，AF3 环境通常已有）
- ⚠️ `mdtraj` - **可选**（仅用于性能优化，缺失时使用 BioPython 方法）

## 功能影响

### 如果 mdtraj 未安装

**仍然可用的功能**：
- ✅ pLDDT 提取
- ✅ iPTM 提取
- ✅ PAE 矩阵提取
- ✅ **基础 pDockQ 计算**
- ✅ IPSAE 计算
- ✅ 碰撞检测
- ✅ 二级结构分析
- ✅ SAP 评分
- ✅ 界面分析（如果安装了 PyRosetta）

**pDockQ2 和 LIS 的完整功能**：
- ✅ **需要安装 `biopython` 和 `pandas`**（AF3 环境通常没有）
- ✅ 如果安装了这两个包，pDockQ2 和 LIS **完全可用**
- ⚠️ 如果没有 `mdtraj`，会使用 BioPython 方法（功能相同，可能稍慢）

**注意**：
- `biopython` 和 `pandas` 是 **pDockQ2 和 LIS 的必需依赖**
- 如果没有这两个包，pDockQ2 和 LIS 将无法计算
- `mdtraj` 只是性能优化，不影响功能

## 验证安装

### 检查依赖

```python
import numpy
import scipy
import Bio
import pandas
print("核心依赖已安装")

# 检查可选依赖
try:
    import mdtraj
    print("mdtraj 已安装（完整功能可用）")
except ImportError:
    print("mdtraj 未安装（使用基础功能）")
```

### 测试库功能

```python
from protein_filter import Design, ProteinFilter, FilterConfig

# 测试基本功能
design = Design(
    sequence="MKLLVL...",
    pdb_path="test.cif",
    target_chain="A",
    binder_chain="B",
)

print("库安装成功！")
```

## 常见问题

### Q1: 安装时提示 numpy 版本冲突？

**A**: AF3 环境中的 numpy 版本可能与要求不匹配。可以：

1. **检查 AF3 环境的 numpy 版本**：
   ```bash
   conda activate af3_env
   python -c "import numpy; print(numpy.__version__)"
   ```

2. **如果版本在 1.20.0-3.0.0 之间**：直接安装即可
   ```bash
   pip install -e . --no-deps  # 不安装依赖，使用 AF3 已有的
   ```

3. **如果版本不在范围内**：可能需要调整版本要求（联系开发者）

### Q2: mdtraj 安装失败？

**A**: `mdtraj` 是可选的，安装失败不影响核心功能：

```bash
# 跳过 mdtraj，只安装核心功能
pip install -e . --no-deps
pip install biopython pandas  # 只安装缺失的核心依赖
```

### Q3: 如何确认是否使用了 mdtraj？

**A**: 检查日志或代码：

```python
from protein_filter.utils.pdockq_utils import MDTRAJ_AVAILABLE
print(f"mdtraj available: {MDTRAJ_AVAILABLE}")
```

### Q4: 在 AF3 环境中安装会影响 AF3 吗？

**A**: 
- **核心依赖**（numpy, scipy）：版本要求已放宽，不会强制升级
- **新增依赖**（biopython, pandas）：AF3 通常不依赖这些，不会冲突
- **mdtraj**：可选，不安装不影响 AF3

**建议**：如果担心，可以先备份 AF3 环境：
```bash
conda create --name af3_backup --clone af3_env
```

## 推荐工作流

### 场景 1：完全兼容 AF3 环境（最安全）

```bash
# 1. 激活 AF3 环境
conda activate af3_env

# 2. 只安装缺失的核心依赖
pip install biopython pandas

# 3. 安装库（不安装依赖）
pip install -e . --no-deps

# 4. 验证
python -c "from protein_filter import Design; print('OK')"
```

### 场景 2：需要完整功能（包括 mdtraj）

```bash
# 1. 激活 AF3 环境
conda activate af3_env

# 2. 安装核心依赖
pip install biopython pandas

# 3. 尝试安装 mdtraj（如果失败可以跳过）
pip install mdtraj || echo "mdtraj 安装失败，将使用基础功能"

# 4. 安装库
pip install -e .
```

## 总结

- ✅ **已调整版本要求**：兼容 AF3 环境的 numpy/scipy 版本
- ✅ **mdtraj 可选**：缺失时自动回退，不影响核心功能
- ✅ **最小化依赖**：只添加 AF3 环境中通常没有的包（biopython, pandas）
- ✅ **向后兼容**：不影响独立环境安装

现在可以直接在 AF3 环境中使用本库了！
