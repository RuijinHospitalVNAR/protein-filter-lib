# 聚类分析器后端模块

本模块包含抗原-抗体互作位置聚类分析的核心实现，用于在stage1阶段筛选符合目的结合界面的结构。

## 文件说明

- `analyzer.py`: 聚类分析器核心类，提供 `AF3ClusterAnalyzer` 类
  - 支持基于接触集的Jaccard距离进行粗聚类
  - 支持HDBSCAN、KMeans、DBSCAN等聚类算法
  - 提供自动参数估计功能

## 使用方式

本模块通过 `protein_filter.clustering` 模块集成，无需直接调用。

### 在stage1中使用

编辑 `scripts/compute_stage1_metrics.sh`：

```bash
# 启用聚类筛选
ENABLE_CLUSTERING=true

# 配置链信息
TARGET_CHAIN="A"        # 目标链（通常是抗体/受体链）
BINDER_CHAIN="B"         # 结合子链（通常是抗原链）

# 配置聚类参数
CLUSTERING_METHOD="hdbscan"              # 推荐使用hdbscan（自动参数估计）
CLUSTERING_MIN_CLUSTER_SIZE=5            # 最小簇大小（0表示自动估计）
CLUSTERING_MIN_SAMPLES=3                 # 最小样本数（0表示自动估计）
CLUSTERING_TARGET_CLUSTER=""             # 空字符串表示选择最大的簇
CLUSTERING_CONTACT_CUTOFF=5.0            # 接触距离阈值（Å）
CLUSTERING_INTERFACE_CUTOFF=8.0          # 界面原子识别距离阈值（Å）
```

运行脚本：

```bash
./scripts/compute_stage1_metrics.sh
```

## 工作原理

1. **接触信息提取**：从PDB/CIF文件中提取抗原-抗体接触信息
   - 识别界面残基（距离 < interface_cutoff）
   - 检测接触对（距离 < contact_cutoff）
   - 生成接触集（每个结构对应一个接触残基对集合）

2. **距离计算**：使用Jaccard距离计算结构间的相似性
   - Jaccard距离 = 1 - (交集大小 / 并集大小)
   - 距离越小，结合界面越相似

3. **聚类分析**：使用选定的聚类算法进行分组
   - HDBSCAN：自动参数估计，适合大数据集
   - KMeans：速度快，适合已知簇数量
   - DBSCAN：适合密度不均匀的数据

4. **簇选择**：选择目标簇（默认选择最大的簇）
   - 最大簇通常代表主要的结合模式
   - 只保留该簇中的结构进行后续分析

## 依赖要求

- numpy >= 1.20.0
- scipy >= 1.7.0
- scikit-learn >= 0.24.0
- hdbscan >= 0.8.27（可选，用于HDBSCAN聚类）
- biopython >= 1.79（用于结构解析）

## 相关文档

- [Stage1聚类分析优化说明](../docs/STAGE1_CLUSTERING_OPTIMIZATION.md)
- [聚类筛选功能说明](../docs/CLUSTERING_FILTER.md)
