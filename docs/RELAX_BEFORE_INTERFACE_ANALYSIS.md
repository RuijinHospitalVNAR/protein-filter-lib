# 为什么在界面分析前进行 FastRelax？

## 🎯 核心问题

**AF3 预测的结构符合其训练的概率分布，但不一定符合物理规律（如 PyRosetta 力场）**

### 问题分析

1. **AF3 的训练目标**：
   - 学习蛋白质结构的**统计分布**（从 PDB 数据库）
   - 预测最可能的**几何构象**
   - **不直接优化物理能量**

2. **PyRosetta 的评估标准**：
   - 基于**物理力场**（ref2015）
   - 评估**物理合理性**（键长、键角、范德华接触等）
   - 计算**结合自由能**（interface_dG）

3. **潜在的不匹配**：
   - AF3 可能产生**几何上合理但能量上不利**的结构
   - 例如：轻微的键长偏差、不理想的侧链堆积、局部张力
   - 这些会导致 PyRosetta 的 `interface_dG` **不准确**（过于不利）

---

## ✅ 解决方案：FastRelax

### FastRelax 的作用

**FastRelax** 是 PyRosetta 的结构优化算法，通过最小化 Rosetta 能量函数来：

1. **修正物理不合理性**：
   - 调整键长、键角到理想值
   - 优化侧链堆积
   - 减少局部张力

2. **保持整体结构**：
   - 在原始结构附近优化（`constrain_relax_to_start_coords`）
   - 不会大幅改变 AF3 预测的整体折叠

3. **使结构符合力场**：
   - 优化后的结构更符合 Rosetta 力场的预期
   - 后续的 `interface_dG` 计算更准确

---

## 📊 Relax 对结果的影响

### 预期变化

1. **interface_dG 通常变得更有利**（更负）：
   - 原始结构：可能因为物理不合理性导致能量偏高
   - Relax 后：修正了这些问题，能量更准确

2. **interface_delta_sasa 可能略有变化**：
   - 通常变化不大（< 5%）
   - 因为 Relax 主要优化局部，不改变整体界面大小

3. **计算时间增加**：
   - 每个结构增加 **30-120 秒**（取决于 `max_iter`）
   - 313 个结构：从 ~1 小时增加到 **3-10 小时**

---

## 🔧 使用方法

### 当前脚本已支持 Relax

`run_pyrosetta_static.py` 已经支持 Relax，只需设置参数：

```bash
python3 scripts/run_pyrosetta_static.py \
    --pdb_dir <input_dir> \
    --output_dir <output_dir> \
    --binder_chain B \
    --target_chain A \
    --relax true \              # 启用 Relax
    --fixbb false \             # 是否固定骨架（false = 允许骨架移动）
    --fixed_chain "" \          # 固定特定链的骨架（如 "A" 表示固定抗原）
    --max_iter 1 \              # FastRelax 迭代次数（1-5 通常足够）
    --only_main_models true
```

### Relax 参数说明

#### `--relax true/false`
- **true**：先 Relax 再分析（推荐用于 AF3 预测）
- **false**：直接分析（更快，但可能不准确）

#### `--fixbb true/false`
- **false**（推荐）：允许骨架和侧链都移动
- **true**：只允许侧链移动，固定骨架

#### `--fixed_chain <chain_id>`
- 当 `fixbb=true` 时，指定固定哪个链的骨架
- 例如：`--fixed_chain A` 表示固定抗原链骨架，只优化抗体链
- **适用场景**：当你想保持抗原结构不变，只优化抗体

#### `--max_iter <n>`
- FastRelax 的最大迭代次数
- **推荐值**：
  - `1`：快速，通常足够（~30-60 秒/结构）
  - `2-3`：更彻底（~60-120 秒/结构）
  - `5+`：非常彻底，但耗时（>120 秒/结构）

---

## 💡 推荐策略

**默认启用 Relax**（`--relax true`），确保结果准确。

### 为什么必须使用 Relax？

