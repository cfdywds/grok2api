# Zeabur 部署指南

本文档详细说明如何将 Grok2API 部署到 Zeabur 平台。

## 🌟 为什么选择 Zeabur？

Zeabur 是**最适合国内用户**的部署平台！

### 与其他平台对比

| 特性 | Zeabur | Railway | Render |
|------|--------|---------|--------|
| **免费额度** | ✅ $5/月（持续） | ⚠️ $5（一次性） | ✅ 750h/月 |
| **需要信用卡** | ✅ **不需要** | ❌ 需要 | ✅ 不需要 |
| **休眠问题** | ✅ **不休眠** | ✅ 不休眠 | ❌ 15分钟休眠 |
| **国内访问** | ✅ **快（香港）** | ❌ 慢（美国） | ❌ 慢（美国） |
| **中文支持** | ✅ **完整** | ❌ 无 | ❌ 无 |
| **长期免费** | ✅ **是** | ❌ 否 | ✅ 是（但休眠） |
| **推荐指数** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

### Zeabur 的优势

**🇨🇳 国内友好：**
- ✅ 香港节点，ping < 50ms
- ✅ 中文界面和文档
- ✅ 支持支付宝（如需付费）

**💰 真正免费：**
- ✅ 每月 $5 免费额度（持续，不是一次性）
- ✅ 无需信用卡验证
- ✅ 轻度使用完全免费

**🚀 功能完整：**
- ✅ 支持 Docker 部署
- ✅ 不会休眠
- ✅ 自动 HTTPS
- ✅ 自定义域名
- ✅ 环境变量管理

**📱 手机访问：**
- ✅ 完美支持手机浏览器
- ✅ 响应式设计
- ✅ 可添加到主屏幕

---

## 📋 部署前准备

### 1. 注册 Zeabur 账号

