#!/usr/bin/env python3
"""Part3 结果可视化：RMSD 时间序列 + MMGBSA ΔG_bind 柱状图。

从 AMBER Part3 输出目录收集 rmsd_bb.dat 与 MMGBSA CSV，绘制：
1. 各结构 backbone RMSD 随帧（时间）变化；
2. 各结构 ΔG_bind 柱状图（含标准误）。

用法示例（仓库根目录）：
  python3 examples/part3_analysis/plot_rmsd_and_mmgbsa.py \
    --amber_root examples/affinity_maturation_example/part3_amber_out \
    --mmgbsa_csv examples/affinity_maturation_example/mmgbsa_results.csv \
    --out_dir examples/part3_analysis/figures

  # 仅 MMGBSA（不扫描 RMSD）
  python3 examples/part3_analysis/plot_rmsd_and_mmgbsa.py \
    --mmgbsa_csv examples/affinity_maturation_example/mmgbsa_results.csv \
    --out_dir examples/part3_analysis/figures
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def load_rmsd_dat(path: Path) -> pd.DataFrame | None:
    """加载 cpptraj 输出的 rmsd_bb.dat（#Frame 与 rmsd_bb 列）。"""
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, sep=r"\s+", comment="#", names=["frame", "rmsd_bb"])
        return df
    except Exception:
        return None


def collect_rmsd_from_amber_root(amber_root: Path) -> dict[str, pd.DataFrame]:
    """从 amber_root 下 gpu*/*/rmsd_bb.dat 收集每个 model 的 RMSD 序列。"""
    out: dict[str, pd.DataFrame] = {}
    for rmsd_file in amber_root.rglob("rmsd_bb.dat"):
        model = rmsd_file.parent.name
        df = load_rmsd_dat(rmsd_file)
        if df is not None and len(df) > 0:
            out[model] = df
    return out


def plot_rmsd(
    rmsd_data: dict[str, pd.DataFrame],
    out_path: Path,
    time_per_frame_ns: float = 0.002,
) -> None:
    """绘制各结构 backbone RMSD 随时间变化（单位 ns）。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("跳过 RMSD 图：未安装 matplotlib")
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    for model, df in list(rmsd_data.items())[:20]:  # 最多 20 条线，避免过密
        time_ns = df["frame"].to_numpy() * time_per_frame_ns
        ax.plot(time_ns, df["rmsd_bb"].to_numpy(), label=model, alpha=0.8)
    if len(rmsd_data) > 20:
        ax.set_title(f"Backbone RMSD (前 20 个结构，共 {len(rmsd_data)} 个)")
    else:
        ax.set_title("Backbone RMSD")
    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("RMSD (Å)")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=7)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"已保存: {out_path}")


def plot_mmgbsa(
    csv_path: Path,
    out_path: Path,
) -> None:
    """绘制 MMGBSA ΔG_bind 柱状图（含 standard error）。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("跳过 MMGBSA 图：未安装 matplotlib")
        return

    df = pd.read_csv(csv_path)
    if "delta_total" not in df.columns or "model" not in df.columns:
        print(f"CSV 需包含 model, delta_total 列: {csv_path}")
        return
    df = df.sort_values("delta_total")
    models = df["model"].tolist()
    delta = df["delta_total"].tolist()
    stderr = df.get("delta_total_stderr", pd.Series([0] * len(df))).tolist()

    fig, ax = plt.subplots(figsize=(max(8, len(models) * 0.35), 5))
    x = range(len(models))
    bars = ax.bar(x, delta, yerr=stderr, capsize=2, alpha=0.8, color="steelblue", edgecolor="navy")
    ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("ΔG_bind (kcal/mol)")
    ax.set_xlabel("Model")
    ax.set_title("MMGBSA binding free energy")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"已保存: {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Part3 结果可视化：RMSD + MMGBSA")
    ap.add_argument("--amber_root", "-i", help="Part3 AMBER 输出根目录（含 gpu*/*/rmsd_bb.dat）")
    ap.add_argument("--mmgbsa_csv", "-m", help="MMGBSA 汇总 CSV（model, delta_total, delta_total_stderr）")
    ap.add_argument("--out_dir", "-o", default="examples/part3_analysis/figures", help="输出图片目录")
    ap.add_argument("--time_per_frame_ns", type=float, default=0.002, help="每帧对应时间 (ns)，用于 RMSD 横轴")
    args = ap.parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.amber_root:
        amber_root = Path(args.amber_root).resolve()
        if amber_root.is_dir():
            rmsd_data = collect_rmsd_from_amber_root(amber_root)
            if rmsd_data:
                plot_rmsd(
                    rmsd_data,
                    out_dir / "part3_rmsd_bb.png",
                    time_per_frame_ns=args.time_per_frame_ns,
                )
            else:
                print("未在 amber_root 下找到 rmsd_bb.dat")
        else:
            print(f"amber_root 不是目录: {amber_root}")

    if args.mmgbsa_csv:
        csv_path = Path(args.mmgbsa_csv).resolve()
        if csv_path.exists():
            plot_mmgbsa(csv_path, out_dir / "part3_mmgbsa_deltaG.png")
        else:
            print(f"mmgbsa_csv 不存在: {csv_path}")

    if not args.amber_root and not args.mmgbsa_csv:
        print("请至少指定 --amber_root 或 --mmgbsa_csv")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
