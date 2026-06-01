# AlphaFold 3 最佳多聚体结构分析计划

## 目标
对 AlphaFold 3 预测的 A9 蛋白多聚体结构（ipTM 最佳）中每种类型选择一个最佳结构，进行 Part2 (PyRosetta) 和 Part3 (AMBER MD) 分析。

## 最佳结构选择

| 聚合体 | 文件路径 | ipTM | pTM | 置信度排名 |
|--------|----------|------|-----|-----------|
| **二聚体** | `dimer/output/A9_dimer/seed-389_sample-2/A9_dimer_seed-389_sample-2_model.cif` | 0.450 | 0.690 | #1 |
| **三聚体** | `trimer/output/A9_trimer/seed-192_sample-0/A9_trimer_seed-192_sample-0_model.cif` | 0.160 | 0.420 | #1 |
| **四聚体** | `tetramer/output/A9_tetramer_20260422_135013/seed-430_sample-0/A9_tetramer_seed-430_sample-0_model.cif` | 0.370 | 0.520 | #1 |

## 分析流程

### 阶段 1: 结构准备
1. 复制最佳结构文件到统一目录
2. CIF/PDB 格式转换
3. 结构检查和修复

### 阶段 2: Part2 - PyRosetta 结构优化
1. 运行 PyRosetta 静态松弛
2. 生成优化后的 PDB 文件
3. 输出: `*_relaxed.pdb`

### 阶段 3: Part3 - AMBER MD 模拟
1. 系统构建 (tleap)
2. 能量最小化
3. 加热过程
4. 平衡过程
5. 成品 MD (1ns)
6. MMPBSA 结合自由能计算

## 目录结构

```
/data/wcf/protein_filter_lib/examples/best_multimers_analysis/
├── dimer/
│   ├── input/
│   ├── part2_output/
│   └── part3_output/
├── trimer/
│   ├── input/
│   ├── part2_output/
│   └── part3_output/
└── tetramer/
    ├── input/
    ├── part2_output/
    └── part3_output/
```

## 预计时间

| 阶段 | 二聚体 | 三聚体 | 四聚体 |
|------|--------|--------|--------|
| Part2 PyRosetta | ~30 min | ~45 min | ~60 min |
| Part3 tleap | ~20 min | ~25 min | ~30 min |
| Part3 MD (1ns) | ~2-3 hours | ~2-3 hours | ~2-3 hours |
| MMPBSA | ~30 min | ~30 min | ~30 min |
| **总计** | ~4-5 hours | ~4-5 hours | ~5-6 hours |

## 注意事项

1. **四聚体较大**: 需要更多内存和时间
2. **MD 长度**: 1ns 可能不足以观察稳定行为
3. **三聚体 ipTM 较低**: 结果可靠性可能较低

## 依赖资源

- GPU: 可用（需要为 MD 预留）
- 内存: 每个任务需要 ~30GB
- 磁盘: 每个任务需要 ~10GB
