# Vercel 部署检查清单

## ✅ 部署前检查

- [ ] 已通过一键部署链接创建项目
- [ ] 项目名称：grok2api
- [ ] 使用分支：navy
- [ ] 已登录 Vercel 账号

## 📋 环境变量配置（必做）

访问：https://vercel.com/dashboard → 你的项目 → Settings → Environment Variables

### 添加以下 5 个变量：

- [ ] `LOG_LEVEL` = `INFO`
- [ ] `LOG_FILE_ENABLED` = `false`
- [ ] `DATA_DIR` = `/tmp/data`
- [ ] `SERVER_STORAGE_TYPE` = `local`
- [ ] `SERVER_STORAGE_URL` = (留空)

**重要：** 每个变量都要勾选 ✅ Production

## 🔄 重新部署

- [ ] 进入 Deployments 标签
- [ ] 找到最新部署
- [ ] 点击 ⋯ → Redeploy
- [ ] 等待部署完成（2-5 分钟）

## ✅ 部署后验证

- [ ] 部署状态显示绿色 ✓
- [ ] 可以访问应用 URL
- [ ] 可以访问 /admin 管理面板
- [ ] 可以使用密码 `grok2api` 登录
- [ ] 管理面板功能正常

## 🎯 下一步（可选）

### 配置数据库（推荐）

如果需要数据持久化：

#### 选项 A：Vercel Postgres
- [ ] Storage → Create Database → Postgres
- [ ] 复制连接字符串
- [ ] 修改 `SERVER_STORAGE_TYPE` = `pgsql`
- [ ] 修改 `SERVER_STORAGE_URL` = `postgresql+asyncpg://...`
- [ ] 重新部署

#### 选项 B：Supabase
- [ ] 访问 https://supabase.com 创建项目
- [ ] 获取连接字符串
- [ ] 修改 Vercel 环境变量
- [ ] 重新部署

### 添加 Grok Token

- [ ] 登录管理面板
- [ ] 进入 Token 管理
- [ ] 添加你的 Grok Token
- [ ] 测试 API 调用

### 修改默认密码

- [ ] 登录管理面板
- [ ] 进入配置管理
- [ ] 修改 `app.app_key` 配置项
- [ ] 保存并重新登录

## 🆘 遇到问题？

### 部署失败
1. 查看 Deployments → 点击部署 → Build Logs
2. 检查环境变量是否都已添加
3. 确认 Environment 选择了 Production

### 管理面板打不开
1. 检查 URL：`/admin` 而不是 `/admin/`
2. 查看浏览器控制台错误
3. 检查部署日志

### 数据丢失
- 原因：使用本地存储（`SERVER_STORAGE_TYPE=local`）
- 解决：配置数据库（见上面的数据库配置）

## 📚 参考文档

- `docs/VERCEL_QUICKSTART.md` - 图文教程
- `docs/VERCEL_ENV_SETUP.md` - 详细配置说明
- `VERCEL_DEPLOY.md` - 完整部署指南
- `README.md` - 项目说明

## 🎉 完成标志

当以下所有项都完成时，部署就成功了：

- ✅ 环境变量已配置
- ✅ 部署状态为成功
- ✅ 可以访问应用
- ✅ 可以登录管理面板
- ✅ 可以添加 Token
- ✅ API 可以正常调用

---

**提示：** 如果使用本地存储，每次部署后数据会丢失。建议配置数据库。

**下次部署：** 推送代码到 navy 分支会自动触发部署。
