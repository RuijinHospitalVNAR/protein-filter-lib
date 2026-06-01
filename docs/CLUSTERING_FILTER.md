# 抗原-抗体互作位置聚类筛选功能

## 概述

在stage1阶段，新增了基于抗原-抗体互作位置的聚类分析功能。该功能可以在计算指标前先对结构进行聚类筛选，只保留符合目的结合界面的结构进行后续分析。

## 功能特点

1. **基于接触集的Jaccard距离聚类**：使用抗原-抗体接触信息进行聚类分析
2. **多种聚类算法支持**：支持HDBSCAN、KMeans、DBSCAN三种聚类方法
3. **自动参数估计**：对于HDBSCAN和DBSCAN，可以自动估计合适的参数
4. **灵活的目标簇选择**：可以选择最大的簇或指定特定的簇ID
5. **与Alphafold3环境兼容**：所有依赖都与Alphafold3环境兼容

## 使用方法

### 1. 在part1_compute_stage1_metrics.sh中启用聚类筛选

编辑 `scripts/part1_compute_stage1_metrics.sh`，修改以下配置：

```bash
# 聚类筛选配置（在计算指标前先进行聚类筛选）
ENABLE_CLUSTERING=true                     # 启用聚类筛选
CLUSTERING_METHOD="hdbscan"                 # 聚类方法：hdbscan, kmeans, dbscan
CLUSTERING_MIN_CLUSTER_SIZE=5               # 最小簇大小（用于HDBSCAN）
CLUSTERING_MIN_SAMPLES=3                    # 最小样本数（用于HDBSCAN/DBSCAN）
CLUSTERING_TARGET_CLUSTER=""                # 目标簇ID（空字符串表示选择最大的簇）
CLUSTERING_CONTACT_CUTOFF=5.0               # 接触距离阈值（Å）
CLUSTERING_INTERFACE_CUTOFF=8.0             # 界面原子识别距离阈值（Å）
```

### 2. 配置链信息

确保正确配置了链信息：

```bash
TARGET_CHAIN="A"                            # 目标链 ID（通常是抗体链）
BINDER_CHAIN="B"                            # 结合子链 ID（通常是抗原链，可以是多个，用逗号分隔）
```

### 3. 运行脚本

```bash
./scripts/part1_compute_stage1_metrics.sh
```

脚本会：
1. 首先执行聚类分析，筛选出符合目的结合界面的结构
2. 然后只对筛选出的结构计算stage1指标
3. 保存筛选结果到 `stage1_metrics/clustering_selected_files.txt`

## 聚类方法说明

### HDBSCAN（推荐）

- **优点**：自动估计簇数量，适合大数据集
- **参数**：
  - `min_cluster_size`: 最小簇大小（设为0时自动估计）
  - `min_samples`: 最小样本数（设为0时自动估计）

### KMeans

- **优点**：适合已知簇数量的情况
- **参数**：自动根据数据规模估计簇数量

### DBSCAN

- **优点**：适合密度不均匀的数据
- **参数**：自动估计eps和min_samples

## 输出文件

聚类筛选会在 `stage1_metrics/` 目录下生成以下文件：

- `clustering_selected_files.txt`: 筛选出的结构文件列表
- `clustering_filter.log`: 聚类筛选的日志文件
- `clustering_filter.py`: 临时生成的聚类筛选脚本

## 在Alphafold3环境中安装

### 方法1：使用pip安装（推荐）

```bash
# 激活Alphafold3环境
conda activate Alphafold3

# 进入项目目录
cd /data/Tools/protein_filter_lib

# 安装核心依赖（Alphafold3环境通常已有numpy和scipy）
pip install biopython>=1.79 pandas>=1.3.0 scikit-learn>=0.24.0

# 安装聚类相关依赖（可选）
pip install hdbscan>=0.8.27 matplotlib>=3.3.0 psutil>=5.8.0

# 安装项目本身
pip install -e .
```

### 方法2：使用requirements.txt

```bash
# 激活Alphafold3环境
conda activate Alphafold3

# 进入项目目录
cd /data/Tools/protein_filter_lib

# 安装依赖（跳过Alphafold3已有的包）
pip install -r requirements.txt --no-deps
pip install biopython>=1.79 pandas>=1.3.0 scikit-learn>=0.24.0 hdbscan>=0.8.27 matplotlib>=3.3.0 psutil>=5.8.0

# 安装项目本身
pip install -e .
```

## 注意事项

1. **依赖兼容性**：
   - numpy和scipy通常在Alphafold3环境中已安装，无需重复安装
   - 如果hdbscan安装失败，可以使用kmeans或dbscan作为替代

2. **性能考虑**：
   - 对于大量结构（>1000），聚类可能需要较长时间
   - 建议先在小数据集上测试参数

3. **链配置**：
   - 确保TARGET_CHAIN和BINDER_CHAIN配置正确
   - 如果结构中的链ID不同，需要相应调整

4. **聚类失败处理**：
   - 如果聚类失败，脚本会继续使用所有文件进行计算
   - 检查 `clustering_filter.log` 了解失败原因

## 故障排除

### 问题1：聚类模块导入失败

**解决方案**：
- 确保聚类后端模块存在：`src/protein_filter/clustering/backend/analyzer.py`
- 重新安装库：`pip install -e .`

### 问题2：hdbscan安装失败

**解决方案**：
- 使用kmeans或dbscan作为替代：
  ```bash
  CLUSTERING_METHOD="kmeans"  # 或 "dbscan"
  ```

### 问题3：内存不足

**解决方案**：
- 减少并行线程数（在clustering.py中调整n_jobs参数）
- 分批处理结构文件

## 示例配置

### 示例1：使用HDBSCAN自动参数

```bash
ENABLE_CLUSTERING=true
CLUSTERING_METHOD="hdbscan"
CLUSTERING_MIN_CLUSTER_SIZE=0  # 0表示自动估计
CLUSTERING_MIN_SAMPLES=0       # 0表示自动估计
```

### 示例2：使用KMeans固定簇数

```bash
ENABLE_CLUSTERING=true
CLUSTERING_METHOD="kmeans"
# KMeans会自动估计簇数
```

### 示例3：选择特定簇

```bash
ENABLE_CLUSTERING=true
CLUSTERING_METHOD="hdbscan"
CLUSTERING_TARGET_CLUSTER="2"  # 选择簇ID为2的簇
```

## 相关文件

- `src/protein_filter/clustering.py`: 聚类筛选模块
- `scripts/part1_compute_stage1_metrics.sh`: Stage1指标计算脚本（已集成聚类筛选）
- `src/protein_filter/clustering/backend/analyzer.py`: 底层聚类分析器
