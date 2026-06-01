# pDockQ 模块添加完成

## ✅ 已完成的工作

### 1. pDockQ 工具函数模块 (`utils/pdockq_utils.py`)

**提取来源：** `germinal/filters/pDockQ.py`

**包含的函数：**
- ✅ `parse_atm_record()` - 解析 PDB ATOM 记录
- ✅ `pdb_2_coords()` - 从 PDB 提取坐标和 pLDDT
- ✅ `calc_pdockq()` - 计算 pDockQ 分数
- ✅ `compute_pdockq()` - 从 PDB 字符串计算 pDockQ
- ✅ `get_pdockq()` - 从 PDB 文件获取 pDockQ
- ✅ `retrieve_IFplddt()` - 获取界面 pLDDT
- ✅ `retrieve_IFPAEinter()` - 获取界面 PAE
- ✅ `calc_pmidockq()` - 计算 pmiDockQ (pDockQ2)
- ✅ `pDockQ2()` - 计算 pDockQ2 分数
- ✅ `calculate_lis()` - 计算 LIS (Local Interaction Score)
- ✅ `_transform_pae_matrix()` - PAE 矩阵转换
- ✅ `_get_chain_lengths()` - 获取链长度
- ✅ `_calculate_contact_map()` - 计算接触图
- ✅ `_calculate_mean_lis()` - 计算平均 LIS
- ✅ `_calculate_count_metrics()` - 计算计数指标 (LIA, LIR, cLIA, cLIR)
- ✅ `sigmoid()` - Sigmoid 函数

**状态：** 完整实现，~450 行代码

---

### 2. PDockQCalculator (`metrics/calculators.py`)

**功能：**
- ✅ 基本 pDockQ 计算（仅需 PDB 文件）
- ✅ pDockQ2 计算（需要 PAE 矩阵）
- ✅ LIS 指标计算（需要 PAE 矩阵）
- ✅ 界面 pLDDT 和 PAE 计算

**方法：**
- `calculate()` - 基本 pDockQ 计算
- `calculate_with_pae()` - 使用 PAE 矩阵计算 pDockQ2 和 LIS

**返回指标：**
- `pdockq` - pDockQ 分数（0-1，越高越好）
- `pdockq2` - pDockQ2 分数（需要 PAE）
- `i_plddt` - 界面 pLDDT（归一化到 0-1）
- `i_pae` - 界面 PAE（归一化）
- `lis` - Local Interaction Score
- `lia` - Local Interaction Area
- `clis` - Contact-based LIS
- `ilis` - Integrated LIS (sqrt(LIS * cLIS))

**状态：** 完整实现

---

### 3. MetricAggregator 更新

**更新内容：**
- ✅ 添加 PDockQCalculator 支持
- ✅ 自动检测 PAE 矩阵
- ✅ 如果 PAE 可用，自动计算 pDockQ2 和 LIS
- ✅ 如果 PAE 不可用，仅计算基本 pDockQ

**状态：** 完整实现

---

## 📊 支持的指标

### pDockQ 系列

1. **pDockQ** (`pdockq`)
   - 仅需 PDB 文件
   - 基于界面 pLDDT 和接触数
   - 范围：0-1，越高越好
   - 阈值：>0.23 表示高质量对接

2. **pDockQ2** (`pdockq2`)
   - 需要 PAE 矩阵
   - 结合界面 PAE 和 pLDDT
   - 更准确的对接质量评估

3. **界面指标**
   - `i_plddt` - 界面 pLDDT（归一化）
   - `i_pae` - 界面 PAE（归一化）

### LIS 系列

1. **LIS** (`lis`)
   - Local Interaction Score
   - 基于 PAE 矩阵转换
   - 范围：0-1，越高越好

2. **cLIS** (`clis`)
   - Contact-based LIS
   - 结合接触图和 PAE

3. **iLIS** (`ilis`)
   - Integrated LIS
   - sqrt(LIS * cLIS)

4. **LIA** (`lia`)
   - Local Interaction Area
   - 界面残基数量

---

## 🔧 使用方法

### 基本使用（仅 pDockQ）

