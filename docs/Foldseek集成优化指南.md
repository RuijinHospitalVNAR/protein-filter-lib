# Foldseek集成优化指南：大幅缩短聚类分析时间

## 📊 当前状况分析

### 当前任务耗时
- **总耗时**：约4.5-5.5小时
- **主要瓶颈**：
  1. 文件加载和处理：4-4.5小时（18,000个CIF文件）
  2. 距离矩阵计算：30-60分钟
  3. 聚类计算：10-30分钟

### Foldseek优势
- ✅ **速度极快**：3Di序列比对，比Jaccard距离快100-1000倍
- ✅ **内存占用低**：不需要存储完整结构对象
- ✅ **预筛选高效**：快速找到相似结构对

---

## 🎯 优化方案：Foldseek预筛选 + Jaccard精聚类

### 策略
使用Foldseek快速预筛选相似结构，只对相似结构对计算Jaccard距离

### 流程对比

**当前流程**：
```
1. 加载所有文件（4-4.5小时）
   ↓
2. 提取接触集（包含在步骤1）
   ↓
3. 计算稀疏Jaccard距离矩阵（30-60分钟）
   ↓
4. 聚类（10-30分钟）
```

**优化后流程**：
```
1. Foldseek快速搜索（5-10分钟）
   → 找到每个结构的top-K相似结构
   ↓
2. 只加载Foldseek找到的相似结构对（1-1.5小时）
   → 大幅减少需要处理的结构对
   ↓
3. 计算Jaccard距离（仅对相似对，20-30分钟）
   ↓
4. 稀疏图聚类（10-20分钟）
```

### 预期效果
- **总耗时**：从4.5-5.5小时 → **1.5-2小时**（缩短**65-75%**）
- **内存**：基本不变（已优化）
- **精度**：保持高精度（基于接触集的Jaccard距离）

---

## 💻 实施步骤

### 步骤1：确认Foldseek可用

```bash
# Foldseek已安装在：
/mnt/share/public/foldseek/bin/foldseek

# 测试可用性
/mnt/share/public/foldseek/bin/foldseek --version
```

### 步骤2：修改代码集成Foldseek预筛选

需要修改的主要位置：

#### 2.1 修改 `perform_coarse_clustering()` 方法

在 `src/protein_filter/clustering/backend/analyzer.py` 中：

```python
def perform_coarse_clustering(self, method='hdbscan', distance_metric=None, 
                              use_foldseek_prescreening=True, **kwargs):
    """
    第一阶段：基于接触集的粗聚类
    
    新增参数：
    - use_foldseek_prescreening: 是否使用Foldseek预筛选（默认True）
    """
    # ... 现有代码 ...
    
    if use_foldseek_prescreening and len(self.contact_sets) > 1000:
        logger.info("使用Foldseek预筛选优化距离矩阵计算")
        # 使用Foldseek预筛选
        foldseek_neighbors = self._foldseek_prescreening_coarse(**kwargs)
        # 只对Foldseek找到的相似对计算Jaccard距离
        D = self.jaccard_distance_matrix_with_foldseek(
            self.contact_sets,
            foldseek_neighbors,
            **kwargs
        )
    else:
        # 原有逻辑
        use_sparse = len(self.contact_sets) > 1000
        # ... 现有代码 ...
```

#### 2.2 添加 `_foldseek_prescreening_coarse()` 方法

```python
def _foldseek_prescreening_coarse(self, k_neighbors=100, **kwargs):
    """
    使用Foldseek进行粗聚类预筛选
    
    返回：邻居矩阵（sparse matrix或dict）
    """
    import subprocess
    import tempfile
    from pathlib import Path
    
    logger.info(f"Foldseek预筛选：为每个结构找top-{k_neighbors}相似结构")
    
    n_structures = len(self.file_names)
    neighbor_dict = {}  # {(i, j): True} 格式
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # 步骤1：准备结构文件（批量转换CIF到PDB）
        logger.info("准备结构文件用于Foldseek...")
        structure_files = self._prepare_all_structures_for_foldseek(temp_path)
        
        # 步骤2：创建Foldseek数据库
        logger.info("创建Foldseek数据库...")
        database_path = temp_path / "structures_db"
        self._create_foldseek_database(structure_files, database_path, **kwargs)
        
        # 步骤3：运行Foldseek搜索
        logger.info(f"运行Foldseek搜索（k={k_neighbors}）...")
        foldseek_results = self._run_foldseek_search(
            database_path, database_path, temp_path, k_neighbors, **kwargs
        )
        
        # 步骤4：解析结果
        logger.info("解析Foldseek结果...")
        neighbor_dict = self._parse_foldseek_results_for_coarse(
            foldseek_results, n_structures, k_neighbors
        )
    
    logger.info(f"Foldseek预筛选完成：找到 {len(neighbor_dict)} 个相似结构对")
    return neighbor_dict
```

