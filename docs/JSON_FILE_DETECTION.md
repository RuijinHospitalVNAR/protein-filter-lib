# JSON 文件识别与数据提取说明

## 概述

本软件会自动识别 AlphaFold3 输出的 JSON 文件，并从中提取 iPTM、PAE、PTM 等预测指标。整个过程是**自动的**，无需手动指定 JSON 文件路径。

## 自动识别流程

### 1. 触发时机

当创建 `Design` 对象时，如果未提供 `prediction_metrics`，系统会自动尝试提取：

```python
design = Design(
    sequence="MKLLVL...",
    pdb_path="af3_output/design_001.cif",  # 结构文件路径
    target_chain="A",
    binder_chain="B",
    # prediction_metrics=None  # 未提供，触发自动提取
)
```

### 2. 查找 JSON 文件的策略

系统会按照以下优先级查找 JSON 文件：

#### 策略 A：与结构文件同目录查找（默认）

**查找顺序**：

1. **优先查找**：`*_scores.json` 模式
   - 例如：`design_001_scores.json`
   - 这是 AlphaFold3 常见的命名模式

2. **其次查找**：任何 `.json` 文件
   - 如果目录中有多个 JSON 文件，选择第一个找到的

3. **查找位置**：与结构文件**相同的目录**
   - 例如：如果结构文件是 `af3_output/design_001.cif`
   - 则在 `af3_output/` 目录中查找 JSON 文件

**代码实现**：

```python
# 在 extract_metrics_from_af3_output() 中
output_dir = struct_file.parent  # 结构文件所在目录

# 查找 JSON 文件
json_files = list(output_dir.glob("*_scores.json"))  # 优先查找
if not json_files:
    json_files = list(output_dir.glob("*.json"))      # 其次查找任何 JSON
```

#### 策略 B：从 prediction_metrics 中获取 JSON 路径

如果 `Design` 对象创建时提供了 `prediction_metrics`，且其中包含 JSON 路径：

```python
design = Design(
    sequence="MKLLVL...",
    pdb_path="design_001.cif",
    prediction_metrics={
        "json_path": "path/to/scores.json",  # 手动指定
        # 或
        "json_file": "path/to/scores.json",
    }
)
```

#### 策略 C：IPSAE 计算时的特殊查找

在计算 IPSAE 时，如果未找到 JSON 文件，会尝试从 PAE 矩阵创建临时 JSON：

```python
# 在 IPSAECalculator 中
if json_path is None:
    # 尝试从 PAE 矩阵创建临时 JSON
    if "pae_matrix" in prediction_metrics:
        # 创建临时 JSON 文件供 ipsae.py 使用
```

## JSON 文件格式要求

### AlphaFold3 标准格式

软件期望的 JSON 文件格式（AlphaFold3 标准输出）：

```json
{
  "plddt": [95.2, 92.1, 88.5, ...],           // 每个残基的 pLDDT 分数（0-100）
  "ptm": 0.85,                                // Predicted TM-score
  "iptm": 0.78,                               // Interface Predicted TM-score
  "pae": [[2.1, 3.5, ...], [1.8, 2.9, ...]], // PAE 矩阵（二维数组）
  "confidence": 0.82,                         // 整体置信度（可选）
  "predicted_aligned_error": [...]            // 替代字段名（如果 "pae" 不存在）
}
```

### 字段说明

| 字段名 | 类型 | 说明 | 是否必需 |
|--------|------|------|---------|
| `plddt` | Array[float] | 每个残基的 pLDDT 分数（0-100） | 可选 |
| `ptm` | float | Predicted TM-score (0-1) | 可选 |
| `iptm` | float | Interface Predicted TM-score (0-1) | 可选 |
| `i_ptm` | float | 替代字段名（如果 `iptm` 不存在） | 可选 |
| `pae` | Array[Array[float]] | PAE 矩阵（二维数组，单位：Å） | **必需**（用于 IPSAE） |
| `predicted_aligned_error` | Array[Array[float]] | 替代字段名（如果 `pae` 不存在） | 可选 |
| `confidence` | float | 整体置信度 | 可选 |

