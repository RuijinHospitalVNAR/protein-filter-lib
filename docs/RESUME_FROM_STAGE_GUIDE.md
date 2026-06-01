# 从指定阶段继续运行指南

## 概述

三阶段分析脚本现在支持从已完成的阶段继续运行，避免重复运行已完成的阶段，节省时间。

## 使用场景

### 场景1：Stage 1已完成，从Stage 2开始

如果Stage 1已经成功完成并保存了结果，可以直接从Stage 2开始运行：

```bash
python3 analyze_af3_three_stage.py \
  /mnt/share/chufan/IgGM_RBD_KRAS/I1_KRAS_RBD450_VNAR/0109_1seed_output/batch_0001_0114 \
  --chainA H \
  --antigen-chains A \
  --output-dir /mnt/share/.../batch_0001_0114_three_stage_clustering \
  --start-from-stage 2
```

或者使用简化的选项：

```bash
python3 analyze_af3_three_stage.py \
  /mnt/share/chufan/IgGM_RBD_KRAS/I1_KRAS_RBD450_VNAR/0109_1seed_output/batch_0001_0114 \
  --chainA H \
  --antigen-chains A \
  --output-dir /mnt/share/.../batch_0001_0114_three_stage_clustering \
  --skip-stage1
```

### 场景2：Stage 1和Stage 2已完成，从Stage 3开始

如果Stage 1和Stage 2都已经完成，可以直接从Stage 3开始：

```bash
python3 analyze_af3_three_stage.py \
  /mnt/share/chufan/IgGM_RBD_KRAS/I1_KRAS_RBD450_VNAR/0109_1seed_output/batch_0001_0114 \
  --chainA H \
  --antigen-chains A \
  --output-dir /mnt/share/.../batch_0001_0114_three_stage_clustering \
  --start-from-stage 3
```

## 参数说明

### `--start-from-stage` (1, 2, 或 3)

指定从哪个阶段开始运行：
- `1`: 从Stage 1开始（默认，运行所有阶段）
- `2`: 从Stage 2开始（跳过Stage 1，加载Stage 1结果）
- `3`: 从Stage 3开始（跳过Stage 1和Stage 2，加载之前的结果）

### `--skip-stage1`

跳过Stage 1，直接从Stage 2开始（等同于 `--start-from-stage 2`）

## 前提条件

### 从Stage 2开始需要：
- `stage1_filtering_result.json` 文件存在于输出目录

### 从Stage 3开始需要：
- `stage1_filtering_result.json` 文件存在于输出目录
- `stage2_foldseek_clustering.json` 文件存在于输出目录

## 示例：当前情况

对于当前的任务，Stage 1已经完成，可以直接从Stage 2开始：

```bash
cd /data/protein_filter_lib

# 停止当前运行的任务（如果还在运行）
ps aux | grep analyze_af3_three_stage | grep -v grep | awk '{print $2}' | xargs -r kill -9

# 从Stage 2开始运行（使用修复后的代码）
python3 analyze_af3_three_stage.py \
  /mnt/share/chufan/IgGM_RBD_KRAS/I1_KRAS_RBD450_VNAR/0109_1seed_output/batch_0001_0114 \
  --chainA H \
  --antigen-chains A \
  --output-dir /mnt/share/chufan/IgGM_RBD_KRAS/I1_KRAS_RBD450_VNAR/0109_1seed_output/batch_0001_0114_three_stage_clustering \
  --start-from-stage 2 \
  --foldseek-path /mnt/share/public/foldseek/bin/foldseek \
  --foldseek-sensitivity 7.5 \
  --min-cluster-size 5 \
  --contact-cutoff 5.0 \
  --interface-cutoff 8.0 \
  --clustering-method kmeans \
  --n-jobs 8 \
  --max-representatives 3
```

## 优势

### 时间节省

| 场景 | 重新运行全部 | 从Stage 2开始 | 节省时间 |
|------|------------|--------------|---------|
| Stage 1失败后修复 | ~1小时 | ~15分钟 | ~45分钟 |
| Stage 2失败后修复 | ~1小时 | ~15分钟 | ~45分钟 |
| Stage 3失败后修复 | ~1小时 | ~10分钟 | ~50分钟 |

### 资源节省

- 避免重复读取18,000个CIF文件
- 避免重复提取AF3评分
- 减少CPU和内存使用

## 注意事项

1. **结果文件必须存在**：如果指定的结果文件不存在，脚本会报错并退出
2. **参数一致性**：虽然可以跳过阶段，但建议保持参数一致（如链配置等）
3. **日志记录**：每次运行都会创建新的日志文件，但会加载之前的结果

## 验证结果文件

在从指定阶段开始之前，可以验证结果文件是否存在：

```bash
OUTPUT_DIR="/mnt/share/.../batch_0001_0114_three_stage_clustering"

# 检查Stage 1结果
if [ -f "$OUTPUT_DIR/stage1_filtering_result.json" ]; then
    echo "✅ Stage 1结果存在"
    # 查看筛选后的结构数量
    python3 -c "import json; data=json.load(open('$OUTPUT_DIR/stage1_filtering_result.json')); print(f'筛选后的结构数: {len(data[\"filtered_files\"])}')"
else
    echo "❌ Stage 1结果不存在"
fi

# 检查Stage 2结果
if [ -f "$OUTPUT_DIR/stage2_foldseek_clustering.json" ]; then
    echo "✅ Stage 2结果存在"
    # 查看粗簇数量
    python3 -c "import json; data=json.load(open('$OUTPUT_DIR/stage2_foldseek_clustering.json')); print(f'粗簇数: {data[\"n_coarse_clusters\"]}')"
else
    echo "⏳ Stage 2结果不存在"
fi
```

## 相关文档

- `README_THREE_STAGE.md` - 三阶段流程完整文档
- `TASK_RESTART_SUMMARY.md` - 任务重新启动总结
- `STAGE2_FIX_SUMMARY.md` - Stage 2修复说明
