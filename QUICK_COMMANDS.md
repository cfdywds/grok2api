# 快速命令参考

## 🚀 立即可用的命令

### 1. 清理重复图片

```bash
# 查看将要删除的文件（安全预览）
python cleanup_duplicates.py

# 执行实际清理（需要确认）
python cleanup_duplicates.py --clean

# 为所有图片添加哈希值
python cleanup_duplicates.py --add-hashes --clean
```

**预期效果**:
- 删除 1012 个重复文件
- 释放 176.77 MB 空间
- 保留有提示词的图片

---

### 2. 推送代码到远程

```bash
# 推送所有提交
git push origin main

# 如果需要强制推送（谨慎使用）
git push origin main --force
```

---

### 3. 查看系统状态

```bash
# 查看图片目录大小
du -sh data/tmp/image

# 统计图片数量
find data/tmp/image -type f \( -name "*.jpg" -o -name "*.png" \) | wc -l

# 查看元数据中的图片数量
python -c "import json; data = json.load(open('data/image_metadata.json')); print(f'元数据中的图片数: {len(data[\"images\"])}')"

# 查看最近的日志
tail -f app.log

# 查看最近50行日志
tail -50 app.log
```

---

### 4. 启动服务

```bash
# 启动开发服务器
python main.py

# 或使用 uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

### 5. 测试功能

```bash
# 测试图生图 API
curl -X POST http://localhost:8000/api/v1/admin/img2img \
  -F "prompt=beautiful landscape" \
  -F "image=@test_image.jpg" \
  -F "n=2"

# 测试提示词优化 API
curl -X POST http://localhost:8000/api/v1/prompt/optimize \
  -H "Content-Type: application/json" \
  -d '{"prompt": "beautiful girl", "context": "imagine"}'

# 测试图片生成 API
curl -X POST http://localhost:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a beautiful sunset", "n": 2}'
```

---

## 📊 数据分析命令

### 查找重复图片的哈希值

```bash
# 查看有哈希值的图片数量
python -c "
import json
data = json.load(open('data/image_metadata.json'))
with_hash = sum(1 for img in data['images'] if img.get('metadata', {}).get('content_hash'))
print(f'有哈希值的图片: {with_hash}/{len(data[\"images\"])}')
"
```

### 查看提示词统计

```bash
# 统计有提示词的图片
python -c "
import json
data = json.load(open('data/image_metadata.json'))
with_prompt = sum(1 for img in data['images'] if img.get('prompt') and not img['prompt'].startswith('导入:'))
print(f'有提示词的图片: {with_prompt}/{len(data[\"images\"])}')
"
```

### 查看导入的图片

```bash
# 统计导入的图片
python -c "
import json
data = json.load(open('data/image_metadata.json'))
imported = sum(1 for img in data['images'] if img.get('prompt', '').startswith('导入:'))
print(f'导入的图片: {imported}/{len(data[\"images\"])}')
"
```

---

## 🔧 维护命令

### 备份数据

```bash
# 备份图片目录
cp -r data/tmp/image data/tmp/image_backup_$(date +%Y%m%d)

# 备份元数据
cp data/image_metadata.json data/image_metadata.json.backup_$(date +%Y%m%d)

# 创建完整备份
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz data/
```

### 恢复数据

```bash
# 恢复图片目录
cp -r data/tmp/image_backup_20260210 data/tmp/image

# 恢复元数据
cp data/image_metadata.json.backup_20260210 data/image_metadata.json

# 从完整备份恢复
tar -xzf backup_20260210_235900.tar.gz
```

### 清理日志

```bash
# 清空日志文件
> app.log

# 只保留最近1000行
tail -1000 app.log > app.log.tmp && mv app.log.tmp app.log

# 归档旧日志
mv app.log app.log.$(date +%Y%m%d) && touch app.log
```

---

## 🐛 故障排除

### 检查依赖

```bash
# 检查 Python 版本
python --version

# 检查已安装的包
pip list | grep -E "fastapi|uvicorn|pillow|orjson"

# 重新安装依赖
pip install -r requirements.txt
```

### 检查端口占用

```bash
# Windows
netstat -ano | findstr :8000

# Linux/Mac
lsof -i :8000
```

### 检查磁盘空间

```bash
# Windows
dir data\tmp\image

