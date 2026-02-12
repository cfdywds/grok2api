@echo off
chcp 65001 >nul
echo ========================================
echo   Grok2API 启动脚本
echo ========================================
echo.

echo [1/3] 检查虚拟环境...
if not exist ".venv\Scripts\python.exe" (
    echo 错误: 虚拟环境不存在，请先运行 uv sync
    pause
    exit /b 1
)

echo [2/3] 获取本机IP地址...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set IP=%%a
    goto :found
)
:found
set IP=%IP:~1%
echo 本机IP: %IP%

echo [3/3] 启动服务...
echo.
echo ========================================
echo   服务已启动
echo ========================================
echo   本地访问: http://localhost:8000
echo   局域网访问: http://%IP%:8000
echo   
echo   管理页面:
echo   - 图片管理: http://localhost:8000/admin/gallery
echo   - Token管理: http://localhost:8000/admin/token
echo   - 配置管理: http://localhost:8000/admin/config
echo   
echo   手机访问: 点击页面右上角 📱 按钮扫码
echo ========================================
echo.
echo 按 Ctrl+C 停止服务
echo.

.venv\Scripts\python.exe main.py