## 数据提取过程

### 提取函数：`extract_metrics_from_af3_json()`

**位置**：`src/protein_filter/utils/af3_utils.py`

**提取的指标**：

```python
def extract_metrics_from_af3_json(json_path: str) -> Dict[str, Any]:
    """
    从 JSON 文件提取以下指标：
    
    1. plddt: 平均 pLDDT（归一化到 0-1）
    2. ptm: Predicted TM-score
    3. iptm: Interface Predicted TM-score
    4. pae: 平均 PAE（Å）
    5. pae_matrix: PAE 矩阵（numpy 数组）
    6. pae_max: 最大 PAE 值
    7. confidence: 整体置信度（如果存在）
    """
```

### 提取逻辑

```python
# 1. 读取 JSON 文件
with open(json_path, 'r') as f:
    data = json.load(f)

# 2. 提取 pLDDT
if 'plddt' in data:
    plddt_array = np.array(data['plddt'])
    if plddt_array.max() > 1.0:
        plddt_array = plddt_array / 100.0  # 归一化到 0-1
    metrics['plddt'] = float(np.mean(plddt_array))

# 3. 提取 PTM
if 'ptm' in data:
    metrics['ptm'] = float(data['ptm'])

# 4. 提取 iPTM（支持两种字段名）
if 'iptm' in data:
    metrics['iptm'] = float(data['iptm'])
elif 'i_ptm' in data:
    metrics['iptm'] = float(data['i_ptm'])

# 5. 提取 PAE 矩阵（支持两种字段名）
if 'pae' in data:
    pae_matrix = np.array(data['pae'])
    metrics['pae'] = float(np.mean(pae_matrix))
    metrics['pae_matrix'] = pae_matrix
elif 'predicted_aligned_error' in data:
    pae_matrix = np.array(data['predicted_aligned_error'])
    metrics['pae'] = float(np.mean(pae_matrix))
    metrics['pae_matrix'] = pae_matrix

# 6. 提取其他指标
if 'confidence' in data:
    metrics['confidence'] = float(data['confidence'])
```

## 文件命名约定

### 推荐的命名模式

为了确保自动识别，建议使用以下命名模式：

```
af3_output/
├── design_001.cif              # 结构文件
├── design_001_scores.json      # ✅ 推荐：JSON 文件（优先匹配）
├── design_002.cif
├── design_002_scores.json
└── ...
```

### 其他支持的命名

- `design_001.json` - 也会被识别
- `scores.json` - 如果只有一个 JSON 文件
- 任何 `.json` 文件 - 作为备选

### 不推荐的命名

- ❌ `design_001_data.json` - 不会优先匹配（但会被 `*.json` 匹配）
- ❌ `design_001_results.json` - 不会优先匹配（但会被 `*.json` 匹配）

## 使用示例

### 示例 1：自动识别（推荐）

```python
from protein_filter import Design

# 结构文件和 JSON 文件在同一目录
design = Design(
    sequence="MKLLVL...",
    pdb_path="af3_output/design_001.cif",  # 结构文件
    target_chain="A",
    binder_chain="B",
    # 系统会自动查找 af3_output/design_001_scores.json
)

# 提取的指标会自动存储在 design.prediction_metrics 中
print(design.prediction_metrics)
# 输出：
# {
#     'plddt': 0.85,
#     'ptm': 0.82,
#     'iptm': 0.78,
#     'pae': 3.5,
#     'pae_matrix': array([[...]]),
#     'pae_max': 12.3
# }
```

### 示例 2：手动指定 JSON 路径

```python
from protein_filter import Design

# 如果 JSON 文件在不同位置或不同名称
design = Design(
    sequence="MKLLVL...",
    pdb_path="af3_output/design_001.cif",
    target_chain="A",
    binder_chain="B",
    prediction_metrics={
        "json_path": "custom/path/to/scores.json",  # 手动指定
        # 或先提取指标
        # "iptm": 0.78,
        # "pae_matrix": np.array([...]),
    }
)
```

