# 提示词管理功能使用指南

## ✅ 功能已修复并测试通过

### 修复的问题
- ✅ 修复了 `StorageFactory.get_instance()` 方法名错误
- ✅ 改为正确的 `StorageFactory.get_storage()` 方法
- ✅ 所有 API 端点测试通过
- ✅ 数据持久化正常工作

---

## 🚀 快速开始

### 1. 启动服务
```bash
python main.py
```

### 2. 访问页面
```
http://localhost:8000/admin/prompts
```

或通过导航栏：**服务管理 → 提示词管理**

---

## 📝 使用示例

### 添加提示词

#### 示例 1：写作助手
```
标题：写作助手
内容：请帮我写一篇关于 [主题] 的文章，要求：
1. 字数约 [数量] 字
2. 风格：[正式/轻松/专业]
3. 包含：[要点1]、[要点2]、[要点3]
分类：写作
标签：文章, 创意, 内容创作
```

#### 示例 2：代码优化
```
标题：代码优化助手
内容：请帮我优化以下代码：
[粘贴代码]

优化目标：
- 提高性能
- 增强可读性
- 遵循最佳实践
分类：编程
标签：Python, 优化, 重构
```

#### 示例 3：翻译助手
```
标题：专业翻译
内容：请将以下内容翻译成 [目标语言]，要求：
- 保持专业术语准确
- 语言流畅自然
- 符合目标语言习惯

[待翻译内容]
分类：翻译
标签：英文, 中文, 专业
```

#### 示例 4：数据分析
```
标题：数据分析助手
内容：请分析以下数据并提供：
1. 关键指标总结
2. 趋势分析
3. 改进建议

[粘贴数据]
分类：分析
标签：数据, 报告, 洞察
```

---

## 🎯 功能测试清单

### 基础功能
- [x] 添加提示词
- [x] 编辑提示词
- [x] 删除提示词
- [x] 收藏提示词
- [x] 复制提示词

### 筛选功能
- [x] 搜索提示词（标题/内容/标签）
- [x] 按分类筛选
- [x] 按标签筛选
- [x] 仅显示收藏

### 导入导出
- [x] 导出为 JSON
- [x] 从 JSON 导入
- [x] 合并模式
- [x] 覆盖模式

### 数据持久化
- [x] 本地存储（data/prompts.json）
- [x] Redis 存储
- [x] PostgreSQL/MySQL 存储

---

## 🔧 API 测试

### 测试结果
```
✅ GET  /api/v1/admin/prompts/list          - 200 OK
✅ GET  /api/v1/admin/prompts/{id}          - 200 OK
✅ POST /api/v1/admin/prompts/create        - 200 OK
✅ PUT  /api/v1/admin/prompts/{id}          - 200 OK
✅ POST /api/v1/admin/prompts/delete        - 200 OK
✅ POST /api/v1/admin/prompts/{id}/use      - 200 OK
✅ GET  /api/v1/admin/prompts/export/all    - 200 OK
✅ POST /api/v1/admin/prompts/import        - 200 OK
```

### 测试命令
```bash
# 获取所有提示词
curl http://localhost:8000/api/v1/admin/prompts/list

# 创建提示词
curl -X POST http://localhost:8000/api/v1/admin/prompts/create \
  -H "Content-Type: application/json" \
  -d '{
    "title": "测试提示词",
    "content": "这是测试内容",
    "category": "测试",
    "tags": ["test"]
  }'

# 搜索提示词
curl "http://localhost:8000/api/v1/admin/prompts/list?search=写作"

# 按分类筛选
curl "http://localhost:8000/api/v1/admin/prompts/list?category=编程"

# 导出所有提示词
curl http://localhost:8000/api/v1/admin/prompts/export/all > prompts_backup.json

# 导入提示词
curl -X POST http://localhost:8000/api/v1/admin/prompts/import?merge=true \
  -H "Content-Type: application/json" \
  -d @prompts_backup.json
```

---

## 📊 数据格式

