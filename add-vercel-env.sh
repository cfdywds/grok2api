#!/bin/bash

# Vercel 环境变量配置脚本
# 使用方法：先安装 vercel CLI，然后运行此脚本

echo "正在添加 Vercel 环境变量..."

# 添加环境变量到 Production 环境
vercel env add LOG_LEVEL production <<< "INFO"
vercel env add LOG_FILE_ENABLED production <<< "false"
vercel env add DATA_DIR production <<< "/tmp/data"
vercel env add SERVER_STORAGE_TYPE production <<< "local"
vercel env add SERVER_STORAGE_URL production <<< ""

echo "环境变量添加完成！"
echo "现在运行 'vercel --prod' 重新部署"
