# 如何读取 Parquet 文件

## Parquet 文件简介

Parquet 是一种**列式存储格式**，专为大数据分析设计，具有以下优势：

- ✅ **高效压缩**：文件大小通常比 CSV 小 5-10 倍
- ✅ **快速读取**：列式存储，支持按列查询，读取速度快
- ✅ **类型保留**：自动保留数据类型（整数、浮点数、字符串等）
- ✅ **跨平台**：支持 Python、R、Julia、Spark 等

## 读取方式

### 方式 1: 使用 Python + Pandas（推荐）

这是最常用和推荐的方式：

```python
import pandas as pd

# 读取 Parquet 文件
df = pd.read_parquet("stage1_metrics/stage1_metrics.parquet")

# 查看数据
print(df.head())  # 查看前 5 行
print(df.info())  # 查看列信息和数据类型
print(df.describe())  # 查看统计信息

# 查看特定列
print(df['external_plddt'])  # 查看 pLDDT 列
print(df[['design_name', 'external_plddt', 'pdockq']])  # 查看多列

# 筛选数据
high_plddt = df[df['external_plddt'] >= 0.8]  # 筛选 pLDDT >= 0.8
print(f"高置信度设计数量: {len(high_plddt)}")
```

**安装依赖**：
```bash
pip install pandas pyarrow
```

### 方式 2: 使用本库的工具函数

本库提供了便捷的读取函数：

```python
from protein_filter.utils import load_metrics_from_parquet

# 读取所有数据
df = load_metrics_from_parquet("stage1_metrics/stage1_metrics.parquet")

# 只读取特定设计的数据
design_names = ["design_001", "design_002", "design_003"]
df = load_metrics_from_parquet(
    "stage1_metrics/stage1_metrics.parquet",
    design_names=design_names
)
```

### 方式 3: 转换为 Excel（用于 Excel 查看）

**Excel 365（2021 及以后版本）**：
- Excel 365 可以直接打开 Parquet 文件（但功能有限）
- 推荐先转换为 CSV 或 Excel 格式

**转换为 Excel**：

```python
import pandas as pd

# 读取 Parquet
df = pd.read_parquet("stage1_metrics/stage1_metrics.parquet")

# 转换为 Excel（注意：Excel 最多支持 1,048,576 行）
df.to_excel("stage1_metrics.xlsx", index=False)

# 如果数据量很大，可以分批保存
if len(df) > 1000000:
    # 分批保存到多个 Excel 文件
    chunk_size = 1000000
    for i in range(0, len(df), chunk_size):
        chunk = df.iloc[i:i+chunk_size]
        chunk.to_excel(f"stage1_metrics_part_{i//chunk_size + 1}.xlsx", index=False)
```

**转换为 CSV**（更通用，但文件更大）：

```python
import pandas as pd

# 读取 Parquet
df = pd.read_parquet("stage1_metrics/stage1_metrics.parquet")

# 转换为 CSV
df.to_csv("stage1_metrics.csv", index=False)
```

**安装 Excel 支持**：
```bash
pip install openpyxl  # 用于写入 .xlsx 文件
```

### 方式 4: 使用 Jupyter Notebook 交互式查看

```python
import pandas as pd

# 读取数据
df = pd.read_parquet("stage1_metrics/stage1_metrics.parquet")

# 在 Jupyter 中直接显示（自动格式化表格）
df.head(20)  # 显示前 20 行

# 使用交互式表格（需要安装 qgrid）
# pip install qgrid
import qgrid
qgrid.show_grid(df, show_toolbar=True)
```

### 方式 5: 使用命令行工具

**使用 Python 命令行快速查看**：

```bash
# 快速查看前 10 行
python -c "import pandas as pd; df = pd.read_parquet('stage1_metrics/stage1_metrics.parquet'); print(df.head(10))"

# 查看统计信息
python -c "import pandas as pd; df = pd.read_parquet('stage1_metrics/stage1_metrics.parquet'); print(df.describe())"
```

**使用 parquet-tools**（需要安装）：

```bash
# 安装 parquet-tools
pip install parquet-tools

# 查看文件信息
parquet-tools schema stage1_metrics/stage1_metrics.parquet

# 查看前几行
parquet-tools head stage1_metrics/stage1_metrics.parquet
```

## 实用示例脚本

### 示例 1: 查看指标统计

```python
#!/usr/bin/env python3
"""
查看 Parquet 文件中的指标统计信息
"""

import pandas as pd
import sys

if len(sys.argv) < 2:
    print("Usage: python view_metrics.py <parquet_file>")
    sys.exit(1)

parquet_file = sys.argv[1]

# 读取数据
df = pd.read_parquet(parquet_file)

print(f"总设计数量: {len(df)}")
print(f"\n列名: {list(df.columns)}")
print(f"\n统计信息:")
print(df.describe())

# 如果有 pLDDT 列，显示分布
if 'external_plddt' in df.columns:
    print(f"\npLDDT 分布:")
    print(f"  平均值: {df['external_plddt'].mean():.3f}")
    print(f"  中位数: {df['external_plddt'].median():.3f}")
    print(f"  最小值: {df['external_plddt'].min():.3f}")
    print(f"  最大值: {df['external_plddt'].max():.3f}")
```

### 示例 2: 转换为 Excel

