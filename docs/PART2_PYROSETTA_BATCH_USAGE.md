# Part 2 PyRosetta 批量分析使用指南

## 环境配置

已创建 **VNAR_OP** conda 环境，包含 PyRosetta 和所有依赖。

### 快速开始

```bash
# 1. 激活环境
conda activate VNAR_OP

# 2. 运行批量分析（已配置好路径）
cd /data/wcf/protein_filter_lib
./scripts/part2/part2_run_pyrosetta_batch.sh
```

### 配置说明

**`scripts/part2/part2_run_pyrosetta_batch.sh`** 中的配置：

- `INPUT_DIR`: AF3 预测结果目录
- `OUTPUT_DIR`: 输出目录（同级新文件夹）
- `BINDER_CHAIN`: 抗体链（默认 B）
- `TARGET_CHAIN`: 抗原链（默认 A）
- `RELAX`: 是否先 Relax（默认 false，更快）
- `--only_main_models true`: **只分析主模型**（排除 seed- 目录中的文件）

## 功能特性

1. **自动 CIF 转 PDB**：AF3 的 mmCIF 文件会自动转换为 PDB 格式供 PyRosetta 使用
2. **只分析主模型**：自动排除 `seed-*` 目录中的文件，只处理每个设计的主模型（如 `C87S/C87S/C87S_model.cif`）
3. **错误处理**：单个文件失败不会中断整个流程
4. **进度显示**：每处理 50 个文件显示进度

## 输出结果

- **CSV 文件**: `<output_dir>/rosetta_static_0.csv`
  - `pdb_name`: 结构名称
  - `pdb_path`: 文件路径
  - `interface_score`: 界面结合自由能（interface_dG，kcal/mol，越低越好）
  - `interface_delta_sasa`: 界面埋藏表面积（Å²）
  - `complexed_sasa`: 复合物表面积（Å²）
  - `time_consumed`: 处理时间（秒）

## 监控进度

```bash
# 查看实时进度
./monitor_pyrosetta_batch.sh

# 或查看日志
tail -f /data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_output_pyrosetta/run.log
```

## 环境安装（如需要重新安装）

```bash
cd /data/wcf/protein_filter_lib
./setup_VNAR_OP.sh
```

脚本会自动：
1. 创建 VNAR_OP conda 环境
2. 安装所有依赖（numpy, pandas, biopython 等）
3. 安装 protein_filter_lib
4. 解压并配置 PyRosetta
5. 测试 PyRosetta 导入

## 注意事项

- **处理时间**：每个结构约需 5-15 秒，313 个结构预计需要 30-80 分钟
- **临时文件**：CIF 转 PDB 的临时文件保存在 `<output_dir>/.temp_pdb/`，可定期清理
- **内存使用**：PyRosetta 初始化会占用一定内存，建议至少 4GB 可用内存
