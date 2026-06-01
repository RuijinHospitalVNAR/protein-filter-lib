# 两阶段筛选指南

## 概述

对于大规模设计筛选（100,000+ 个预测结果），使用两阶段筛选策略可以显著提高计算效率：

1. **阶段1（粗筛）**：使用快速指标筛选，保留 top N 候选
2. **阶段2（精筛）**：对 top N 候选进行详细分析

## 计算成本分析

### 快速指标（阶段1使用）

这些指标计算速度快，不需要 PyRosetta 的重型计算或模型推理：

| 指标类别 | 指标 | 计算成本 | 说明 |
|---------|------|---------|------|
| **结构预测置信度** | `external_plddt`, `external_ptm`, `external_iptm` | ⚡ 极快 | 从 JSON/PDB 提取，几乎无计算 |
| **结构质量** | `clashes`, `clashes_ca` | ⚡ 快 | scipy cKDTree，毫秒级 |
| **pDockQ 系列** | `pdockq`, `pdockq2`, `lis`, `lia` | ⚡ 快 | 数值计算，秒级 |
| **二级结构** | `alpha_all`, `beta_all`, `loops_all` | ⚡ 较快 | PyRosetta Dssp，相对较快 |

**阶段1总时间**：约 0.1-1 秒/设计（取决于结构大小）

### 慢速指标（阶段2使用）

这些指标需要 PyRosetta 的重型计算或模型推理：

| 指标类别 | 指标 | 计算成本 | 说明 |
|---------|------|---------|------|
| **界面分析** | `interface_dG`, `interface_dSASA`, `interface_packstat` 等（16个） | 🐌 慢 | PyRosetta InterfaceAnalyzer，10-30秒/设计 |
| **SAP 评分** | `sap_score`, `cdr_sap` | 🐌 较慢 | PyRosetta SAP 计算，5-10秒/设计 |
| **亲和力预测** | `a2binder_affinity` | 🐌 慢 | 模型推理，取决于硬件，1-5秒/设计 |

**阶段2总时间**：约 20-50 秒/设计（取决于启用的指标）

## 性能提升估算

假设筛选 100,000 个设计：

### 单阶段筛选（全部指标）

```
总时间 = 100,000 × 30秒 = 3,000,000秒 ≈ 833小时 ≈ 35天
```

### 两阶段筛选

**阶段1（快速）**：
```
时间 = 100,000 × 0.5秒 = 50,000秒 ≈ 14小时
保留 top 1,000 候选
```

**阶段2（详细）**：
```
时间 = 1,000 × 30秒 = 30,000秒 ≈ 8小时
```

**总时间**：约 22 小时（相比单阶段提升 **97%**）

## 使用示例

### 基本用法

```python
from protein_filter import ProteinFilter, FilterConfig, Design
from examples.two_stage_filtering import two_stage_filtering_pipeline

# 加载所有设计
designs = load_designs_from_af3_output(...)  # 100,000 个设计

# 运行两阶段筛选
results = two_stage_filtering_pipeline(
    designs,
    top_n=1000,  # 阶段1保留 top 1,000
    fast_output_dir="./fast_screen_results",
    detailed_output_dir="./detailed_analysis_results"
)

# 获取通过的设计
passed_designs = [(d, m) for d, m, passed in results if passed]
```

### 自定义快速筛选评分

```python
def calculate_fast_score(metrics: dict) -> float:
    """自定义评分函数"""
    score = 0.0
    
    # 根据你的优先级调整权重
    score += 0.4 * metrics.get("external_plddt", 0.0)  # 高权重
    score += 0.3 * metrics.get("external_iptm", 0.0)
    score += 0.2 * metrics.get("pdockq", 0.0)
    score -= 0.1 * min(metrics.get("clashes", 0) / 10.0, 1.0)  # 惩罚碰撞
    
    return score
```

### 并行化阶段1

阶段1可以轻松并行化，因为每个设计独立计算：

