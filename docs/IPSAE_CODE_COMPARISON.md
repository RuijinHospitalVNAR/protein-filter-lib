# IPSAE 与现有实现的计算方式对比

## 分析依据

由于 IPSAE 脚本是外部工具，我们基于以下信息进行分析：
1. GitHub 仓库的 README 说明
2. 算法来源文献
3. 我们的实现（来自 Germinal）

## 详细对比

### 1. ipTM 对比

#### 我们的实现 (`external_iptm`)
- **来源**：`ConfidenceCalculator` → `af3_utils.py:extract_metrics_from_af3_json()`
- **计算方式**：直接从 AF3 JSON 文件的 `iptm` 或 `i_ptm` 字段提取
- **代码位置**：`src/protein_filter/utils/af3_utils.py:59-62`

```python
# 我们的实现
if 'iptm' in data:
    metrics['iptm'] = float(data['iptm'])
elif 'i_ptm' in data:
    metrics['iptm'] = float(data['i_ptm'])
```

#### IPSAE 的 `ipTM_af`
- **来源**：IPSAE 脚本从 JSON 文件读取
- **计算方式**：根据 README，对于 AF3 是从 summary JSON 文件的对称成对值提取
- **可能差异**：IPSAE 可能处理了 AF2 和 AF3 的差异

**结论**：✅ **基本相同** - 都是从 JSON 提取，但 IPSAE 可能处理了更多边界情况

**建议**：保留 `external_iptm`（我们的实现），`ipsae_iptm_af` 可用于验证

---

### 2. pDockQ 对比

#### 我们的实现 (`pdockq`)
- **来源**：`PDockQCalculator` → `pdockq_utils.py:calc_pdockq()`
- **算法**：Bryant, Pozzati, Elofsson (2022)
- **公式**：
  ```python
  x = avg_if_plddt * log10(n_contacts + 1)
  pdockq = 0.724 / (1 + exp(-0.052 * (x - 152.611))) + 0.018
  ```
- **参数**：
  - `contact_cutoff = 8.0 Å`
  - 使用上三角矩阵避免重复计数
  - 界面残基：参与跨链接触的所有残基

#### IPSAE 的 `pDockQ`
- **来源**：IPSAE 脚本内部计算
- **算法**：Bryant, Pozzati, Elofsson (2022) - **相同算法**
- **可能差异**：
  - 界面定义方式可能不同
  - 接触计数方式可能不同
  - 参数值可能不同

**结论**：⚠️ **算法相同，实现可能不同** - 可能产生细微差异

**建议**：保留两者用于交叉验证，但主要使用我们的实现（更可控）

---

### 3. pDockQ2 对比

#### 我们的实现 (`pdockq2`)
- **来源**：`PDockQCalculator` → `pdockq_utils.py:pDockQ2()`
- **算法**：Zhu, Shenoy, Kundrotas, Elofsson (2023)
- **计算步骤**：
  1. 识别界面残基（距离 < 10.0 Å）
  2. 提取界面 pLDDT（从 B-factor）
  3. 提取界面 PAE（从 PAE 矩阵）
  4. 归一化 PAE：`mean(1 / (1 + (PAE / d)^2))`，其中 d = 10.0
  5. 计算乘积：`prot = normalized_PAE × interface_pLDDT`
  6. Sigmoid 转换：
     ```python
     L=1.310, x0=84.73, k=0.0747, b=0.0050
     pdockq2 = sigmoid(prot, L, x0, k, b)
     ```

#### IPSAE 的 `pDockQ2`
- **来源**：IPSAE 脚本内部计算
- **算法**：Zhu, Shenoy, Kundrotas, Elofsson (2023) - **相同算法**
- **可能差异**：
  - 距离阈值可能不同
  - PAE 归一化方式可能不同
  - Sigmoid 参数可能不同

**结论**：⚠️ **算法相同，实现可能不同** - 可能产生细微差异

**建议**：保留两者用于交叉验证，但主要使用我们的实现（更可控）

---

### 4. LIS 对比

#### 我们的实现 (`lis`)
- **来源**：`PDockQCalculator` → `pdockq_utils.py:calculate_lis()`
- **算法**：Kim, Hu, Comjean, Rodiger, Mohr, Perrimon (2024)
- **计算步骤**：
  1. PAE 变换：`LIS = 1 - (PAE / 12.0)` 当 PAE < 12.0，否则 0
  2. 计算接触图（Cβ 原子，距离 < 8.0 Å）
  3. 计算链间平均 LIS
  4. 计算 cLIS（基于接触的 LIS）
  5. 计算 iLIS = sqrt(LIS × cLIS)

#### IPSAE 的 `LIS`
- **来源**：IPSAE 脚本内部计算
- **算法**：Kim, Hu, Comjean 等 - **相同算法**
- **可能差异**：
  - PAE cutoff 可能不同（我们使用 12.0）
  - 距离阈值可能不同（我们使用 8.0）
  - 接触定义方式可能不同

**结论**：⚠️ **算法相同，实现可能不同** - 可能产生细微差异

**建议**：保留两者用于交叉验证，但主要使用我们的实现（更可控）

---

## 处理建议

### 方案 A：只保留 IPSAE 特有参数（推荐用于生产环境）

**优点**：
- 避免重复
- 指标列表更简洁
- 减少计算开销

**实现**：
```python
# 在 IPSAECalculator 中只输出 IPSAE 特有参数
return {
    "ipsae": ipsae,
    "ipsae_d0chn": ipsae_d0chn,
    "ipsae_d0dom": ipsae_d0dom,
    # 不输出可能重合的参数
}
```

### 方案 B：保留所有参数，但添加配置选项（推荐用于开发/验证）

**优点**：
- 可以交叉验证
- 灵活配置
- 便于调试

**实现**：
```python
# 在 MetricConfig 中添加配置
@dataclass
class MetricConfig:
    # ...
    ipsae_include_duplicate_metrics: bool = False  # 是否包含可能重合的参数
```

### 方案 C：智能去重（根据算法来源）

**逻辑**：
- `ipTM_af` vs `external_iptm`：基本相同，只保留 `external_iptm`
- `pDockQ`、`pDockQ2`、`LIS`：算法相同但实现可能不同，保留两者用于验证

## 最终推荐

**推荐使用方案 B（配置选项）**，原因：

1. **开发阶段**：设置 `ipsae_include_duplicate_metrics=True`，用于交叉验证
2. **生产环境**：设置 `ipsae_include_duplicate_metrics=False`，只保留 IPSAE 特有参数
3. **灵活性**：用户可以根据需求选择

## 实现代码

更新 `IPSAECalculator` 和 `MetricConfig`：

```python
# config.py
@dataclass
class MetricConfig:
    # ...
    ipsae_include_duplicate_metrics: bool = False  # 是否包含可能重合的参数

# calculators.py
class IPSAECalculator:
    def __init__(self, ..., include_duplicate_metrics: bool = False):
        self.include_duplicate_metrics = include_duplicate_metrics
    
    def calculate(...):
        metrics = {
            "ipsae": ipsae,
            "ipsae_d0chn": ipsae_d0chn,
            "ipsae_d0dom": ipsae_d0dom,
        }
        
        if self.include_duplicate_metrics:
            # 添加可能重合的参数
            metrics["ipsae_iptm_af"] = iptm_af
            metrics["ipsae_pdockq"] = pdockq
            metrics["ipsae_pdockq2"] = pdockq2
            metrics["ipsae_lis"] = lis
        
        return metrics
```
