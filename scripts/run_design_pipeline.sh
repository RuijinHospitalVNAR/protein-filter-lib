#!/usr/bin/env bash
# 兼容旧名称：现由 run_optimization_pipeline.sh 提供亲和力成熟模式入口
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
exec bash "${REPO_ROOT}/scripts/run_optimization_pipeline.sh" "$@"
