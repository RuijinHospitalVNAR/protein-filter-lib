# FastRelax 参数配置对比与分析

## 📊 三种配置对比

### 1. Germinal 配置

**来源**: `germinal/filters/pyrosetta_utils.py:pr_relax()`

```python
fastrelax = FastRelax()
scorefxn = pr.get_fa_scorefxn()
fastrelax.set_scorefxn(scorefxn)
fastrelax.set_movemap(mmf)
fastrelax.max_iter(200)                                    # ✅ 200次迭代
fastrelax.min_type("lbfgs_armijo_nonmonotone")            # ✅ 设置最小化类型
fastrelax.constrain_relax_to_start_coords(True)            # ✅ 约束到起始坐标

# MoveMap 配置
mmf = MoveMap()
mmf.set_chi(True)      # 允许侧链移动
mmf.set_bb(True)       # 允许骨架移动
mmf.set_jump(False)    # 禁止整体链移动

# 后续处理
# - 对齐到原始结构（AlignChainMover）
# - 复制 B factors
```

**特点**：
- ✅ **200次迭代**：更彻底，但耗时（每个结构可能需要几分钟）
- ✅ **约束到起始坐标**：保持结构接近原始，避免大幅改变
- ✅ **LBFGS最小化**：使用更高级的最小化算法
- ✅ **对齐步骤**：确保 Relax 后的结构与原始对齐

---

### 2. PPIFlow 配置

**来源**: `PPIFlow-main/demo_scripts/relax_complex.py`

```python
fr = FastRelax()
fr.set_scorefxn(scorefxn)
fr.max_iter(int(args.max_iter))                           # ✅ 可配置迭代次数（通常1-5）
movemap = MoveMap()
movemap.set_bb(True)                                      # ✅ 允许骨架移动
movemap.set_chi(True)                                     # ✅ 允许侧链移动
fr.set_movemap(movemap)
fr.apply(pose)
```

**特点**：
- ✅ **可配置迭代次数**：通常使用 1-5 次（快速模式）
- ❌ **无约束**：不约束到起始坐标，可能改变较大
- ❌ **无最小化类型设置**：使用默认最小化
- ❌ **无对齐步骤**：直接使用 Relax 后的结构

---

### 3. 当前脚本配置

**来源**: `scripts/run_pyrosetta_static.py`

```python
fr = FastRelax()
fr.set_scorefxn(scorefxn)
fr.max_iter(max_iter)                                     # ✅ 可配置（默认1）
mm = MoveMap()
mm.set_bb(True)                                           # ✅ 允许骨架移动
mm.set_chi(True)                                          # ✅ 允许侧链移动
if fixbb and fixed_chains:                                # ✅ 支持固定特定链
    for i in range(1, pose.total_residue() + 1):
        ch = pose.pdb_info().chain(i)
        mm.set_bb(i, ch not in fixed_chains)
fr.set_movemap(mm)
fr.apply(pose)
```

**特点**：
- ✅ **可配置迭代次数**：默认1次（快速）
- ❌ **无约束**：不约束到起始坐标
- ❌ **无最小化类型设置**：使用默认最小化
- ✅ **支持 fixbb**：可以固定特定链的骨架

---

## 🔍 关键参数说明

### `max_iter`（迭代次数）

| 值 | 效果 | 时间 | 适用场景 |
|---|------|------|---------|
| **1** | 快速优化 | ~30-60秒 | 大规模筛选（推荐） |
| **2-3** | 中等优化 | ~60-120秒 | 中等规模筛选 |
| **5** | 较好优化 | ~120-180秒 | 小规模精细筛选 |
| **200** (Germinal) | 非常彻底 | ~3-10分钟 | 单个结构精细优化 |

**建议**：
- **大规模筛选（313个结构）**：使用 **1-2 次迭代**
- **最终候选评估**：可以使用 **3-5 次迭代**

---

### `constrain_relax_to_start_coords`（约束到起始坐标）

**作用**：
- `True`：限制 Relax 后的结构不能偏离原始结构太远
- `False`：允许更大的结构变化

**影响**：
- **True**：更保守，保持 AF3 预测的整体结构
- **False**：更激进，可能改变更大，但优化更彻底

**建议**：
- **AF3 预测结构**：建议使用 `True`（保持预测的折叠）
- **对接结构**：可以使用 `False`（允许更大优化）

