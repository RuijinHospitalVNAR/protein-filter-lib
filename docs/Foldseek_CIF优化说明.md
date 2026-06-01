# Foldseek CIF直接支持优化说明

## ✅ 重要发现

**Foldseek原生支持mmCIF格式！** 无需转换为PDB。

### Foldseek支持情况

从 `foldseek createdb --help` 可以看到：

```
usage: foldseek createdb <i:directory|.tsv>|<i:PDB|mmCIF[.gz]|tar[.gz]|DB> ... <o:sequenceDB>
```

**支持的格式**：
- PDB
- **mmCIF** ✅（直接支持！）
- tar[.gz]
- DB文件

**输入格式选项**：
```
--input-format INT  Format of input structures:
                    0: Auto-detect by extension
                    1: PDB
                    2: mmCIF  ← 直接支持CIF！
                    3: mmJSON
                    4: ChemComp
                    5: Foldcomp
```

---

## 🚀 优化方案

### 当前问题

代码中不必要地进行了CIF→PDB转换：

```python
# 当前代码（analyzer.py）
if original_file.suffix.lower() == '.cif':
    self._convert_cif_to_pdb(original_file, temp_file)  # ❌ 不必要的转换
```

**问题**：
1. **时间浪费**：18,000个CIF文件转换需要大量时间
2. **内存浪费**：每个文件需要加载完整结构对象到内存
3. **磁盘I/O**：需要写入18,000个PDB文件

### 优化方案

**直接使用CIF文件**：

```python
# 优化后的代码
if original_file.suffix.lower() == '.cif':
    # 直接使用CIF文件，无需转换
    structure_files.append(str(original_file.resolve()))
else:
    # PDB文件直接使用
    structure_files.append(str(original_file.resolve()))
```

**Foldseek命令**：

```python
cmd = [
    foldseek_path, 'createdb',
    str(list_file), str(database_path),
    '--input-format', '2',  # 指定mmCIF格式
    # 或者不指定，让Foldseek自动检测（推荐）
]
```

---

## 📈 预期效果

### 时间节省

- **转换时间**：从 ~1-2小时 → **0分钟** ✅
- **总耗时**：预计缩短 **1-2小时**

### 内存节省

- **转换内存**：每个文件需要加载完整结构（~10-50MB）
- **18,000个文件**：峰值内存可能达到数百GB
- **直接使用CIF**：Foldseek内部处理，内存占用极低 ✅

### 磁盘I/O节省

- **不需要写入**：18,000个临时PDB文件
- **节省空间**：每个PDB文件约100-500KB，总计约2-9GB

---

## 💻 实施步骤

### 1. 修改 `_prepare_all_structures_for_foldseek()` 方法

```python
def _prepare_all_structures_for_foldseek(self, temp_path):
    """
    为Foldseek准备所有结构文件（直接使用CIF，无需转换）
    """
    structure_files = []
    
    for i, file_name in enumerate(self.file_names):
        original_file = self.pdb_dir / file_name
        
        if not original_file.exists():
            continue
        
        # ✅ 直接使用原始文件，无需转换
        structure_files.append(str(original_file.resolve()))
    
    return structure_files
```

### 2. 修改 `_create_foldseek_database()` 方法

```python
def _create_foldseek_database(self, structure_files, database_path, **kwargs):
    """
    创建 Foldseek 数据库（支持CIF和PDB）
    """
    # 创建文件列表
    list_file = database_path.parent / "structures_list.txt"
    with open(list_file, 'w') as f:
        for struct_file in structure_files:
            f.write(f"{struct_file}\n")
    
    # Foldseek会自动检测格式，或明确指定
    cmd = [
        foldseek_path, 'createdb',
        str(list_file), str(database_path),
        # '--input-format', '2',  # 可选：明确指定mmCIF
    ]
    
    # ... 运行命令
```

### 3. 删除不必要的转换方法

可以保留 `_convert_cif_to_pdb()` 作为备用，但不再使用。

---

## ⚠️ 注意事项

1. **文件路径**：确保Foldseek可以访问原始CIF文件路径
2. **格式检测**：Foldseek会自动检测格式，通常无需指定 `--input-format`
3. **向后兼容**：如果某些情况下需要PDB，可以保留转换功能作为fallback

---

## 📊 性能对比

| 项目 | 当前（转换PDB） | 优化后（直接CIF） | 改善 |
|------|----------------|------------------|------|
| **转换时间** | 1-2小时 | 0分钟 | **100%** |
| **内存峰值** | 高（数百GB） | 低（<50GB） | **80%+** |
| **磁盘I/O** | 高（写入18K文件） | 低（只读） | **90%+** |
| **总耗时** | 5-6小时 | **3-4小时** | **40-50%** |

---

## ✅ 总结

1. ✅ **Foldseek原生支持mmCIF**，无需转换
2. ✅ **跳过转换可以节省1-2小时**
3. ✅ **大幅降低内存和磁盘I/O**
4. ✅ **代码更简单，更高效**

**建议立即实施此优化！**
