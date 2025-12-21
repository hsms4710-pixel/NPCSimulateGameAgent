#!/usr/bin/env python3
"""
艾伦谷 NPC 模拟器演示
启动GUI界面展示NPC智能行为
"""

import sys
import os

def main():
    """主函数"""
    print("艾伦谷 NPC 行为模拟器演示")
    print("=" * 50)
    print("正在启动GUI界面...")
    print("如果窗口没有出现，请检查是否有GUI环境支持")
    print("按 Ctrl+C 退出程序")
    print()

    try:
        # 导入并启动GUI
        from gui_interface import main as gui_main
        gui_main()

    except ImportError as e:
        print(f"导入错误: {e}")
        print("请确保所有文件都在正确的位置")
        return 1

    except KeyboardInterrupt:
        print("\n程序已停止")
        return 0

    except Exception as e:
        print(f"启动失败: {e}")
        print("请检查日志文件 'npc_simulator.log' 获取详细信息")
        return 1

if __name__ == "__main__":
    sys.exit(main())
