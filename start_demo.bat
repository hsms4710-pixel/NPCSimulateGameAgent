@echo off
chcp 65001 >nul
echo ========================================
echo    艾伦谷 NPC 行为模拟器
echo    Ellen Valley NPC Simulator
echo ========================================
echo.

echo 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python
    echo 请安装Python 3.8或更高版本
    pause
    exit /b 1
)

echo.
echo 选择启动模式:
echo   1. Web界面 (推荐，自动打开浏览器)
echo   2. GUI界面 (Tkinter)
echo   3. 命令行模式
echo.
set /p mode=请输入选项 (1/2/3，默认1):

if "%mode%"=="" set mode=1

if "%mode%"=="1" (
    echo.
    echo 启动Web服务器...
    echo 访问地址: http://localhost:8000
    echo.
    start http://localhost:8000
    python run.py --web --port 8000
) else if "%mode%"=="2" (
    echo.
    echo 启动GUI界面...
    python run.py
) else if "%mode%"=="3" (
    echo.
    echo 启动命令行模式...
    python run.py --cli
) else (
    echo 无效选项，启动默认Web模式...
    start http://localhost:8000
    python run.py --web --port 8000
)

if errorlevel 1 (
    echo.
    echo 程序异常退出
    echo 请检查错误信息
)

echo.
echo 按任意键退出...
pause >nul
