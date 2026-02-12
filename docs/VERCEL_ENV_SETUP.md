# Vercel 环境变量配置指南

## 快速配置步骤

### 1. 进入项目设置

1. 访问 Vercel Dashboard: https://vercel.com/dashboard
2. 找到你的项目 `grok2api`
3. 点击项目进入详情页
4. 点击顶部的 **Settings** 标签
5. 在左侧菜单点击 **Environment Variables**

### 2. 添加环境变量

点击 **Add New** 按钮，逐个添加以下变量：

#### 必需的环境变量

**变量 1: LOG_LEVEL**
- Key: `LOG_LEVEL`
- Value: `INFO`
- Environment: ✅ Production (勾选)
- 点击 **Save**

**变量 2: LOG_FILE_ENABLED**
- Key: `LOG_FILE_ENABLED`
- Value: `false`
- Environment: ✅ Production
- 点击 **Save**

**变量 3: DATA_DIR**
- Key: `DATA_DIR`
- Value: `/tmp/data`
- Environment: ✅ Production
- 点击 **Save**

**变量 4: SERVER_STORAGE_TYPE**
- Key: `SERVER_STORAGE_TYPE`
- Value: `local`
- Environment: ✅ Production
- 点击 **Save**

**变量 5: SERVER_STORAGE_URL**
- Key: `SERVER_STORAGE_URL`
- Value: (留空，不填任何内容)
- Environment: ✅ Production
- 点击 **Save**

### 3. 重新部署

添加完所有环境变量后：

1. 点击顶部的 **Deployments** 标签
2. 找到最新的部署记录
3. 点击右侧的三个点菜单 **⋯**
4. 选择 **Redeploy**
5. 在弹出的对话框中点击 **Redeploy** 确认

### 4. 等待部署完成

- 部署通常需要 2-5 分钟
- 可以点击部署记录查看实时日志
- 部署成功后会显示绿色的 ✓ 标记

### 5. 访问应用

部署成功后，你会得到一个 URL，例如：
```
https://grok2api-xxx.vercel.app
```

访问管理面板：
```
https://grok2api-xxx.vercel.app/admin
```

默认密码：`grok2api`

## 使用数据库（推荐配置）

如果你想要数据持久化，需要配置数据库。

### 选项 A: Vercel Postgres（最简单）

1. **创建数据库**
   - 在项目页面，点击 **Storage** 标签
   - 点击 **Create Database**
   - 选择 **Postgres**
   - 点击 **Continue**
   - 输入数据库名称（如 `grok2api-db`）
   - 选择区域（建议选择离你最近的）
   - 点击 **Create**

2. **获取连接字符串**
   - 数据库创建后，Vercel 会自动添加环境变量
   - 找到 `POSTGRES_URL` 或 `POSTGRES_PRISMA_URL`
   - 复制连接字符串（格式：`postgresql://user:pass@host:5432/db`）

3. **更新环境变量**
   - 回到 **Settings** → **Environment Variables**
   - 找到 `SERVER_STORAGE_TYPE`，点击编辑
   - 将值改为 `pgsql`
   - 找到 `SERVER_STORAGE_URL`，点击编辑
   - 粘贴连接字符串，**注意：将 `postgresql://` 改为 `postgresql+asyncpg://`**
   - 例如：`postgresql+asyncpg://user:pass@host:5432/db`

4. **重新部署**
   - 按照上面的步骤重新部署

### 选项 B: Supabase（免费额度更大）

1. **创建 Supabase 项目**
   - 访问 https://supabase.com
   - 注册/登录账号
   - 点击 **New Project**
   - 输入项目名称和数据库密码
   - 选择区域
   - 点击 **Create new project**

2. **获取连接字符串**
   - 项目创建后，点击左侧的 **Settings** 图标
   - 点击 **Database**
   - 找到 **Connection string** 部分
   - 选择 **URI** 格式
   - 复制连接字符串
   - 格式：`postgresql://postgres:[YOUR-PASSWORD]@[HOST]:5432/postgres`

3. **配置 Vercel 环境变量**
   - 在 Vercel 项目设置中
   - 编辑 `SERVER_STORAGE_TYPE` = `pgsql`
   - 编辑 `SERVER_STORAGE_URL` = `postgresql+asyncpg://postgres:[YOUR-PASSWORD]@[HOST]:5432/postgres`
   - **重要：** 将 `postgresql://` 改为 `postgresql+asyncpg://`

4. **重新部署**

## 环境变量说明

| 变量名 | 说明 | 可选值 | 默认值 |
|--------|------|--------|--------|
| `LOG_LEVEL` | 日志级别 | DEBUG, INFO, WARNING, ERROR | INFO |
| `LOG_FILE_ENABLED` | 是否启用文件日志 | true, false | false（Vercel 必须为 false） |
| `DATA_DIR` | 数据目录 | 任意路径 | /tmp/data（Vercel 必须用 /tmp） |
| `SERVER_STORAGE_TYPE` | 存储类型 | local, pgsql, mysql, redis | local |
| `SERVER_STORAGE_URL` | 数据库连接字符串 | 数据库 URL | 空（local 时） |

## 验证配置

### 检查环境变量

1. 进入 **Settings** → **Environment Variables**
2. 确认所有变量都已添加
3. 确认环境选择了 **Production**

### 检查部署状态

1. 进入 **Deployments**
2. 查看最新部署的状态
3. 如果失败，点击查看日志

### 测试应用

访问你的应用 URL，应该能看到：
- 管理面板可以访问
- 可以登录（密码：grok2api）
- 可以添加 Token

## 常见问题

### Q1: 部署失败，显示 "Missing environment variables"

**解决方案：**
1. 检查是否添加了所有必需的环境变量
2. 确认环境变量的 Environment 选择了 **Production**
3. 重新部署

### Q2: 应用可以访问，但数据丢失

**原因：** 使用了本地存储（`SERVER_STORAGE_TYPE=local`）

**解决方案：** 配置数据库（见上面的数据库配置部分）

### Q3: 数据库连接失败

**检查：**
1. 连接字符串格式是否正确
2. 是否将 `postgresql://` 改为 `postgresql+asyncpg://`
3. 数据库密码是否正确
4. 数据库是否允许外部连接

### Q4: 如何查看应用日志

1. 进入 **Deployments**
2. 点击具体的部署
3. 查看 **Function Logs**

### Q5: 如何更新环境变量

1. 进入 **Settings** → **Environment Variables**
2. 找到要修改的变量
3. 点击右侧的编辑图标
4. 修改值
5. 保存
6. 重新部署

## 下一步

配置完成后：

1. **访问管理面板**
   - URL: `https://your-app.vercel.app/admin`
   - 密码: `grok2api`

2. **修改默认密码**
   - 登录后进入配置管理
   - 修改 `app.app_key` 配置项

3. **添加 Grok Token**
   - 进入 Token 管理
   - 添加你的 Grok Token

4. **测试 API**
   ```bash
   curl https://your-app.vercel.app/v1/chat/completions \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer your-api-key" \
     -d '{
       "model": "grok-4",
       "messages": [{"role": "user", "content": "Hello"}]
     }'
   ```

## 获取帮助

如果遇到问题：
- 查看 Vercel 部署日志
- 查看项目 GitHub Issues
- 参考 VERCEL_DEPLOY.md 文档
