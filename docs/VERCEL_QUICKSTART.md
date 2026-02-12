# Vercel 环境变量配置 - 图文教程

## 📋 配置清单

在开始之前，准备好以下信息：

- [ ] Vercel 账号（已登录）
- [ ] 项目已部署（grok2api）
- [ ] 5 分钟时间

## 🎯 第一步：找到环境变量设置

### 1. 打开 Vercel Dashboard

访问：https://vercel.com/dashboard

### 2. 找到你的项目

在项目列表中找到 `grok2api` 项目，点击进入。

### 3. 进入设置页面

```
项目页面 → Settings（顶部标签）→ Environment Variables（左侧菜单）
```

## ⚙️ 第二步：添加环境变量

点击右上角的 **"Add New"** 按钮，然后按照下面的表格逐个添加：

### 环境变量配置表

| 序号 | Key | Value | 说明 |
|------|-----|-------|------|
| 1 | `LOG_LEVEL` | `INFO` | 日志级别 |
| 2 | `LOG_FILE_ENABLED` | `false` | 禁用文件日志 |
| 3 | `DATA_DIR` | `/tmp/data` | 临时数据目录 |
| 4 | `SERVER_STORAGE_TYPE` | `local` | 存储类型 |
| 5 | `SERVER_STORAGE_URL` | (留空) | 数据库连接 |

### 添加步骤（每个变量重复）

1. 点击 **"Add New"**
2. 在 **"Key"** 输入框输入变量名（如 `LOG_LEVEL`）
3. 在 **"Value"** 输入框输入值（如 `INFO`）
4. 在 **"Environment"** 部分，确保勾选 ✅ **Production**
5. 点击 **"Save"**
6. 重复以上步骤添加其他变量

### 📸 添加示例

```
┌─────────────────────────────────────────┐
│ Add Environment Variable                │
├─────────────────────────────────────────┤
│ Key:   LOG_LEVEL                        │
│ Value: INFO                             │
│                                         │
│ Environment:                            │
│ ✅ Production                           │
│ ☐ Preview                               │
│ ☐ Development                           │
│                                         │
│ [Cancel]              [Save]            │
└─────────────────────────────────────────┘
```

## 🔄 第三步：重新部署

添加完所有环境变量后：

### 方法 A：通过 UI 重新部署

1. 点击顶部的 **"Deployments"** 标签
2. 找到最新的部署记录（第一行）
3. 点击右侧的三个点 **⋯** 菜单
4. 选择 **"Redeploy"**
5. 在弹出框中再次点击 **"Redeploy"** 确认

### 方法 B：推送代码触发部署

如果你修改了代码：

```bash
git add .
git commit -m "update"
git push origin navy
```

Vercel 会自动检测并重新部署。

## ✅ 第四步：验证部署

### 1. 检查部署状态

在 **Deployments** 页面：
- ✅ 绿色勾号 = 部署成功
- ⏳ 黄色圆圈 = 正在部署
- ❌ 红色叉号 = 部署失败

### 2. 查看部署日志

如果部署失败：
1. 点击失败的部署记录
2. 查看 **"Build Logs"** 和 **"Function Logs"**
3. 找到错误信息

### 3. 访问应用

部署成功后，点击 **"Visit"** 按钮或复制 URL：

```
https://grok2api-xxx.vercel.app
```

### 4. 测试管理面板

访问：
```
https://grok2api-xxx.vercel.app/admin
```

- 应该能看到登录页面
- 使用密码 `grok2api` 登录
- 能看到管理界面

## 🎉 完成！

如果以上步骤都成功，你的 Grok2API 已经成功部署到 Vercel！

## 📊 配置检查清单

完成后，检查以下项目：

- [ ] 5 个环境变量都已添加
- [ ] 所有变量的 Environment 都选择了 Production
- [ ] 重新部署已完成
- [ ] 部署状态显示成功（绿色勾号）
- [ ] 可以访问应用 URL
- [ ] 可以访问管理面板 /admin
- [ ] 可以使用密码 grok2api 登录

## 🔧 进阶配置：添加数据库

如果你想要数据持久化（推荐），继续以下步骤：

### 选项 1：Vercel Postgres（推荐新手）

#### 1. 创建数据库

```
项目页面 → Storage（顶部标签）→ Create Database → Postgres
```

#### 2. 配置数据库

- Database Name: `grok2api-db`
- Region: 选择离你最近的区域
- 点击 **"Create"**

#### 3. 获取连接字符串

