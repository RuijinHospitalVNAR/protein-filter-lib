# PyRosetta 分析：默认启用 Relax

## ✅ 已完成的更改

### 1. 默认启用 Relax

**原因**：
- AF3 预测结构符合统计分布，但不一定符合物理力场
- 不使用 Relax 可能导致 `interface_dG` 评估不准确
- **可能错误地剔除有价值的设计**

**更改**：
- `scripts/part2/part2_run_pyrosetta_batch.sh`：`RELAX=true`（默认）
- `scripts/run_pyrosetta_static.py`：`--relax` 默认值为 `True`

### 2. 清理两阶段筛选相关代码

- 已移除文档中关于"两阶段筛选"的推荐
- 默认配置直接使用 Relax，确保结果准确

### 3. 添加资源监控

**功能**：
- 实时监控 CPU 使用率
- 实时监控内存使用（当前值和峰值）
- 记录处理时间（总时间和平均每个结构）
- 自动生成资源使用报告（`resource_usage.json`）

**实现**：
- 使用 `psutil` 库监控资源
- 每处理 50 个结构显示一次资源使用情况
- 处理完成后生成完整的资源使用报告

**输出文件**：
- `resource_usage.json`：包含详细的资源使用统计

---

## 📊 资源监控报告格式

`resource_usage.json` 包含以下信息：

```json
{
  "start_time": "2026-01-27T10:00:00",
  "end_time": "2026-01-27T15:30:00",
  "elapsed_time_seconds": 19800.0,
  "elapsed_time_formatted": "5h 30m 0.0s",
  "cpu_time_seconds": {
    "user": 18000.0,
    "system": 500.0,
    "total": 18500.0
  },
  "cpu_utilization_percent": 93.4,
  "current_memory_mb": 2048.0,
  "peak_memory_mb": 2560.0,
  "memory_increase_mb": 512.0,
  "total_structures": 313,
  "relax_enabled": true,
  "max_iter": 1
}
```

---

## 🚀 使用方法

### 运行分析（默认启用 Relax）

```bash
cd /data/wcf/protein_filter_lib
./scripts/part2/part2_run_pyrosetta_batch.sh
```

### 监控进度和资源

```bash
# 查看进度和资源使用
./monitor_pyrosetta_batch.sh

# 查看资源报告
cat /data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_output_pyrosetta/resource_usage.json | python3 -m json.tool
```

---

## ⚙️ 配置参数

### Relax 相关参数

- `RELAX=true`：启用 Relax（默认）
- `MAX_ITER=1`：FastRelax 迭代次数（1 通常足够，2-3 更彻底但更慢）
- `FIXBB=false`：允许骨架和侧链都移动（推荐）
- `FIXED_CHAIN=""`：不固定任何链（推荐）

### 性能预期

- **每个结构**：30-120 秒（取决于 `max_iter`）
- **313 个结构**：约 3-10 小时
- **内存使用**：峰值约 2-4 GB
- **CPU 利用率**：通常 80-100%（单线程）

---

## 📝 注意事项

1. **时间成本**：
   - Relax 使计算时间增加 3-10 倍
   - 但这是**必要的**，确保结果准确

2. **资源监控**：
   - 自动记录资源使用情况
   - 可以通过 `monitor_pyrosetta_batch.sh` 实时查看

3. **结果准确性**：
   - Relax 后的 `interface_dG` 更准确
   - 避免错误地剔除有价值的设计

---

## 🔄 与之前版本的对比

| 项目 | 之前版本 | 当前版本 |
|------|---------|---------|
| **Relax 默认** | `false` | `true` ✅ |
| **资源监控** | ❌ 无 | ✅ 有 |
| **推荐策略** | 两阶段筛选 | 直接使用 Relax |
| **结果准确性** | ⚠️ 可能不准确 | ✅ 准确 |

---

## 📚 相关文档

- [为什么需要 Relax](RELAX_BEFORE_INTERFACE_ANALYSIS.md)
- [SASA 指标说明](SASA_METRICS_EXPLANATION.md)
- [Part 2 使用指南](PART2_PYROSETTA.md)
