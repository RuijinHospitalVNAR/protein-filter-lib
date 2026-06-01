# Plan: 使用新参数运行真实样例测试

## 目标
验证修改后的Part3脚本完整流程（MD + MMPBSA），使用新的ff19SB力场参数。

## 输入准备
- 使用已有的benchmark预构建拓扑文件跳过慢的tleap初始化
- 输出目录: `/data/wcf/protein_filter_lib/examples/test_pipeline/part3_ff19sb_test`

## 参数设置
```bash
--input_csv: 使用benchmark CSV或直接用预构建文件
--production_ns: 1 (测试用)
--npt_ns: 0 (最小预平衡)
--forcefield: ff19SB
--buffer: 8.0
--interval: 5
```

## 执行步骤

### Step 1: 准备输入
- 方案A: 复制benchmark预构建文件到新目录
- 方案B: 直接用AMBER脚本的--resume跳过tleap

### Step 2: 运行MD (1ns)
- 使用ff19SB/opc力场
- 轨迹输出: md_1.nc

### Step 3: 运行MMPBSA
- postprocess去水
- MM/GBSA计算
- RMSD计算

### Step 4: 验证结果
- md_1.nc存在
- FINAL_RESULTS_MMGBSA_BINDING.dat存在
- rmsd_bb.dat存在
- mmgbsa_summary.csv存在

## 预期结果
完整的MD(1ns) + MMPBSA流程成功，输出文件齐全。

## 时间估算
- MD (1ns): ~3-5分钟
- MMPBSA: ~5-10分钟
- 总计: ~15分钟