数据库创建后，Vercel 会自动添加环境变量。找到：
- `POSTGRES_URL` 或
- `POSTGRES_PRISMA_URL`

复制连接字符串，格式类似：
```
postgresql://user:password@host:5432/database
```

#### 4. 更新环境变量

回到 **Settings** → **Environment Variables**：

**修改 SERVER_STORAGE_TYPE：**
- 找到 `SERVER_STORAGE_TYPE`
- 点击编辑图标
- 将值改为 `pgsql`
- 保存

**修改 SERVER_STORAGE_URL：**
- 找到 `SERVER_STORAGE_URL`
- 点击编辑图标
- 粘贴连接字符串
- **重要：** 将开头的 `postgresql://` 改为 `postgresql+asyncpg://`
- 例如：`postgresql+asyncpg://user:password@host:5432/database`
- 保存

#### 5. 重新部署

按照前面的步骤重新部署。

### 选项 2：Supabase（推荐进阶用户）

#### 1. 创建 Supabase 账号

访问：https://supabase.com

#### 2. 创建项目

- 点击 **"New Project"**
- 输入项目名称：`grok2api`
- 设置数据库密码（记住这个密码！）
- 选择区域
- 点击 **"Create new project"**

#### 3. 获取连接字符串

项目创建后：
```
Settings（左侧）→ Database → Connection string → URI
```

复制连接字符串，格式：
```
postgresql://postgres:[YOUR-PASSWORD]@[HOST]:5432/postgres
```

将 `[YOUR-PASSWORD]` 替换为你设置的密码。

#### 4. 配置 Vercel

在 Vercel 的环境变量中：

- `SERVER_STORAGE_TYPE` = `pgsql`
- `SERVER_STORAGE_URL` = `postgresql+asyncpg://postgres:[YOUR-PASSWORD]@[HOST]:5432/postgres`

**注意：** 将 `postgresql://` 改为 `postgresql+asyncpg://`

#### 5. 重新部署

## 🆘 常见问题

### Q1: 找不到 "Add New" 按钮

**位置：** Settings → Environment Variables → 右上角

如果还是找不到，尝试刷新页面。

### Q2: 保存环境变量时提示错误

**可能原因：**
- Key 名称包含空格或特殊字符
- Value 格式不正确
- 没有选择 Environment

**解决方案：**
- 确保 Key 只包含字母、数字和下划线
- 检查 Value 是否正确
- 确保勾选了 Production

### Q3: 重新部署后还是失败

**检查步骤：**
1. 确认所有 5 个环境变量都已添加
2. 查看部署日志中的错误信息
3. 确认 Python 版本兼容（应该是 3.12）

### Q4: 应用可以访问但管理面板打不开

**可能原因：**
- 路由配置问题
- 静态文件未正确部署

**解决方案：**
- 检查 URL 是否正确：`/admin` 而不是 `/admin/`
- 查看浏览器控制台的错误信息

### Q5: 数据库连接失败

**检查清单：**
- [ ] 连接字符串格式正确
- [ ] 已将 `postgresql://` 改为 `postgresql+asyncpg://`
- [ ] 数据库密码正确
- [ ] 数据库允许外部连接
- [ ] 已重新部署

## 📞 获取帮助

如果遇到问题：

1. **查看部署日志**
   - Deployments → 点击部署 → Build Logs / Function Logs

2. **查看 Vercel 文档**
   - https://vercel.com/docs

3. **查看项目文档**
   - README.md
   - VERCEL_DEPLOY.md
   - docs/VERCEL_ENV_SETUP.md

4. **提交 Issue**
   - https://github.com/cfdywds/grok2api/issues

## 🎓 下一步学习

配置完成后，你可以：

1. **自定义域名**
   - Settings → Domains → Add Domain

2. **配置 HTTPS**
   - Vercel 自动提供免费 SSL 证书

3. **监控和分析**
   - Analytics → 查看访问统计

4. **配置 CI/CD**
   - Git → 配置自动部署规则

5. **优化性能**
   - 配置缓存策略
   - 使用 Edge Functions

## 📚 相关资源

- [Vercel 官方文档](https://vercel.com/docs)
- [FastAPI 部署指南](https://fastapi.tiangolo.com/deployment/)
- [Supabase 文档](https://supabase.com/docs)
- [项目 GitHub](https://github.com/cfdywds/grok2api)

---

**最后更新：** 2025-02-12

**版本：** 1.0

**作者：** Grok2API Team