# Linux/Mac
df -h
du -sh data/tmp/image/*
```

### 修复权限问题

```bash
# Linux/Mac
chmod +x cleanup_duplicates.py
chmod -R 755 data/
```

---

## 📈 性能监控

### 监控内存使用

```bash
# Windows
tasklist | findstr python

# Linux/Mac
ps aux | grep python
top -p $(pgrep -f "python main.py")
```

### 监控请求日志

```bash
# 实时查看请求
tail -f app.log | grep -E "POST|GET"

# 统计请求数量
grep -c "POST /v1/images/generations" app.log

# 查看错误日志
grep "ERROR" app.log | tail -20
```

---

## 🔍 调试命令

### 测试清理工具

```bash
# 测试扫描功能（不删除）
python cleanup_duplicates.py

# 测试单个图片的哈希
python -c "
import hashlib
from pathlib import Path
file_path = Path('data/tmp/image/test.jpg')
if file_path.exists():
    hash_val = hashlib.sha256(file_path.read_bytes()).hexdigest()
    print(f'哈希值: {hash_val}')
"
```

### 验证元数据完整性

```bash
# 检查元数据格式
python -c "
import json
try:
    data = json.load(open('data/image_metadata.json'))
    print('✓ 元数据格式正确')
    print(f'  图片数量: {len(data.get(\"images\", []))}')
except Exception as e:
    print(f'✗ 元数据格式错误: {e}')
"
```

### 检查文件和元数据一致性

```bash
# 检查孤立文件（有文件但无元数据）
python -c "
import json
from pathlib import Path

data = json.load(open('data/image_metadata.json'))
metadata_files = {img['filename'] for img in data['images']}
image_dir = Path('data/tmp/image')
actual_files = {f.name for f in image_dir.glob('*.jpg')} | {f.name for f in image_dir.glob('*.png')}

orphan_files = actual_files - metadata_files
missing_files = metadata_files - actual_files

print(f'孤立文件（有文件无元数据）: {len(orphan_files)}')
if orphan_files and len(orphan_files) <= 10:
    for f in list(orphan_files)[:10]:
        print(f'  - {f}')

print(f'缺失文件（有元数据无文件）: {len(missing_files)}')
if missing_files and len(missing_files) <= 10:
    for f in list(missing_files)[:10]:
        print(f'  - {f}')
"
```

---

## 🎯 一键操作脚本

### Windows 批处理脚本

创建 `quick_cleanup.bat`:
```batch
@echo off
echo ========================================
echo 重复图片清理工具
echo ========================================
echo.
echo 1. 试运行（查看将要删除的文件）
echo 2. 执行清理（实际删除重复文件）
echo 3. 添加哈希值
echo 4. 退出
echo.
set /p choice=请选择操作 (1-4):

if "%choice%"=="1" (
    python cleanup_duplicates.py
    pause
)
if "%choice%"=="2" (
    python cleanup_duplicates.py --clean
    pause
)
if "%choice%"=="3" (
    python cleanup_duplicates.py --add-hashes --clean
    pause
)
if "%choice%"=="4" (
    exit
)
```

### Linux/Mac Shell 脚本

创建 `quick_cleanup.sh`:
```bash
#!/bin/bash

echo "========================================"
echo "重复图片清理工具"
echo "========================================"
echo ""
echo "1. 试运行（查看将要删除的文件）"
echo "2. 执行清理（实际删除重复文件）"
echo "3. 添加哈希值"
echo "4. 退出"
echo ""
read -p "请选择操作 (1-4): " choice

case $choice in
    1)
        python cleanup_duplicates.py
        ;;
    2)
        python cleanup_duplicates.py --clean
        ;;
    3)
        python cleanup_duplicates.py --add-hashes --clean
        ;;
    4)
        exit 0
        ;;
    *)
        echo "无效的选择"
        ;;
esac
```

---

## 📚 相关文档

- **SESSION_SUMMARY.md**: 完整的开发会话总结
- **CLEANUP_GUIDE.md**: 重复图片清理详细指南
- **README.md**: 项目主文档
- **CHANGELOG.md**: 更新日志

---

## 💡 提示

### 最佳实践

1. **定期清理**: 建议每周运行一次清理工具
2. **定期备份**: 建议每天备份一次数据
3. **监控日志**: 定期检查错误日志
4. **更新哈希**: 为所有图片添加哈希值以提高去重效率

### 常见问题

**Q: 清理后能恢复吗？**
A: 如果提前备份了，可以从备份恢复。建议清理前先备份。

**Q: 清理会影响正在运行的服务吗？**
A: 不会。清理工具使用文件锁，确保不会与正在运行的服务冲突。

**Q: 如何确认清理是否成功？**
A: 运行清理后，检查日志输出，确认删除的文件数量和释放的空间。

**Q: 为什么有些图片没有哈希值？**
A: 旧图片在去重功能实现前生成，没有哈希值。运行 `--add-hashes` 可以添加。

---

**最后更新**: 2026-02-10
**版本**: 1.0.0
