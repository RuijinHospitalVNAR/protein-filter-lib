# ipSAE 计算与筛选集成分析报告

## 1. 脚本版本对比

### IPSAE-main/ipsae.py
- **版本**: v3 (April 6, 2025)
- **来源**: DunbrackLab/IPSAE 官方仓库
- **状态**: 旧版本

### scripts/ipsae.py
- **版本**: v4 (January 3, 2026)
- **更新**: 修复了 Boltz2 问题（PDB 和 mmCIF 格式，chainIDs）
- **状态**: ✅ **当前使用版本**（更新）

## 2. ipSAE 核心计算逻辑分析

### 2.1 计算步骤（符合 Dunbrack/Levitate 描述）

根据 `scripts/ipsae.py` 的实现，ipSAE 计算遵循以下步骤：

#### 步骤 1: 过滤高置信度残基对
```python
# 只使用 PAE < cutoff 的残基对（高置信度界面区域）
valid_pairs_matrix = np.outer(chains == chain1, chains == chain2) & (pae_matrix < pae_cutoff)
```
✅ **符合 Levitate 描述**：只包含 PAE 低的残基对，过滤掉低质量对齐

#### 步骤 2: 计算 d0（基于高置信度残基数）
```python
# d0res: 基于每个残基 i 对应的 chain2 中 PAE < cutoff 的残基数
n0res_byres_all = np.sum(valid_pairs_matrix, axis=1)
d0res_byres_all = calc_d0_array(n0res_byres_all, chain_pair_type[chain1][chain2])
```
✅ **符合 Levitate 描述**：长度归一化只考虑高置信度残基，而非全长

#### 步骤 3: 使用 PAE 直接计算 PTM 分数
```python
# 对每个残基 i，使用对应的 d0 计算 PTM 矩阵
ptm_row_d0res = ptm_func_vec(pae_matrix[i], d0res_byres[chain1][chain2][i])
# PTM 函数: 1.0/(1+(x/d0)**2.0)
ipsae_d0res_byres[chain1][chain2][i] = ptm_row_d0res[valid_pairs].mean()
```
✅ **符合 Levitate 描述**：直接使用 PAE 值计算残基-残基对齐分数，而非概率分布

#### 步骤 4: 取最大值作为链对分数
```python
# 对每个残基的 ipSAE 值，取最大值
interchain_values = ipsae_d0res_byres[chain1][chain2]
max_index = np.argmax(interchain_values)
ipsae_d0res_asym[chain1][chain2] = interchain_values[max_index]

# 取对称对的最大值（A->B 和 B->A 的最大值）
maxvalue = max(ipsae_d0res_asym[chain1][chain2], ipsae_d0res_asym[chain2][chain1])
ipsae_d0res_max[chain1][chain2] = maxvalue  # 这就是输出的 "ipSAE"
```

### 2.2 三种 ipSAE 变体

脚本输出三种 ipSAE 变体：

1. **`ipSAE`** (即 `ipsae_d0res_max`): ✅ **主要分数**
   - d0 基于每个残基对应的 chain2 中 PAE < cutoff 的残基数
   - **这是推荐使用的分数**（对应 Levitate 文章中的 ipSAE）

2. **`ipSAE_d0chn`**: d0 = 链长度之和（len(chain1) + len(chain2)）
   - 使用全长，但仍有 PAE cutoff 过滤

3. **`ipSAE_d0dom`**: d0 = 两个链中任何链间 PAE < cutoff 的残基总数
   - 使用域残基数

### 2.3 计算合理性验证

✅ **符合 Dunbrack 论文**：
- 只使用 PAE < cutoff 的残基对
- d0 归一化基于高置信度残基数
- 直接使用 PAE 值（非概率分布）

✅ **符合 Levitate 文章**：
- 高 ipSAE = 高界面置信度
- > 0.6 常用作可能结合
- 真实互作多接近 0.8

## 3. 筛选集成检查

### 3.1 在 `analyze_af3_three_stage.py` 中的集成

#### 提取 ipSAE（第 242-250 行）
```python
# 尝试提取ipSAE（如果存在）
if 'ipsae' not in metrics:
    for key in ['ipsae', 'ipSAE', 'ipsae_score']:
        if key in metrics:
            metrics['ipsae'] = metrics[key]
            break
```
✅ **正确**：从 JSON 或计算结果中提取 ipSAE

#### 筛选逻辑（第 388-392 行）
```python
# ipSAE筛选（如果存在）。高 ipSAE = 高界面置信度，须 >= 阈值才通过
ipsae = metrics.get('ipsae', None)
if ipsae is not None and ipsae < ipsae_threshold:
    filter_stats['failed_ipsae'] += 1
    passed = False
    continue
```
✅ **正确**：**ipSAE >= 阈值** 才通过（已修复，之前误用 `<=`）

