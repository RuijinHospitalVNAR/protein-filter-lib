# Protein Filter Library API 文档

## 核心类

### ProteinFilter

主要的过滤系统类。

```python
from protein_filter import ProteinFilter, FilterConfig

filter_system = ProteinFilter(config)
result = filter_system.filter(design)
```

**方法：**
- `filter(design: Design) -> FilterResult`: 过滤设计

### FilterConfig

配置类，包含所有设置。

```python
config = FilterConfig(
    structure_relaxer=FilterConfig.StructureRelaxerConfig(name="pyrosetta"),
    metrics=FilterConfig.MetricConfig(
        enabled=["plddt", "iptm", "clashes"]
    ),
    filters={
        "external_plddt": {"threshold": 0.7, "operator": ">="},
    }
)
```

### Design

设计数据结构。

```python
design = Design(
    sequence="MKLLVL...",
    pdb_path="design.pdb",  # 外部预测得到的PDB文件
    target_chain="A",
    binder_chain="B",
    prediction_metrics={  # 可选：预测指标
        "plddt": 0.85,
        "ptm": 0.75,
        "iptm": 0.70,
    }
)
```

### FilterResult

过滤结果。

```python
result.passed  # bool
result.metrics  # Dict[str, Any]
result.filter_results  # Dict[str, bool]
result.relaxed_pdb_path  # str
```

## 接口

### StructureRelaxer

结构优化接口。

**实现类：**
- `PyRosettaRelaxer`
- `NoOpRelaxer` (跳过松弛)

### MetricCalculator

指标计算接口。

**实现类：**
- `ClashCalculator` - 碰撞检测
- `InterfaceCalculator` - 界面分析
- `ConfidenceCalculator` - 置信度指标（pLDDT等）
- `SAPCalculator` - SAP评分
- `SecondaryStructureCalculator` - 二级结构分析
- `PDockQCalculator` - pDockQ系列指标
- `A2binderCalculator` - A2binder亲和力预测
- `IgLMCalculator` - IgLM对数似然

## 支持的指标

### 置信度指标
- `external_plddt`: 预测的 pLDDT
- `external_ptm`: 预测的 PTM
- `external_iptm`: 界面 PTM
- `external_pae`: 预测对齐误差
- `external_i_pae`: 界面 PAE

### 结构指标
- `clashes`: 碰撞数
- `sc_rmsd`: 侧链 RMSD

### 界面指标
- `interface_dG`: 界面结合自由能
- `interface_dSASA`: 界面溶剂可及表面积变化
- `interface_packstat`: 界面包装统计
- `interface_hbonds`: 界面氢键数
- `interface_dG_SASA_ratio`: dG/dSASA 比率

### 其他指标
- `sap_score`: SAP 评分
- `iglm_ll`: IgLM 对数似然
- `alpha_all`, `beta_all`, `loops_all`: 二级结构比例

## 使用示例

参见 [examples/basic_usage.py](../examples/basic_usage.py)

