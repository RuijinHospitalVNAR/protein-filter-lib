# 安装问题排查指南

## 权限错误（Permission Denied）

### 问题描述

```
error: [Errno 1] Operation not permitted: '/path/to/protein_filter_lib/src/protein_filter_lib.egg-info/...'
```

### 原因

这通常发生在以下情况：
1. 在共享挂载点（如 `/mnt/share/`）上操作
2. 文件系统权限不足
3. 目录被其他进程锁定

### 解决方案

#### 方案 1：使用 `--user` 安装（推荐）

```bash
pip install --user -e .
```

这会将包安装到用户目录（`~/.local/lib/python3.x/site-packages/`），避免权限问题。

**注意**：使用 `--user` 后，可能需要将用户 Python 路径添加到 `PYTHONPATH`：

```bash
export PYTHONPATH="${HOME}/.local/lib/python3.10/site-packages:${PYTHONPATH}"
```

#### 方案 2：修改目录权限

```bash
# 检查当前权限
ls -ld /mnt/share/chufan/IgGM_RBD_KRAS/protein_filter_lib

# 如果需要，修改权限（需要管理员权限）
sudo chown -R $USER:$USER /mnt/share/chufan/IgGM_RBD_KRAS/protein_filter_lib
chmod -R u+w /mnt/share/chufan/IgGM_RBD_KRAS/protein_filter_lib
```

#### 方案 3：在本地目录安装

如果共享挂载点有权限限制，可以：

1. **复制到本地目录**：
```bash
# 复制到用户目录
cp -r /mnt/share/chufan/IgGM_RBD_KRAS/protein_filter_lib ~/protein_filter_lib
cd ~/protein_filter_lib
pip install -e .
```

2. **使用符号链接**：
```bash
# 创建符号链接到本地目录
ln -s /mnt/share/chufan/IgGM_RBD_KRAS/protein_filter_lib ~/protein_filter_lib
cd ~/protein_filter_lib
pip install -e .
```

#### 方案 4：清理并重试

```bash
# 清理可能存在的构建文件
rm -rf src/protein_filter_lib.egg-info
rm -rf build dist *.egg-info

# 重新安装
pip install -e .
```

#### 方案 5：使用 conda 环境（推荐用于共享系统）

如果是在共享系统上，使用 conda 环境可以避免权限问题：

```bash
# 创建环境（在用户目录）
conda create -n protein-filter-lib python=3.10 -y
conda activate protein-filter-lib

# 安装依赖
conda install -y -c conda-forge numpy scipy biopython pandas

# 使用 --user 安装库
cd /mnt/share/chufan/IgGM_RBD_KRAS/protein_filter_lib
pip install --user -e .
```

## TOML 格式错误

### 问题描述

```
TOMLDecodeError: Cannot declare ('project', 'optional-dependencies') twice
```

### 解决方案

确保 `pyproject.toml` 中 `[project.optional-dependencies]` 只声明一次，所有可选依赖组都在同一个块中：

```toml
[project.optional-dependencies]
full = ["mdtraj>=1.9.0"]
dev = ["pytest>=7.0", "black>=22.0"]
```

## 许可证格式警告

### 问题描述

```
SetuptoolsDeprecationWarning: `project.license` as a TOML table is deprecated
```

### 解决方案

使用简单的 SPDX 字符串格式：

```toml
# 旧格式（已弃用）
license = {text = "Apache-2.0"}

# 新格式（推荐）
license = "Apache-2.0"
```

## 依赖冲突

### 问题描述

```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed.
```

### 解决方案

这通常是警告而非错误。如果安装成功，可以忽略。如果需要解决：

```bash
# 查看冲突的包
pip check

# 如果需要，可以忽略依赖检查（不推荐）
pip install --no-deps -e .
```

## 常见问题

### Q: 安装后仍然找不到模块

**A**: 检查 Python 路径：

```bash
# 检查安装位置
pip show protein-filter-lib

# 检查 Python 路径
python -c "import sys; print('\n'.join(sys.path))"

# 如果使用 --user，确保路径在 PYTHONPATH 中
export PYTHONPATH="${HOME}/.local/lib/python3.10/site-packages:${PYTHONPATH}"
```

### Q: 在共享系统上如何避免权限问题？

**A**: 推荐使用 conda 环境 + `--user` 安装：

```bash
# 1. 创建环境（在用户目录）
conda create -n protein-filter-lib python=3.10 -y
conda activate protein-filter-lib

# 2. 安装依赖
conda install -y -c conda-forge numpy scipy biopython pandas

# 3. 使用 --user 安装库
cd /path/to/protein_filter_lib
pip install --user -e .

# 4. 设置 PYTHONPATH（可选，通常不需要）
export PYTHONPATH="${HOME}/.local/lib/python3.10/site-packages:${PYTHONPATH}"
```

### Q: 如何验证安装成功？

```bash
# 方法 1：检查包信息
pip show protein-filter-lib

# 方法 2：尝试导入
python -c "from protein_filter import ProteinFilter; print('✅ 安装成功')"

# 方法 3：检查依赖
python -c "import numpy, scipy, Bio, pandas; print('✅ 所有依赖已安装')"
```

## 完整安装流程（避免权限问题）

### 方法 A：修改权限后使用可编辑安装（推荐，如果可能）

```bash
# 1. 激活环境
conda activate protein-filter-lib

# 2. 修改目录权限（需要管理员权限或联系管理员）
sudo chown -R $USER:$USER /mnt/share/chufan/IgGM_RBD_KRAS/protein_filter_lib
chmod -R u+w /mnt/share/chufan/IgGM_RBD_KRAS/protein_filter_lib

# 3. 安装核心依赖
conda install -y -c conda-forge numpy scipy biopython pandas

# 4. 进入库目录
cd /mnt/share/chufan/IgGM_RBD_KRAS/protein_filter_lib

# 5. 清理旧的构建文件
rm -rf src/protein_filter_lib.egg-info build dist *.egg-info

# 6. 使用可编辑安装
pip install -e .

# 7. 验证安装
python -c "from protein_filter import ProteinFilter; print('✅ 安装成功')"
```

### 方法 B：使用非可编辑安装（如果无法修改权限）

```bash
# 1. 激活环境
conda activate protein-filter-lib

# 2. 安装核心依赖
conda install -y -c conda-forge numpy scipy biopython pandas

# 3. 进入库目录
cd /mnt/share/chufan/IgGM_RBD_KRAS/protein_filter_lib

# 4. 使用非可编辑安装脚本
chmod +x install_without_editable.sh
./install_without_editable.sh

# 或手动安装：
python -m build --wheel --outdir dist/
pip install --user dist/*.whl

# 5. 验证安装
python -c "from protein_filter import ProteinFilter; print('✅ 安装成功')"
```

**注意**：非可编辑安装后，修改代码需要重新安装。

### 方法 C：复制到本地目录（最可靠）

```bash
# 1. 复制到用户目录
cp -r /mnt/share/chufan/IgGM_RBD_KRAS/protein_filter_lib ~/protein_filter_lib
cd ~/protein_filter_lib

# 2. 激活环境
conda activate protein-filter-lib

# 3. 安装依赖
conda install -y -c conda-forge numpy scipy biopython pandas

# 4. 可编辑安装（现在在本地目录，有完整权限）
pip install -e .

# 5. 验证安装
python -c "from protein_filter import ProteinFilter; print('✅ 安装成功')"
```

**注意**：如果使用符号链接，仍然会有权限问题，必须完整复制。