```python
from concurrent.futures import ProcessPoolExecutor
from examples.two_stage_filtering import fast_screen

def filter_design_batch(designs_batch):
    """处理一批设计"""
    config = FilterConfig(...)  # 快速指标配置
    filter_system = ProteinFilter(config)
    results = []
    for design in designs_batch:
        result = filter_system.filter(design)
        results.append((design, result.metrics))
    return results

# 并行处理
with ProcessPoolExecutor(max_workers=8) as executor:
    batch_size = len(designs) // 8
    batches = [designs[i:i+batch_size] for i in range(0, len(designs), batch_size)]
    all_results = executor.map(filter_design_batch, batches)
```

## 推荐配置

### 阶段1（快速筛选）配置

```python
fast_config = FilterConfig(
    structure_relaxer=FilterConfig.StructureRelaxerConfig(name="none"),  # 跳过松弛
    metrics=FilterConfig.MetricConfig(
        enabled=[
            "plddt",           # 从 PDB 提取
            "clashes",         # 快速碰撞检测
            "pdockq",          # 基础 pDockQ
            "pdockq2", "lis",  # 如果有 PAE 矩阵
            "alpha_all",       # 二级结构（相对快）
        ]
    ),
    filters={
        "external_plddt": {"threshold": 0.7, "operator": ">="},
        "clashes": {"threshold": 5, "operator": "<"},  # 宽松阈值
        "pdockq": {"threshold": 0.2, "operator": ">="},
    },
)
```

### 阶段2（详细分析）配置

```python
detailed_config = FilterConfig(
    structure_relaxer=FilterConfig.StructureRelaxerConfig(name="pyrosetta"),  # 启用松弛
    metrics=FilterConfig.MetricConfig(
        enabled=[
            # 所有快速指标
            "plddt", "clashes", "pdockq", "pdockq2",
            # 慢速指标
            "interface_dG", "interface_dSASA", "interface_packstat",
            "interface_sc", "interface_hbonds",
            "sap_score",
            # 可选：A2binder
            # "a2binder_affinity",
        ],
    ),
    filters={
        # 更严格的阈值
        "external_plddt": {"threshold": 0.75, "operator": ">="},
        "external_iptm": {"threshold": 0.6, "operator": ">="},
        "clashes": {"threshold": 1, "operator": "<"},
        "interface_dG": {"threshold": -10.0, "operator": "<"},
        "interface_packstat": {"threshold": 0.6, "operator": ">="},
        "pdockq": {"threshold": 0.23, "operator": ">="},
        "sap_score": {"threshold": 100, "operator": "<"},
    },
)
```

## 最佳实践

1. **阶段1阈值设置**：
   - 设置相对宽松的阈值，避免过早淘汰潜在好设计
   - 主要目的是快速排序，而不是严格筛选

2. **top_n 选择**：
   - 根据计算资源调整：资源充足可以保留更多（如 5,000）
   - 建议保留 1-5% 的候选（100,000 → 1,000-5,000）

3. **并行化**：
   - 阶段1可以轻松并行化（每个设计独立）
   - 阶段2也可以并行化，但需要注意 PyRosetta 的线程安全

4. **结果保存**：
   - 保存阶段1的结果，方便后续分析
   - 保存阶段2的完整指标，用于最终决策

5. **内存管理**：
   - 对于超大规模筛选，考虑分批处理
   - 及时释放不需要的中间结果

## 注意事项

- **阶段1跳过松弛**：为了速度，阶段1通常跳过结构松弛。如果松弛对某些指标很重要，可以在阶段2启用。
- **PAE 矩阵**：pDockQ2 和 LIS 需要 PAE 矩阵。如果 AF3 输出中没有，这些指标将无法计算。
- **A2binder**：如果使用 A2binder，确保模型已加载。模型加载是一次性成本，但推理仍有开销。

## 总结

两阶段筛选策略可以：
- ✅ 将 100,000 设计的筛选时间从 **35天** 降至 **22小时**
- ✅ 保持筛选质量（先粗筛再精筛）
- ✅ 灵活调整各阶段的指标和阈值
- ✅ 支持并行化加速

这是处理大规模设计筛选的推荐方法。
