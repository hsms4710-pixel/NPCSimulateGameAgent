@echo off
echo ========================================
echo    艾伦谷 NPC 行为模拟器演示
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

echo 启动模拟器...
python demo.py

if errorlevel 1 (
    echo.
    echo 程序异常退出
    echo 请检查错误信息
)

echo.
echo 按任意键退出...
pause >nul
