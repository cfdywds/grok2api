# 图片管理功能快速开始指南

## 🚀 快速开始

### 1. 启动服务

```bash
cd D:\navy_code\github_code\grok2api
python main.py
```

服务将在 `http://localhost:8000` 启动。

### 2. 访问图片管理页面

打开浏览器访问：
- **直接访问**: `http://localhost:8000/admin/gallery`
- **通过导航**: 点击导航栏 "服务管理" → "图片管理"

### 3. 生成图片（自动保存元数据）

使用任何方式生成图片，元数据会自动保存：

#### 方式 1: OpenAI 兼容 API
```bash
curl -X POST http://localhost:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "prompt": "a beautiful sunset over the ocean",
    "model": "grok-imagine-1.0",
    "n": 1,
    "size": "1024x1024"
  }'
```

#### 方式 2: Imagine WebSocket
访问 `http://localhost:8000/admin/imagine` 使用实时图片生成功能。

### 4. 查看和管理图片

在图片管理页面，你可以：

#### 📊 查看统计信息
- 图片总数
- 总文件大小
- 本月新增数量
- 常用标签

#### 🔍 筛选图片
- **搜索**: 在搜索框输入关键词搜索提示词
- **模型筛选**: 选择特定模型
- **宽高比筛选**: 选择特定比例（1:1, 2:3, 3:2, 9:16, 16:9）
- **排序**: 按时间或大小排序（升序/降序）

#### 👁️ 切换视图
- **网格视图**: 卡片式展示，适合浏览
- **列表视图**: 表格式展示，显示更多信息

#### ✅ 批量操作
1. 勾选图片复选框
2. 点击"全选"可选择当前页所有图片
3. 点击"导出"下载选中图片为 ZIP
4. 点击"删除"删除选中图片

#### 🏷️ 管理标签
1. 点击图片查看详情
2. 在详情弹窗中添加或删除标签
3. 标签会立即保存并显示在图片卡片上

## 📁 数据存储

### 图片文件位置
```
data/tmp/image/
├── uuid1.jpg
├── uuid2.jpg
└── ...
```

### 元数据文件位置
```
data/image_metadata.json
```

元数据文件示例：
```json
{
  "images": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "550e8400-e29b-41d4-a716-446655440000.jpg",
      "prompt": "a beautiful sunset over the ocean",
      "model": "grok-imagine-1.0",
      "aspect_ratio": "1:1",
      "created_at": 1707321600000,
      "file_size": 245678,
      "width": 1024,
      "height": 1024,
      "tags": ["sunset", "ocean", "nature"],
      "nsfw": false,
      "metadata": {}
    }
  ],
  "version": "1.0"
}
```

## 🔧 配置选项

### 存储后端

默认使用本地文件存储，可以通过环境变量切换：

#### Local Storage (默认)
```bash
# 无需配置，默认使用
```

#### Redis Storage
```bash
export SERVER_STORAGE_TYPE=redis
export SERVER_STORAGE_URL=redis://localhost:6379/0
```

#### SQL Storage (MySQL/PostgreSQL)
```bash
# MySQL
export SERVER_STORAGE_TYPE=mysql
export SERVER_STORAGE_URL=mysql://user:password@localhost:3306/grok2api

# PostgreSQL
export SERVER_STORAGE_TYPE=pgsql
export SERVER_STORAGE_URL=postgresql://user:password@localhost:5432/grok2api
```

### 分页大小

默认每页显示 50 张图片，可以在代码中修改：

```javascript
// app/static/gallery/gallery.js
const state = {
    pageSize: 50,  // 修改这里
    // ...
};
```

## 🎯 使用场景

### 场景 1: 查找特定提示词的图片
1. 在搜索框输入关键词，如 "sunset"
2. 点击"筛选"按钮
3. 浏览筛选结果

### 场景 2: 导出本月生成的所有图片
1. 选择排序为"最新优先"
2. 点击"全选"选择当前页
3. 翻页并继续选择
4. 点击"导出"下载 ZIP

### 场景 3: 清理旧图片
1. 选择排序为"最早优先"
2. 勾选要删除的图片
3. 点击"删除"按钮
4. 确认删除

### 场景 4: 为图片添加标签
1. 点击图片查看详情
2. 在"添加标签"输入框输入标签名
3. 按回车或点击"添加"按钮
4. 标签会显示在图片卡片上

