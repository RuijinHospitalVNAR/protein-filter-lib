# Part 3 配置指南

本文档说明如何使用 YAML 配置文件驱动 Part 3 运行。

## 配置文件位置

- `config/part3.yaml` - 默认配置
- `config/part3_100ns.yaml` - 正式运行配置（100ns）

## 配置结构

```yaml
# 输入配置
input:
  csv: ""              # Part 2 CSV 文件路径
  dir: ""               # 或结构目录路径
  top_n: 30             # 仅处理前 N 个结构（0=全部）

# 链约定
chains:
  target_chain: "A"     # 抗原链
  binder_chain: "B"     # 抗体链

# 物理参数
physics:
  temperature: 298.15   # K
  ph: 7.4
  ion_concentration: 0.154  # M

# MD 参数
md:
  production_ns: 100    # 生产模拟时长（ns）
  npt_ns: 1            # NPT 平衡时长（ns）
  interval: 5          # MM/PBSA 取帧间隔

# 力场
forcefield: "amber99sb"

# 资源分配
resources:
  n_gpu: 8             # 总 GPU 数
  gpu_ids: [0, 1, 2, 3, 4, 5, 6, 7]
  ntomp: 6             # 每个任务的 OpenMP 线程数

# 输出配置
output:
  base_dir: ""         # 输出根目录（必填）
  run_id: ""           # 运行 ID（自动生成）
  structure_subdir: true

# Resume 选项
resume:
  enabled: false       # 是否启用 resume
  rerun_failed: false  # 是否只重跑失败结构
```

## 使用方式

### 1. 使用预设配置

```bash
# 正式运行
python3 scripts/run_part3.py \
  --config config/part3_100ns.yaml \
  --input_csv /path/to/rosetta_static_0.csv \
  --output_dir /path/to/output
```

### 2. 命令行覆盖配置

```bash
# 覆盖单个参数
python3 scripts/run_part3.py \
  --config config/part3.yaml \
  --input_csv /path/to/rosetta_static_0.csv \
  --output_dir /path/to/output \
  --production_ns 50 \
  --top_n 20

# 覆盖多个参数
python3 scripts/run_part3.py \
  --config config/part3.yaml \
  --input_csv /path/to/rosetta_static_0.csv \
  --output_dir /path/to/output \
  --production_ns 50 \
  --npt_ns 2 \
  --top_n 20 \
  --n_gpu 4
```

### 3. 自定义配置

复制预设配置并修改：

```bash
cp config/part3.yaml config/my_custom.yaml
# 编辑 config/my_custom.yaml
python3 scripts/run_part3.py \
  --config config/my_custom.yaml \
  --input_csv /path/to/rosetta_static_0.csv \
  --output_dir /path/to/output
```

## 输出结构

使用配置驱动方式时，输出结构为：

```
<output_dir>/
  runs/
    <run_id>/
      config.yaml          # 使用的配置（保存）
      manifest.json        # 运行信息（git、时间戳等）
      gpu0/                # GPU 0 的结果
        <pdb_name>/
          status.json      # 结构状态
          mmgbsa_summary.csv
          FINAL_RESULTS_MMPBSA.dat
          rmsd.xvg
        part3_results.csv
        run.log
      gpu1/ ...            # GPU 1-7
```

## Resume 功能

### 跳过已完成结构

```bash
python3 scripts/run_part3.py \
  --config config/part3.yaml \
  --input_csv /path/to/rosetta_static_0.csv \
  --output_dir /path/to/output \
  --resume
```

### 只重跑失败结构

```bash
python3 scripts/run_part3.py \
  --config config/part3.yaml \
  --input_csv /path/to/rosetta_static_0.csv \
  --output_dir /path/to/output \
  --rerun-failed
```

Resume 基于 `status.json` 文件：
- `status: "success"` - 跳过
- `status: "failed"` - 重跑（如果使用 `--rerun-failed`）
- 无 `status.json` - 运行

## 推荐配置

### 正式运行（100ns）

- **配置文件**：`config/part3_100ns.yaml`
- **Production**：100 ns
- **GPU**：8 张并行
- **适用**：最终筛选、正式分析
