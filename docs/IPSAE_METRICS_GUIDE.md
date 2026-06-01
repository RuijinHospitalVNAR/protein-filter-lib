# ipSAE 指标选择指南

## 概述

ipSAE (Interaction prediction Score from Aligned Errors) 是 Dunbrack Lab 开发的用于评估蛋白质-蛋白质界面质量的指标，特别适用于 AlphaFold2/3 预测结果。

## ipSAE 输出格式

`ipsae.py` 脚本会为每个结构生成多个结果行，每行代表不同的链对组合：

```
Chn1 Chn2  PAE Dist  Type   ipSAE    ipSAE_d0chn ipSAE_d0dom  ipTM_af  ...
A    H     10   10   asym  0.013208    0.626594    0.022945    0.600   ...
H    A     10   10   asym  0.015472    0.652138    0.176965    0.600   ...
A    H     10   10   max   0.015472    0.652138    0.176965    0.600   ...
```

### 列说明

- **Chn1/Chn2**: 链标识（例如 A=抗原，H=抗体）
- **Type**: 
  - `asym`: 非对称值（A→H 或 H→A 方向）
  - `max`: 对称最大值（取两个方向的较大值）
- **ipSAE**: 核心指标，范围 0-1，**越高越好**
- **ipSAE_d0chn**: 基于链长度归一化的 ipSAE
- **ipSAE_d0dom**: 基于结构域归一化的 ipSAE

## 对于抗原-抗体互作分析

### 推荐指标：`ipSAE` (max 类型)

**原因**：
1. **对称性**：抗原-抗体互作是对称的，`max` 类型取两个方向的最大值，更准确反映接口质量
2. **标准化**：范围 0-1，易于理解和比较
3. **文献推荐**：Dunbrack Lab 的原始论文推荐使用 `max` 类型

### 辅助指标：`ipSAE_d0chn`

**用途**：
- 比较不同大小的抗体（例如 VHH vs 全长 IgG）
- 链长度归一化可以消除大小偏差

### 何时使用 `ipSAE_d0dom`

- 分析多结构域复合物
- 需要结构域级别的接口质量评估

## 筛选阈值建议

根据文献和实际应用：

- **严格筛选**: `ipSAE >= 0.1` (高质量接口)
- **中等筛选**: `ipSAE >= 0.05` (中等质量接口)
- **宽松筛选**: `ipSAE >= 0.01` (低质量但可能有用)

**注意**：阈值取决于 PAE/Dist cutoff 设置：
- PAE=10, Dist=10（推荐）：上述阈值适用
- PAE=5, Dist=5（严格）：大多数结构 ipSAE=0，不推荐
- PAE=15, Dist=15（宽松）：阈值应相应提高

## 代码实现

本软件自动选择 `max` 类型的 `ipSAE` 值：

```python
# 在 _parse_ipsae_output_file 中
if score_type == "max" or "ipsae" not in metrics:
    metrics["ipsae"] = ipsae  # 使用 max 类型的 ipSAE
    # ...
    if score_type == "max":
        break  # 找到 max 类型后停止解析
```

## 参考

- Dunbrack Lab IPSAE: https://github.com/DunbrackLab/IPSAE/
- 原始论文: [Fixing the Flaws in AlphaFold's Interface Scoring](https://levitate.bio/fixing-the-flaws-in-alphafolds-interface-scoring-meet-dunbracks-ipsae/)
