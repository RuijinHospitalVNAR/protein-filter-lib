# Part 3 MM/PBSA 结果解读指南

## 结果文件说明

### 1. FINAL_RESULTS_MMPBSA.dat
MM/PBSA 计算的详细结果文件，包含：
- Complex（复合物）、Receptor（受体）、Ligand（配体）的能量组分
- Delta（结合能）= Complex - Receptor - Ligand
- 各能量组分的平均值、标准差、标准误差

### 2. FINAL_DECOMP_MMPBSA.dat
残基分解结果（如果启用了 decomposition），显示每个残基对结合能的贡献。

### 3. mmgbsa_summary.csv
汇总结果 CSV，包含：
- `mmgbsa_dG_kcal_mol`: 结合自由能（kcal/mol）
- `rmsd_mean_nm`: 平均 RMSD（nm）
- `rmsd_max_nm`: 最大 RMSD（nm）

## 关键指标解读

### 结合自由能 (ΔG_binding = ΔTOTAL)

**位置**: `FINAL_RESULTS_MMPBSA.dat` 中的 `ΔTOTAL` 行

**解读**:
- **负值** = 有利结合（自发结合）
- **正值** = 不利结合
- **数值越小（越负）** = 结合越强

**典型范围**:
- 强结合: < -10 kcal/mol
- 中等结合: -5 到 -10 kcal/mol
- 弱结合: -1 到 -5 kcal/mol
- 不结合: > -1 kcal/mol

**示例结果**:
```
ΔTOTAL = -6.88 kcal/mol
```
- 表示中等强度的有利结合
- 标准差: 11.97 kcal/mol（较大，说明帧间波动）
- 标准误差: 3.61 kcal/mol

### 能量组分分解

**ΔGGAS** (气相结合能):
- 来自范德华力和静电相互作用
- 通常为负值（有利）

**ΔGSOLV** (溶剂化能):
- 来自溶剂效应（PBSA）
- 通常为正值（不利，因为结合时失去溶剂化）

**ΔTOTAL = ΔGGAS + ΔGSOLV**

**示例**:
```
ΔGGAS  = -564.67 kcal/mol  (气相有利)
ΔGSOLV = +557.79 kcal/mol  (溶剂化不利，几乎抵消)
ΔTOTAL = -6.88 kcal/mol    (净结合能)
```

### RMSD 指标

**rmsd_mean_nm**: 平均 backbone RMSD
- 反映结构稳定性
- 通常 < 0.3 nm 表示结构稳定

**rmsd_max_nm**: 最大 RMSD
- 反映结构最大偏离
- 通常 < 0.5 nm 表示结构稳定

## 结果是否正常？

### ✅ 正常结果的特征：
1. **文件完整**: `FINAL_RESULTS_MMPBSA.dat` 包含完整的能量组分
2. **数值合理**: 
   - ΔTOTAL 通常在 -20 到 +20 kcal/mol 范围内
   - RMSD < 0.5 nm
3. **误差可接受**: SEM < 5 kcal/mol（对于结合能）
4. **计算完成**: 日志显示 "Finalized" 且无严重错误

### ⚠️ 需要注意的情况：
1. **标准差过大** (> 20 kcal/mol): 可能帧数不足或结构不稳定
2. **ΔTOTAL 接近 0**: 结合很弱，可能不显著
3. **RMSD 过大** (> 1 nm): 结构可能不稳定或模拟时间不足

## 查看结果的命令

```bash
# 查看结合自由能
grep "ΔTOTAL" FINAL_RESULTS_MMPBSA.dat

# 查看能量组分
grep -E "ΔGGAS|ΔGSOLV" FINAL_RESULTS_MMPBSA.dat

# 查看汇总CSV
cat mmgbsa_summary.csv

# 查看RMSD统计
awk '!/^[@#]/{sum+=$2;n++;if($2>m)m=$2}END{print "平均:",sum/n,"最大:",m}' rmsd.xvg
```

## 结果文件位置

测试目录: `/data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_part3_test`

- `FINAL_RESULTS_MMPBSA.dat`: MM/PBSA 详细结果
- `FINAL_DECOMP_MMPBSA.dat`: 残基分解结果
- `mmgbsa_summary.csv`: 汇总 CSV（如果已生成）
- `rmsd.xvg`: RMSD 随时间变化
