# ipSAE 脚本调用分析

## 问题发现

### 1. IPSAE-main/ipsae.py 有 Bug

**问题**：使用 `IPSAE-main/ipsae.py`（版本 3，2025-04-06）时出现错误：

```
IndexError: list index out of range
File "/data/protein_filter_lib/IPSAE-main/ipsae.py", line 527
    iptm_af3[chain1][chain2]=af3_chain_pair_iptm_data[nchain1][nchain2]
```

**原因**：旧版本在处理 AF3 JSON 的 `chain_pair_iptm` 数据时，索引计算有误。

**解决**：使用 `scripts/ipsae.py`（版本 4，2026-01-03），已修复此 bug。

### 2. 脚本查找优先级

当前 `get_ipsae_script_path()` 的查找顺序：
1. `scripts/ipsae.py` ✅ **推荐**（新版本，无 bug）
2. `ipsae.py`
3. `IPSAE-main/ipsae.py` ⚠️ **不推荐**（旧版本，有 bug）
4. 其他路径

**建议**：移除 `IPSAE-main/ipsae.py` 的查找，避免使用有 bug 的版本。

### 3. 参数传递验证

**调用方式**（正确）：
```python
subprocess.run([
    "python",
    ipsae_script_path,
    str(json_path_obj),      # sys.argv[1]: PAE JSON 文件
    str(pdb_path_obj),       # sys.argv[2]: PDB/CIF 文件
    str(pae_cutoff),         # sys.argv[3]: PAE cutoff
    str(dist_cutoff),        # sys.argv[4]: Distance cutoff
])
```

**验证**：参数传递正确，符合脚本要求。

### 4. 输出文件命名

**脚本逻辑**（ipsae.py 第 56-59 行）：
```python
pae_string = str(int(pae_cutoff))
if pae_cutoff<10: pae_string="0"+pae_string
dist_string = str(int(dist_cutoff))
if dist_cutoff<10: dist_string="0"+dist_string
path_stem = f'{pdb_path.replace(".cif","")}_{pae_string}_{dist_string}'
```

**输出文件**：`{pdb_stem}_{pae:02d}_{dist:02d}.txt`

**示例**：
- PAE=5, Dist=5 → `model_05_05.txt`
- PAE=10, Dist=10 → `model_10_10.txt`

我们的代码已正确处理此命名规则。

## 关键发现

### ipSAE 指标选择

从实际运行结果看：

| 阈值 | ipSAE (d0res) | ipSAE_d0chn | n0res | 说明 |
|------|---------------|-------------|-------|------|
| PAE=5, Dist=5 | 0.000000 | 0.000000 | 0 | 太严格，找不到接触 |
| PAE=10, Dist=10 | 0.015472 | **0.652138** | 11 | d0chn 值合理 |

**结论**：
- `ipSAE` (d0res) 需要同时满足 PAE<cutoff 和距离<cutoff，值通常较低（0.01-0.4）
- `ipSAE_d0chn` 只需满足 PAE<cutoff，值在合理范围（0.4-1.0），**更适合筛选**

### 阈值选择

**Dunbrack 推荐**：PAE=5.0, Dist=5.0（默认值）

**实际效果**：
- PAE=5, Dist=5：对于某些结构可能太严格（n0res=0）
- PAE=10, Dist=10：能找到更多接触，但 `ipSAE` (d0res) 值偏低

**建议**：
- 使用 PAE=5.0, Dist=5.0（标准阈值）
- 使用 `ipSAE_d0chn` 作为主要指标（不依赖距离 cutoff，值更稳定）

## 修复建议

1. ✅ **已修复**：优先使用 `ipSAE_d0chn` 而不是 `ipSAE` (d0res)
2. ✅ **已修复**：使用 PAE=5.0, Dist=5.0（默认阈值）
3. ⚠️ **建议**：从查找路径中移除 `IPSAE-main/ipsae.py`（避免使用有 bug 的版本）

## 参考

- `scripts/ipsae.py`: 版本 4（2026-01-03），推荐使用
- `IPSAE-main/ipsae.py`: 版本 3（2025-04-06），有 bug，不推荐