---

### `min_type`（最小化类型）

**选项**：
- `"lbfgs_armijo_nonmonotone"`：LBFGS 算法，更高级，收敛更快
- 默认：通常使用简单的梯度下降

**影响**：
- LBFGS：通常收敛更快，但内存占用稍高
- 默认：更稳定，但可能稍慢

**建议**：
- **大规模筛选**：可以使用默认（更稳定）
- **精细优化**：使用 LBFGS（更快收敛）

---

### MoveMap 配置

**关键设置**：
- `set_bb(True)`：允许骨架移动
- `set_chi(True)`：允许侧链移动
- `set_jump(False)`：禁止整体链移动（保持相对位置）

**fixbb 模式**：
- 固定特定链的骨架，只优化其他链
- 适用于：保持抗原结构不变，只优化抗体

---

## 💡 推荐配置

### 配置 1：快速筛选（当前默认，推荐）

```python
fr = FastRelax()
fr.set_scorefxn(scorefxn)
fr.max_iter(1)                    # 快速，1次迭代
mm = MoveMap()
mm.set_bb(True)
mm.set_chi(True)
fr.set_movemap(mm)
fr.apply(pose)
```

**优点**：
- ✅ 快速（~30-60秒/结构）
- ✅ 适合大规模筛选
- ✅ 结果通常足够准确

**缺点**：
- ⚠️ 可能不如多次迭代彻底

---

### 配置 2：平衡模式（推荐用于最终筛选）

```python
fr = FastRelax()
fr.set_scorefxn(scorefxn)
fr.max_iter(2)                                    # 2次迭代
fr.constrain_relax_to_start_coords(True)          # 约束到起始坐标
fr.min_type("lbfgs_armijo_nonmonotone")          # LBFGS最小化
mm = MoveMap()
mm.set_bb(True)
mm.set_chi(True)
mm.set_jump(False)                                # 禁止整体移动
fr.set_movemap(mm)
fr.apply(pose)
```

**优点**：
- ✅ 更彻底（~60-120秒/结构）
- ✅ 保持结构接近原始
- ✅ 使用高级最小化算法

**缺点**：
- ⚠️ 比配置1慢约2倍

---

### 配置 3：Germinal 风格（精细优化）

```python
fr = FastRelax()
fr.set_scorefxn(scorefxn)
fr.max_iter(200)                                  # 200次迭代
fr.min_type("lbfgs_armijo_nonmonotone")          # LBFGS最小化
fr.constrain_relax_to_start_coords(True)         # 约束到起始坐标
mm = MoveMap()
mm.set_bb(True)
mm.set_chi(True)
mm.set_jump(False)
fr.set_movemap(mm)
fr.apply(pose)

# 对齐到原始结构
align = AlignChainMover()
align.source_chain(0)
align.target_chain(0)
align.pose(start_pose)
align.apply(pose)
```

**优点**：
- ✅ 非常彻底
- ✅ 保持结构对齐

**缺点**：
- ⚠️ 非常慢（~3-10分钟/结构）
- ⚠️ 不适合大规模筛选

---

## 🎯 针对你的场景的建议

### 场景：313个 AF3 预测结构，需要快速筛选

**推荐配置**：

```python
# 快速模式（当前默认）
max_iter = 1
constrain_relax_to_start_coords = False  # 或 True（如果希望更保守）
min_type = None  # 使用默认
```

**理由**：
1. **313个结构**：需要快速处理
2. **AF3 预测**：通常质量较好，1次迭代通常足够
3. **筛选目的**：快速识别最佳候选，后续可以精细优化

**预计时间**：
- 单进程：~8-10小时
- 32进程：~15-30分钟

---

### 如果时间允许，使用平衡模式

```python
max_iter = 2
constrain_relax_to_start_coords = True
min_type = "lbfgs_armijo_nonmonotone"
```

**预计时间**：
- 32进程：~30-60分钟

---

## 📝 建议的改进

可以考虑添加以下参数到脚本：

1. **`--constrain_coords`**：是否约束到起始坐标（默认 False，快速模式）
2. **`--min_type`**：最小化类型（默认 None，使用默认算法）
3. **`--align_after_relax`**：Relax 后是否对齐（默认 False）

这样可以根据需要选择不同的配置模式。