### 示例 3：使用脚本（自动处理）

在 `part1_compute_stage1_metrics.sh` 中，系统会自动处理：

```bash
# 脚本会自动：
# 1. 查找每个 .cif 或 .pdb 文件
# 2. 在同一目录查找对应的 JSON 文件
# 3. 提取所有指标
# 4. 计算 IPSAE 等指标

./scripts/part1_compute_stage1_metrics.sh
```

## 错误处理

### 情况 1：JSON 文件不存在

**行为**：
- 系统会记录警告，但**不会报错**
- 只从结构文件提取 pLDDT（从 B-factor 字段）
- 其他指标（iPTM、PAE）会缺失

**日志**：
```
WARNING: AF3 JSON file not found: af3_output/design_001_scores.json
```

### 情况 2：JSON 文件格式错误

**行为**：
- 系统会记录警告，但**不会报错**
- 跳过该 JSON 文件
- 只从结构文件提取 pLDDT

**日志**：
```
WARNING: Error parsing AF3 JSON file: Expecting ',' delimiter: line 5 column 10
```

### 情况 3：JSON 文件缺少某些字段

**行为**：
- 系统会提取**存在的字段**
- 缺失的字段不会出现在 `prediction_metrics` 中
- 例如：如果 JSON 中没有 `iptm`，则 `prediction_metrics` 中不会有 `iptm`

## 调试技巧

### 1. 检查 JSON 文件是否被找到

```python
from protein_filter.utils import auto_extract_af3_metrics

metrics = auto_extract_af3_metrics("af3_output/design_001.cif")
print(f"提取的指标: {list(metrics.keys())}")
```

### 2. 查看提取的指标值

```python
from protein_filter import Design

design = Design(
    sequence="MKLLVL...",
    pdb_path="af3_output/design_001.cif",
    target_chain="A",
    binder_chain="B",
)

print("提取的指标:")
for key, value in design.prediction_metrics.items():
    if key == 'pae_matrix':
        print(f"  {key}: shape={value.shape}")
    else:
        print(f"  {key}: {value}")
```

### 3. 手动指定 JSON 路径测试

```python
from protein_filter.utils import extract_metrics_from_af3_json

# 直接测试 JSON 文件
metrics = extract_metrics_from_af3_json("path/to/scores.json")
print(metrics)
```

## 常见问题

### Q1: 为什么找不到 JSON 文件？

**可能原因**：
1. JSON 文件不在结构文件同一目录
2. JSON 文件命名不符合约定（不是 `*_scores.json` 或 `*.json`）
3. JSON 文件在子目录中

**解决方案**：
- 检查文件是否在同一目录
- 使用 `prediction_metrics={"json_path": "..."}` 手动指定

### Q2: 为什么 iPTM 或 PAE 是 None？

**可能原因**：
1. JSON 文件中没有这些字段
2. JSON 文件字段名不同（如使用 `i_ptm` 而不是 `iptm`）

**解决方案**：
- 检查 JSON 文件内容
- 确认字段名是否正确

### Q3: 如何查看提取的指标？

**方法**：
```python
design = Design(...)
print(design.prediction_metrics)
```

或使用日志：
```python
import logging
logging.basicConfig(level=logging.INFO)
# 会自动输出提取的指标列表
```

## 总结

- ✅ **自动识别**：系统会自动查找与结构文件同目录的 JSON 文件
- ✅ **优先匹配**：优先查找 `*_scores.json` 模式
- ✅ **容错处理**：JSON 文件缺失或格式错误不会导致程序崩溃
- ✅ **灵活配置**：可以手动指定 JSON 路径
- ✅ **多格式支持**：支持 `iptm`/`i_ptm`、`pae`/`predicted_aligned_error` 等字段名变体
