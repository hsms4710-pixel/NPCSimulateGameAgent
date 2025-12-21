#!/usr/bin/env python3
"""
NPC模拟器启动脚本
运行命令: python run_simulator.py
"""

import sys
import subprocess
import os
from pathlib import Path

def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 8):
        print("错误: 需要Python 3.8或更高版本")
        print(f"当前版本: {sys.version}")
        return False
    return True

def install_dependencies():
    """安装依赖"""
    print("正在安装依赖...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"依赖安装失败: {e}")
        return False

def check_tkinter():
    """检查tkinter是否可用"""
    try:
        import tkinter
        tkinter.Tk().destroy()  # 测试是否能创建窗口
        return True
    except ImportError:
        print("错误: tkinter不可用")
        print("在Ubuntu/Debian上: sudo apt-get install python3-tk")
        print("在macOS上: tkinter通常已预装")
        print("在Windows上: tkinter通常已预装")
        return False
    except Exception as e:
        print(f"tkinter测试失败: {e}")
        return False

def main():
    """主函数"""
    print("艾伦谷 NPC 行为模拟器启动器")
    print("=" * 40)

    # 检查Python版本
    if not check_python_version():
        sys.exit(1)

    # 检查tkinter
    if not check_tkinter():
        sys.exit(1)

    # 检查依赖
    try:
        import requests
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        print("缺少必要的依赖，正在安装...")
        if not install_dependencies():
            sys.exit(1)

    # 启动主程序
    print("正在启动模拟器...")
    try:
        from main import main as app_main
        app_main()
    except KeyboardInterrupt:
        print("\n程序已停止")
    except Exception as e:
        print(f"启动失败: {e}")
        print("请检查日志文件 'npc_simulator.log' 获取详细信息")
        sys.exit(1)

if __name__ == "__main__":
    main()
