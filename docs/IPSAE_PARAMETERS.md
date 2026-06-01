# IPSAE 参数说明

## 概述

IPSAE 计算需要两个关键参数，用于定义"高置信度界面区域"：

## 参数详解

### 1. `IPSAE_PAE_CUTOFF` (PAE 截断值)

**含义**：PAE (Predicted Aligned Error) 截断值，单位：**Å（埃）**

**作用**：
- PAE 是 AlphaFold 预测的**残基对齐误差**
- 表示预测结构的不确定性
- **只考虑 PAE < cutoff 的残基对**用于计算 IPSAE

**默认值**：`5.0 Å`

**为什么重要**：
- **PAE 越小** = 预测越可靠 = 残基位置越准确
- IPSAE 的核心创新是**只关注高置信度区域**，避免低置信度区域干扰
- 如果 PAE 很大（> 5.0），说明这个残基对的预测不可靠，不应该用于评分

**代码中的使用**：
```python
# 只考虑 PAE < pae_cutoff 的残基对
valid_pairs_matrix = (pae_matrix < pae_cutoff)
```

**调整建议**：
- **更严格**（如 3.0）：只考虑非常可靠的残基对，适合高质量结构
- **更宽松**（如 10.0）：包含更多残基对，但可能引入噪声
- **默认 5.0**：平衡可靠性和覆盖范围

---

### 2. `IPSAE_DISTANCE_CUTOFF` (距离截断值)

**含义**：CA-CA 原子之间的距离截断值，单位：**Å（埃）**

**作用**：
- 定义**界面接触**的标准
- 只有 CA-CA 距离 < cutoff 的残基对才被认为是"界面接触"
- 用于识别参与界面相互作用的残基

**默认值**：`5.0 Å`

**为什么重要**：
- **距离越小** = 残基越接近 = 越可能是真实的界面接触
- 用于区分"界面残基"和"非界面残基"
- 帮助 IPSAE 专注于真正的相互作用区域

**代码中的使用**：
```python
# 同时满足 PAE < cutoff 和距离 < cutoff 的残基对
valid_pairs = (pae_matrix[i] < pae_cutoff) & (distances[i] < dist_cutoff)
```

**调整建议**：
- **更严格**（如 4.0）：只考虑非常紧密的接触，适合紧密结合的复合物
- **更宽松**（如 8.0）：包含更多接触，适合松散结合的复合物
- **默认 5.0**：标准的界面接触距离

---

## 两个参数的协同作用

IPSAE 使用**两个条件同时筛选**：

```
有效的界面残基对 = (PAE < PAE_CUTOFF) AND (距离 < DISTANCE_CUTOFF)
```

**示例**：
- 残基对 A：PAE = 3.0 Å，距离 = 4.0 Å → ✅ **有效**（两个条件都满足）
- 残基对 B：PAE = 7.0 Å，距离 = 4.0 Å → ❌ **无效**（PAE 太大）
- 残基对 C：PAE = 3.0 Å，距离 = 7.0 Å → ❌ **无效**（距离太远）
- 残基对 D：PAE = 7.0 Å，距离 = 7.0 Å → ❌ **无效**（两个条件都不满足）

## 参数对 IPSAE 分数的影响

### PAE_CUTOFF 的影响

| PAE_CUTOFF | 包含的残基对 | IPSAE 分数特点 |
|-----------|------------|--------------|
| **3.0** | 很少（只包含最可靠的） | 分数可能较低，但非常可靠 |
| **5.0** (默认) | 中等（平衡） | 平衡可靠性和覆盖范围 |
| **10.0** | 很多（包含更多区域） | 分数可能较高，但可能包含噪声 |

### DISTANCE_CUTOFF 的影响

| DISTANCE_CUTOFF | 界面定义 | IPSAE 分数特点 |
|----------------|---------|--------------|
| **4.0** | 只考虑紧密接触 | 专注于核心界面 |
| **5.0** (默认) | 标准界面接触 | 平衡覆盖范围 |
| **8.0** | 包含松散接触 | 覆盖更广，但可能包含非界面区域 |

## 实际应用建议

### 场景 1：高质量结构（pLDDT > 80）

```bash
IPSAE_PAE_CUTOFF=3.0      # 更严格，只考虑最可靠的残基
IPSAE_DISTANCE_CUTOFF=4.0  # 只考虑紧密接触
```

### 场景 2：中等质量结构（pLDDT 60-80）

```bash
IPSAE_PAE_CUTOFF=5.0      # 默认值，平衡
IPSAE_DISTANCE_CUTOFF=5.0  # 默认值
```

### 场景 3：低质量结构（pLDDT < 60）

```bash
IPSAE_PAE_CUTOFF=10.0     # 更宽松，包含更多区域
IPSAE_DISTANCE_CUTOFF=6.0  # 稍微宽松
```

### 场景 4：紧密结合的复合物

```bash
IPSAE_PAE_CUTOFF=5.0
IPSAE_DISTANCE_CUTOFF=4.0  # 只考虑紧密接触
```

### 场景 5：松散结合的复合物

```bash
IPSAE_PAE_CUTOFF=5.0
IPSAE_DISTANCE_CUTOFF=7.0  # 包含更远的接触
```

## 在脚本中的配置

在 `part1_compute_stage1_metrics.sh` 中：

```bash
# IPSAE 配置
IPSAE_PAE_CUTOFF=5.0        # PAE 截断值（Å）
IPSAE_DISTANCE_CUTOFF=5.0   # 距离截断值（Å）
```

这些参数会传递给 `ipsae.py` 脚本：

```bash
python ipsae.py <json_file> <pdb_file> <PAE_CUTOFF> <DISTANCE_CUTOFF>
```

## 总结

- **`IPSAE_PAE_CUTOFF`**：控制**预测可靠性**的筛选（只考虑 PAE < cutoff 的残基对）
- **`IPSAE_DISTANCE_CUTOFF`**：控制**界面接触**的定义（只考虑距离 < cutoff 的残基对）
- **两个参数协同工作**：只有同时满足两个条件的残基对才用于计算 IPSAE
- **默认值 5.0/5.0**：适合大多数情况，平衡可靠性和覆盖范围
- **根据结构质量调整**：高质量结构可以用更严格的值，低质量结构可以用更宽松的值