```python
#!/usr/bin/env python3
"""
将 Parquet 文件转换为 Excel
"""

import pandas as pd
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: python parquet_to_excel.py <parquet_file> [output_file]")
    sys.exit(1)

parquet_file = Path(sys.argv[1])
output_file = sys.argv[2] if len(sys.argv) > 2 else parquet_file.with_suffix('.xlsx')

# 读取数据
print(f"读取 {parquet_file}...")
df = pd.read_parquet(parquet_file)
print(f"共 {len(df)} 行，{len(df.columns)} 列")

# 转换为 Excel
print(f"转换为 Excel: {output_file}...")
df.to_excel(output_file, index=False)
print("完成！")
```

### 示例 3: 筛选并导出

```python
#!/usr/bin/env python3
"""
从 Parquet 文件中筛选数据并导出
"""

import pandas as pd
import sys

if len(sys.argv) < 2:
    print("Usage: python filter_metrics.py <parquet_file>")
    sys.exit(1)

parquet_file = sys.argv[1]

# 读取数据
df = pd.read_parquet(parquet_file)

# 筛选条件
filtered = df[
    (df['external_plddt'] >= 0.7) &
    (df['pdockq'] >= 0.2) &
    (df['clashes'] < 5)
]

print(f"原始数据: {len(df)} 个设计")
print(f"筛选后: {len(filtered)} 个设计")

# 导出筛选结果
output_file = "filtered_metrics.xlsx"
filtered.to_excel(output_file, index=False)
print(f"已导出到: {output_file}")
```

## Excel 兼容性说明

### Excel 版本支持

| Excel 版本 | Parquet 支持 | 推荐方式 |
|-----------|-------------|---------|
| Excel 365 (2021+) | ✅ 部分支持（可直接打开，但功能有限） | 转换为 Excel 格式 |
| Excel 2019 及更早 | ❌ 不支持 | 转换为 CSV 或 Excel 格式 |
| Excel Online | ❌ 不支持 | 转换为 CSV 或 Excel 格式 |

### 推荐工作流

1. **数据分析**：使用 Python + Pandas（最快、最灵活）
2. **查看和编辑**：转换为 Excel 格式
3. **分享数据**：转换为 CSV（最通用）

### 转换脚本

创建一个便捷的转换脚本：

```bash
#!/bin/bash
# parquet_to_excel.sh

if [ $# -lt 1 ]; then
    echo "Usage: $0 <parquet_file> [output_file]"
    exit 1
fi

PARQUET_FILE="$1"
OUTPUT_FILE="${2:-${PARQUET_FILE%.parquet}.xlsx}"

python3 << EOF
import pandas as pd
from pathlib import Path

parquet_file = Path("$PARQUET_FILE")
output_file = Path("$OUTPUT_FILE")

print(f"Reading {parquet_file}...")
df = pd.read_parquet(parquet_file)
print(f"Loaded {len(df)} rows, {len(df.columns)} columns")

print(f"Converting to Excel: {output_file}...")
df.to_excel(output_file, index=False)
print("Done!")
EOF
```

使用方法：
```bash
chmod +x parquet_to_excel.sh
./parquet_to_excel.sh stage1_metrics/stage1_metrics.parquet
```

## 常见问题

### Q1: Excel 无法打开 Parquet 文件？

**A**: Excel 2019 及更早版本不支持 Parquet。请先转换为 Excel 或 CSV 格式：

```python
import pandas as pd
df = pd.read_parquet("file.parquet")
df.to_excel("file.xlsx", index=False)  # 或 df.to_csv("file.csv", index=False)
```

### Q2: Parquet 文件太大，无法转换为 Excel？

**A**: Excel 最多支持 1,048,576 行。如果数据量更大：

1. **分批转换**：
```python
chunk_size = 1000000
for i in range(0, len(df), chunk_size):
    chunk = df.iloc[i:i+chunk_size]
    chunk.to_excel(f"part_{i//chunk_size + 1}.xlsx", index=False)
```

2. **转换为 CSV**（无行数限制）：
```python
df.to_csv("file.csv", index=False)
```

3. **使用 Python 分析**（推荐，无限制）

### Q3: 如何查看 Parquet 文件的结构？

**A**: 
```python
import pandas as pd
df = pd.read_parquet("file.parquet")
print(df.info())  # 查看列名、数据类型、非空值数量
print(df.head())  # 查看前几行数据
```

### Q4: 如何合并多个 Parquet 文件？

**A**: 使用本库的工具函数：
```python
from protein_filter.utils import merge_metrics_files

merge_metrics_files(
    ["stage1_metrics.parquet", "stage2_metrics.parquet"],
    "merged_metrics.parquet"
)
```

或使用 pandas：
```python
import pandas as pd

df1 = pd.read_parquet("file1.parquet")
df2 = pd.read_parquet("file2.parquet")
merged = pd.merge(df1, df2, on="design_name", how="outer")
merged.to_parquet("merged.parquet", index=False)
```

## 总结

- ✅ **推荐方式**：使用 Python + Pandas 读取和分析
- ✅ **Excel 查看**：先转换为 Excel 或 CSV 格式
- ✅ **大数据**：Parquet 格式最适合，Excel 有行数限制
- ✅ **跨平台**：Parquet 支持多种编程语言和工具
