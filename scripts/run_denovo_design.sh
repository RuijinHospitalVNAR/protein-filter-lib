#!/usr/bin/env bash

# De novo design 模式一键流水线封装脚本
#
# 功能：
#   - 以 "de novo design" 模式运行完整筛选/聚类/打分（Part1+Part2，按需触发 Part3）。
#   - 底层调用 scripts/part1/part1_run_denovo_orchestrator.py 与 YAML 配置。
#
# 用法示例（从仓库根目录）：
#   # 使用默认配置文件 config/full_pipeline.yaml，并跑到 Part3（如配置启用）
#   bash scripts/run_denovo_design.sh
#
#   # 指定其它配置文件
#   CONFIG=config/my_pipeline.yaml bash scripts/run_denovo_design.sh
#
# 说明：
#   - CONFIG 环境变量指定 FullPipelineConfig YAML 路径，默认为 config/full_pipeline.yaml。
#   - 默认会运行 Part3 MD（RUN_PART3 未设置或为 1）；若希望只跑筛选/打分（Part1+Part2），可设置 RUN_PART3=0 关闭 MD。

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG_PATH="${CONFIG:-${REPO_ROOT}/config/full_pipeline.yaml}"

cd "$REPO_ROOT"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "错误：未找到配置文件: $CONFIG_PATH" >&2
  echo "请创建或修改 CONFIG 环境变量指向有效的 FullPipelineConfig YAML。" >&2
  exit 1
fi

ARGS=("${REPO_ROOT}/scripts/part1/part1_run_denovo_orchestrator.py" "--config" "$CONFIG_PATH")

# 默认运行 Part3；若 RUN_PART3=0，则不追加 --run-part3，让配置只跑 Part1+Part2
if [[ "${RUN_PART3:-1}" != "0" ]]; then
  ARGS+=("--run-part3")
fi

exec python3 "${ARGS[@]}"
