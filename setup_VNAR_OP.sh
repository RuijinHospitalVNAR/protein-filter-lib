#!/bin/bash
###############################################################################
# 创建并配置 VNAR_OP 环境（包含 PyRosetta）
#
# 1. 创建 conda 环境 VNAR_OP
# 2. 安装依赖和 protein_filter_lib
# 3. 安装 PyRosetta（从 tar.bz2）
#
# 用法（在仓库根目录）：./setup_VNAR_OP.sh  或  bash setup_VNAR_OP.sh
###############################################################################

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

ENV_NAME="VNAR_OP"
PYROSETTA_ARCHIVE="/data/Tools/PyRosetta4.Release.python310.linux.release-387.tar.bz2"
PYROSETTA_EXTRACT_DIR="/data/Tools/PyRosetta4.Release.python310.linux.release-387"

echo "=========================================="
echo "创建 VNAR_OP 环境并安装 PyRosetta"
echo "=========================================="
echo ""

# 1. 创建 conda 环境
echo "步骤 1: 创建 conda 环境 $ENV_NAME..."
if conda env list | grep -q "^${ENV_NAME} "; then
    echo "⚠️  环境 $ENV_NAME 已存在，是否删除并重新创建？(y/n)"
    read -p "" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        conda env remove -n "$ENV_NAME" -y
        echo "✅ 已删除旧环境"
    else
        echo "使用现有环境"
    fi
fi

if ! conda env list | grep -q "^${ENV_NAME} "; then
    conda env create -f environment_VNAR_OP.yml
    echo "✅ 环境 $ENV_NAME 创建完成"
else
    echo "✅ 环境 $ENV_NAME 已存在"
fi

# 2. 激活环境并安装
echo ""
echo "步骤 2: 激活环境并安装依赖..."
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

# 安装 protein_filter_lib（如果尚未安装）
echo "安装 protein_filter_lib..."
pip install -e . --quiet

# 3. 解压并配置 PyRosetta
echo ""
echo "步骤 3: 安装 PyRosetta..."

if [ ! -f "$PYROSETTA_ARCHIVE" ]; then
    echo "❌ 错误：PyRosetta 压缩包不存在: $PYROSETTA_ARCHIVE"
    exit 1
fi

# 解压 PyRosetta（如果尚未解压）
if [ ! -d "$PYROSETTA_EXTRACT_DIR" ]; then
    echo "解压 PyRosetta 压缩包..."
    cd /data/Tools
    tar -xjf "$PYROSETTA_ARCHIVE"
    echo "✅ 解压完成"
else
    echo "✅ PyRosetta 目录已存在: $PYROSETTA_EXTRACT_DIR"
fi

# 查找 PyRosetta 的 Python 包路径
PYROSETTA_PYTHON_PATH=""
if [ -d "$PYROSETTA_EXTRACT_DIR/setup" ]; then
    PYROSETTA_PYTHON_PATH="$PYROSETTA_EXTRACT_DIR/setup"
elif [ -d "$PYROSETTA_EXTRACT_DIR" ]; then
    # 尝试查找包含 pyrosetta 的目录
    PYROSETTA_PYTHON_PATH=$(find "$PYROSETTA_EXTRACT_DIR" -type d -name "pyrosetta" | head -1 | xargs dirname 2>/dev/null || echo "")
fi

if [ -z "$PYROSETTA_PYTHON_PATH" ] || [ ! -d "$PYROSETTA_PYTHON_PATH" ]; then
    echo "⚠️  警告：无法自动找到 PyRosetta Python 路径"
    echo "   请手动检查: $PYROSETTA_EXTRACT_DIR"
    echo "   然后设置 PYTHONPATH 或修改 scripts/part2/part2_run_pyrosetta_batch.sh"
else
    echo "✅ 找到 PyRosetta Python 路径: $PYROSETTA_PYTHON_PATH"
    
    # 测试导入
    echo "测试 PyRosetta 导入..."
    export PYTHONPATH="$PYROSETTA_PYTHON_PATH:$PYTHONPATH"
    python3 -c "import pyrosetta; print('✅ PyRosetta 导入成功')" || {
        echo "❌ PyRosetta 导入失败，请检查路径"
        exit 1
    }
    
    # 保存路径到配置文件（仓库根目录）
    CONFIG_FILE="$REPO_ROOT/.pyrosetta_path"
    echo "$PYROSETTA_PYTHON_PATH" > "$CONFIG_FILE"
    echo "✅ PyRosetta 路径已保存到: $CONFIG_FILE"
fi

echo ""
echo "=========================================="
echo "✅ VNAR_OP 环境配置完成！"
echo "=========================================="
echo ""
echo "使用方法："
echo "  conda activate $ENV_NAME"
echo "  bash scripts/part2/part2_run_pyrosetta_batch.sh   # Part2 批量 PyRosetta（或 bash scripts/run_pyrosetta_batch.sh）"
echo ""
echo "PyRosetta 路径: $PYROSETTA_PYTHON_PATH"
echo "（已自动设置到 .pyrosetta_path，供 part2_run_pyrosetta_batch.sh 等使用）"