### 提示词对象
```json
{
  "id": "uuid",
  "title": "提示词标题",
  "content": "提示词内容",
  "category": "分类名称",
  "tags": ["标签1", "标签2"],
  "favorite": false,
  "use_count": 0,
  "created_at": 1707654321000,
  "updated_at": 1707654321000
}
```

### 导出格式
```json
{
  "prompts": [
    {
      "id": "prompt-1",
      "title": "写作助手",
      "content": "帮我写一篇...",
      "category": "写作",
      "tags": ["文章", "创意"],
      "favorite": false,
      "use_count": 5,
      "created_at": 1707654321000,
      "updated_at": 1707654321000
    }
  ],
  "version": "1.0"
}
```

---

## 💡 使用技巧

### 1. 组织提示词
- 使用清晰的分类（写作、编程、翻译、分析等）
- 添加描述性标签（便于搜索）
- 收藏常用提示词（快速访问）

### 2. 编写高质量提示词
- 标题简洁明了
- 内容结构清晰
- 包含占位符（如 [主题]、[数量]）
- 提供具体要求和示例

### 3. 快速使用
- 点击复制按钮（📋）一键复制
- 使用次数自动统计
- 按使用频率排序

### 4. 备份和分享
- 定期导出备份
- 分享给团队成员
- 导入他人的提示词库

---

## 🎨 界面说明

### 顶部操作栏
```
[提示词管理] [总计: X]     [添加提示词] [导入] [导出]
```

### 筛选栏
```
[搜索框] [分类筛选] [标签筛选] [☑ 仅显示收藏]
```

### 提示词卡片
```
┌─────────────────────────┐
│ 标题                  ❤️ │  ← 点击收藏
│ 内容预览（3行）...      │
│ [分类] [标签1] [标签2]  │
│ 使用 5 次  [📋] [✏️] [🗑️] │  ← 复制/编辑/删除
└─────────────────────────┘
```

---

## 🔒 数据安全

### 本地存储
- 文件位置：`data/prompts.json`
- 自动备份：建议定期导出
- 权限控制：需要登录管理后台

### 数据库存储（Vercel）
- PostgreSQL：`prompts` 表
- MySQL：`prompts` 表
- Redis：`grok2api:prompts` 键
- 自动持久化：重启不丢失

---

## 🐛 故障排除

### 问题 1：保存失败
**原因**：StorageFactory 方法名错误
**解决**：已修复，使用 `get_storage()` 方法

### 问题 2：数据丢失
**原因**：使用 local 存储在 Vercel 环境
**解决**：配置外部数据库（PostgreSQL/MySQL/Redis）

### 问题 3：导入失败
**原因**：JSON 格式错误
**解决**：确保 JSON 格式正确，包含 `prompts` 和 `version` 字段

### 问题 4：搜索无结果
**原因**：搜索关键词不匹配
**解决**：尝试搜索标题、内容或标签中的关键词

---

## 📈 最佳实践

### 1. 提示词命名
- ✅ 好：`写作助手 - 技术博客`
- ❌ 差：`提示词1`

### 2. 分类管理
- ✅ 好：`写作`、`编程`、`翻译`、`分析`
- ❌ 差：`其他`、`杂项`

### 3. 标签使用
- ✅ 好：`Python`、`优化`、`重构`
- ❌ 差：`代码`、`好用`

### 4. 内容编写
- ✅ 好：包含占位符、结构清晰、要求明确
- ❌ 差：模糊不清、缺少细节

---

## 🎉 功能完成

提示词管理功能已经完全可用，现在你可以：

1. ✅ 添加和管理提示词
2. ✅ 按分类和标签组织
3. ✅ 快速搜索和筛选
4. ✅ 一键复制使用
5. ✅ 导入导出备份
6. ✅ 数据持久化存储

---

## 📞 需要帮助？

如果遇到问题，请检查：
1. 服务是否正常启动
2. 浏览器控制台是否有错误
3. 数据库连接是否正常
4. API 端点是否可访问

---

**创建时间**：2026-02-11
**版本**：1.0
**状态**：✅ 已完成并测试通过