### 场景 5: 按标签筛选图片
1. 先为图片添加标签
2. 在筛选工具栏可以按标签筛选（需要扩展功能）

## 🐛 故障排除

### 问题 1: 图片管理页面无法访问

**解决方案**:
1. 确认服务已启动
2. 检查浏览器控制台是否有错误
3. 确认路由已正确注册

### 问题 2: 图片元数据未保存

**解决方案**:
1. 检查 `data/` 目录是否有写入权限
2. 查看服务日志是否有错误信息
3. 确认存储服务正常工作

### 问题 3: 图片显示不出来

**解决方案**:
1. 确认图片文件存在于 `data/tmp/image/` 目录
2. 检查文件服务路由 `/v1/files/image/` 是否正常
3. 查看浏览器网络请求是否成功

### 问题 4: 删除图片后元数据仍存在

**解决方案**:
1. 使用图片管理页面的删除功能（会同步删除元数据）
2. 或手动运行清理孤立元数据：
```python
import asyncio
from app.services.gallery.service import get_image_metadata_service

async def cleanup():
    service = get_image_metadata_service()
    count = await service.cleanup_orphaned_metadata()
    print(f"Cleaned up {count} orphaned metadata entries")

asyncio.run(cleanup())
```

## 📊 API 端点参考

### 获取图片列表
```bash
GET /api/v1/admin/gallery/images?page=1&page_size=50&search=sunset&sort_by=created_at&sort_order=desc
```

### 获取图片详情
```bash
GET /api/v1/admin/gallery/images/{image_id}
```

### 批量删除图片
```bash
POST /api/v1/admin/gallery/images/delete
Content-Type: application/json

{
  "image_ids": ["uuid1", "uuid2"]
}
```

### 更新图片标签
```bash
POST /api/v1/admin/gallery/images/{image_id}/tags
Content-Type: application/json

{
  "tags": ["sunset", "ocean", "nature"]
}
```

### 获取所有标签
```bash
GET /api/v1/admin/gallery/tags
```

### 获取统计信息
```bash
GET /api/v1/admin/gallery/stats
```

### 批量导出图片
```bash
POST /api/v1/admin/gallery/images/export
Content-Type: application/json

{
  "image_ids": ["uuid1", "uuid2"]
}
```

## 🎨 自定义样式

如需自定义样式，编辑 `app/static/gallery/gallery.css`：

```css
/* 修改主题色 */
:root {
    --primary-color: #007bff;  /* 改为你喜欢的颜色 */
    --danger-color: #dc3545;
    /* ... */
}

/* 修改网格列数 */
.images-grid {
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    /* 改为 minmax(200px, 1fr) 显示更多列 */
}
```

## 🚀 性能优化建议

### 1. 使用 Redis 存储
对于大量图片，建议使用 Redis 存储元数据：
```bash
export SERVER_STORAGE_TYPE=redis
export SERVER_STORAGE_URL=redis://localhost:6379/0
```

### 2. 定期清理旧图片
```python
# 删除 30 天前的图片
import asyncio
from datetime import datetime, timedelta
from app.services.gallery.service import get_image_metadata_service

async def cleanup_old_images():
    service = get_image_metadata_service()
    cutoff = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)

    data = await service.storage.load_image_metadata()
    old_images = [img for img in data.get("images", []) if img.get("created_at", 0) < cutoff]
    old_ids = [img["id"] for img in old_images]

    if old_ids:
        result = await service.delete_images(old_ids)
        print(f"Deleted {result['deleted']} old images")

asyncio.run(cleanup_old_images())
```

### 3. 启用图片压缩
在生成图片时使用较低的质量设置以减少文件大小。

## 📝 下一步

1. ✅ 基础功能已完成
2. 🔄 可选扩展：
   - AI 图片分析（使用 Grok 视觉模型）
   - 图片编辑功能
   - 图片分享功能
   - 收藏夹功能
   - 以图搜图

## 💡 提示

- 图片元数据会在生成时自动保存，无需手动操作
- 删除图片时会同步删除元数据
- 支持批量操作，提高管理效率
- 响应式设计，支持移动端访问
- 所有操作都有日志记录，便于调试

## 📞 获取帮助

如有问题，请查看：
1. `GALLERY_IMPLEMENTATION.md` - 完整实施文档
2. 服务日志 - 查看错误信息
3. GitHub Issues - 提交问题反馈

---

**享受使用图片管理功能！** 🎉
