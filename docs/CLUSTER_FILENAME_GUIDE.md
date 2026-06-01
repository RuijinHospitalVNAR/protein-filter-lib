# Cluster 文件名和源数据追溯指南

## 问题

在 `fine_clusters/` 目录中，结构文件的文件名可能不是原始文件名（例如 `model_100.cif`），这会影响追溯到原始数据。

## 解决方案

### 1. 改进的文件名生成

新版本会生成包含原始路径信息的描述性文件名：

**旧格式**:
```
model_100.cif
model_101.cif
```

**新格式**:
```
gpu4_20260108_174350_RAS-P110_2908_seed-42_sample-0_model.cif
gpu4_20260109_072158_RAS-P110_6_seed-42_sample-1_model.cif
```

文件名包含：
- GPU 标识（`gpu4_20260108_174350_RAS-P110_2908`）
- Seed 和 Sample 信息（`seed-42_sample-0`）
- 原始文件名（`model`）

### 2. 符号链接

所有 cluster 文件都是**符号链接**，指向原始数据：

```bash
# 查看符号链接指向
ls -la fine_clusters/cluster_0/model_*.cif

# 输出示例：
# model_100.cif -> /mnt/share/.../gpu4_.../seed-42_sample-0/model.cif
```

### 3. 使用追溯工具

我们提供了 `find_cluster_source.py` 脚本来帮助追溯：

```bash
# 查找单个文件的源路径
python scripts/find_cluster_source.py fine_clusters/cluster_0/model_100.cif

# 查找整个簇的所有文件
python scripts/find_cluster_source.py fine_clusters/cluster_0/

# 生成完整映射表（TSV格式）
python scripts/find_cluster_source.py fine_clusters/ \
    --pdb-dir /path/to/original/pdb/dir \
    --output cluster_mapping.tsv
```

### 4. 从 cluster_info.tsv 获取信息

`fine_clusters/cluster_info.tsv` 包含每个簇的基本信息：

```tsv
cluster_id	n_structures
0	145
1	146
```

### 5. 从 stage3 结果获取完整映射

`stage3_fine_clustering.json` 包含完整的文件名映射：

```python
import json

with open('stage3_fine_clustering.json') as f:
    data = json.load(f)

# file_names 是原始相对路径列表
# fine_labels 是对应的簇标签
for label, filename in zip(data['fine_labels'], data['file_names']):
    print(f"Cluster {label}: {filename}")
```

## 最佳实践

1. **使用符号链接**：直接访问符号链接即可访问原始文件，无需复制
2. **生成映射表**：对于大量文件，使用 `find_cluster_source.py --output` 生成映射表
3. **保留原始路径**：新文件名包含足够信息，可以直接识别源数据

## 示例

```bash
# 1. 查看簇中的文件
ls fine_clusters/cluster_0/

# 2. 查看符号链接指向
readlink -f fine_clusters/cluster_0/gpu4_20260108_174350_RAS-P110_2908_seed-42_sample-0_model.cif

# 3. 使用工具脚本
python scripts/find_cluster_source.py fine_clusters/cluster_0/ \
    --pdb-dir /mnt/share/.../batch_0001_0114 \
    --output cluster_0_mapping.tsv

# 4. 查看映射表
head cluster_0_mapping.tsv
```