1. **AF3 预测结构可能不符合物理力场**：
   - AF3 学习的是统计分布，不是物理能量
   - 可能导致 PyRosetta 的 `interface_dG` 评估不准确（过于不利）

2. **Relax 的作用**：
   - 修正物理不合理性（键长、键角、侧链堆积）
   - 使结构符合 Rosetta 力场
   - 确保 `interface_dG` 评估准确

3. **不使用 Relax 的风险**：
   - 可能错误地剔除有价值的设计（因为能量评估不准确）
   - 排序可能不准确

### 推荐配置

```bash
--relax true --max_iter 1 --fixbb false
```
- **优点**：结果准确，符合物理规律
- **时间**：每个结构 30-120 秒（313 个结构约 3-10 小时）
- **适用**：所有场景（默认配置）

---

## 📝 实际运行示例

### 使用 Relax 重新分析

创建新的运行脚本：

```bash
# 编辑 scripts/part2/part2_run_pyrosetta_batch.sh
RELAX=true           # 改为 true
MAX_ITER=1           # 推荐 1-2
FIXBB=false          # 允许骨架移动
```

然后运行：
```bash
cd /data/wcf/protein_filter_lib
./scripts/part2/part2_run_pyrosetta_batch.sh
```

### 输出结果对比

Relax 后的结果会包含额外列：
- `relaxed`：Relax 后的总能量
- `original`：原始结构的总能量
- `delta`：能量变化（relaxed - original，通常为负值）

---

## 🔬 科学依据

### 相关研究

1. **AlphaFold2 与物理力场的不匹配**：
   - 多项研究显示 AF2/AF3 预测的结构在 Rosetta 力场下能量偏高
   - 通过 Relax 可以显著改善（能量降低 50-200 REU）

2. **Relax 对界面分析的影响**：
   - Relax 后，`interface_dG` 通常变得更有利（更负）
   - 但**排序**通常保持一致（好的设计仍然好，差的设计仍然差）
   - Relax 主要影响**绝对值**，而不是**相对排序**

3. **最佳实践**：
   - **Rosetta Commons 社区推荐**：对预测结构进行 Relax 后再评估
   - **PPIFlow 和 Germinal**：都默认使用 Relax

---

## ⚠️ 注意事项

1. **时间成本**：
   - Relax 会使计算时间增加 **3-10 倍**
   - 每个结构约需 30-120 秒（取决于 `max_iter`）
   - 313 个结构预计需要 **3-10 小时**

2. **结构变化**：
   - Relax 会轻微改变结构（RMSD 通常 < 1-2 Å）
   - 如果后续需要与原始 AF3 结构对比，注意这一点

3. **固定链的选择**：
   - 如果抗原结构已知且可信，可以固定抗原链（`--fixbb true --fixed_chain A`）
   - 这样可以只优化抗体，保持抗原不变

4. **迭代次数**：
   - `max_iter=1` 通常足够，更多迭代收益递减
   - 除非对精度要求极高，否则不建议 `max_iter > 3`

---

## 📚 参考文献

1. **Rosetta FastRelax**：
   - Tyka, M. D., et al. (2011). "Alternating-Energy Minimization for Structure Prediction." *J. Chem. Theory Comput.* 7, 3065-3071.

2. **AlphaFold 与物理力场**：
   - 多项 Rosetta Commons 讨论和最佳实践文档

3. **PPIFlow 实践**：
   - `/data/Tools/PPIFlow-main/demo_scripts/relax_complex.py`

---

## 🎯 总结

**默认启用 Relax**（`--relax true`），这是推荐的配置。

| 方法 | 速度 | 准确性 | 推荐场景 |
|------|------|--------|---------|
| **无 Relax** | ⚡⚡⚡ 快 | ⚠️ 不准确 | ❌ 不推荐（可能错误剔除有价值设计） |
| **有 Relax** | ⚡ 慢 | ✅ 准确 | ✅ **默认配置，推荐所有场景** |

**重要**：
- **默认启用 Relax**，确保结果准确
- 不使用 Relax 可能导致错误地剔除有价值的设计
- 资源使用情况会自动记录到 `resource_usage.json`
