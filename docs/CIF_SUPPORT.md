# CIF 文件支持说明

## 概述

本库现已支持 **mmCIF 格式**的结构文件，这是 AlphaFold3 的默认输出格式。所有核心功能都已更新，可以无缝处理 PDB 和 mmCIF 两种格式。

## 支持的功能

### ✅ 已支持 CIF 的功能

1. **结构文件读取**
   - `get_sequence_from_pdb()` - 从 CIF 文件提取序列
   - `calculate_clash_score()` - 计算 CIF 结构的碰撞分数
   - `hotspot_residues()` - 识别 CIF 结构中的热点残基

2. **指标计算**
   - pLDDT 提取（从 CIF 的 B-factor 字段）
   - pDockQ 计算
   - pDockQ2 计算
   - IPSAE 计算（通过 ipsae.py 脚本）

3. **AF3 输出处理**
   - 自动检测 CIF 文件
   - 从 AF3 输出目录提取指标
   - 支持 CIF + JSON 组合

4. **脚本支持**
   - `part1_compute_stage1_metrics.sh` - 支持 CIF 文件模式
   - `part1_compute_stage2_metrics.sh` - 支持 CIF 文件模式
   - `run_full_pipeline.sh` - 支持 CIF 文件

## 使用方法

### 基本使用

```python
from protein_filter import Design, ProteinFilter, FilterConfig

# 直接使用 CIF 文件路径
design = Design(
    sequence="MKLLVL...",
    pdb_path="af3_output/design_001.cif",  # CIF 文件
    target_chain="A",
    binder_chain="B",
)

# 库会自动识别 CIF 格式并使用相应的解析器
filter_system = ProteinFilter(config)
result = filter_system.filter(design)
```

### 脚本使用

在脚本配置中，文件模式已更新为支持 CIF：

```bash
# part1_compute_stage1_metrics.sh 和 part1_compute_stage2_metrics.sh
PDB_PATTERN="*.{pdb,cif}"  # 支持 PDB 和 CIF
```

脚本会自动查找并处理 `.pdb` 和 `.cif` 文件。

## 技术实现

### 文件类型检测

库使用文件扩展名自动检测文件类型：

```python
def _is_cif_file(file_path: str) -> bool:
    """检查文件是否为 mmCIF 格式"""
    path = Path(file_path)
    return path.suffix.lower() in ['.cif', '.mmcif']
```

### 解析器选择

根据文件类型自动选择解析器：

```python
def _get_parser(file_path: str):
    """获取适当的解析器（PDB 或 mmCIF）"""
    if _is_cif_file(file_path):
        return MMCIFParser(QUIET=True)
    else:
        return PDBParser(QUIET=True)
```

### 修改的文件

1. **`src/protein_filter/utils/pdb_utils.py`**
   - 添加 `_is_cif_file()` 和 `_get_parser()` 辅助函数
   - 更新所有函数以支持 CIF 文件

2. **`src/protein_filter/utils/pdockq_utils.py`**
   - 添加 CIF 文件检测和解析支持
   - 更新 `pdb_2_coords()` 以支持 CIF
   - 更新 `get_pdockq()` 和 `pDockQ2()` 以支持 CIF

3. **`src/protein_filter/utils/af3_utils.py`**
   - 更新文件查找逻辑，优先查找 CIF 文件（AF3 默认格式）
   - 更新 `auto_extract_af3_metrics()` 以支持 CIF

4. **`src/protein_filter/utils/ipsae_utils.py`**
   - 更新 IPSAE 计算以支持 CIF 文件

5. **`src/protein_filter/design.py`**
   - 更新文档说明支持 CIF 文件

6. **脚本文件**
   - `part1_compute_stage1_metrics.sh` - 更新文件模式匹配
   - `part1_compute_stage2_metrics.sh` - 更新文件模式匹配
   - `run_full_pipeline.sh` - 更新文档说明

## AF3 输出结构

AlphaFold3 通常输出以下文件：

```
af3_output/
├── design_001.cif          # 结构文件（mmCIF 格式）
├── design_001_scores.json  # 指标文件（PTM, iPTM, PAE 等）
├── design_002.cif
├── design_002_scores.json
└── ...
```

库会自动：
1. 检测 CIF 文件
2. 查找对应的 JSON 文件
3. 提取所有可用指标

## 注意事项

### 1. 松弛（Relaxation）

- **PyRosetta relaxer**：目前只支持 PDB 格式输入
- 如果使用 CIF 文件，建议：
  - 使用 `RELAXER="none"` 跳过松弛
  - 或先将 CIF 转换为 PDB（如果需要松弛）

### 2. 文件清理

- `clean_pdb()` 函数只处理 PDB 格式
- CIF 文件不会被修改（这是预期的行为）

### 3. 兼容性

- 所有使用 BioPython 的功能都支持 CIF
- 使用 PyRosetta 的功能可能需要 PDB 格式
- IPSAE 脚本（`ipsae.py`）原生支持 CIF 格式

## 示例

### 示例 1: 处理 AF3 CIF 输出

```python
from protein_filter import Design, ProteinFilter, FilterConfig

# AF3 输出目录结构
# af3_output/
#   ├── design_001.cif
#   └── design_001_scores.json

design = Design(
    sequence="MKLLVL...",
    pdb_path="af3_output/design_001.cif",  # CIF 文件
    target_chain="A",
    binder_chain="B",
    design_name="design_001",
)

# 库会自动：
# 1. 识别 CIF 格式
# 2. 查找并解析 design_001_scores.json
# 3. 提取所有指标
```

### 示例 2: 使用脚本处理 CIF 文件

```bash
# 1. 编辑 part1_compute_stage1_metrics.sh
INPUT_DIR="./af3_predictions"  # 包含 .cif 文件的目录
PDB_PATTERN="*.{pdb,cif}"       # 支持两种格式

# 2. 运行脚本
./scripts/part1/part1_compute_stage1_metrics.sh

# 脚本会自动查找并处理所有 .cif 文件
```

## 测试

要测试 CIF 支持，可以使用以下代码：

```python
from protein_filter.utils import get_sequence_from_pdb, calculate_clash_score

# 测试 CIF 文件读取
sequences = get_sequence_from_pdb("test.cif")
print(f"Chains: {list(sequences.keys())}")

# 测试碰撞检测
clashes = calculate_clash_score("test.cif")
print(f"Clashes: {clashes}")
```

## 总结

- ✅ **完全支持 mmCIF 格式**
- ✅ **自动文件类型检测**
- ✅ **向后兼容 PDB 格式**
- ✅ **脚本已更新支持 CIF**
- ✅ **AF3 输出自动处理**

现在可以直接使用 AlphaFold3 的 CIF 输出文件，无需转换为 PDB 格式！
