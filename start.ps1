# Grok2API PowerShell 启动脚本
# 适用于 PowerShell 7.x

# 设置控制台编码为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Grok2API 启动脚本 (PowerShell)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查虚拟环境
Write-Host "[1/3] 检查虚拟环境..." -ForegroundColor Yellow
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "错误: 虚拟环境不存在，请先运行 uv sync" -ForegroundColor Red
    Read-Host "按任意键退出"
    exit 1
}
Write-Host "✓ 虚拟环境存在" -ForegroundColor Green

# 获取本机 IP 地址
Write-Host "[2/3] 获取本机IP地址..." -ForegroundColor Yellow
$IP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.IPAddress -notlike "169.254.*" } | Select-Object -First 1).IPAddress
if ($IP) {
    Write-Host "✓ 本机IP: $IP" -ForegroundColor Green
} else {
    $IP = "localhost"
    Write-Host "⚠ 无法获取IP，使用 localhost" -ForegroundColor Yellow
}

# 启动服务
Write-Host "[3/3] 启动服务..." -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  服务已启动" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "  本地访问: http://localhost:8000" -ForegroundColor White
Write-Host "  局域网访问: http://${IP}:8000" -ForegroundColor White
Write-Host ""
Write-Host "  管理页面:" -ForegroundColor Cyan
Write-Host "  - 图片管理: http://localhost:8000/admin/gallery" -ForegroundColor White
Write-Host "  - Token管理: http://localhost:8000/admin/token" -ForegroundColor White
Write-Host "  - 配置管理: http://localhost:8000/admin/config" -ForegroundColor White
Write-Host ""
Write-Host "  手机访问: 点击页面右上角 📱 按钮扫码" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host ""

# 设置 Python 输出编码为 UTF-8
$env:PYTHONIOENCODING = "utf-8"

# 启动服务
& ".venv\Scripts\python.exe" main.py
