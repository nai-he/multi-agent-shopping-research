@echo off
echo ========================================
echo Multi-Agent 购物调研系统 - Web 启动器
echo ========================================
echo.

cd /d "%~dp0"

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 检查依赖
echo [1/3] 检查依赖...
pip show Flask >nul 2>&1
if errorlevel 1 (
    echo [提示] 正在安装依赖...
    pip install -r requirements.txt
)

REM 检查 .env 文件
if not exist .env (
    echo [警告] 未找到 .env 文件，请先配置 API 密钥
    echo [提示] 可以复制 .env.example 为 .env 并修改
    pause
    exit /b 1
)

echo [2/3] 准备就绪
echo [3/3] 启动应用...
echo.
echo ========================================
echo 访问地址: http://localhost:5000
echo 按 Ctrl+C 停止服务
echo ========================================
echo.

python app.py

pause
