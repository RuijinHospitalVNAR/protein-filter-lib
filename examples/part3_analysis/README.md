# Part3 结果可视化示例

在 Part3 AMBER MD + 后处理 + MMGBSA 完成后，可用本目录下的脚本对 RMSD 与结合自由能进行可视化。

## 依赖

- Python 3.8+
- pandas
- matplotlib（可选，用于出图）

## 用法

```bash
# 从仓库根目录运行
# 同时绘制 RMSD 时间序列 + MMGBSA ΔG_bind 柱状图
python3 examples/part3_analysis/plot_rmsd_and_mmgbsa.py \
  --amber_root examples/affinity_maturation_example/part3_amber_out \
  --mmgbsa_csv examples/affinity_maturation_example/mmgbsa_results.csv \
  --out_dir examples/part3_analysis/figures

# 仅根据 MMGBSA CSV 出图（不扫描 RMSD）
python3 examples/part3_analysis/plot_rmsd_and_mmgbsa.py \
  --mmgbsa_csv examples/affinity_maturation_example/mmgbsa_results.csv \
  --out_dir examples/part3_analysis/figures
```

- **amber_root**：Part3 输出根目录（含 `gpu0/`, `gpu1/`, ... 及各结构子目录下的 `rmsd_bb.dat`）。
- **mmgbsa_csv**：由 `pf-part3-collect-mmgbsa` 或 `AMBER_MMPBSA/collect_mmgbsa_binding_to_csv.py` 生成的 CSV（列：model, delta_total, delta_total_stderr 等）。
- **out_dir**：输出 PNG 的目录，默认 `examples/part3_analysis/figures`。

输出文件：

- `part3_rmsd_bb.png`：各结构 backbone RMSD 随模拟时间变化（若提供了 amber_root 且找到 rmsd_bb.dat）。
- `part3_mmgbsa_deltaG.png`：各结构 ΔG_bind 柱状图（含标准误）。

## 参考

- Part3 流程与后处理： [docs/PART3_AMBER_WORKFLOW_SUMMARY.md](../../docs/PART3_AMBER_WORKFLOW_SUMMARY.md)、[PART3_AMBER_POSTPROCESS.md](../../docs/PART3_AMBER_POSTPROCESS.md)
- MMGBSA 结果解读：[docs/PART3_RESULTS_INTERPRETATION.md](../../docs/PART3_RESULTS_INTERPRETATION.md)
