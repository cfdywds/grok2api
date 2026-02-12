#!/bin/bash

# Vercel 部署诊断脚本

echo "==================================="
echo "Vercel 部署诊断工具"
echo "==================================="
echo ""

# 检查 Git 状态
echo "📋 检查 Git 状态..."
git status --short
echo ""

# 检查最近的提交
echo "📝 最近的提交:"
git log --oneline -5
echo ""

# 检查分支
echo "🌿 当前分支:"
git branch --show-current
echo ""

# 检查远程仓库
echo "🔗 远程仓库:"
git remote -v
echo ""

# 检查 vercel.json
echo "⚙️  检查 vercel.json 配置:"
if [ -f "vercel.json" ]; then
    echo "✅ vercel.json 存在"
    echo "内容预览:"
    head -20 vercel.json
else
    echo "❌ vercel.json 不存在"
fi
echo ""

# 检查 requirements.txt
echo "📦 检查 requirements.txt:"
if [ -f "requirements.txt" ]; then
    echo "✅ requirements.txt 存在"
    echo "依赖包数量: $(wc -l < requirements.txt)"
else
    echo "❌ requirements.txt 不存在"
fi
echo ""

# 检查 pyproject.toml
echo "🐍 检查 Python 配置:"
if [ -f "pyproject.toml" ]; then
    echo "✅ pyproject.toml 存在"
    grep "requires-python" pyproject.toml
else
    echo "❌ pyproject.toml 不存在"
fi
echo ""

echo "==================================="
echo "诊断完成"
echo "==================================="
echo ""
echo "下一步操作:"
echo "1. 确保已推送到远程: git push origin navy"
echo "2. 访问 Vercel Dashboard 查看部署状态"
echo "3. 如果部署失败，查看 Build Logs"
echo ""
