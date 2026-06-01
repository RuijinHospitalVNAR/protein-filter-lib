# SASA 指标详解：interface_delta_sasa 与 complexed_sasa

## 📊 两种 SASA 指标

在 PyRosetta 的 `InterfaceAnalyzerMover` 分析结果中，有两种不同的 SASA（Solvent-Accessible Surface Area，溶剂可及表面积）指标：

### 1. `interface_delta_sasa` (ΔSASA)
**界面埋藏表面积变化**

### 2. `complexed_sasa` 
**复合物总表面积**

---

## 🔬 计算方式与物理意义

### `interface_delta_sasa` (ΔSASA)

**定义**：界面埋藏表面积变化，也称为 **Buried Surface Area (BSA)**

**计算公式**：
```
ΔSASA = SASA_separated - SASA_complexed
```

其中：
- **SASA_separated**：两个蛋白质**分离状态**下的总表面积（A链 + B链各自独立时的表面积之和）
- **SASA_complexed**：两个蛋白质**形成复合物**后的总表面积

**物理意义**：
- 表示在形成复合物时，**被埋藏在界面中的表面积**
- 数值越大，说明界面接触面积越大，埋藏的表面积越多
- 单位：**Å²**（平方埃）

**生物学意义**：
- 反映界面的**大小**和**接触范围**
- 通常 ΔSASA > 1000 Å² 表示有意义的蛋白质-蛋白质相互作用
- 抗体-抗原界面的典型 ΔSASA 范围：**1000-3000 Å²**

**示例解释**：
```
如果 ΔSASA = 1881 Å²
→ 意味着在形成复合物时，有 1881 Å² 的表面积从溶剂暴露状态变成了埋藏在界面中
→ 这个值越大，说明界面越大，接触越紧密
```

---

### `complexed_sasa`

**定义**：复合物状态下的总溶剂可及表面积

**计算公式**：
```
complexed_sasa = SASA_complexed
```

即：形成复合物后，整个复合物（A链 + B链）暴露在溶剂中的总表面积。

**物理意义**：
- 表示复合物的**总表面积**
- 反映复合物的**大小**和**形状**
- 单位：**Å²**（平方埃）

**生物学意义**：
- 复合物越大，这个值越大
- 可以用于评估复合物的**整体尺寸**
- 对于相同大小的蛋白质，如果 `complexed_sasa` 较小，可能表示：
  - 界面更紧密
  - 复合物更紧凑
  - 埋藏的表面积更多

**示例解释**：
```
如果 complexed_sasa = 12520 Å²
→ 意味着整个复合物暴露在溶剂中的表面积是 12520 Å²
→ 这个值反映了复合物的整体大小
```

---

## 🔗 两者的关系

### 数学关系

```
SASA_separated = complexed_sasa + interface_delta_sasa
```

或者更准确地说：
```
SASA_separated = SASA_chainA_separated + SASA_chainB_separated
interface_delta_sasa = SASA_separated - complexed_sasa
```

### 实际数据验证

从你的结果文件中可以看到：

| 结构 | interface_delta_sasa | complexed_sasa | 估算的 SASA_separated |
|------|---------------------|----------------|---------------------|
| C87S_model | 1881.21 | 12520.25 | ~14401 Å² |
| C87S_C93Y_model | 2301.32 | 10642.24 | ~12943 Å² |
| C87S_E96R_model | 1954.67 | 12167.15 | ~14122 Å² |

**注意**：由于计算精度和四舍五入，直接相加可能不完全等于分离状态的总表面积，但概念上是这样的关系。

---

## 📈 如何解读结果

### 1. `interface_delta_sasa` 的解读

**数值范围参考**：
- **< 500 Å²**：界面很小，可能是弱相互作用或非特异性接触
- **500-1000 Å²**：中等界面，可能有功能性相互作用
- **1000-2000 Å²**：较大的界面，典型的蛋白质-蛋白质相互作用
- **> 2000 Å²**：非常大的界面，通常是强结合（如抗体-抗原）