访问 [Zeabur](https://zeabur.com/) 并注册账号。

**注册方式：**
- GitHub 登录（推荐）
- Google 登录
- 邮箱注册

> 💡 提示：使用 GitHub 登录可以直接连接仓库，更方便！

**重要：无需绑定信用卡！**

### 2. 准备 GitHub 仓库

确保你的项目已经推送到 GitHub 仓库。

### 3. 准备 Grok Token

- 登录 [X.com](https://x.com/)
- 获取你的 Grok Token（稍后在管理面板中添加）

### 4. 注册 Supabase（推荐）

为了数据持久化，建议配置 Supabase 数据库：

1. 访问 [Supabase](https://supabase.com/)
2. 使用 GitHub 登录
3. 创建新项目（选择新加坡或东京节点）
4. 获取数据库连接串

---

## 🚀 快速部署

### 步骤 1：创建项目

1. 登录 [Zeabur Dashboard](https://dash.zeabur.com/)
2. 点击 **New Project**
3. 输入项目名称（如 `grok2api`）
4. 选择区域：**Hong Kong**（推荐）

### 步骤 2：部署服务

1. 在项目页面点击 **Create Service**
2. 选择 **Deploy from GitHub**
3. 如果是首次使用，需要授权 Zeabur 访问你的 GitHub
4. 在仓库列表中找到 `grok2api`
5. 点击仓库名称

Zeabur 会自动检测到 Dockerfile 并开始部署。

### 步骤 3：配置环境变量

在服务部署过程中，点击服务卡片，进入 **Variables** 标签。

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

# 存储配置（先使用本地存储）
SERVER_STORAGE_TYPE=local
SERVER_STORAGE_URL=
```

点击 **Save** 保存环境变量。

### 步骤 4：生成公网域名

1. 在服务页面找到 **Networking** 部分
2. 点击 **Generate Domain**
3. Zeabur 会自动生成一个域名，如：
   ```
   https://grok2api-xxx.zeabur.app
   ```

### 步骤 5：等待部署完成

- 在 **Deployments** 标签查看部署进度
- 首次部署约需 3-5 分钟
- 部署成功后状态显示为 **Running**

---

## 🗄️ 配置数据持久化（推荐）

### 为什么需要数据持久化？

Zeabur 的容器重启后会丢失本地数据，因此需要外部数据库。

### 使用 Supabase PostgreSQL（推荐）

#### 1. 创建 Supabase 项目

1. 登录 [Supabase Dashboard](https://supabase.com/dashboard)
2. 点击 **New Project**
3. 填写项目信息：
   - **Name**: `grok2api`
   - **Database Password**: 设置一个强密码（记住它！）
   - **Region**: 选择 **Southeast Asia (Singapore)** 或 **Northeast Asia (Tokyo)**
   - **Pricing Plan**: **Free**
4. 点击 **Create new project**
5. 等待创建完成（约 2-3 分钟）

#### 2. 获取数据库连接串

1. 在 Supabase 项目页面，点击左侧 **Settings** (⚙️)
2. 选择 **Database**
3. 找到 **Connection string** → **URI**
4. 复制连接串，格式如下：
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxx.supabase.co:5432/postgres
   ```

#### 3. 转换为 asyncpg 格式

将连接串中的 `postgresql://` 改为 `postgresql+asyncpg://`：

```
postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.xxx.supabase.co:5432/postgres
```

> ⚠️ 注意：将 `[YOUR-PASSWORD]` 替换为你设置的密码

#### 4. 在 Zeabur 配置环境变量

回到 Zeabur 服务页面，进入 **Variables** 标签，修改：

```bash
SERVER_STORAGE_TYPE=pgsql
SERVER_STORAGE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.xxx.supabase.co:5432/postgres
```

点击 **Save**，服务会自动重启。

---

## 📱 手机访问配置

### 1. 获取访问地址

部署成功后，你会获得一个 HTTPS 域名：
```
https://grok2api-xxx.zeabur.app
```

### 2. 手机浏览器访问

**方式 1：直接访问**

在手机浏览器中输入：
```
https://grok2api-xxx.zeabur.app/admin
```

**方式 2：扫码访问（推荐）**

1. 在电脑浏览器访问管理面板
2. 点击页面右上角的 📱 按钮
3. 使用手机扫描二维码
4. 自动跳转到管理面板

### 3. 添加到主屏幕

**iOS (Safari):**
1. 在 Safari 中打开管理面板
2. 点击底部的分享按钮
3. 选择"添加到主屏幕"
4. 像 App 一样使用

**Android (Chrome):**
1. 在 Chrome 中打开管理面板
2. 点击右上角菜单
3. 选择"添加到主屏幕"
4. 像 App 一样使用

### 4. 支持的手机浏览器

- ✅ Safari (iOS)
- ✅ Chrome (Android/iOS)
- ✅ Firefox (Android/iOS)
- ✅ Edge (Android/iOS)
- ✅ 微信内置浏览器
- ✅ QQ 浏览器
- ✅ UC 浏览器

---

## 🔧 管理面板使用

### 访问管理面板

```
https://your-domain.zeabur.app/admin
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
https://your-domain.zeabur.app/v1
```

**API Key:**

在管理面板的 **配置管理** 中查看或修改 `app.api_key`。

### 示例：对话接口

```bash
curl https://your-domain.zeabur.app/v1/chat/completions \
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
curl https://your-domain.zeabur.app/v1/chat/completions \
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
curl https://your-domain.zeabur.app/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "grok-imagine-1.0",
    "prompt": "a beautiful sunset over the ocean",
    "n": 1,
    "size": "1024x1024"
  }'
```

### 在第三方应用中使用

**ChatGPT Next Web:**
```
API 地址: https://your-domain.zeabur.app/v1
API Key: YOUR_API_KEY
模型: grok-4
```

**OpenCat (iOS):**
```
API 地址: https://your-domain.zeabur.app/v1
API Key: YOUR_API_KEY
模型: grok-4
```

**ChatBox:**
```
API 地址: https://your-domain.zeabur.app/v1
API Key: YOUR_API_KEY
模型: grok-4
```

---

## ⚙️ 高级配置

### 自定义域名

1. 在 Zeabur 服务页面进入 **Networking**
2. 点击 **Custom Domain**
3. 输入你的域名（如 `api.yourdomain.com`）
4. 按照提示配置 DNS 记录：
   - 类型：CNAME
   - 名称：api
   - 值：your-service.zeabur.app
5. 等待 DNS 生效（通常 5-10 分钟）

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

---

## 💰 费用说明

### 免费额度

**Zeabur Developer Plan:**
- ✅ **每月 $5 免费额度**（持续，不是一次性）
- ✅ 每月自动重置
- ✅ 无需信用卡
- ✅ 支持多个项目

### 用量估算

**Grok2API 资源消耗：**
- CPU: 0.1-0.2 vCPU
- 内存: 256-512 MB
- 网络: 取决于使用量

**预计费用：**

**轻度使用（<1000 请求/天）：**
- 预计消耗：$2-3/月
- 免费额度：$5/月
- **实际费用：$0/月** ✅

**中度使用（1000-5000 请求/天）：**
- 预计消耗：$4-6/月
- 免费额度：$5/月
- **实际费用：$0-1/月** ✅

**重度使用（>5000 请求/天）：**
- 预计消耗：$8-15/月
- 免费额度：$5/月
- **实际费用：$3-10/月** ⚠️

### 节省费用技巧

1. **使用单 Worker**
   ```bash
   SERVER_WORKERS=1
   ```

2. **降低日志级别**
   ```bash
   LOG_LEVEL=WARNING
   ```

3. **使用外部数据库**
   - Supabase 500 MB 免费
   - 不占用 Zeabur 额度

4. **设置用量上限**
   - 在 Zeabur 设置中配置
   - 防止意外超支

### 查看用量

1. 在 Zeabur Dashboard 点击项目
2. 查看 **Usage** 标签
3. 实时监控资源消耗

---

## 🐛 常见问题

### Q1: 部署失败怎么办？

**A:** 检查以下几点：
1. 查看 **Deployments** 标签的日志
2. 确保 Dockerfile 正确
3. 确保所有依赖都在 `pyproject.toml` 中
4. 尝试重新部署：点击 **Redeploy**

### Q2: 无法访问服务

**A:** 检查以下几点：
1. 确保已生成公网域名（Networking → Generate Domain）
2. 检查 `SERVER_HOST` 是否为 `0.0.0.0`
3. 检查 `SERVER_PORT` 是否为 `8000`
4. 查看日志确认服务是否正常启动

### Q3: 数据丢失

**A:**
- 如果使用本地存储，重启会丢失数据
- 配置外部数据库（Supabase）解决
- 参考上方 **配置数据持久化** 章节

### Q4: Token 自动刷新失败

**A:**
- 检查日志确认调度器是否启动
- 查看 Token 管理页面的刷新记录
- 如果使用 Redis，确保连接正常
- 手动触发刷新测试

### Q5: 超出免费额度

**A:**
- 在 Zeabur Dashboard 查看用量
- 优化资源使用（减少 Worker、降低日志级别）
- 升级到付费计划
- 或者暂停服务等待下月重置

### Q6: 国内访问慢

**A:**
- Zeabur 香港节点，国内访问应该很快
- 如果慢，检查网络连接
- 尝试使用不同的网络（移动/联通/电信）
- 或者使用 CDN 加速

### Q7: 图片无法显示

**A:**
- 检查图片存储路径
- 如果使用外部存储，确保配置正确
- 查看日志确认图片是否成功保存
- 检查静态文件服务是否正常

### Q8: WebSocket 连接失败

**A:**
- Zeabur 支持 WebSocket，无需特殊配置
- 检查防火墙设置
- 查看浏览器控制台的错误信息
- 确保使用 HTTPS（不是 HTTP）

---

## 📊 监控和日志

### 查看日志

**实时日志：**
1. 在 Zeabur 服务页面点击 **Logs** 标签
2. 查看实时日志输出
3. 可以搜索和过滤日志

**历史日志：**
- Zeabur 保留最近的日志记录
- 可以下载日志文件

### 监控指标

在 **Metrics** 标签可以查看：
- CPU 使用率
- 内存使用率
- 网络流量
- 请求数量

### 用量统计

在 **Usage** 标签可以查看：
- 本月已使用额度
- 剩余免费额度
- 预计费用

---

## 🔄 更新部署

### 自动部署

Zeabur 默认启用自动部署：
1. 推送代码到 GitHub
2. Zeabur 自动检测并重新部署
3. 无需手动操作

### 禁用自动部署

如果你想手动控制部署：
1. 进入服务 **Settings**
2. 找到 **Git** 部分
3. 关闭 **Auto Deploy**

### 手动部署

1. 在 Zeabur 服务页面点击 **Redeploy**
2. 选择要部署的分支或提交
3. 等待部署完成

### 回滚版本

1. 进入 **Deployments** 标签
2. 找到之前的成功部署
3. 点击 **Redeploy**

---

## 🆘 获取帮助

### 官方资源

- **Zeabur 文档**: [docs.zeabur.com](https://docs.zeabur.com/)
- **Zeabur Discord**: [discord.gg/zeabur](https://discord.gg/zeabur)
- **Zeabur GitHub**: [github.com/zeabur](https://github.com/zeabur)

### 项目资源

- **项目文档**: [readme.md](./readme.md)
- **GitHub Issues**: [提交问题](https://github.com/chenyme/grok2api/issues)
- **更新日志**: [CHANGELOG.md](./CHANGELOG.md)

---

## ✅ 部署检查清单

### 部署前

- [ ] 注册 Zeabur 账号（无需信用卡）
- [ ] 注册 Supabase 账号
- [ ] 创建 Supabase 项目（选择亚洲节点）
- [ ] 准备 GitHub 仓库
- [ ] 准备 Grok Token

### 部署中

- [ ] 在 Zeabur 创建项目
- [ ] 从 GitHub 部署服务
- [ ] 配置环境变量
- [ ] 配置 Supabase 数据库连接
- [ ] 生成公网域名
- [ ] 等待部署完成

### 部署后

- [ ] 访问管理面板
- [ ] 修改默认密码
- [ ] 添加 Grok Token
- [ ] 测试 API 接口
- [ ] 手机浏览器访问测试
- [ ] 验证数据持久化（重启后数据不丢失）
- [ ] 配置自定义域名（可选）

---

## 🎉 部署成功！

恭喜你成功部署 Grok2API 到 Zeabur！

**接下来你可以：**
- 📱 在手机浏览器访问管理面板
- 🔌 在第三方应用中使用 API
- 🖼️ 生成和管理图片
- ⚙️ 自定义配置和域名

**享受你的 Grok2API 服务吧！** 🚀

---

## 📝 附录

### A. 环境变量模板

复制以下内容到 Zeabur 的 Variables 中：

```bash
# 基础配置
TZ=Asia/Shanghai
LOG_LEVEL=INFO
LOG_FILE_ENABLED=true

# 服务配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_WORKERS=1

# 存储配置（使用 Supabase）
SERVER_STORAGE_TYPE=pgsql
SERVER_STORAGE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.xxx.supabase.co:5432/postgres
```

### B. 数据库连接串格式

**PostgreSQL (Supabase):**
```
postgresql+asyncpg://postgres:password@db.xxx.supabase.co:5432/postgres
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

**查看服务状态:**
```bash
# 在 Zeabur Logs 标签查看
```

**重启服务:**
```bash
# 在 Zeabur 服务页面点击 Redeploy
```

**查看用量:**
```bash
# 在 Zeabur Usage 标签查看
```

---

**祝你部署顺利！** 🎉
