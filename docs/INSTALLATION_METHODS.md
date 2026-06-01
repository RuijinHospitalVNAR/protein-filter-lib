# 安装方法对比

## 可编辑安装 vs 普通安装

### `pip install -e .`（可编辑安装）

**特点**：
- ✅ **开发模式**：修改源代码后立即生效，无需重新安装
- ✅ **适合开发**：适合需要频繁修改代码的场景
- ❌ **需要写权限**：在源目录创建 `.egg-info` 文件，需要写权限
- ❌ **权限问题**：在共享挂载点可能遇到权限错误

**适用场景**：
- 正在开发或修改库的代码
- 需要测试代码修改
- 有源目录的写权限

### `pip install .`（普通安装）

**特点**：
- ✅ **不需要写权限**：只读取源目录，不写入文件
- ✅ **适合使用**：适合只使用库，不修改代码的场景
- ❌ **修改需重装**：修改代码后需要重新安装才能生效
- ✅ **更干净**：不会在源目录留下构建文件

**适用场景**：
- 只使用库，不修改代码
- 在共享挂载点上（权限受限）
- 生产环境部署

## 安装方法对比表

| 方法 | 命令 | 需要写权限 | 修改代码后 | 适用场景 |
|------|------|-----------|-----------|---------|
| **可编辑安装** | `pip install -e .` | ✅ 是 | 立即生效 | 开发 |
| **普通安装** | `pip install .` | ❌ 否 | 需重装 | 使用/生产 |
| **分发包安装** | `pip install dist/*.whl` | ❌ 否 | 需重装 | 使用/生产 |
| **用户安装** | `pip install --user .` | ❌ 否* | 需重装 | 无管理员权限 |

*注：`--user` 安装仍然需要写权限来创建 `.egg-info`（对于可编辑安装）

## 推荐安装方法

### 场景 1：只使用库（推荐用于共享系统）

```bash
# 方法 A：普通安装（推荐）
cd /mnt/share/chufan/IgGM_RBD_KRAS/protein_filter_lib
pip install --user .

# 方法 B：构建分发包后安装（更灵活）
python -m build --wheel --outdir dist/
pip install --user dist/*.whl
```

**优点**：
- ✅ 不需要源目录写权限
- ✅ 不会在源目录留下构建文件
- ✅ 适合共享系统

**缺点**：
- ❌ 修改代码后需要重新安装

### 场景 2：开发库（需要修改代码）

```bash
# 如果源目录有写权限
cd /path/to/protein_filter_lib
pip install -e .

# 如果没有写权限，复制到本地
cp -r /mnt/share/.../protein_filter_lib ~/protein_filter_lib
cd ~/protein_filter_lib
pip install -e .
```

**优点**：
- ✅ 修改代码后立即生效
- ✅ 适合开发

**缺点**：
- ❌ 需要源目录写权限

## 实际使用建议

### 对于您的场景（共享挂载点）

**推荐使用普通安装**：

```bash
# 1. 激活环境
conda activate protein-filter-lib

# 2. 安装依赖
conda install -y -c conda-forge numpy scipy biopython pandas

# 3. 普通安装（不需要写权限）
cd /mnt/share/chufan/IgGM_RBD_KRAS/protein_filter_lib
pip install --user .

# 4. 验证
python -c "from protein_filter import ProteinFilter; print('✅ 安装成功')"
```

**如果代码更新了，重新安装**：

```bash
cd /mnt/share/chufan/IgGM_RBD_KRAS/protein_filter_lib
pip install --user . --upgrade
```

### 什么时候需要可编辑安装？

只有在以下情况才需要 `-e`：

1. **正在开发库本身**：需要频繁修改代码并测试
2. **调试库的问题**：需要添加调试代码
3. **贡献代码**：向项目提交代码前测试

**对于大多数用户**：只需要使用库，不需要可编辑安装！

## 常见问题

### Q: 使用普通安装后，如何更新库？

```bash
# 方法 1：重新安装
pip install --user . --upgrade

# 方法 2：卸载后重装
pip uninstall protein-filter-lib
pip install --user .
```

### Q: 如何知道当前是哪种安装方式？

```bash
# 检查安装信息
pip show protein-filter-lib

# 可编辑安装会显示：
# Location: /path/to/protein_filter_lib/src
# Editable project location: /path/to/protein_filter_lib

# 普通安装会显示：
# Location: /home/user/.local/lib/python3.10/site-packages
```

### Q: 普通安装会影响性能吗？

**不会**。普通安装和可编辑安装的性能完全相同，只是安装方式不同。

### Q: 脚本会受影响吗？

**不会**。所有脚本都使用 `#!/usr/bin/env python3`，会自动使用当前 Python 环境中的库，无论是可编辑安装还是普通安装。

## 总结

- **`pip install -e .`**：开发时使用，需要写权限
- **`pip install .`**：使用时使用，不需要写权限 ✅ **推荐用于您的场景**
- **`pip install --user .`**：无管理员权限时使用

**对于共享系统上的用户，推荐使用普通安装（`pip install --user .`），不需要可编辑安装！**
