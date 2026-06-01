# Part 3: MD 计算（MM/PBSA、RMSD）— 模块说明

详细使用与续跑见 [PART3_使用与续跑说明.md](PART3_使用与续跑说明.md)。

Part 3 对 Part 2 筛选出的候选结构运行 **分子动力学（MD）** 与 **MM/PBSA**，输出结合自由能与 **RMSD** 统计，用于最终排序与选择。

## 1. 功能

- **MD**：GROMACS（amber14sb_parmbsc1、TIP3P、PME），pdb2pqr → 盒子/溶剂/离子 → EM → NPT → 生产。
- **MM/PBSA**：gmx_MMPBSA（PB + 非极性，蛋白-蛋白），链对分解（target vs binder）。
- **RMSD**：相对首帧 backbone 的 RMSD（`rmsd.xvg`），可选后续扩展为相对 `--reference`。
- **输入**：Part 2 的 `rosetta_static_*.csv`（含 `pdb_path`、`pdb_name`），或含 PDB/CIF 的目录。
- **输出**：`<output_dir>/part3_results.csv` 汇总；每结构子目录含 `mmgbsa_summary.csv`、`rmsd.xvg`、`FINAL_RESULTS_MMPBSA.dat` 等。

## 2. 链约定（与 Part 2 一致）

- **`--target_chain`**：默认 `A`，通常为抗原。
- **`--binder_chain`**：默认 `B`，通常为抗体。

Part 2 使用 `binder_chain=B`、`target_chain=A`；Part 3 沿用相同约定，确保 PDB/CIF 中链 ID 一致。

## 3. 依赖

- **GROMACS**（含 `gmx`）
- **gmx_MMPBSA**（Amber 拓扑 + PB，用于 MM/PBSA）
- **pdb2pqr**、**obabel**（pH、CIF→PDB）

力场 `amber14sb_parmbsc1` 已随 `YZC_MD_SCRIPT` 提供；GROMACS 通过 `GMXLIB` 指向脚本目录使用。

## 4. 用法

### 4.1 从 Part 2 CSV 运行（推荐）

```bash
cd /data/wcf/protein_filter_lib

python3 scripts/run_md_mmgbsa_rmsd.py \
  --input_csv /path/to/rosetta_static_0.csv \
  --output_dir /path/to/part3_output \
  --target_chain A \
  --binder_chain B \
  --top_n 20 \
  --production_ns 10 \
  --npt_ns 1 \
  --tmp 298.15 \
  --ph 7.4 \
  --conc 0.154 \
  --gpu_id 0 \
  --interval 5 \
  --ntomp 12
```

- **`--top_n`**：仅处理 `interface_score` 最优的前 N 个（0 表示全部）。
- **`--production_ns`** / **`--npt_ns`**：生产与 NPT 时长（ns）。

### 4.2 从目录扫描 PDB/CIF

```bash
python3 scripts/run_md_mmgbsa_rmsd.py \
  --input_dir /path/to/structures \
  --output_dir /path/to/part3_output \
  --target_chain A \
  --binder_chain B \
  --production_ns 10
```

会递归发现 `*.pdb`、`*.cif`、`*.mmcif`，并跳过路径中含 `seed-` 的文件。

### 4.3 单结构直接跑 Shell 脚本

```bash
./YZC_MD_SCRIPT/run_part3_md_single.sh \
  --structure /path/to/complex.pdb \
  --output_dir /path/to/run_dir \
  --target_chain A \
  --binder_chain B \
  --production_ns 10 \
  --npt_ns 1 \
  --tmp 298.15 \
  --ph 7.4 \
  --conc 0.154 \
  --gpu_id 0 \
  --interval 5 \
  --ntomp 12
```

支持 `.pdb` 或 `.cif`；CIF 会先转为 PDB 再跑 MD。

## 5. 输出说明

- **`part3_results.csv`**：汇总所有结构的 `pdb_name`、`structure_path`、`target_chain`、`binder_chain`、`mmgbsa_dG_kcal_mol`、`rmsd_mean_nm`、`rmsd_max_nm`、`error`。
- **`<output_dir>/<pdb_name>/mmgbsa_summary.csv`**：单结构 MM/PBSA 与 RMSD 摘要。
- **`<output_dir>/<pdb_name>/FINAL_RESULTS_MMPBSA.dat`**：gmx_MMPBSA 原始结果。
- **`<output_dir>/<pdb_name>/rmsd.xvg`**：backbone RMSD 随时间。

