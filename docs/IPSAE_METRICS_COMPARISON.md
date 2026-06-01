# IPSAE 指标与现有指标对比分析

## IPSAE 脚本输出的参数

根据 [IPSAE GitHub 仓库](https://github.com/DunbrackLab/IPSAE/)，`ipsae.py` 脚本会输出以下参数：

### IPSAE 特有参数（不重合）

1. **`ipSAE`**: IPSAE 核心分数（主要输出）
   - 基于 PAE cutoff 和 d0（由第二链中 PAE < cutoff 的残基数确定）
   - **这是 IPSAE 的核心创新**，改进了 ipTM

2. **`ipSAE_d0chn`**: IPSAE (d0 = 链长度之和)
   - 使用链长度之和作为 d0

3. **`ipSAE_d0dom`**: IPSAE (d0 = 两个链中任何链间 PAE < cutoff 的残基总数)
   - 使用域残基数作为 d0

### 可能重合的参数

4. **`ipTM_af`**: AlphaFold 的 ipTM 值
   - 对于 AF2：来自 JSON 文件的整个复合物的 ipTM
   - 对于 AF3：来自 summary JSON 文件的对称成对值

5. **`ipTM_d0chn`**: 从 PAE 矩阵计算的 ipTM (d0 = 链长度之和)
   - 不使用 PAE cutoff

6. **`pDockQ`**: 基于 pLDDT 的分数
   - 来自 Bryant, Pozzati, Elofsson 的方法

7. **`pDockQ2`**: 基于 PAE 的分数
   - 来自 Zhu, Shenoy, Kundrotas, Elofsson 的方法

8. **`LIS`**: Local Interaction Score
   - 基于 PAE 变换，来自 Kim, Hu, Comjean 等的方法

## 与现有指标的对比

### 1. ipTM 对比

| 参数 | 来源 | 计算方式 | 是否相同 |
|------|------|---------|---------|
| `external_iptm` | ConfidenceCalculator | 从 AF3 JSON 直接提取 | ✅ **相同** |
| `ipsae_iptm_af` | IPSAE 脚本 | 从 AF3 JSON 提取（AF2 为整个复合物，AF3 为对称成对值） | ⚠️ **可能相同** |
| `ipsae_iptm_d0chn` | IPSAE 脚本 | 从 PAE 矩阵计算（d0 = 链长度之和） | ❌ **不同**（计算方法不同） |

**处理建议**：
- `external_iptm` 和 `ipsae_iptm_af` 可能相同，保留两者但添加注释说明
- `ipsae_iptm_d0chn` 是 IPSAE 特有的计算方式，保留

### 2. pDockQ 对比

| 参数 | 来源 | 计算方式 | 是否相同 |
|------|------|---------|---------|
| `pdockq` | PDockQCalculator | 基于界面 pLDDT 和接触数（Bryant 方法） | ⚠️ **可能相同** |
| `ipsae_pdockq` | IPSAE 脚本 | 基于 pLDDT（Bryant 方法） | ⚠️ **可能相同** |

**处理建议**：
- 两者可能使用相同的算法，但实现可能有细微差异
- 保留两者，但添加前缀区分：`pdockq`（我们的实现）和 `ipsae_pdockq`（IPSAE 脚本输出）
- 用户可以选择使用哪个

### 3. pDockQ2 对比

| 参数 | 来源 | 计算方式 | 是否相同 |
|------|------|---------|---------|
| `pdockq2` | PDockQCalculator | 基于 PAE 和界面 pLDDT（Zhu 方法） | ⚠️ **可能相同** |
| `ipsae_pdockq2` | IPSAE 脚本 | 基于 PAE（Zhu 方法） | ⚠️ **可能相同** |

**处理建议**：
- 两者可能使用相同的算法（Zhu 方法），但实现可能有差异
- 保留两者，添加前缀区分
- 可以用于交叉验证

### 4. LIS 对比

| 参数 | 来源 | 计算方式 | 是否相同 |
|------|------|---------|---------|
| `lis` | PDockQCalculator | 基于 PAE 变换（Kim 方法） | ⚠️ **可能相同** |
| `ipsae_lis` | IPSAE 脚本 | 基于 PAE 变换（Kim 方法） | ⚠️ **可能相同** |

**处理建议**：
- 两者可能使用相同的算法，但实现可能有差异
- 保留两者，添加前缀区分
- 可以用于交叉验证

## 处理方案

### 方案 1：配置选项控制（✅ 已采用）

**实现**：通过配置选项 `ipsae_include_duplicate_metrics` 控制是否输出可能重合的参数

**优点**：
- 生产环境：默认只输出 IPSAE 特有参数，避免重复
- 开发/验证：可以启用重合参数进行交叉验证
- 灵活配置：用户可以根据需求选择

**使用方式**：
```python
# 只输出 IPSAE 特有参数（默认，推荐用于生产环境）
config = FilterConfig(
    metrics=FilterConfig.MetricConfig(
        enabled=["ipsae"],
        ipsae_include_duplicate_metrics=False  # 默认 False
    )
)

# 输出所有参数（用于交叉验证）
config = FilterConfig(
    metrics=FilterConfig.MetricConfig(
        enabled=["ipsae"],
        ipsae_include_duplicate_metrics=True  # 启用重合参数
    )
)
```

### 方案 2：保留所有参数，添加前缀区分（已废弃）

**优点**：
- 保留所有信息，不丢失数据
- 可以用于交叉验证
- 用户可以选择使用哪个

**实现**：
- IPSAE 输出的参数统一添加 `ipsae_` 前缀
- 我们的实现保持原有名称

**示例**：
```python
{
    # IPSAE 特有参数
    "ipsae": 0.65,
    "ipsae_d0chn": 0.68,
    "ipsae_d0dom": 0.66,
    
    # 可能重合的参数（添加前缀）
    "ipsae_iptm_af": 0.70,      # IPSAE 脚本的 ipTM
    "ipsae_pdockq": 0.45,       # IPSAE 脚本的 pDockQ
    "ipsae_pdockq2": 0.50,      # IPSAE 脚本的 pDockQ2
    "ipsae_lis": 0.35,          # IPSAE 脚本的 LIS
    
    # 我们的实现（保持原名称）
    "external_iptm": 0.70,      # 从 AF3 JSON 提取
    "pdockq": 0.45,             # 我们的 pDockQ 实现
    "pdockq2": 0.50,            # 我们的 pDockQ2 实现
    "lis": 0.35,                 # 我们的 LIS 实现
}
```

## 指标命名规范

- **IPSAE 特有参数**：`ipsae`, `ipsae_d0chn`, `ipsae_d0dom`
- **IPSAE 输出的可能重合参数**：`ipsae_iptm_af`, `ipsae_pdockq`, `ipsae_pdockq2`, `ipsae_lis`
- **我们的实现**：保持原名称（`external_iptm`, `pdockq`, `pdockq2`, `lis` 等）

## 使用建议

1. **主要筛选指标**：使用 `ipsae`（IPSAE 核心分数）
2. **交叉验证**：比较 `ipsae_pdockq` vs `pdockq`，`ipsae_pdockq2` vs `pdockq2`
3. **选择使用**：根据需求选择使用哪个实现
4. **文档说明**：在 README 中已说明哪些参数可能重合

## ipSAE 解读与筛选方向（Dunbrack / Levitate）

ipSAE（Interaction prediction Score from Aligned Errors）改进 ipTM，**仅用高置信度界面残基对**，避免无序区拉低分数。

- **语义**：**高 ipSAE = 高界面置信度**（与 pLDDT、iPTM 等相同，越高越好）。
- **常用阈值**：[Levitate](https://levitate.bio/fixing-the-flaws-in-alphafolds-interface-scoring-meet-dunbracks-ipsae/) 与 Dunbrack：**> 0.6** 常用作可能结合，真实互作多接近 **0.8**。
- **本库筛选**：**ipSAE ≥ 阈值** 才通过；**ipSAE < 阈值** 则记入 `failed_ipsae`。默认阈值 0.6，宽松可设 0.45。
- **历史纠错**：此前误将 ipSAE 当作“越低越好”，使用 `ipSAE ≤ 阈值` 通过、`ipSAE > 阈值` 剔除，方向已修正。

参考文献：Roland L. Dunbrack Jr., “Rēs ipSAE loquunt: What’s wrong with AlphaFold’s ipTM score and how to fix it” bioRxiv (2025). [doi:10.1101/2025.02.10.637595](https://doi.org/10.1101/2025.02.10.637595)

## 总结

- ✅ **已实现**：所有 IPSAE 输出的参数都添加了 `ipsae_` 前缀
- ✅ **清晰区分**：通过前缀明确区分来源
- ✅ **保留信息**：不丢失任何数据，可用于交叉验证
- ✅ **用户选择**：用户可以根据需求选择使用哪个指标
- ✅ **筛选方向**：ipSAE 为“越高越好”，筛选使用 **≥ 阈值** 通过