**你的数据**：
- 最小值：~1446 Å²（C87S_G91S_model）
- 最大值：~2301 Å²（C87S_C93Y_model）
- 平均值：约 1800-1900 Å²

**结论**：所有设计的界面都比较大，属于有意义的蛋白质-蛋白质相互作用。

---

### 2. `complexed_sasa` 的解读

**数值范围**：
- 取决于复合物的总大小（链长、分子量）
- 对于你的抗体-抗原复合物（~211 残基），**10000-13000 Å²** 是合理的范围

**你的数据**：
- 最小值：~10642 Å²（C87S_C93Y_model）
- 最大值：~12711 Å²（C87S_E96V_model）
- 平均值：约 12000 Å²

**结论**：所有复合物的总表面积相近，说明结构大小相似。

---

### 3. 结合 `interface_score` 的综合评估

**重要指标组合**：

1. **`interface_score` (interface_dG)**：界面结合自由能（kcal/mol）
   - **越低越好**（负值表示有利结合）
   - 你的数据中，最低值：**0.73 kcal/mol**（C87S_E96R_model）

2. **`interface_delta_sasa`**：界面大小
   - **越大越好**（更大的界面通常意味着更强的结合）
   - 你的数据中，最大值：**2301 Å²**（C87S_C93Y_model）

3. **`interface_dG / interface_delta_sasa`**：结合能密度
   - 反映**单位面积**的结合强度
   - **越低越好**（负值表示高效结合）

**筛选建议**：
- 优先选择 `interface_score` < 0 的设计（有利结合）
- 在有利结合中，选择 `interface_delta_sasa` 较大的（界面更大）
- 计算 `interface_score / interface_delta_sasa`，选择比值更负的（结合更高效）

---

## 💡 实际应用示例

### 示例 1：C87S_E96R_model（最佳结合能）
```
interface_score: 0.73 kcal/mol（接近 0，轻微不利）
interface_delta_sasa: 1954.67 Å²（中等偏大）
complexed_sasa: 12167.15 Å²（正常）
```
**解读**：结合能接近中性，界面大小中等。

### 示例 2：C87S_C93Y_model（最大界面）
```
interface_score: 67.50 kcal/mol（不利，结合较弱）
interface_delta_sasa: 2301.32 Å²（最大界面）
complexed_sasa: 10642.24 Å²（较小）
```
**解读**：虽然界面最大，但结合能不利，可能是界面质量不好（如疏水暴露、氢键不足等）。

### 示例 3：C87S_model（参考）
```
interface_score: 129.69 kcal/mol（非常不利）
interface_delta_sasa: 1881.21 Å²（中等）
complexed_sasa: 12520.25 Å²（正常）
```
**解读**：结合能非常不利，不适合作为候选。

---

## 📚 参考文献

1. **Rosetta InterfaceAnalyzerMover 文档**：
   - https://docs.rosettacommons.org/docs/latest/scripting_documentation/RosettaScripts/Movers/movers_pages/analysis/InterfaceAnalyzerMover

2. **SASA 计算原理**：
   - Lee, B. & Richards, F. M. (1971). The interpretation of protein structures: estimation of static accessibility. *J. Mol. Biol.* 55, 379-400.

3. **界面分析标准**：
   - 典型的蛋白质-蛋白质界面：ΔSASA > 1000 Å²
   - 抗体-抗原界面：ΔSASA 通常在 1000-3000 Å²

---

## 🎯 总结

| 指标 | 含义 | 单位 | 越大越好？ | 典型范围 |
|------|------|------|-----------|---------|
| **interface_delta_sasa** | 界面埋藏表面积 | Å² | ✅ 是 | 1000-3000 Å² |
| **complexed_sasa** | 复合物总表面积 | Å² | ❌ 无关（反映大小） | 取决于复合物大小 |

**关键要点**：
- **`interface_delta_sasa`** 是评估界面质量的**核心指标**之一
- 结合 `interface_score` 一起分析，可以全面评估结合质量
- 优先选择 `interface_score` < 0 且 `interface_delta_sasa` > 1500 Å² 的设计