## 6. 与 Pipeline 的衔接

- **Part 1** → AF3 筛选与聚类，得到候选列表。
- **Part 2** → PyRosetta 静态分析，得到 `rosetta_static_*.csv`（含 `pdb_path`、`pdb_name`、`interface_score` 等）。
- **Part 3** → 读取 Part 2 CSV（或结构目录），对候选跑 MD + MM/PBSA，写 `part3_results.csv`，供最终排序与选择。

实现基于 `YZC_MD_SCRIPT/run_part3_md_single.sh`（改编自 `AutoMD_Protein_PBSA`），专为 **抗原-抗体复合物**（双链蛋白）做了链解析、index 组号、轨迹前处理（`-pbc mol`）与 MM/PBSA 蛋白力场等适配。详见 `YZC_MD_SCRIPT/MD_SCRIPT_ANALYSIS_AG_AB.md`。

## 7. 推荐配置清单

### 7.1 正式运行（100ns）

- **配置文件**：`config/part3_100ns.yaml`
- **Production**：100 ns
- **NPT**：1 ns
- **GPU**：8 张并行
- **适用场景**：最终筛选、正式分析

### 7.2 力场选择

- **`amber99sb`**（默认）：稳定、完整，推荐用于生产
- **`amber14sb_parmbsc1`**：DNA/RNA 优化，蛋白也可用
- **`charmm36`**：CHARMM 力场，需额外安装

## 8. 常见故障排查

### 8.1 GROMACS 相关

**问题**：`Only the md integrator is supported`（EM 阶段）
- **原因**：Energy Minimization（`steep`、`cg`）不支持 GPU 加速
- **解决**：脚本已自动处理，EM 阶段强制使用 CPU（`-update cpu -nb cpu`）

**问题**：`gmx pdb2gmx` 失败
- **检查**：力场文件是否存在（`GMXLIB` 环境变量）
- **解决**：确保 `GMXLIB` 指向正确的力场目录

### 8.2 gmx_MMPBSA 相关

**问题**：`MMPBSA_Error: Define a valid index group`
- **原因**：`index.ndx` 中缺少 `ChainA`、`ChainB` 组
- **解决**：脚本已自动创建 `index_mmpbsa.ndx`，使用残基范围定义链组

**问题**：MM/PBSA 结果异常（如 `ΔG` 为 0）
- **检查**：查看 `FINAL_RESULTS_MMPBSA.dat`，确认 `ΔTOTAL` 行
- **解决**：检查轨迹文件是否正常生成，`gmx trjconv` 是否成功

### 8.3 pdb2pqr / obabel 相关

**问题**：`No module named 'Bio'`（CIF 转 PDB）
- **原因**：BioPython 未安装
- **解决**：脚本优先使用 `obabel`，fallback 到 BioPython（需安装）

**问题**：`obabel` 转换失败
- **检查**：CIF 文件格式是否正确
- **解决**：手动检查 CIF 文件，或安装 BioPython 作为 fallback

### 8.4 GPU 相关

**问题**：所有任务都在 GPU 0 运行
- **检查**：`nvidia-smi` 查看 GPU 使用情况
- **解决**：确保 `--gpu_id` 参数正确传递，检查 `run.log` 中的 GPU 分配日志

**问题**：CPU 过载
- **检查**：`htop` 查看 CPU 使用率
- **解决**：降低 `--ntomp`（如从 12 降到 6），8 GPU 并行时建议 `ntomp=6`

### 8.5 Resume 相关

**问题**：Resume 不生效
- **检查**：确认 `status.json` 文件存在且 `status` 为 `success`
- **解决**：手动删除 `status.json` 或使用 `--rerun-failed` 重跑失败结构

## 9. 监控命令

```bash
# GPU 使用情况
watch -n 5 nvidia-smi

# CPU 使用情况
htop

# 查看各 GPU 任务进度
tail -f <output_dir>/runs/<run_id>/gpu*/run.log

# 统计已完成结构数
find <output_dir>/runs/<run_id>/gpu* -name "status.json" -exec grep -l "success" {} \; | wc -l
```
