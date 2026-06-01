# Part 3 运行时间与 GPU 加速说明

## 1. 当前测试配置的时间估算

### 测试配置（快速验证）
- **NPT 平衡**：1 ns
- **Production MD**：1 ns
- **总 MD 时间**：2 ns

### 实际运行时间（基于当前测试）

**性能指标**（NPT 阶段）：
- **速度**：727.427 ns/day
- **每 ns 耗时**：约 0.033 小时（约 **2 分钟/ns**）

**总时间估算**：
- **NPT (1 ns)**：约 2 分钟
- **Production (1 ns)**：约 2 分钟
- **预处理**（pdb2pqr, pdb2gmx, 盒子, 溶剂, 离子, EM）：约 2-3 分钟
- **轨迹处理**（trjconv, RMSD）：约 1 分钟
- **MM/PBSA**：约 5-15 分钟（取决于帧数和系统大小）
- **总计**：约 **12-23 分钟**（测试配置）

### 生产环境配置（推荐）

对于实际筛选，建议：
- **NPT 平衡**：1-2 ns（足够平衡）
- **Production MD**：10-100 ns（取决于需求）
- **总 MD 时间**：11-102 ns

**时间估算**（基于 727 ns/day）：
- **11 ns**：约 22 分钟 MD + 预处理 + MM/PBSA = **约 30-40 分钟**
- **100 ns**：约 200 分钟（3.3 小时）MD + 预处理 + MM/PBSA = **约 3.5-4 小时**

## 2. GPU 加速状态

### 当前配置

✅ **已启用 GPU 加速**

脚本已配置使用 GPU：
```bash
--gpu_id 0  # 使用 GPU 0
```

在 `run_part3_md_single.sh` 中：
```bash
if command -v nvidia-smi &>/dev/null; then
    gmx mdrun ... -update gpu -gpu_id "$gpu_id" ...
else
    gmx mdrun ... # CPU only
fi
```

### GPU 使用情况

**可用 GPU**：
- 8 × NVIDIA GeForce RTX 4090（24 GB 显存）
- 当前测试使用 GPU 0

**GPU 加速效果**：
- **CPU only**：约 50-100 ns/day（取决于 CPU 核心数）
- **GPU 加速**：约 700-800 ns/day（**7-16 倍加速**）

### 优化建议

#### 1. 多 GPU 并行（多结构）

对于批量运行多个结构，可以：
- 使用不同的 `--gpu_id` 并行运行多个结构
- 例如：结构 1 用 GPU 0，结构 2 用 GPU 1，...

```bash
# 并行运行多个结构（使用不同 GPU）
for i in {0..7}; do
    python3 scripts/run_md_mmgbsa_rmsd.py \
        --input_csv rosetta_static_0.csv \
        --output_dir output_gpu${i} \
        --gpu_id ${i} \
        --top_n 10 &
done
wait
```

#### 2. 单结构多 GPU（不推荐）

GROMACS 2021.4 支持多 GPU，但对于单个结构（~50k 原子），单 GPU 已足够：
- 多 GPU 主要用于超大系统（>100k 原子）
- 当前系统大小：~50k 原子（蛋白 + 水 + 离子）

#### 3. GPU 选择策略

```bash
# 检查 GPU 使用情况
nvidia-smi

# 选择空闲 GPU
--gpu_id 0  # 如果 GPU 0 空闲
--gpu_id 1  # 如果 GPU 1 空闲
```

## 3. 性能优化建议

### 对于批量筛选

**策略 1：串行运行（单 GPU）**
- 优点：简单，资源占用可控
- 缺点：总时间长
- 适用：少量结构（<10）

**策略 2：并行运行（多 GPU）**
- 优点：总时间短
- 缺点：需要管理多个进程
- 适用：大量结构（>10）

**策略 3：混合策略**
- 对 top N 候选并行运行（多 GPU）
- 其他结构串行运行（单 GPU）

### 时间优化

1. **减少 Production 时间**：
   - 快速筛选：10 ns（约 20 分钟 MD）
   - 精细分析：50-100 ns（约 1.5-3 小时 MD）

2. **优化 MM/PBSA 间隔**：
   - `--interval 10`：每 10 帧分析一次（默认）
   - `--interval 20`：每 20 帧分析一次（更快，精度略降）

3. **使用更短的 NPT**：
   - 1 ns 通常足够平衡（当前配置）

## 4. 实际运行时间示例

### 测试配置（1 ns NPT + 1 ns Production）
- **总时间**：约 12-23 分钟
- **MD 部分**：约 4 分钟
- **MM/PBSA**：约 5-15 分钟

### 生产配置（1 ns NPT + 10 ns Production）
- **总时间**：约 30-40 分钟
- **MD 部分**：约 22 分钟
- **MM/PBSA**：约 5-15 分钟

### 精细配置（2 ns NPT + 100 ns Production）
- **总时间**：约 3.5-4 小时
- **MD 部分**：约 3.3 小时
- **MM/PBSA**：约 10-20 分钟

## 5. 总结

✅ **GPU 已启用**：当前脚本已配置 GPU 加速（`-update gpu -gpu_id 0`）

✅ **性能良好**：约 727 ns/day，每 ns 约 2 分钟

✅ **可并行化**：8 个 GPU 可用于并行运行多个结构

**建议**：
- 对于快速筛选：使用 10 ns Production（约 30-40 分钟/结构）
- 对于精细分析：使用 50-100 ns Production（约 2-4 小时/结构）
- 批量运行：使用多 GPU 并行（每个 GPU 一个结构）
