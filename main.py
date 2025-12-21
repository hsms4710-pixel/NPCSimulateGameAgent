#!/usr/bin/env python3
"""
艾伦谷 NPC 行为模拟器主程序
使用DeepSeek API驱动的智能NPC行为模拟
"""

import sys
import os
import logging
from pathlib import Path

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('npc_simulator.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # 设置第三方库日志级别
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

def check_dependencies():
    """检查依赖"""
    required_modules = [
        'tkinter',
        'requests',
        'json',
        'threading',
        'time',
        'datetime',
        'random',
        'typing'
    ]

    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)

    if missing_modules:
        print(f"缺少必要的模块: {', '.join(missing_modules)}")
        print("请运行: pip install -r requirements.txt")
        return False

    return True

def main():
    """主函数"""
    print("艾伦谷 NPC 行为模拟器")
    print("=" * 50)

    # 检查依赖
    if not check_dependencies():
        sys.exit(1)

    # 设置日志
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # 导入GUI模块
        from gui_interface import main as gui_main

        logger.info("启动NPC模拟器...")
        print("正在启动GUI界面...")

        # 启动GUI
        gui_main()

    except ImportError as e:
        logger.error(f"导入错误: {e}")
        print(f"导入错误: {e}")
        print("请确保所有文件都在正确的位置")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.info("用户中断程序")
        print("\n程序已停止")

    except Exception as e:
        logger.error(f"程序运行错误: {e}")
        print(f"程序运行错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