```python
from protein_filter import ProteinFilter, FilterConfig, Design

config = FilterConfig(
    metrics=MetricConfig(
        enabled=["pdockq"]  # 仅需 PDB，不需要 PAE
    )
)

filter_system = ProteinFilter(config)
result = filter_system.filter(design)

print(f"pDockQ: {result.metrics.get('pdockq', 'N/A')}")
```

### 完整使用（pDockQ2 + LIS，需要 PAE）

```python
config = FilterConfig(
    metrics=MetricConfig(
        enabled=[
            "pdockq",      # 基本 pDockQ
            "pdockq2",     # pDockQ2（需要 PAE）
            "lis",         # LIS（需要 PAE）
            "lia",         # LIA（需要 PAE）
            "i_plddt",     # 界面 pLDDT（需要 PAE）
            "i_pae",       # 界面 PAE（需要 PAE）
        ]
    )
)

# 注意：prediction_metrics 需要包含 'pae_matrix' 或 'pae'
# 这通常来自结构预测工具（如 AlphaFold3）
```

### 在预测器中提供 PAE

```python
# 在 AF3Predictor 或 ChaiPredictor 中
def predict(self, design: Design, output_dir: str):
    # ... 运行预测 ...
    
    # 提取 PAE 矩阵
    pae_matrix = self._extract_pae_from_output(output_dir)
    
    # 返回包含 PAE 的指标
    return pdb_path, {
        "plddt": plddt_value,
        "pae_matrix": pae_matrix,  # 重要：提供 PAE 矩阵
        # ... 其他指标 ...
    }
```

---

## 📝 配置示例

### YAML 配置

```yaml
metrics:
  enabled:
    - pdockq      # 基本 pDockQ（总是可用）
    - pdockq2     # pDockQ2（需要 PAE）
    - lis          # LIS（需要 PAE）
    - lia          # LIA（需要 PAE）
    - i_plddt      # 界面 pLDDT（需要 PAE）
    - i_pae        # 界面 PAE（需要 PAE）

filters:
  pdockq:
    threshold: 0.23
    operator: ">"
  pdockq2:
    threshold: 0.5
    operator: ">"
  lis:
    threshold: 0.5
    operator: ">"
```

---

## ⚠️ 注意事项

### 1. PAE 矩阵要求

- **pDockQ2** 和 **LIS** 指标需要 PAE 矩阵
- PAE 矩阵应该来自结构预测工具（AlphaFold3, Chai-1 等）
- 如果 PAE 不可用，这些指标将返回 0.0

### 2. 链顺序

- pDockQ 和 LIS 计算假设链按顺序排列
- 确保 PDB 文件中的链顺序正确

### 3. 依赖项

- `numpy` - 数组操作
- `pandas` - DataFrame 操作（用于 pDockQ2）
- `scipy` - 距离计算
- `mdtraj` - 接触图计算
- `BioPython` - PDB 解析

### 4. 性能

- pDockQ 计算很快（仅需 PDB）
- pDockQ2 和 LIS 需要 PAE 矩阵，计算时间取决于矩阵大小
- 对于大型复合物，LIS 计算可能需要几秒钟

---

## 📚 参考文献

**pDockQ:**
Bryant, P., Pozzati, G. & Elofsson, A. Improved prediction of protein-protein interactions using AlphaFold2.
Nat Commun 13, 1265 (2022). https://doi.org/10.1038/s41467-022-28865-w

**LIS:**
（参考 Germinal 代码中的实现）

---

## ✅ 总结

**已完成：**
- ✅ pDockQ 工具函数模块（~450 行）
- ✅ PDockQCalculator 类
- ✅ MetricAggregator 集成
- ✅ 支持 8 个 pDockQ/LIS 相关指标

**当前状态：**
- 🎯 pDockQ 模块已完整实现
- 🎯 支持基本 pDockQ（仅需 PDB）
- 🎯 支持 pDockQ2 和 LIS（需要 PAE）
- 🎯 自动检测 PAE 可用性

**下一步：**
- 在 AF3Predictor/ChaiPredictor 中提供 PAE 矩阵
- 测试 pDockQ 计算准确性
- 验证与 Germinal 结果的一致性

pDockQ 模块已成功添加！🎉

