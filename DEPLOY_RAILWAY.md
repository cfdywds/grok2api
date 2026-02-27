# Railway 部署指南

本文档详细说明如何将 Grok2API 部署到 Railway 平台。

## 🌟 为什么选择 Railway？

相比 Render，Railway 有以下优势：

| 特性 | Railway | Render 免费版 |
|------|---------|--------------|
| 休眠问题 | ✅ **不会休眠** | ❌ 15分钟无访问会休眠 |
| 访问速度 | ✅ **即时响应** | ⚠️ 首次访问需30-60秒唤醒 |
| 免费额度 | $5/月 | 750小时/月 |
| 部署速度 | ✅ **更快** | 较慢 |
| 用户体验 | ✅ **流畅** | ⚠️ 首次访问慢 |

**推荐指数：⭐⭐⭐⭐⭐**

---

## 📋 部署前准备

### 1. 注册 Railway 账号

访问 [Railway](https://railway.app/) 并注册账号。

**注册方式：**
- GitHub 登录（推荐）
- Google 登录
- 邮箱注册

> 💡 提示：使用 GitHub 登录可以直接连接仓库，更方便！

### 2. 验证账号（重要！）

Railway 免费版需要验证账号才能使用：

**方式 1：绑定信用卡（推荐）**
- 不会扣费，只是验证身份
- 每月 $5 免费额度
- 超出额度才会收费

**方式 2：GitHub 学生认证**
- 如果你有 GitHub 学生包
- 可以获得额外的免费额度

### 3. 准备 GitHub 仓库

确保你的项目已经推送到 GitHub 仓库。

### 4. 准备 Grok Token

- 登录 [X.com](https://x.com/)
- 获取你的 Grok Token（稍后在管理面板中添加）

---

## 🚀 快速部署

### 方式 1：从 GitHub 部署（推荐）

#### 步骤 1：创建新项目

1. 登录 [Railway Dashboard](https://railway.app/dashboard)
2. 点击 **New Project**
3. 选择 **Deploy from GitHub repo**
4. 如果是首次使用，需要授权 Railway 访问你的 GitHub

#### 步骤 2：选择仓库

1. 在仓库列表中找到 `grok2api`
2. 点击仓库名称
3. Railway 会自动检测到 Dockerfile

#### 步骤 3：配置环境变量

Railway 会自动开始部署，但我们需要先配置环境变量：

1. 点击部署的服务
2. 进入 **Variables** 标签
3. 点击 **New Variable**，添加以下环境变量：

**基础环境变量：**

```bash
# 时区设置
TZ=Asia/Shanghai

# 日志配置
LOG_LEVEL=INFO
LOG_FILE_ENABLED=true

# 服务配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_WORKERS=1

# 存储配置（见下方持久化存储章节）
SERVER_STORAGE_TYPE=local
SERVER_STORAGE_URL=
```

#### 步骤 4：生成公网域名

1. 进入 **Settings** 标签
2. 找到 **Networking** 部分
3. 点击 **Generate Domain**
4. 你会获得一个域名，如：`grok2api-production.up.railway.app`

#### 步骤 5：等待部署完成

- 在 **Deployments** 标签查看部署进度
- 首次部署约需 3-5 分钟
- 部署成功后状态显示为 **Active**

---

### 方式 2：使用 Railway CLI（高级）

如果你熟悉命令行，可以使用 Railway CLI：

```bash
# 安装 Railway CLI
npm i -g @railway/cli

# 登录
railway login

# 初始化项目
railway init

# 部署
railway up
```

---

## 🗄️ 持久化存储配置（重要！）

### ⚠️ 数据持久化说明

Railway 的容器重启后会丢失本地数据，因此**强烈建议配置外部数据库**！

### 方案 1：使用 Railway PostgreSQL（推荐）

Railway 提供了一键添加 PostgreSQL 数据库的功能！

#### 1.1 添加 PostgreSQL 服务

1. 在项目页面点击 **New**
2. 选择 **Database** → **Add PostgreSQL**
3. Railway 会自动创建数据库并生成连接信息

#### 1.2 配置环境变量

PostgreSQL 创建后，Railway 会自动生成以下变量：
- `PGHOST`
- `PGPORT`
- `PGUSER`
- `PGPASSWORD`
- `PGDATABASE`
- `DATABASE_URL`

**在 Web Service 中添加变量：**

```bash
SERVER_STORAGE_TYPE=pgsql
SERVER_STORAGE_URL=${{Postgres.DATABASE_URL}}
```

> 💡 提示：`${{Postgres.DATABASE_URL}}` 是 Railway 的变量引用语法，会自动替换为实际的数据库连接串

#### 1.3 修改连接串格式

Railway 的 `DATABASE_URL` 格式是 `postgresql://...`，需要改为 `postgresql+asyncpg://...`

**方式 1：使用自定义变量（推荐）**

添加一个新变量：
```bash
SERVER_STORAGE_URL=postgresql+asyncpg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
```

**方式 2：代码已自动处理**

本项目的 `storage.py` 已经自动处理了这个转换，直接使用 `DATABASE_URL` 也可以：
```bash
SERVER_STORAGE_TYPE=pgsql
SERVER_STORAGE_URL=${{Postgres.DATABASE_URL}}
```

### 方案 2：使用外部 PostgreSQL

如果你有自己的 PostgreSQL 数据库：

```bash
SERVER_STORAGE_TYPE=pgsql
SERVER_STORAGE_URL=postgresql+asyncpg://user:password@host:5432/dbname
```

**免费 PostgreSQL 服务推荐：**
- [Supabase](https://supabase.com/) - 500 MB 免费，亚洲节点快
- [Neon](https://neon.tech/) - 3 GB 免费，Serverless
- [ElephantSQL](https://www.elephantsql.com/) - 20 MB 免费

### 方案 3：使用 Railway Redis

#### 3.1 添加 Redis 服务

1. 在项目页面点击 **New**
2. 选择 **Database** → **Add Redis**
3. Railway 会自动创建 Redis 并生成连接信息

#### 3.2 配置环境变量

```bash
SERVER_STORAGE_TYPE=redis
SERVER_STORAGE_URL=${{Redis.REDIS_URL}}
```

### 方案 4：使用外部 Redis

```bash
SERVER_STORAGE_TYPE=redis
SERVER_STORAGE_URL=redis://user:password@host:6379/0
```

**免费 Redis 服务推荐：**
- [Upstash](https://upstash.com/) - 10,000 命令/天免费
- [Redis Cloud](https://redis.com/try-free/) - 30 MB 免费

### 方案 5：使用本地存储（不推荐）

仅用于测试，重启会丢失数据：

```bash
SERVER_STORAGE_TYPE=local
SERVER_STORAGE_URL=
```

---

## 📱 手机访问配置

### 1. 获取访问地址

部署成功后，你会获得一个 HTTPS 域名：
```
https://grok2api-production.up.railway.app
```

### 2. 手机浏览器访问

**方式 1：直接访问**

在手机浏览器中输入：
```
https://grok2api-production.up.railway.app/admin
```

**方式 2：扫码访问（推荐）**

1. 在电脑浏览器访问管理面板
2. 点击页面右上角的 📱 按钮
3. 使用手机扫描二维码
4. 自动跳转到管理面板

### 3. 支持的手机浏览器

- ✅ Safari (iOS) - 完美支持
- ✅ Chrome (Android/iOS) - 完美支持
- ✅ Firefox (Android/iOS) - 完美支持
- ✅ Edge (Android/iOS) - 完美支持
- ✅ 微信内置浏览器 - 支持
- ✅ QQ 浏览器 - 支持
- ✅ UC 浏览器 - 支持

### 4. 手机访问体验

**优势：**
- ✅ 即时响应，无需等待唤醒
- ✅ HTTPS 加密，安全可靠
- ✅ 响应式设计，适配手机屏幕
- ✅ 支持触摸操作
- ✅ 可以添加到主屏幕（PWA）

**添加到主屏幕（iOS）：**
1. 在 Safari 中打开管理面板
2. 点击底部的分享按钮
3. 选择"添加到主屏幕"
4. 像 App 一样使用

**添加到主屏幕（Android）：**
1. 在 Chrome 中打开管理面板
2. 点击右上角菜单
3. 选择"添加到主屏幕"
4. 像 App 一样使用

---

## 🔧 管理面板使用

### 访问管理面板

```
https://your-domain.up.railway.app/admin
```

**默认密码：** `grok2api`

> ⚠️ 首次登录后请立即修改密码！

### 修改默认密码

1. 登录管理面板
2. 进入 **配置管理**
3. 找到 `app.app_key` 配置项
4. 修改为你的自定义密码
5. 点击保存

### 添加 Grok Token

1. 登录管理面板
2. 进入 **Token 管理**
3. 点击 **添加 Token** 或 **导入 Token**
4. 输入你的 Grok Token
5. 选择 Token 类型：
   - **Basic**: 80 次 / 20h
   - **Super**: 140 次 / 2h
6. 点击保存

### 功能说明

**Token 管理：**
- 添加/删除/刷新 Token
- 查看 Token 状态和配额
- 批量操作（刷新、导出、删除）
- 开启 NSFW 模式（Unhinged）

**图片管理：**
- 查看生成的图片
- 按提示词、模型、质量筛选
- 批量导出 ZIP
- 批量删除
- 质量分析（模糊度、亮度、对比度）
- 自动删除低质量图片（<30分）

**配置管理：**
- 在线修改系统配置
- 修改 API Key
- 修改管理密码
- 配置 Token 刷新策略

**缓存管理：**
- 查看媒体缓存
- 清理缓存

---

## 🔌 API 使用

### 基础配置

**API Base URL:**
```
https://your-domain.up.railway.app/v1
```

**API Key:**

在管理面板的 **配置管理** 中查看或修改 `app.api_key`。

### 示例：对话接口

```bash
curl https://your-domain.up.railway.app/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "grok-4",
    "messages": [{"role":"user","content":"你好"}],
    "stream": false
  }'
```

### 示例：流式对话

```bash
curl https://your-domain.up.railway.app/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "grok-4",
    "messages": [{"role":"user","content":"讲个笑话"}],
    "stream": true
  }'
```

### 示例：图片生成

```bash
curl https://your-domain.up.railway.app/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "grok-imagine-1.0",
    "prompt": "a beautiful sunset over the ocean",
    "n": 1,
    "size": "1024x1024"
  }'
```

### 示例：图片编辑

```bash
curl https://your-domain.up.railway.app/v1/images/edits \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "image=@original.png" \
  -F "prompt=add a rainbow in the sky" \
  -F "model=grok-imagine-1.0-edit"
```

### 在第三方应用中使用

**ChatGPT Next Web:**
```
API 地址: https://your-domain.up.railway.app/v1
API Key: YOUR_API_KEY
模型: grok-4
```

**OpenCat (iOS):**
```
API 地址: https://your-domain.up.railway.app/v1
API Key: YOUR_API_KEY
模型: grok-4
```

**ChatBox:**
```
API 地址: https://your-domain.up.railway.app/v1
API Key: YOUR_API_KEY
模型: grok-4
```

---

## ⚙️ 高级配置

### 自定义域名

1. 在 Railway 项目页面进入 **Settings**
2. 找到 **Networking** → **Custom Domain**
3. 点击 **Add Custom Domain**
4. 输入你的域名（如 `api.yourdomain.com`）
5. 按照提示配置 DNS 记录：
   - 类型：CNAME
   - 名称：api
   - 值：your-project.up.railway.app
6. 等待 DNS 生效（通常 5-10 分钟）

### 环境变量完整列表

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `TZ` | `UTC` | 时区设置（推荐 `Asia/Shanghai`） |
| `LOG_LEVEL` | `INFO` | 日志级别（DEBUG/INFO/WARNING/ERROR） |
| `LOG_FILE_ENABLED` | `true` | 是否启用文件日志 |
| `DATA_DIR` | `./data` | 数据目录 |
| `SERVER_HOST` | `0.0.0.0` | 服务监听地址 |
| `SERVER_PORT` | `8000` | 服务端口 |
| `SERVER_WORKERS` | `1` | Worker 数量（推荐1） |
| `SERVER_STORAGE_TYPE` | `local` | 存储类型（local/redis/mysql/pgsql） |
| `SERVER_STORAGE_URL` | `` | 存储连接串 |

### 性能优化

**启用多 Worker（可选）：**
```bash
SERVER_WORKERS=2
```

> ⚠️ 注意：多 Worker 会增加内存使用，可能超出免费额度

**调整日志级别：**
```bash
LOG_LEVEL=WARNING  # 减少日志输出
```

### 健康检查

Railway 会自动进行健康检查，你也可以手动访问：

```bash
curl https://your-domain.up.railway.app/
```

---

## 🐛 常见问题

### 1. 部署失败

**问题：** 部署时出现错误。

**解决方案：**
- 查看 **Deployments** 标签的日志
- 检查 Dockerfile 是否正确
- 确保所有依赖都在 `pyproject.toml` 中
- 尝试重新部署：点击 **Redeploy**

### 2. 无法访问服务

**问题：** 部署成功但无法访问。

**解决方案：**
- 确保已生成公网域名（Settings → Networking → Generate Domain）
- 检查 `SERVER_HOST` 是否为 `0.0.0.0`
- 检查 `SERVER_PORT` 是否为 `8000`
- 查看日志确认服务是否正常启动

### 3. 数据丢失

**问题：** 重启后 Token 和配置丢失。

**解决方案：**
- 配置外部数据库（PostgreSQL/Redis）
- 参考上方 **持久化存储配置** 章节
- 确保 `SERVER_STORAGE_TYPE` 和 `SERVER_STORAGE_URL` 配置正确

### 4. Token 自动刷新失败

**问题：** Token 刷新调度器不工作。

**解决方案：**
- 检查日志确认调度器是否启动
- 查看 Token 管理页面的刷新记录
- 如果使用 Redis，确保连接正常
- 手动触发刷新测试

### 5. 超出免费额度

**问题：** 收到超额通知。

**解决方案：**
- 在 Railway Dashboard 查看用量
- 优化资源使用（减少 Worker、降低日志级别）
- 升级到付费计划
- 或者暂停服务等待下月重置

### 6. 手机访问慢

**问题：** 手机访问速度慢。

**解决方案：**
- Railway 服务器在美国，国内访问可能较慢
- 考虑使用 CDN 加速
- 或者使用国内的云服务（如腾讯云、阿里云）

### 7. 图片无法显示

**问题：** 生成的图片无法显示。

**解决方案：**
- 检查图片存储路径
- 如果使用外部存储，确保配置正确
- 查看日志确认图片是否成功保存
- 检查静态文件服务是否正常

### 8. WebSocket 连接失败

**问题：** 图片生成的 WebSocket 连接失败。

**解决方案：**
- Railway 支持 WebSocket，无需特殊配置
- 检查防火墙设置
- 查看浏览器控制台的错误信息
- 确保使用 HTTPS（不是 HTTP）

---

## 📊 监控和日志

### 查看日志

**实时日志：**
1. 在 Railway 项目页面点击服务
2. 进入 **Deployments** 标签
3. 点击最新的部署
4. 查看实时日志输出

**历史日志：**
- Railway 保留最近的日志记录
- 可以搜索和过滤日志

### 监控指标

在 **Metrics** 标签可以查看：
- CPU 使用率
- 内存使用率
- 网络流量
- 磁盘使用

### 用量统计

在 **Usage** 标签可以查看：
- 本月已使用额度
- 剩余免费额度
- 预计费用

---

## 🔄 更新部署

### 自动部署

Railway 默认启用自动部署：
1. 推送代码到 GitHub
2. Railway 自动检测并重新部署
3. 无需手动操作

### 禁用自动部署

如果你想手动控制部署：
1. 进入 **Settings** 标签
2. 找到 **Service** → **Deployment Triggers**
3. 关闭 **Auto Deploy**

### 手动部署

1. 在 Railway 项目页面点击服务
2. 点击 **Deploy** 按钮
3. 选择要部署的分支或提交

### 回滚版本

1. 进入 **Deployments** 标签
2. 找到之前的成功部署
3. 点击 **Redeploy**

---

## 💰 费用说明

### 免费额度

- ✅ **$5/月** 免费额度
- ✅ 不会休眠
- ✅ 即时响应
- ✅ 支持自定义域名
- ✅ 支持 WebSocket

### 用量估算

**本项目预计用量：**
- CPU: 0.1-0.2 vCPU
- 内存: 256-512 MB
- 网络: 取决于使用量

**预计费用：**
- 轻度使用（<1000 请求/天）：**免费**
- 中度使用（1000-5000 请求/天）：**$0-2/月**
- 重度使用（>5000 请求/天）：**$2-5/月**

### 付费计划

如果超出免费额度，Railway 会按使用量计费：
- CPU: $0.000463/vCPU/分钟
- 内存: $0.000231/GB/分钟
- 网络: $0.10/GB

### 节省费用技巧

1. **优化资源使用**
   - 使用单 Worker（`SERVER_WORKERS=1`）
   - 降低日志级别（`LOG_LEVEL=WARNING`）
   - 关闭不必要的功能

2. **使用外部服务**
   - 图片存储使用 S3（更便宜）
   - 数据库使用 Supabase（免费）

3. **监控用量**
   - 定期查看 Usage 标签
   - 设置用量警报

---

## 🆘 获取帮助

### 官方资源

- **Railway 文档**: [docs.railway.app](https://docs.railway.app/)
- **Railway Discord**: [discord.gg/railway](https://discord.gg/railway)
- **Railway 状态**: [status.railway.app](https://status.railway.app/)

### 项目资源

- **项目文档**: [README.md](./readme.md)
- **GitHub Issues**: [提交问题](https://github.com/chenyme/grok2api/issues)
- **更新日志**: [CHANGELOG.md](./CHANGELOG.md)

---

## ✅ 部署检查清单

### 部署前

- [ ] 注册 Railway 账号
- [ ] 验证账号（绑定信用卡）
- [ ] 准备 GitHub 仓库
- [ ] 准备 Grok Token

### 部署中

- [ ] 从 GitHub 创建项目
- [ ] 配置环境变量
- [ ] 添加 PostgreSQL 数据库（推荐）
- [ ] 生成公网域名
- [ ] 等待部署完成

### 部署后

- [ ] 访问管理面板
- [ ] 修改默认密码
- [ ] 添加 Grok Token
- [ ] 测试 API 接口
- [ ] 手机浏览器访问测试
- [ ] 配置自定义域名（可选）
- [ ] 设置用量警报（可选）

---

## 🎉 部署成功！

恭喜你成功部署 Grok2API 到 Railway！

**接下来你可以：**
- 📱 在手机浏览器访问管理面板
- 🔌 在第三方应用中使用 API
- 🖼️ 生成和管理图片
- ⚙️ 自定义配置和域名

**享受你的 Grok2API 服务吧！** 🚀

---

## 📝 附录

### A. 环境变量模板

复制以下内容到 Railway 的 Variables 中：

```bash
# 基础配置
TZ=Asia/Shanghai
LOG_LEVEL=INFO
LOG_FILE_ENABLED=true

# 服务配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_WORKERS=1

# 存储配置（使用 Railway PostgreSQL）
SERVER_STORAGE_TYPE=pgsql
SERVER_STORAGE_URL=${{Postgres.DATABASE_URL}}
```

### B. 数据库连接串格式

**PostgreSQL:**
```
postgresql+asyncpg://user:password@host:5432/dbname
```

**MySQL:**
```
mysql+aiomysql://user:password@host:3306/dbname
```

**Redis:**
```
redis://user:password@host:6379/0
```

### C. 常用命令

**查看日志:**
```bash
railway logs
```

**查看变量:**
```bash
railway variables
```

**连接数据库:**
```bash
railway connect postgres
```

---

**祝你部署顺利！** 🎉
