# Render 部署指南

本文档详细说明如何将 Grok2API 部署到 Render 平台。

## 📋 部署前准备

### 1. 注册 Render 账号

访问 [Render](https://render.com/) 并注册账号（支持 GitHub 登录）。

### 2. 准备 GitHub 仓库

确保你的项目已经推送到 GitHub 仓库。

### 3. 准备 Grok Token

- 登录 [X.com](https://x.com/)
- 获取你的 Grok Token（在管理面板中添加）

---

## 🚀 快速部署（一键部署）

### 方式 1：使用 Deploy Button

点击下方按钮一键部署：

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/chenyme/grok2api)

### 方式 2：手动部署

#### 步骤 1：创建 Web Service

1. 登录 Render Dashboard
2. 点击 **New +** → **Web Service**
3. 连接你的 GitHub 仓库
4. 选择 `grok2api` 仓库

#### 步骤 2：配置服务

**基础配置：**
- **Name**: `grok2api`（或自定义名称）
- **Region**: 选择离你最近的区域（推荐 Singapore 或 Oregon）
- **Branch**: `main`
- **Runtime**: `Docker`
- **Instance Type**: `Free`（免费版）

**环境变量配置：**

点击 **Advanced** → **Add Environment Variable**，添加以下环境变量：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `TZ` | `Asia/Shanghai` | 时区设置 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `SERVER_HOST` | `0.0.0.0` | 服务监听地址 |
| `SERVER_PORT` | `8000` | 服务端口 |
| `SERVER_STORAGE_TYPE` | `local` | 存储类型（见下方说明） |
| `SERVER_STORAGE_URL` | `` | 存储连接串（local 时留空） |

#### 步骤 3：部署

点击 **Create Web Service**，等待部署完成（约 3-5 分钟）。

部署成功后，你会获得一个公网域名，如：
```
https://grok2api-xxxx.onrender.com
```

---

## 🗄️ 持久化存储配置（重要！）

### ⚠️ 免费版限制

Render 免费实例有以下限制：
- **15 分钟无访问会休眠**
- **重启/休眠会丢失本地数据**
- 每月 750 小时免费（约 31 天）

**因此，强烈建议配置外部数据库进行持久化存储！**

### 方案 1：使用 PostgreSQL（推荐）

#### 1.1 在 Render 创建 PostgreSQL 数据库

1. 在 Render Dashboard 点击 **New +** → **PostgreSQL**
2. 配置数据库：
   - **Name**: `grok2api-db`
   - **Database**: `grok2api`
   - **User**: `grok2api`
   - **Region**: 与 Web Service 相同
   - **Instance Type**: `Free`
3. 点击 **Create Database**
4. 等待创建完成，复制 **Internal Database URL**

#### 1.2 配置环境变量

在 Web Service 的环境变量中修改：

```bash
SERVER_STORAGE_TYPE=pgsql
SERVER_STORAGE_URL=postgresql+asyncpg://user:password@host:5432/grok2api
```

> 💡 提示：使用 Internal Database URL 可以获得更快的连接速度

### 方案 2：使用外部 PostgreSQL

如果你有自己的 PostgreSQL 数据库（如 Supabase、Neon 等）：

```bash
SERVER_STORAGE_TYPE=pgsql
SERVER_STORAGE_URL=postgresql+asyncpg://user:password@host:5432/dbname
```

**免费 PostgreSQL 服务推荐：**
- [Supabase](https://supabase.com/) - 500 MB 免费
- [Neon](https://neon.tech/) - 3 GB 免费
- [ElephantSQL](https://www.elephantsql.com/) - 20 MB 免费

### 方案 3：使用 Redis

如果你有 Redis 服务：

```bash
SERVER_STORAGE_TYPE=redis
SERVER_STORAGE_URL=redis://user:password@host:6379/0
```

**免费 Redis 服务推荐：**
- [Upstash](https://upstash.com/) - 10,000 命令/天免费
- [Redis Cloud](https://redis.com/try-free/) - 30 MB 免费

### 方案 4：使用本地存储（不推荐）

如果只是测试，可以使用本地存储（会丢失数据）：

```bash
SERVER_STORAGE_TYPE=local
SERVER_STORAGE_URL=
```

---

## 📱 手机访问配置

### 1. 获取访问地址

部署成功后，你会获得一个 HTTPS 域名：
```
https://grok2api-xxxx.onrender.com
```

### 2. 手机浏览器访问

**方式 1：直接访问**
- 在手机浏览器中输入域名
- 访问管理面板：`https://grok2api-xxxx.onrender.com/admin`

**方式 2：扫码访问**
1. 在电脑浏览器访问：`https://grok2api-xxxx.onrender.com/admin`
2. 点击页面右上角的 📱 按钮
3. 使用手机扫描二维码

### 3. 支持的手机浏览器

- ✅ Safari (iOS)
- ✅ Chrome (Android/iOS)
- ✅ Firefox (Android/iOS)
- ✅ Edge (Android/iOS)
- ✅ 微信内置浏览器
- ✅ 其他现代浏览器

---

## 🔧 管理面板使用

### 访问管理面板

```
https://grok2api-xxxx.onrender.com/admin
```

**默认密码：** `grok2api`

> ⚠️ 首次登录后请立即修改密码！

### 添加 Token

1. 登录管理面板
2. 进入 **Token 管理**
3. 点击 **添加 Token**
4. 输入你的 Grok Token
5. 选择 Token 类型（Basic/Super）
6. 点击保存

### 功能说明

- **Token 管理**：添加、删除、刷新 Token
- **图片管理**：查看、筛选、导出生成的图片
- **配置管理**：在线修改系统配置
- **缓存管理**：查看和清理媒体缓存

---

## 🔌 API 使用

### 基础配置

**API Base URL:**
```
https://grok2api-xxxx.onrender.com/v1
```

**API Key:**
在管理面板的 **配置管理** 中查看或修改。

### 示例：对话接口

```bash
curl https://grok2api-xxxx.onrender.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "grok-4",
    "messages": [{"role":"user","content":"你好"}]
  }'
```

### 示例：图片生成

```bash
curl https://grok2api-xxxx.onrender.com/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "grok-imagine-1.0",
    "prompt": "a beautiful sunset",
    "n": 1,
    "size": "1024x1024"
  }'
```

---

## ⚙️ 高级配置

### 自定义域名

1. 在 Render Dashboard 进入你的 Web Service
2. 点击 **Settings** → **Custom Domain**
3. 添加你的域名（如 `api.yourdomain.com`）
4. 按照提示配置 DNS 记录

### 环境变量完整列表

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `LOG_LEVEL` | `INFO` | 日志级别（DEBUG/INFO/WARNING/ERROR） |
| `LOG_FILE_ENABLED` | `true` | 是否启用文件日志 |
| `DATA_DIR` | `./data` | 数据目录 |
| `SERVER_HOST` | `0.0.0.0` | 服务监听地址 |
| `SERVER_PORT` | `8000` | 服务端口 |
| `SERVER_WORKERS` | `1` | Worker 数量 |
| `SERVER_STORAGE_TYPE` | `local` | 存储类型（local/redis/mysql/pgsql） |
| `SERVER_STORAGE_URL` | `` | 存储连接串 |

### 性能优化

**启用多 Worker（付费版）：**
```bash
SERVER_WORKERS=2
```

> ⚠️ 免费版只支持单 Worker

---

## 🐛 常见问题

### 1. 服务休眠问题

**问题：** 15 分钟无访问后服务休眠，首次访问需要 30-60 秒唤醒。

**解决方案：**
- 使用 [UptimeRobot](https://uptimerobot.com/) 等服务定期 ping 你的服务
- 升级到付费版（不会休眠）
- 或者使用 Railway（免费版不休眠）

### 2. 数据丢失问题

**问题：** 重启后 Token 和配置丢失。

**解决方案：**
- 配置外部数据库（PostgreSQL/Redis）
- 参考上方 **持久化存储配置** 章节

### 3. Token 自动刷新失败

**问题：** Token 刷新调度器不工作。

**解决方案：**
- 检查环境变量 `token.auto_refresh` 是否为 `true`
- 查看日志确认调度器是否启动
- 如果使用 Redis，确保多实例不会重复刷新

### 4. 手机访问慢

**问题：** 手机访问速度慢。

**解决方案：**
- 选择离你最近的 Region（Singapore 适合亚洲用户）
- 检查网络连接
- 首次访问需要唤醒服务（30-60 秒）

### 5. 图片无法显示

**问题：** 生成的图片无法显示。

**解决方案：**
- 检查图片存储路径是否正确
- 如果使用外部存储，确保配置正确
- 查看日志确认图片是否成功保存

---

## 📊 监控和日志

### 查看日志

1. 在 Render Dashboard 进入你的 Web Service
2. 点击 **Logs** 标签
3. 实时查看应用日志

### 监控指标

在 **Metrics** 标签可以查看：
- CPU 使用率
- 内存使用率
- 请求数量
- 响应时间

---

## 🔄 更新部署

### 自动部署

Render 默认启用自动部署，当你推送代码到 GitHub 时会自动重新部署。

### 手动部署

1. 在 Render Dashboard 进入你的 Web Service
2. 点击 **Manual Deploy** → **Deploy latest commit**

### 回滚版本

1. 点击 **Events** 标签
2. 找到之前的部署记录
3. 点击 **Rollback to this version**

---

## 💰 费用说明

### 免费版限制

- ✅ 750 小时/月（约 31 天）
- ✅ 512 MB RAM
- ✅ 0.1 CPU
- ⚠️ 15 分钟无访问会休眠
- ⚠️ 重启会丢失数据

### 付费版优势

**Starter ($7/月):**
- ✅ 不会休眠
- ✅ 更多资源
- ✅ 更快的构建速度
- ✅ 支持多 Worker

---

## 🆘 获取帮助

- **项目文档**: [README.md](./readme.md)
- **GitHub Issues**: [提交问题](https://github.com/chenyme/grok2api/issues)
- **Render 文档**: [Render Docs](https://render.com/docs)

---

## ✅ 部署检查清单

- [ ] 注册 Render 账号
- [ ] 连接 GitHub 仓库
- [ ] 配置环境变量
- [ ] 配置外部数据库（推荐）
- [ ] 部署成功并获得域名
- [ ] 访问管理面板
- [ ] 修改默认密码
- [ ] 添加 Grok Token
- [ ] 测试 API 接口
- [ ] 手机浏览器访问测试
- [ ] 配置 UptimeRobot（可选）

---

**祝你部署顺利！** 🎉