#### 默认阈值（第 279 行）
```python
ipsae_threshold: float = 0.6,
```
✅ **正确**：默认 0.6，符合 Levitate 的 "> 0.6 常用作可能结合"

#### 日志输出（第 409, 419 行）
```python
logger.info(f"  - ipSAE >= {ipsae_threshold} (如果存在)")
logger.info(f"    * ipSAE不足: {filter_stats['failed_ipsae']}")
```
✅ **正确**：明确显示 "ipSAE >= 阈值" 和 "ipSAE不足"

### 3.2 在 `IPSAECalculator` 中的集成

#### 调用 ipsae.py 脚本（calculators.py 第 774-880 行）
```python
from ..utils.ipsae_utils import calculate_ipsae_from_script
all_metrics = calculate_ipsae_from_script(
    json_path=json_path,
    pdb_path=pdb_path,
    pae_cutoff=self.pae_cutoff,
    dist_cutoff=self.distance_cutoff,
    ipsae_script_path=self.ipsae_script_path,
)
```
✅ **正确**：使用 `ipsae_utils.py` 封装调用官方脚本

#### 解析输出（ipsae_utils.py 第 100-136 行）
```python
# 解析 ipsae.py 的输出
# Format: Chn1 Chn2 PAE Dist Type ipSAE ipSAE_d0chn ipSAE_d0dom ipTM_af ...
ipsae = float(parts[5])  # 第 5 列是 ipSAE（即 ipsae_d0res_max）
metrics["ipsae"] = ipsae
```
✅ **正确**：正确解析 `ipSAE` 列（对应 `ipsae_d0res_max`）

### 3.3 脚本路径查找

`ipsae_utils.py` 按以下顺序查找 `ipsae.py`：
1. `scripts/ipsae.py` ✅ **推荐位置**（当前使用）
2. `ipsae.py`（项目根目录）
3. `tools/ipsae.py` 或 `external/ipsae.py`
4. 当前工作目录
5. 用户本地 bin

✅ **正确**：优先使用 `scripts/ipsae.py`（v4，最新版本）

## 4. 总结

### ✅ ipSAE 计算合理性

1. **算法实现**：✅ 完全符合 Dunbrack 论文和 Levitate 文章描述
   - 只使用 PAE < cutoff 的残基对
   - d0 归一化基于高置信度残基数
   - 直接使用 PAE 值计算（非概率分布）

2. **脚本版本**：✅ 使用最新版本（v4，2026-01-03）
   - 修复了 Boltz2 问题
   - 位于 `scripts/ipsae.py`

3. **输出解析**：✅ 正确解析 `ipSAE` 列（对应 `ipsae_d0res_max`）

### ✅ 筛选集成正确性

1. **筛选方向**：✅ **已修复**
   - 使用 **ipSAE >= 阈值** 通过（之前误用 `<=`，已修正）
   - 默认阈值 0.6（符合 Levitate 建议）

2. **提取逻辑**：✅ 正确从 JSON 或计算结果中提取 ipSAE

3. **错误处理**：✅ 如果 ipSAE 不存在，跳过此筛选条件

4. **日志输出**：✅ 明确显示筛选条件和失败原因

### ⚠️ 建议

1. **统一脚本版本**：考虑将 `IPSAE-main/ipsae.py`（v3）更新为 `scripts/ipsae.py`（v4），或删除旧版本

2. **文档说明**：已在 `docs/IPSAE_METRICS_COMPARISON.md` 中添加 ipSAE 解读说明（Dunbrack/Levitate）

3. **阈值建议**：
   - **严格筛选**：ipSAE >= 0.6（可能结合）
   - **宽松筛选**：ipSAE >= 0.45（包含更多候选）
   - **高质量**：ipSAE >= 0.8（真实互作）

## 5. 验证测试

建议运行以下测试验证 ipSAE 计算和筛选：

```bash
# 使用已知结构的 AF3 预测结果
python3 scripts/ipsae.py \
  <af3_json_file> \
  <af3_cif_file> \
  5.0 5.0

# 检查输出的 ipSAE 值是否合理（应在 0-1 之间，高值表示高置信度）
# 然后运行三阶段脚本，验证筛选逻辑
python3 analyze_af3_three_stage.py \
  <pdb_dir> \
  --ipsae-threshold 0.6 \
  ...
```

---

**结论**：ipSAE 计算逻辑**合理且正确**，筛选集成**已修复并正确**。✅
