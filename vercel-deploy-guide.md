# Vercel CLI 部署指南

## 1. 安装 Vercel CLI

```bash
npm install -g vercel
```

## 2. 登录 Vercel

```bash
vercel login
```

## 3. 部署项目

```bash
# 切换到 navy 分支
git checkout navy

# 部署到 Vercel
vercel --prod

# 或者指定分支
vercel --prod --branch navy
```

## 4. 设置环境变量

```bash
# 设置环境变量
vercel env add LOG_LEVEL production
vercel env add LOG_FILE_ENABLED production
vercel env add DATA_DIR production
vercel env add SERVER_STORAGE_TYPE production
vercel env add SERVER_STORAGE_URL production
```

## 5. 重新部署

```bash
vercel --prod
```
