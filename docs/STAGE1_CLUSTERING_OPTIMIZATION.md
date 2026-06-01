# Stage1 聚类分析优化说明

## 概述

本次优化实现两个目标：

1. **Stage1聚类分析集成**：集成聚类分析器后端，在计算指标前先进行聚类筛选，只保留符合目的结合界面的结构。
2. **Alphafold3环境兼容性**：确保软件可在Alphafold3环境中直接运行。

## 主要改进

### 1. 聚类功能集成

#### 1.1 优化了 `src/protein_filter/clustering.py`

- ✅ 改进了聚类后端模块的导入机制，使用标准Python包导入
- ✅ 添加了hdbscan可用性检查，如果不可用会自动回退到kmeans
- ✅ 改进了DBSCAN的距离矩阵计算，增加了fallback机制
- ✅ 优化了错误处理和日志输出

#### 1.2 更新了 `scripts/part1/part1_compute_stage1_metrics.sh`

- ✅ 添加了详细的中文说明，解释聚类功能的作用
- ✅ 改进了聚类步骤的输出信息，更清晰地显示配置和结果
- ✅ 优化了错误处理，即使聚类失败也能继续处理所有文件

### 2. 环境与安装

#### 2.1 推荐环境（VNAR_OP）

- 当前推荐使用 **VNAR_OP** 环境运行 Part2/Part3 及全流程：`./setup_VNAR_OP.sh`，见 [environment_VNAR_OP.yml](../environment_VNAR_OP.yml)。
- 若仅跑 Part1（AF3 聚类），可在任意 Python 环境中安装依赖后直接运行 `analyze_af3_three_stage.py` 或 `scripts/run_full_pipeline.sh`。

#### 2.2 创建了环境检测脚本 `scripts/check_environment.py`

- ✅ 检查Python版本兼容性
- ✅ 检查 conda 环境（当前激活的环境）
- ✅ 检查所有必需和可选依赖
- ✅ 检查聚类后端模块
- ✅ 检查protein_filter模块的导入

## 使用方法

### 步骤1：环境安装

```bash
# 方法1：使用 VNAR_OP 环境（推荐，Part2/Part3 全流程）
cd /path/to/protein_filter_lib
./setup_VNAR_OP.sh
conda activate VNAR_OP

# 方法2：仅 Part1（AF3 聚类）时在现有环境中安装
conda activate your_env
pip install biopython pandas scikit-learn hdbscan  # 可选：matplotlib, psutil
pip install -e .
```

### 步骤2：检查环境配置

```bash
# 运行环境检测脚本
python scripts/check_environment.py
```

### 步骤3：配置并运行stage1聚类分析

编辑 `scripts/part1/part1_compute_stage1_metrics.sh`：

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
./scripts/part1/part1_compute_stage1_metrics.sh
```

## 工作流程

当启用聚类筛选时，stage1的工作流程如下：

```
1. 加载所有结构文件
   ↓
2. 执行抗原-抗体互作位置聚类分析
   - 提取接触信息
   - 计算Jaccard距离
   - 执行聚类（HDBSCAN/KMeans/DBSCAN）
   - 选择目标簇（默认选择最大的簇）
   ↓
3. 筛选出符合目的结合界面的结构
   - 保存到 clustering_selected_files.txt
   ↓
4. 只对筛选出的结构计算stage1指标
   - pLDDT, iPTM
   - 碰撞检测
   - pDockQ系列
   - 二级结构
   - SAP, IPSAE等
   ↓
5. 保存指标到 stage1_metrics.parquet
```

## 聚类方法选择

### HDBSCAN（推荐）

- **优点**：自动参数估计，适合大数据集，能识别噪声点
- **适用场景**：结构数量较多（>50），不确定簇数量
- **参数**：`min_cluster_size`, `min_samples`（可设为0自动估计）

### KMeans

- **优点**：速度快，适合已知簇数量的情况
- **适用场景**：结构数量中等，已知大概有几个结合模式
- **参数**：自动估计簇数（基于样本数）

### DBSCAN

- **优点**：能识别任意形状的簇，适合密度不均匀的数据
- **适用场景**：结合界面模式复杂，密度不均匀
- **参数**：自动估计`eps`和`min_samples`

## 输出文件

聚类筛选后，会在输出目录生成以下文件：

- `clustering_selected_files.txt`: 筛选出的结构文件列表
- `clustering_filter.log`: 聚类过程的详细日志
- `stage1_metrics.parquet`: 只包含筛选结构的指标数据

## 故障排除

### 问题1：聚类模块导入失败

**症状**：`ImportError: cannot import name 'AF3ClusterAnalyzer'`

**解决方案**：
1. 检查聚类后端模块是否存在：`ls src/protein_filter/clustering/backend/analyzer.py`
2. 重新安装库：`pip install -e .`
3. 检查Python路径是否正确

### 问题2：hdbscan不可用

**症状**：`ImportError: No module named 'hdbscan'`

**解决方案**：
1. 安装hdbscan：`pip install hdbscan>=0.8.27`
2. 或者改用kmeans：设置`CLUSTERING_METHOD="kmeans"`

### 问题3：聚类结果为空

**症状**：`clustering_selected_files.txt`为空或只有很少文件

**可能原因**：
1. 接触距离阈值太小，导致没有足够的接触信息
2. 最小簇大小设置太大
3. 所有结构分散在不同簇中

**解决方案**：
1. 增大`CLUSTERING_CONTACT_CUTOFF`（如从5.0改为6.0）
2. 减小`CLUSTERING_MIN_CLUSTER_SIZE`（如从5改为3）
3. 检查日志文件了解聚类详情

### 问题4：在Alphafold3环境中安装失败

**症状**：某些依赖包安装失败

**解决方案**：
1. 运行环境检测：`python scripts/check_environment.py`
2. 查看具体缺失的依赖
3. 手动安装缺失的包：`pip install <package_name>`
4. 如果numpy/scipy版本冲突，可能需要使用conda安装：`conda install numpy scipy`

## 性能优化建议

1. **大数据集**：如果结构数量>1000，建议启用聚类筛选以减少计算量
2. **并行处理**：聚类分析会自动使用多线程（`n_jobs=-1`表示使用所有CPU核心）
3. **内存管理**：如果内存不足，可以减小`CLUSTERING_MIN_CLUSTER_SIZE`或使用KMeans

## 相关文档

- [聚类筛选功能说明](CLUSTERING_FILTER.md)
- [AF3环境兼容性说明](AF3_ENVIRONMENT_COMPATIBILITY.md)
- [聚类后端模块说明](../src/protein_filter/clustering/backend/README.md)

## 更新日志

### 2024-01-XX

- ✅ 优化了clustering模块结构，将后端代码整合到标准包结构中
- ✅ 推荐使用 setup_VNAR_OP.sh / VNAR_OP 环境（见 ENVIRONMENT_SETUP.md）
- ✅ 创建了check_environment.py环境检测脚本
- ✅ 改进了part1_compute_stage1_metrics.sh 的聚类功能说明和错误处理
