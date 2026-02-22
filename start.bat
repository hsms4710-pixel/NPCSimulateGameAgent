@echo off
chcp 65001 >nul
title MRAG Enhanced NPC Simulator

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║      MRAG Enhanced NPC Simulator             ║
echo  ║      多层记忆增强型 NPC 行为模拟系统          ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: 检查虚拟环境
if exist ".venv\Scripts\activate.bat" (
    echo  [*] 激活虚拟环境...
    call .venv\Scripts\activate.bat
) else (
    echo  [*] 使用系统 Python
)

:: 检查关键依赖
python -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo  [*] 正在安装依赖，请稍候...
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo  [错误] 依赖安装失败，请手动运行: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo  [OK] 依赖安装完成
)

:: 检查 API 配置
if exist "api_config.json" (
    echo  [OK] 检测到 API 配置文件
) else (
    echo  [警告] 未找到 api_config.json，LLM 功能将不可用
    echo         请在游戏界面 "设置" 中配置 API Key
)

:: 自动选择可用端口（优先 8080，备选 8888 9000）
set PORT=8080
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    set PORT=8888
    netstat -ano | findstr ":8888 " | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        set PORT=9000
    )
)

echo.
echo  [*] 正在启动服务器（端口 %PORT%）...
echo  [*] 访问地址: http://localhost:%PORT%
echo  [*] 按 Ctrl+C 停止服务
echo.

:: 延迟2秒后自动打开浏览器
start "" /b cmd /c "timeout /t 2 >nul && start http://localhost:%PORT%"

:: 启动服务
python -m uvicorn backend.api_server:app --host 127.0.0.1 --port %PORT% --reload

pause
