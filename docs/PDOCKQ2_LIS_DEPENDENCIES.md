# pDockQ2 和 LIS 依赖说明

## 概述

pDockQ2 和 LIS 计算需要以下依赖包。这些包与 AF3 环境兼容，可以直接安装。

## 必需依赖

### 1. BioPython (`biopython`)

**用途**：
- 解析 PDB/CIF 结构文件
- 提取原子坐标
- 计算链间距离
- 提取界面残基

**AF3 兼容性**：✅ **完全兼容**

**安装**：
```bash
conda activate af3_env
pip install biopython>=1.79
# 或使用 conda
conda install -c conda-forge biopython
```

**在代码中的使用**：
```python
from Bio.PDB import PDBParser, MMCIFParser

# 解析结构文件
parser = PDBParser(QUIET=True)  # 或 MMCIFParser
structure = parser.get_structure("protein", pdb_path)

# 提取坐标和计算距离
for residue in structure[0][chain]:
    ca_coord = residue["CA"].coord
    # ...
```

### 2. Pandas (`pandas`)

**用途**：
- 存储和操作 pDockQ2 计算结果
- 数据框操作（DataFrame）
- 链特异性指标的组织

**AF3 兼容性**：✅ **完全兼容**

**安装**：
```bash
conda activate af3_env
pip install pandas>=1.3.0
# 或使用 conda
conda install -c conda-forge pandas
```

**在代码中的使用**：
```python
import pandas as pd

# 创建 DataFrame 存储结果
df = pd.DataFrame()
df["ifpae_norm"] = ifpae_norm
df["ifplddt"] = ifplddt
df["pmidockq"] = sigmoid(df.prot.values, *fitpopt)
```

### 3. NumPy (`numpy`)

**用途**：
- 数组操作
- PAE 矩阵处理
- 数值计算

**AF3 兼容性**：✅ **AF3 环境通常已安装**

**检查**：
```bash
python -c "import numpy; print(numpy.__version__)"
```

### 4. SciPy (`scipy`)

**用途**：
- 距离计算（`scipy.spatial.distance.pdist`）
- 矩阵操作（`squareform`）

**AF3 兼容性**：✅ **AF3 环境通常已安装**

**检查**：
```bash
python -c "import scipy; print(scipy.__version__)"
```

## 可选依赖

### mdtraj（可选，用于性能优化）

**用途**：
- 加速接触图计算（`_calculate_contact_map`）
- 更高效的结构解析

**AF3 兼容性**：⚠️ **可能安装失败**（需要编译）

**如果缺失**：
- 自动使用 BioPython 替代方法
- 功能完全相同，可能稍慢
- **不影响 pDockQ2 和 LIS 的计算结果**

**安装（可选）**：
```bash
conda activate af3_env
pip install mdtraj>=1.9.0
# 或使用 conda（推荐，避免编译问题）
conda install -c conda-forge mdtraj
```

## 完整安装步骤（AF3 环境）

### 步骤 1：安装必需依赖

```bash
# 激活 AF3 环境
conda activate af3_env

# 安装 pDockQ2 和 LIS 的必需依赖
pip install biopython>=1.79 pandas>=1.3.0

# 验证安装
python -c "import Bio; import pandas; print('OK')"
```

### 步骤 2：安装库本身

```bash
cd /path/to/protein_filter_lib
pip install -e .
```

### 步骤 3：（可选）安装性能优化包

```bash
# 尝试安装 mdtraj（如果失败可以跳过）
pip install mdtraj>=1.9.0 || echo "mdtraj 安装失败，将使用 BioPython 方法"
```

## 功能验证

### 测试 pDockQ2 和 LIS

```python
from protein_filter import Design, ProteinFilter, FilterConfig
from protein_filter.utils.pdockq_utils import pDockQ2, calculate_lis
import numpy as np

# 创建测试设计
design = Design(
    sequence="MKLLVL...",
    pdb_path="test.cif",
    target_chain="A",
    binder_chain="B",
)

# 模拟 PAE 矩阵
pae_matrix = np.random.rand(100, 100) * 10

# 测试 pDockQ2
try:
    pdockq2_df, chain_specific = pDockQ2("test.cif", pae_matrix)
    print("pDockQ2 计算成功！")
    print(pdockq2_df)
except Exception as e:
    print(f"pDockQ2 计算失败: {e}")

# 测试 LIS
try:
    lis_metrics = calculate_lis("test.cif", pae_matrix)
    print("LIS 计算成功！")
    print(lis_metrics.keys())
except Exception as e:
    print(f"LIS 计算失败: {e}")
```

## 依赖检查脚本

创建一个检查脚本 `check_dependencies.py`：

```python
#!/usr/bin/env python3
"""检查 pDockQ2 和 LIS 的依赖"""

import sys

deps = {
    "numpy": "数值计算",
    "scipy": "距离计算",
    "Bio": "结构解析（必需）",
    "pandas": "数据处理（必需）",
    "mdtraj": "性能优化（可选）",
}

missing = []
optional_missing = []

for dep, desc in deps.items():
    try:
        if dep == "Bio":
            import Bio
            print(f"✅ {dep:10} - {desc}")
        elif dep == "mdtraj":
            import mdtraj
            print(f"✅ {dep:10} - {desc} (已安装，性能优化可用)")
        else:
            __import__(dep)
            print(f"✅ {dep:10} - {desc}")
    except ImportError:
        if dep == "mdtraj":
            optional_missing.append(dep)
            print(f"⚠️  {dep:10} - {desc} (缺失，将使用 BioPython 方法)")
        else:
            missing.append(dep)
            print(f"❌ {dep:10} - {desc} (缺失，需要安装)")

print("\n" + "="*50)
if missing:
    print(f"❌ 缺失必需依赖: {', '.join(missing)}")
    print(f"   安装命令: pip install {' '.join(missing)}")
    sys.exit(1)
elif optional_missing:
    print(f"✅ 所有必需依赖已安装")
    print(f"⚠️  可选依赖缺失: {', '.join(optional_missing)} (不影响功能)")
    sys.exit(0)
else:
    print(f"✅ 所有依赖已安装（包括性能优化包）")
    sys.exit(0)
```

## 总结

### pDockQ2 和 LIS 的必需依赖

| 包 | 是否必需 | AF3 兼容性 | 安装命令 |
|----|---------|-----------|---------|
| `biopython` | ✅ **必需** | ✅ 兼容 | `pip install biopython` |
| `pandas` | ✅ **必需** | ✅ 兼容 | `pip install pandas` |
| `numpy` | ✅ **必需** | ✅ AF3 通常已有 | 通常无需安装 |
| `scipy` | ✅ **必需** | ✅ AF3 通常已有 | 通常无需安装 |
| `mdtraj` | ⚠️ **可选** | ⚠️ 可能安装失败 | `pip install mdtraj` 或跳过 |

### 快速安装（AF3 环境）

```bash
conda activate af3_env
pip install biopython pandas
pip install -e /path/to/protein_filter_lib
```

**完成！** pDockQ2 和 LIS 现在可以在 AF3 环境中使用了。