#### 2.3 添加 `jaccard_distance_matrix_with_foldseek()` 方法

```python
def jaccard_distance_matrix_with_foldseek(self, contact_sets, foldseek_neighbors, **kwargs):
    """
    使用Foldseek预筛选结果计算Jaccard距离矩阵
    
    只计算Foldseek找到的相似结构对的距离
    """
    from scipy.sparse import dok_matrix
    import numpy as np
    
    N = len(contact_sets)
    D_sparse = dok_matrix((N, N), dtype=np.float32)
    
    # 只计算Foldseek找到的相似对
    for (i, j) in foldseek_neighbors.keys():
        if i < N and j < N:
            distance = self._jaccard_distance(contact_sets[i], contact_sets[j])
            D_sparse[i, j] = distance
            D_sparse[j, i] = distance  # 对称性
    
    # 对角线设为0
    for i in range(N):
        D_sparse[i, i] = 0.0
    
    return D_sparse
```

### 步骤3：配置Foldseek路径

在 `analyze_af3_full.py` 或配置文件中：

```python
# Foldseek路径配置
FOLDSEEK_PATH = "/mnt/share/public/foldseek/bin/foldseek"

# 在调用聚类时传递参数
analyzer.perform_coarse_clustering(
    method='kmeans',
    use_foldseek_prescreening=True,  # 启用Foldseek预筛选
    foldseek_path=FOLDSEEK_PATH,
    k_neighbors=100,  # 每个结构找top-100相似结构
    **other_params
)
```

---

## 📈 性能对比

| 阶段 | 当前耗时 | 优化后耗时 | 缩短比例 |
|------|----------|------------|----------|
| 文件加载和处理 | 4-4.5小时 | 1-1.5小时 | **65-75%** |
| Foldseek预筛选 | - | 5-10分钟 | 新增 |
| 距离矩阵计算 | 30-60分钟 | 20-30分钟 | **33-50%** |
| 聚类计算 | 10-30分钟 | 10-20分钟 | **33%** |
| **总计** | **4.5-5.5小时** | **1.5-2小时** | **65-75%** |

---

## ⚠️ 注意事项

1. **CIF转PDB**：Foldseek需要PDB格式，需要批量转换CIF文件（已有代码支持）
2. **内存管理**：批量转换时注意内存使用，可以分批处理
3. **结果兼容性**：Foldseek预筛选可能略微改变聚类结果，但通常更高效且结果合理
4. **测试建议**：先用小数据集（如1000个文件）测试，确认无误后再应用到18,000个文件

---

## 🚀 快速实施（推荐）

### 方案A：最小改动（最快实施）

只修改 `perform_coarse_clustering()` 方法，在计算距离矩阵前添加Foldseek预筛选：

```python
# 在 perform_coarse_clustering() 中，计算距离矩阵前：
if use_foldseek_prescreening and len(self.contact_sets) > 1000:
    # 使用Foldseek预筛选
    foldseek_neighbors = self._foldseek_prescreening_coarse(**kwargs)
    # 修改稀疏矩阵计算，只计算Foldseek找到的对
    D = self._sparse_jaccard_with_foldseek(
        self.contact_sets, foldseek_neighbors, **kwargs
    )
else:
    # 原有逻辑
    D = self.jaccard_distance_matrix(...)
```

### 方案B：完全集成（最佳性能）

实现完整的Foldseek预筛选流程，包括批量文件转换和优化。

---

## 📝 实施优先级

1. **高优先级**：实施Foldseek预筛选（预计缩短65-75%时间）
2. **中优先级**：优化批量CIF转PDB（减少转换时间）
3. **低优先级**：进一步优化内存使用

---

## ✅ 验证步骤

实施后，验证：
1. ✅ Foldseek搜索成功完成
2. ✅ 距离矩阵计算正确（只计算相似对）
3. ✅ 聚类结果合理（与当前方法对比）
4. ✅ 总耗时显著缩短

---

## 📞 如需帮助

如果实施过程中遇到问题，可以：
1. 检查Foldseek路径配置
2. 查看日志文件中的Foldseek输出
3. 先用小数据集测试
