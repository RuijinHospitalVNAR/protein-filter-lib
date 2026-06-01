#!/usr/bin/env bash
# Part 3 GPU 运行监控脚本
#
# 功能：
# - 显示 GPU 使用情况（nvidia-smi 精简表格）
# - 显示每个 GPU 续跑/正式运行日志的最新若干行
# - 汇总每个 GPU 的任务完成/失败统计
#
# 用法：
#   cd /data/wcf/protein_filter_lib
#   ./scripts/monitor_part3.sh
#   # 或使用 watch 模式：
#   watch -n 5 ./scripts/monitor_part3.sh

set -euo pipefail

# 支持通过环境变量指定监控目录，默认使用正式运行目录
BASE_DIR="${PART3_MONITOR_DIR:-/data/wcf/AF3_prediction/IgGM_2d4d2_sh3_op_260126_part3_100ns}"
LOG_PATTERN_RUN="run.log"
LOG_PATTERN_RESUME="run_resume.log"

# 如果目录不存在，尝试查找 runs 子目录（run_part3.py 的输出结构）
if [ ! -d "$BASE_DIR" ] && [ -d "$(dirname "$BASE_DIR")" ]; then
    # 查找最新的 runs/* 目录
    LATEST_RUN=$(find "$(dirname "$BASE_DIR")" -type d -path "*/runs/*" -maxdepth 3 2>/dev/null | sort -r | head -1)
    if [ -n "$LATEST_RUN" ]; then
        BASE_DIR="$LATEST_RUN"
    fi
fi

echo "=========================================="
echo "Part 3 GPU 运行状态监控"
echo "=========================================="
echo "基准目录: $BASE_DIR"
echo "（可通过环境变量 PART3_MONITOR_DIR 指定其他目录）"
echo ""

# 1. GPU 使用情况
echo "--- GPU 使用情况 (nvidia-smi) ---"
if command -v nvidia-smi &>/dev/null; then
    nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total \
        --format=csv,noheader,nounits 2>/dev/null | \
        awk -F',' 'BEGIN { printf "%-4s %-30s %8s %14s\n", "ID", "Name", "Util(%)", "Mem(used/total, MiB)" }
             {
                 printf "%-4s %-30s %8s %7s/%-6s\n", $1, $2, $3, $4, $5
             }'
else
    echo "nvidia-smi 不可用，跳过 GPU 使用情况显示。"
fi
echo ""

# 2. 每个 GPU 的最新日志
echo "--- 各 GPU 最新日志 ---"
if [ -d "$BASE_DIR" ]; then
    # 支持两种目录结构：
    # 1. BASE_DIR/gpu*/ (resume脚本的输出)
    # 2. BASE_DIR/runs/*/gpu*/ (run_part3.py的输出)
    gpu_dirs=()
    if [ -d "$BASE_DIR/runs" ]; then
        # run_part3.py 结构：查找最新的 run_id
        latest_run=$(find "$BASE_DIR/runs" -mindepth 1 -maxdepth 1 -type d | sort -r | head -1)
        if [ -n "$latest_run" ]; then
            for gpu_dir in "$latest_run"/gpu*; do
                [ -d "$gpu_dir" ] && gpu_dirs+=("$gpu_dir")
            done
        fi
    else
        # resume脚本结构：直接在BASE_DIR下
        for gpu_dir in "$BASE_DIR"/gpu*; do
            [ -d "$gpu_dir" ] && gpu_dirs+=("$gpu_dir")
        done
    fi

    if [ ${#gpu_dirs[@]} -eq 0 ]; then
        echo "未找到GPU目录（查找路径: $BASE_DIR/gpu* 或 $BASE_DIR/runs/*/gpu*）"
    else
        for gpu_dir in "${gpu_dirs[@]}"; do
            gpu_name="$(basename "$gpu_dir")"

            log_file=""
            if [ -f "$gpu_dir/$LOG_PATTERN_RESUME" ]; then
                log_file="$gpu_dir/$LOG_PATTERN_RESUME"
            elif [ -f "$gpu_dir/$LOG_PATTERN_RUN" ]; then
                log_file="$gpu_dir/$LOG_PATTERN_RUN"
            fi

            echo "[$gpu_name]"
            if [ -n "$log_file" ]; then
                echo "  日志文件: $log_file"
                tail -n 8 "$log_file" 2>/dev/null || echo "  (无法读取日志)"
            else
                echo "  未找到日志文件 ($LOG_PATTERN_RESUME / $LOG_PATTERN_RUN)"
            fi
            echo ""
        done
    fi
else
    echo "目录不存在：$BASE_DIR"
fi

# 3. 任务统计（基于日志关键字）
echo "--- 任务统计 (完成/失败) ---"
if [ -d "$BASE_DIR" ]; then
    total_done=0
    total_failed=0

    # 使用与上面相同的逻辑查找GPU目录
    gpu_dirs=()
    if [ -d "$BASE_DIR/runs" ]; then
        latest_run=$(find "$BASE_DIR/runs" -mindepth 1 -maxdepth 1 -type d | sort -r | head -1)
        if [ -n "$latest_run" ]; then
            for gpu_dir in "$latest_run"/gpu*; do
                [ -d "$gpu_dir" ] && gpu_dirs+=("$gpu_dir")
            done
        fi
    else
        for gpu_dir in "$BASE_DIR"/gpu*; do
            [ -d "$gpu_dir" ] && gpu_dirs+=("$gpu_dir")
        done
    fi

    if [ ${#gpu_dirs[@]} -eq 0 ]; then
        echo "未找到GPU目录，无法统计任务状态。"
    else
        for gpu_dir in "${gpu_dirs[@]}"; do
            gpu_name="$(basename "$gpu_dir")"

            gpu_done=$(grep -Eh "完成|success" "$gpu_dir"/run*.log 2>/dev/null | wc -l || true)
            gpu_failed=$(grep -Ei "失败|error|fatal" "$gpu_dir"/run*.log 2>/dev/null | wc -l || true)

            total_done=$((total_done + gpu_done))
            total_failed=$((total_failed + gpu_failed))

            printf "%-8s 完成记录: %3d, 可能失败/错误记录: %3d\n" "$gpu_name" "$gpu_done" "$gpu_failed"
        done

        echo ""
        echo "总计: 完成记录=${total_done}, 可能失败/错误记录=${total_failed}"
    fi
else
    echo "目录不存在：$BASE_DIR，无法统计任务状态。"
fi

echo "=========================================="

