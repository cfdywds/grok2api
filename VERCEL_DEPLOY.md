# Vercel 部署指南

本文档详细说明如何将 Grok2API 部署到 Vercel 平台。

## 快速开始

### 一键部署

点击下面的按钮直接部署（使用 navy 分支）：

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/cfdywds/grok2api/tree/navy&project-name=grok2api&repository-name=grok2api)

## 环境变量配置

### 必需的环境变量

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_FILE_ENABLED` | `false` | 必须关闭文件日志 |
| `DATA_DIR` | `/tmp/data` | 数据目录（Vercel 临时目录） |
| `SERVER_STORAGE_TYPE` | `local` 或 `pgsql` | 存储类型 |
| `SERVER_STORAGE_URL` | 见下文 | 数据库连接字符串 |

### 存储配置方案

#### 方案 1：本地存储（不推荐，数据不持久）

```env
SERVER_STORAGE_TYPE=local
SERVER_STORAGE_URL=
```

**注意：** 每次部署或冷启动后数据会丢失。

#### 方案 2：Vercel Postgres（推荐）

1. 在 Vercel 项目中创建 Postgres 数据库
2. 获取连接字符串
3. 配置环境变量：

```env
SERVER_STORAGE_TYPE=pgsql
SERVER_STORAGE_URL=postgresql+asyncpg://user:password@host:5432/database
```

**注意：** 将 `postgresql://` 改为 `postgresql+asyncpg://`

#### 方案 3：Supabase（推荐，免费额度更大）

1. 访问 https://supabase.com 创建项目
2. 获取数据库连接字符串
3. 配置环境变量：

```env
SERVER_STORAGE_TYPE=pgsql
SERVER_STORAGE_URL=postgresql+asyncpg://postgres:[password]@[host]:5432/postgres
```

#### 方案 4：其他数据库

**MySQL (PlanetScale):**
```env
SERVER_STORAGE_TYPE=mysql
SERVER_STORAGE_URL=mysql+aiomysql://user:password@host:3306/database
```

**Redis (Upstash):**
```env
SERVER_STORAGE_TYPE=redis
SERVER_STORAGE_URL=redis://default:password@host:port
```

## 手动部署步骤

### 1. 导入项目

1. 访问 https://vercel.com/new
2. 选择 GitHub 仓库：`cfdywds/grok2api`
3. 选择分支：`navy`

### 2. 配置项目

- **Framework Preset**: FastAPI（自动检测）
- **Build Command**: `pip install -r requirements.txt`（已在 vercel.json 中配置）
- **Output Directory**: 默认
- **Install Command**: `pip install --upgrade pip`（已在 vercel.json 中配置）

### 3. 设置环境变量

在 "Environment Variables" 部分添加上述环境变量。

### 4. 部署

点击 "Deploy" 按钮，等待构建完成。

## 部署后配置

### 访问管理面板

部署成功后，访问：
```
https://your-app.vercel.app/admin
```

默认密码：`grok2api`

### 添加 Grok Token

1. 登录管理面板
2. 进入 "Token 管理"
3. 添加你的 Grok Token
4. 配置 Token 池

### 测试 API

```bash
curl https://your-app.vercel.app/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "grok-4",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## 常见问题

### Q1: 构建失败 - Python 版本错误

**解决方案：** 项目已配置使用 Python 3.12，Vercel 支持此版本。

### Q2: 依赖安装失败

**解决方案：** 项目已添加 `requirements.txt`，使用传统 pip 安装。

### Q3: 数据丢失

**原因：** 使用本地存储（`SERVER_STORAGE_TYPE=local`）

**解决方案：** 配置数据库（Vercel Postgres 或 Supabase）

### Q4: 函数超时

**原因：** Vercel 免费版函数执行时间限制 10 秒

**解决方案：**
- 升级到 Vercel Pro（60 秒限制）
- 或使用其他部署平台

### Q5: 冷启动慢

**原因：** Vercel 无服务器函数冷启动

**解决方案：**
- 升级到 Vercel Pro（保持函数热启动）
- 使用定时任务保持活跃（如 cron-job.org）

### Q6: 图片生成失败

**原因：** 某些依赖（如 opencv-python）在 Vercel 环境中可能有限制

**解决方案：**
- 使用 opencv-python-headless 替代
- 或考虑使用 Docker 部署（Railway, Render）

## 性能优化

### 1. 使用 CDN

Vercel 自动提供全球 CDN，无需额外配置。

### 2. 配置缓存

在 `vercel.json` 中配置静态资源缓存：

```json
{
  "headers": [
    {
      "source": "/static/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=31536000, immutable"
        }
      ]
    }
  ]
}
```

### 3. 使用环境变量

敏感信息（如 API 密钥）应使用环境变量，不要硬编码在代码中。

## 监控和日志

### 查看部署日志

1. 进入 Vercel 项目
2. 点击 "Deployments"
3. 选择具体的部署
4. 查看 "Build Logs" 和 "Function Logs"

### 实时日志

Vercel Pro 提供实时日志功能。

## 自动部署

### Git 集成

Vercel 已自动配置 Git 集成：
- 推送到 `navy` 分支会自动触发生产部署
- 推送到其他分支会创建预览部署

### 禁用自动部署

如果需要手动控制部署，在项目设置中：
1. 进入 "Git"
2. 取消勾选 "Automatic Deployments"

## 回滚部署

如果新部署有问题：
1. 进入 "Deployments"
2. 找到之前的稳定版本
3. 点击 "Promote to Production"

## 自定义域名

### 添加域名

1. 进入项目设置
2. 点击 "Domains"
3. 添加你的域名
4. 按照提示配置 DNS

### SSL 证书

Vercel 自动提供免费的 SSL 证书。

## 成本估算

### 免费版限制

- 100GB 带宽/月
- 100 小时函数执行时间/月
- 10 秒函数超时
- 无实时日志

### Pro 版（$20/月）

- 1TB 带宽/月
- 1000 小时函数执行时间/月
- 60 秒函数超时
- 实时日志
- 优先支持

## 替代方案

如果 Vercel 不满足需求，可以考虑：

1. **Railway** - 更适合长时间运行的服务
2. **Render** - 提供免费的 Web Service
3. **Fly.io** - 全球边缘部署
4. **自建服务器** - 使用 Docker Compose

## 技术支持

- GitHub Issues: https://github.com/cfdywds/grok2api/issues
- Vercel 文档: https://vercel.com/docs

## 更新日志

- 2025-02-12: 初始版本，配置 navy 分支部署
- 2025-02-12: 添加 requirements.txt 支持
- 2025-02-12: 优化 Python 版本兼容性
